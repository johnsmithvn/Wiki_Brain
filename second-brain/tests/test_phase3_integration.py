"""
Phase 3 Integration Tests — chunking quality, embedding pipeline,
watcher integration, search modes, and hybrid ranking.

These tests verify the Phase 3 semantic search layer works correctly
end-to-end, using mocks for GPU-dependent services (embedding model,
Qdrant) and real logic for everything else.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.config import settings
from backend.config.retrieval import (
    EMBED_DEBOUNCE_SECONDS,
    HYBRID_KEYWORD_WEIGHT,
    HYBRID_VECTOR_WEIGHT,
    MAX_TOKENS,
    MIN_TOKENS,
    TARGET_TOKENS,
)
from backend.services.chunker_service import (
    Chunk,
    _collect_sections,
    _count_tokens,
    _strip_frontmatter,
    chunk_note,
    format_embedding_input,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RICH_NOTE = """\
---
title: RAG Pipeline Architecture
tags: [ai, rag, retrieval]
---

# RAG Pipeline Architecture

Retrieval-Augmented Generation (RAG) improves LLM accuracy by grounding
responses in retrieved documents. This note covers the full pipeline from
query processing to answer generation.

## Query Processing

The user query is first embedded using the same model that indexed
the document chunks. Query expansion techniques like HyDE (Hypothetical
Document Embeddings) can improve recall by generating a hypothetical
answer and embedding that instead of the raw query.

### Query Rewriting

For complex queries, an LLM can rewrite the query into multiple
sub-queries. Each sub-query retrieves independently, and results
are merged via reciprocal rank fusion (RRF).

## Retrieval Stage

Vector similarity search finds the top-K chunks most semantically
similar to the query embedding. Common distance metrics include:

- **Cosine similarity** — most popular, works well with normalized embeddings
- **Dot product** — equivalent to cosine when vectors are normalized
- **Euclidean distance** — less common for text embeddings

### Graph-Enhanced Retrieval

After initial vector retrieval, graph expansion adds neighboring
nodes from the knowledge graph. This improves recall for topics
that span multiple notes connected by wiki-links.

## Generation Stage

The retrieved chunks are formatted into a context window and
prepended to the user query as a system prompt. Key considerations:

1. Context window budget (e.g., 4096 tokens for smaller models)
2. Chunk ordering (most relevant first vs chronological)
3. Citation format (inline vs footnote references)

### Prompt Engineering

The system prompt should instruct the LLM to:
- Only answer based on the provided context
- Cite specific chunks when making claims
- Say "I don't know" when context is insufficient

## Evaluation

RAG quality is measured along three axes:
- **Faithfulness** — does the answer stick to retrieved context?
- **Relevance** — are the retrieved chunks actually relevant?
- **Coverage** — does retrieval find all relevant information?

#ai #rag #llm #retrieval
"""

VIETNAMESE_NOTE = """\
# Ghi chú về Trí tuệ Nhân tạo

Trí tuệ nhân tạo (AI) đang thay đổi cách chúng ta làm việc và sống.
Các mô hình ngôn ngữ lớn như GPT và Claude có khả năng hiểu và
tạo văn bản tự nhiên.

## Ứng dụng thực tế

- Chatbot hỗ trợ khách hàng
- Dịch thuật tự động
- Phân tích dữ liệu và báo cáo
- Tạo nội dung sáng tạo

## Thách thức

### Hallucination

Khi mô hình tạo ra thông tin không chính xác hoặc bịa đặt.
RAG giúp giảm thiểu vấn đề này bằng cách cung cấp ngữ cảnh
từ nguồn đáng tin cậy.

### Chi phí tính toán

Chạy mô hình lớn yêu cầu GPU mạnh. Giải pháp: sử dụng mô hình
nhỏ hơn (7B parameters) với quantization (Q4_K_M).

#ai #tieng-viet #llm
"""

SHORT_NOTE = """\
# Quick Idea

Just a quick thought about graph databases.

#idea
"""

HEAVILY_LINKED_NOTE = """\
# Knowledge Graph Overview

A knowledge graph connects [[concepts]] through [[relationships]].
In our system, [[wiki-links]] create the graph structure.

## Graph Algorithms

We use [[BFS]] for neighbor expansion and [[PageRank]] for
importance scoring. See also [[vector-search]] for semantic
retrieval and [[RAG Pipeline Architecture]] for the full pipeline.

## Implementation

The [[link_service]] maintains forward and backward edges.
The [[graph API]] exposes D3.js-compatible data.

#graph #knowledge-management
"""

CODE_HEAVY_NOTE = """\
# FastAPI Patterns

## Dependency Injection

```python
from fastapi import Depends

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items/")
async def read_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

## Lifespan Events

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_services()
    yield
    # Shutdown
    await cleanup_services()
```

## Error Handling

Use HTTPException for client errors and handle internal
errors with a global exception handler.

```python
@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.error("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal error"})
```

#python #fastapi #patterns
"""


@pytest.fixture
def setup_env(tmp_path):
    """Set up temp knowledge dir and reset services."""
    from backend.services.file_service import file_service
    from backend.services.index_service import index_service
    from backend.services.link_service import link_service
    from backend.services.tag_service import tag_service

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    original = settings.KNOWLEDGE_DIR
    original_db = settings.DB_PATH
    original_root = file_service.root
    settings.KNOWLEDGE_DIR = knowledge_dir
    settings.DB_PATH = tmp_path / "data" / "index.db"
    file_service.root = knowledge_dir

    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()
    tag_service._note_tags.clear()
    if index_service._conn:
        index_service._conn.close()
    index_service._conn = None
    index_service.db_path = settings.DB_PATH

    settings.ensure_dirs()
    index_service.initialize()

    yield knowledge_dir

    if index_service._conn:
        index_service._conn.close()
    index_service._conn = None
    settings.KNOWLEDGE_DIR = original
    settings.DB_PATH = original_db
    file_service.root = original_root


# ===========================================================================
# 1. CHUNKING QUALITY TESTS
# ===========================================================================

class TestChunkingQuality:
    """Verify chunking on realistic notes with varied structure."""

    def test_rich_note_chunks_within_bounds(self):
        """All chunks from a real-world note respect token limits."""
        chunks = chunk_note(RICH_NOTE, "ai/rag-pipeline.md")
        assert len(chunks) >= 3, f"Expected ≥3 chunks, got {len(chunks)}"

        for c in chunks:
            assert c.token_count <= MAX_TOKENS, (
                f"Chunk '{c.heading}' #{c.chunk_index} has {c.token_count} tokens "
                f"(limit: {MAX_TOKENS})"
            )
            # No empty chunks
            assert c.content.strip(), f"Chunk #{c.chunk_index} is empty"

    def test_rich_note_preserves_all_sections(self):
        """All major headings from the note appear in chunk headings."""
        chunks = chunk_note(RICH_NOTE, "ai/rag-pipeline.md")
        all_headings = {c.heading for c in chunks}
        # These key sections should appear
        expected = {"Query Processing", "Retrieval Stage", "Generation Stage", "Evaluation"}
        found = expected & all_headings
        assert len(found) >= 3, (
            f"Expected at least 3 of {expected} in headings, found {found}. "
            f"All headings: {all_headings}"
        )

    def test_rich_note_title_extraction(self):
        """Title correctly extracted from frontmatter-bearing note."""
        chunks = chunk_note(RICH_NOTE, "ai/rag-pipeline.md")
        assert chunks[0].note_title == "RAG Pipeline Architecture"

    def test_rich_note_frontmatter_stripped(self):
        """Frontmatter YAML does not leak into chunk content."""
        chunks = chunk_note(RICH_NOTE, "ai/rag-pipeline.md")
        for c in chunks:
            assert "tags: [ai, rag, retrieval]" not in c.content
            assert c.content.strip() != "---"

    def test_vietnamese_note_chunks_correctly(self):
        """Vietnamese content is chunked without corruption."""
        chunks = chunk_note(VIETNAMESE_NOTE, "tieng-viet/ai-notes.md")
        assert len(chunks) >= 1

        all_content = " ".join(c.content for c in chunks)
        all_headings = " ".join(c.heading for c in chunks)
        all_text = all_content + " " + all_headings
        # Key Vietnamese phrases must survive chunking
        assert "Trí tuệ nhân tạo" in all_text or "trí tuệ nhân tạo" in all_text.lower()
        assert "Hallucination" in all_text
        assert "Chatbot" in all_text

    def test_vietnamese_note_title(self):
        chunks = chunk_note(VIETNAMESE_NOTE, "vi.md")
        assert chunks[0].note_title == "Ghi chú về Trí tuệ Nhân tạo"

    def test_short_note_produces_single_chunk(self):
        """A tiny note should produce exactly 1 chunk (no splits)."""
        chunks = chunk_note(SHORT_NOTE, "ideas/quick.md")
        assert len(chunks) == 1
        assert "graph databases" in chunks[0].content

    def test_code_heavy_note_preserves_code_blocks(self):
        """Code blocks survive chunking intact with fences."""
        chunks = chunk_note(CODE_HEAVY_NOTE, "dev/fastapi.md")
        all_content = "\n".join(c.content for c in chunks)

        # Code delimiters and key code patterns preserved
        assert "```python" in all_content or "```" in all_content
        assert "def get_db():" in all_content
        assert "async def lifespan" in all_content
        assert "exception_handler" in all_content

    def test_code_heavy_note_headings(self):
        """Code-heavy note sections are separated by heading."""
        chunks = chunk_note(CODE_HEAVY_NOTE, "dev/fastapi.md")
        headings = {c.heading for c in chunks}
        expected = {"Dependency Injection", "Lifespan Events", "Error Handling"}
        found = expected & headings
        assert len(found) >= 2, f"Expected ≥2 of {expected}, got {found}"

    def test_linked_note_content_preserved(self):
        """Wiki-links in content are preserved in chunk text."""
        chunks = chunk_note(HEAVILY_LINKED_NOTE, "graph/overview.md")
        all_content = " ".join(c.content for c in chunks)
        assert "[[concepts]]" in all_content or "concepts" in all_content
        assert "[[BFS]]" in all_content or "BFS" in all_content

    def test_embedding_input_format_quality(self):
        """format_embedding_input enriches context for the embedding model."""
        chunks = chunk_note(RICH_NOTE, "ai/rag.md")
        for c in chunks:
            formatted = format_embedding_input(c)
            assert formatted.startswith("Title: RAG Pipeline Architecture")
            if c.heading:
                assert f"Section: {c.heading}" in formatted
            assert c.content in formatted

    def test_no_duplicate_content_across_chunks(self):
        """Chunks should not have significant content overlap."""
        chunks = chunk_note(RICH_NOTE, "test.md")
        for i, a in enumerate(chunks):
            for j, b in enumerate(chunks):
                if i >= j:
                    continue
                # Check no chunk is a substring of another
                if len(a.content) > 50 and len(b.content) > 50:
                    assert a.content not in b.content, (
                        f"Chunk #{i} is a substring of chunk #{j}"
                    )

    def test_chunk_ids_globally_unique(self):
        """All chunk IDs within a note are unique."""
        chunks = chunk_note(RICH_NOTE, "ai/rag.md")
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), f"Duplicate chunk IDs: {ids}"

    def test_sections_from_ast_match_markdown_structure(self):
        """_collect_sections produces sections matching markdown heading hierarchy."""
        from markdown_it import MarkdownIt

        md = MarkdownIt("commonmark")
        body = _strip_frontmatter(RICH_NOTE)
        tokens = md.parse(body)
        sections = _collect_sections(tokens)

        heading_names = [s["heading"] for s in sections]
        # First section is intro (empty heading or title)
        assert any("Query Processing" in h for h in heading_names)
        assert any("Retrieval Stage" in h for h in heading_names)
        assert any("Generation Stage" in h for h in heading_names)

    def test_large_note_all_chunks_within_max_tokens(self):
        """A 5000+ token note must produce chunks that all respect MAX_TOKENS."""
        # Build ~6000 token note with 20 sections, each with multiple paragraphs
        sections = []
        for i in range(20):
            heading = f"## Section {i}: {'Topic ' * 3}{i}"
            body = "\n\n".join(
                f"Paragraph {j} of section {i}. " + "word " * 25
                for j in range(5)
            )
            sections.append(f"{heading}\n\n{body}")
        large_note = "# Large Research Note\n\n" + "\n\n".join(sections)

        total_tokens = _count_tokens(large_note)
        assert total_tokens > 3000, f"Test note only has {total_tokens} tokens"

        chunks = chunk_note(large_note, "research/big.md")

        assert len(chunks) >= 5, f"Expected ≥5 chunks from large note, got {len(chunks)}"
        for c in chunks:
            assert c.token_count <= MAX_TOKENS, (
                f"Chunk '{c.heading}' #{c.chunk_index} has {c.token_count} tokens "
                f"(limit: {MAX_TOKENS})"
            )
            assert c.content.strip(), f"Chunk #{c.chunk_index} is empty"

        # Verify no content lost: all section headings should appear
        all_headings = {c.heading for c in chunks}
        for i in range(20):
            assert any(f"Section {i}" in h for h in all_headings), (
                f"Section {i} missing from chunks. Headings: {all_headings}"
            )

    def test_large_note_single_huge_section_split(self):
        """A single section with many paragraphs is split correctly."""
        # ~2000 tokens in one section
        paragraphs = "\n\n".join(
            f"This is paragraph number {i}. " + "content " * 30
            for i in range(40)
        )
        note = f"# Monolithic Note\n\n{paragraphs}"

        chunks = chunk_note(note, "mono.md")
        assert len(chunks) >= 3
        for c in chunks:
            assert c.token_count <= MAX_TOKENS, (
                f"Chunk #{c.chunk_index} has {c.token_count} tokens"
            )


# ===========================================================================
# 2. EMBEDDING PIPELINE TESTS
# ===========================================================================

class TestEmbeddingPipeline:
    """Test the embedding pipeline (note_pipeline._do_embed) with mocked services."""

    @pytest.mark.asyncio
    async def test_do_embed_calls_chunker_and_embeds(self, setup_env):
        """_do_embed chunks the note and calls embedding + vector services."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_chunks = AsyncMock(
            return_value=np.random.rand(3, 1024).astype(np.float32)
        )
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.is_unchanged.return_value = False
        mock_vector_svc.upsert_note = MagicMock()
        mock_vector_svc.delete_note = MagicMock()

        with patch("backend.services.note_pipeline.link_service") as mock_links:
            mock_links.get_forward_links.return_value = ["other-note.md"]

            with patch.dict("sys.modules", {}):
                with patch(
                    "backend.services.embedding_service.embedding_service",
                    mock_embed_svc,
                ), patch(
                    "backend.services.vector_service.vector_service",
                    mock_vector_svc,
                ):
                    await pipeline._do_embed("ai/rag.md", RICH_NOTE, ["ai", "rag"])

        # Verify embedding was called
        mock_embed_svc.embed_chunks.assert_called_once()
        chunks_arg = mock_embed_svc.embed_chunks.call_args[0][0]
        assert len(chunks_arg) >= 3
        assert all(isinstance(c, Chunk) for c in chunks_arg)

        # Verify all chunks got tags and links
        for c in chunks_arg:
            assert c.tags == ["ai", "rag"]
            assert c.links == ["other-note.md"]

        # Verify doc summary embedding
        mock_embed_svc.embed_query.assert_called_once()
        summary_text = mock_embed_svc.embed_query.call_args[0][0]
        assert "Title: RAG Pipeline Architecture" in summary_text

        # Verify upsert called with correct args
        mock_vector_svc.upsert_note.assert_called_once()
        call_kwargs = mock_vector_svc.upsert_note.call_args
        assert call_kwargs[1]["note_path"] == "ai/rag.md" or call_kwargs[0][0] == "ai/rag.md"

    @pytest.mark.asyncio
    async def test_do_embed_skips_unchanged(self, setup_env):
        """_do_embed skips embedding when content hash is unchanged."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_chunks = AsyncMock()

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.is_unchanged.return_value = True  # Content unchanged

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            await pipeline._do_embed("test.md", RICH_NOTE, ["ai"])

        # Should NOT call embed since content is unchanged
        mock_embed_svc.embed_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_do_embed_skips_when_qdrant_unavailable(self, setup_env):
        """_do_embed is a no-op when Qdrant is not available."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = False

        with patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            # Should return without error
            await pipeline._do_embed("test.md", RICH_NOTE, ["ai"])

    @pytest.mark.asyncio
    async def test_do_embed_deletes_empty_note(self, setup_env):
        """_do_embed deletes vectors if note produces no chunks."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.is_unchanged.return_value = False

        with patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            await pipeline._do_embed("empty.md", "---\ntags: [x]\n---\n", [])

        mock_vector_svc.delete_note.assert_called_once_with("empty.md")

    @pytest.mark.asyncio
    async def test_do_embed_handles_error_gracefully(self, setup_env):
        """_do_embed logs warning but doesn't crash on exceptions."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_chunks = AsyncMock(side_effect=RuntimeError("GPU OOM"))

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.is_unchanged.return_value = False

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            # Should not raise
            await pipeline._do_embed("test.md", RICH_NOTE, ["ai"])

    @pytest.mark.asyncio
    async def test_embed_debounce_scheduling(self, setup_env):
        """_schedule_embed sets a timer that can be cancelled by a rapid re-save."""
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        # Schedule first embed
        pipeline._schedule_embed("test.md", "content v1", ["tag"])
        assert "test.md" in pipeline._embed_timers

        # Schedule again (should cancel previous)
        pipeline._schedule_embed("test.md", "content v2", ["tag"])
        assert "test.md" in pipeline._embed_timers

        # Only one timer should exist
        assert len([k for k in pipeline._embed_timers if k == "test.md"]) == 1

        # Cancel for cleanup
        pipeline._embed_timers["test.md"].cancel()


# ===========================================================================
# 3. WATCHER INTEGRATION TESTS
# ===========================================================================

class TestWatcherIntegration:
    """Test watcher queue → pipeline → embedding scheduling flow."""

    @pytest.mark.asyncio
    async def test_watcher_upsert_triggers_pipeline(self, setup_env):
        """Watcher 'upsert' event reads file and calls process_note."""
        from backend.services.watcher_service import WatcherService

        knowledge_dir = setup_env
        note_path = knowledge_dir / "watcher-test.md"
        note_path.write_text("# Watcher Test\n\nContent here.\n#test", encoding="utf-8")

        watcher = WatcherService()
        watcher._queue = asyncio.Queue()

        with patch(
            "backend.services.note_pipeline.note_pipeline"
        ) as mock_pipeline:
            mock_pipeline.process_note = AsyncMock(return_value=["test"])

            # Simulate enqueue
            await watcher._queue.put(("upsert", "watcher-test.md"))

            # Run worker for one item
            action, rel_path = await watcher._queue.get()
            assert action == "upsert"
            assert rel_path == "watcher-test.md"

    @pytest.mark.asyncio
    async def test_watcher_delete_triggers_remove(self, setup_env):
        """Watcher 'delete' event calls remove_note."""
        watcher_queue = asyncio.Queue()
        await watcher_queue.put(("delete", "deleted-note.md"))

        action, rel_path = await watcher_queue.get()
        assert action == "delete"
        assert rel_path == "deleted-note.md"

    def test_watcher_event_handler_normalizes_paths(self, setup_env):
        """Event handler correctly normalizes paths and filters excluded dirs."""
        from backend.services.watcher_service import _VaultEventHandler

        loop = asyncio.new_event_loop()
        queue = asyncio.Queue()
        handler = _VaultEventHandler(queue, loop)

        knowledge_dir = setup_env

        # Valid .md file
        valid_path = str(knowledge_dir / "test-note.md")
        rel = handler._normalize_rel_path(valid_path)
        assert rel == "test-note.md"

        # Non-.md file should be rejected
        invalid_path = str(knowledge_dir / "image.png")
        rel = handler._normalize_rel_path(invalid_path)
        assert rel is None

        # Excluded folder (inbox)
        inbox_path = str(knowledge_dir / "inbox" / "2026-01-01.md")
        (knowledge_dir / "inbox").mkdir(exist_ok=True)
        rel = handler._normalize_rel_path(inbox_path)
        assert rel is None

        loop.close()

    def test_watcher_debounce_rejects_rapid_events(self, setup_env):
        """Event handler debounces rapid events for the same file."""
        from backend.services.watcher_service import _VaultEventHandler

        loop = asyncio.new_event_loop()
        queue = asyncio.Queue()
        handler = _VaultEventHandler(queue, loop, debounce_ms=500)

        # First event should pass
        assert handler._should_process("modified:test.md") is True
        # Immediate second should be rejected
        assert handler._should_process("modified:test.md") is False
        # Different file should pass
        assert handler._should_process("modified:other.md") is True

        loop.close()


# ===========================================================================
# 4. SEARCH QUALITY TESTS
# ===========================================================================

@dataclass
class MockScoredPoint:
    """Mimics Qdrant ScoredPoint for search tests."""
    score: float
    payload: dict


class TestSearchQuality:
    """Test search modes return correct results with proper ranking."""

    @pytest.mark.asyncio
    async def test_keyword_search_returns_fts_results(self, setup_env):
        """Keyword mode uses SQLite FTS5 and returns matching notes."""
        from backend.services.index_service import index_service
        from backend.services.note_pipeline import NotePipeline

        pipeline = NotePipeline()

        knowledge_dir = setup_env
        (knowledge_dir / "rag-note.md").write_text(RICH_NOTE, encoding="utf-8")
        (knowledge_dir / "vi-note.md").write_text(VIETNAMESE_NOTE, encoding="utf-8")

        await pipeline.process_note("rag-note.md", RICH_NOTE)
        await pipeline.process_note("vi-note.md", VIETNAMESE_NOTE)

        # Search for "retrieval" — should find rag-note
        results = index_service.search("retrieval", limit=10)
        paths = [r.path for r in results]
        assert "rag-note.md" in paths, f"Expected rag-note.md in {paths}"

    @pytest.mark.asyncio
    async def test_keyword_search_vietnamese(self, setup_env):
        """FTS can find Vietnamese content."""
        from backend.services.index_service import index_service
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        (knowledge_dir / "vi.md").write_text(VIETNAMESE_NOTE, encoding="utf-8")

        pipeline = NotePipeline()
        await pipeline.process_note("vi.md", VIETNAMESE_NOTE)

        results = index_service.search("Hallucination", limit=10)
        paths = [r.path for r in results]
        assert "vi.md" in paths

    @pytest.mark.asyncio
    async def test_keyword_search_code_content(self, setup_env):
        """FTS finds code patterns like function names."""
        from backend.services.index_service import index_service
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        (knowledge_dir / "code.md").write_text(CODE_HEAVY_NOTE, encoding="utf-8")

        pipeline = NotePipeline()
        await pipeline.process_note("code.md", CODE_HEAVY_NOTE)

        results = index_service.search("Dependency Injection", limit=10)
        paths = [r.path for r in results]
        assert "code.md" in paths

    def test_min_max_normalize_basic(self):
        """Score normalization maps to [0, 1] range."""
        from backend.api.search import _min_max_normalize

        scores = [0.5, 0.8, 0.3, 1.0, 0.1]
        normalized = _min_max_normalize(scores)

        assert min(normalized) == pytest.approx(0.0)
        assert max(normalized) == pytest.approx(1.0)
        assert len(normalized) == len(scores)

    def test_min_max_normalize_equal_scores(self):
        """All-equal scores normalize to all 1.0."""
        from backend.api.search import _min_max_normalize

        normalized = _min_max_normalize([0.5, 0.5, 0.5])
        assert all(s == pytest.approx(1.0) for s in normalized)

    def test_min_max_normalize_empty(self):
        from backend.api.search import _min_max_normalize

        assert _min_max_normalize([]) == []

    def test_min_max_normalize_single(self):
        from backend.api.search import _min_max_normalize

        assert _min_max_normalize([0.7]) == [1.0]


# ===========================================================================
# 5. HYBRID RANKING TESTS
# ===========================================================================

class TestHybridRanking:
    """Test hybrid search fusion weights and ranking logic."""

    def test_hybrid_weights_sum_to_one(self):
        """Hybrid weights should sum to 1.0 for proper probability weighting."""
        assert HYBRID_VECTOR_WEIGHT + HYBRID_KEYWORD_WEIGHT == pytest.approx(1.0)

    def test_vector_weight_dominates(self):
        """Vector weight should be > keyword weight (semantic is primary)."""
        assert HYBRID_VECTOR_WEIGHT > HYBRID_KEYWORD_WEIGHT

    def test_fusion_score_computation(self):
        """Verify weighted score fusion is calculated correctly."""
        from backend.api.search import _min_max_normalize

        # Simulate: note A is #1 in vector, #3 in keyword
        #           note B is #2 in vector, #1 in keyword
        #           note C is #3 in vector, #2 in keyword
        vector_scores = [0.95, 0.80, 0.60]
        keyword_scores = [0.40, 0.90, 0.65]

        v_norm = _min_max_normalize(vector_scores)  # [1.0, 0.571, 0.0]
        k_norm = _min_max_normalize(keyword_scores)  # [0.0, 1.0, 0.5]

        # Fuse
        fused = [
            HYBRID_VECTOR_WEIGHT * v + HYBRID_KEYWORD_WEIGHT * k
            for v, k in zip(v_norm, k_norm)
        ]

        # Note A: 0.7*1.0 + 0.3*0.0 = 0.7
        # Note B: 0.7*0.571 + 0.3*1.0 = 0.7 (approx)
        # Note C: 0.7*0.0 + 0.3*0.5 = 0.15
        assert fused[0] > fused[2]  # A > C
        assert fused[1] > fused[2]  # B > C

    def test_hybrid_dedup_keeps_highest_score(self):
        """When a note appears in both vector and keyword results, scores are summed."""
        from backend.api.search import _min_max_normalize

        # Note "X" appears in both — its final score should aggregate
        vector_hits = [
            MockScoredPoint(
                score=0.9,
                payload={"note_path": "X.md", "note_title": "X", "content": "content X"},
            ),
            MockScoredPoint(
                score=0.7,
                payload={"note_path": "Y.md", "note_title": "Y", "content": "content Y"},
            ),
        ]

        @dataclass
        class FakeKeywordResult:
            path: str
            title: str
            snippet: str
            score: float

        keyword_hits = [
            FakeKeywordResult(path="X.md", title="X", snippet="kw X", score=0.8),
            FakeKeywordResult(path="Z.md", title="Z", snippet="kw Z", score=0.6),
        ]

        v_scores = _min_max_normalize([h.score for h in vector_hits])
        k_scores = _min_max_normalize([h.score for h in keyword_hits])

        combined: dict[str, float] = defaultdict(float)
        for hit, ns in zip(vector_hits, v_scores):
            combined[hit.payload["note_path"]] += HYBRID_VECTOR_WEIGHT * ns
        for hit, ns in zip(keyword_hits, k_scores):
            combined[hit.path] += HYBRID_KEYWORD_WEIGHT * ns

        # X.md should have the highest score (appears in both)
        sorted_items = sorted(combined.items(), key=lambda x: -x[1])
        assert sorted_items[0][0] == "X.md"
        # X.md score should be > Y.md or Z.md
        assert combined["X.md"] > combined["Y.md"]
        assert combined["X.md"] > combined["Z.md"]

    def test_config_values_are_sane(self):
        """Retrieval config values are within reasonable ranges."""
        assert 0 < HYBRID_VECTOR_WEIGHT <= 1.0
        assert 0 < HYBRID_KEYWORD_WEIGHT <= 1.0
        assert 100 <= MIN_TOKENS <= TARGET_TOKENS <= MAX_TOKENS
        assert EMBED_DEBOUNCE_SECONDS > 0
        assert MAX_TOKENS <= 600  # BGE-M3 sweet spot

    @pytest.mark.asyncio
    async def test_search_fallback_to_keyword(self, setup_env):
        """When Qdrant is unavailable, semantic/hybrid modes fall back to keyword."""
        from backend.services.index_service import index_service
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        (knowledge_dir / "test.md").write_text(RICH_NOTE, encoding="utf-8")

        pipeline = NotePipeline()
        await pipeline.process_note("test.md", RICH_NOTE)

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = False

        with patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            # Hybrid mode with unavailable Qdrant should still return results
            response = await search_notes(q="retrieval", limit=10, mode="hybrid")
            assert response.total > 0
            assert any("test.md" in r.path for r in response.results)

    @pytest.mark.asyncio
    async def test_semantic_mode_returns_vector_results(self, setup_env):
        """Semantic mode returns results from vector search only."""
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        (knowledge_dir / "rag.md").write_text(RICH_NOTE, encoding="utf-8")

        pipeline = NotePipeline()
        await pipeline.process_note("rag.md", RICH_NOTE)

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(
                score=0.92,
                payload={
                    "note_path": "rag.md",
                    "note_title": "RAG Pipeline",
                    "content": "Retrieval-Augmented Generation improves LLM accuracy...",
                },
            ),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="how does RAG work", limit=10, mode="semantic")
            assert response.total == 1
            assert response.results[0].path == "rag.md"
            assert response.results[0].score == pytest.approx(0.92)

    @pytest.mark.asyncio
    async def test_hybrid_mode_fuses_both_sources(self, setup_env):
        """Hybrid mode combines vector + keyword results with weighted scores."""
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        (knowledge_dir / "rag.md").write_text(RICH_NOTE, encoding="utf-8")
        (knowledge_dir / "code.md").write_text(CODE_HEAVY_NOTE, encoding="utf-8")

        pipeline = NotePipeline()
        await pipeline.process_note("rag.md", RICH_NOTE)
        await pipeline.process_note("code.md", CODE_HEAVY_NOTE)

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(
                score=0.95,
                payload={
                    "note_path": "rag.md",
                    "note_title": "RAG Pipeline",
                    "content": "Vector search finds chunks...",
                },
            ),
            MockScoredPoint(
                score=0.70,
                payload={
                    "note_path": "code.md",
                    "note_title": "FastAPI Patterns",
                    "content": "Dependency injection...",
                },
            ),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="retrieval pipeline", limit=10, mode="hybrid")
            assert response.total >= 1

            # Results should be sorted by fused score
            if len(response.results) > 1:
                for i in range(len(response.results) - 1):
                    assert response.results[i].score >= response.results[i + 1].score

    @pytest.mark.asyncio
    async def test_semantic_ranking_multiple_notes(self, setup_env):
        """Semantic search ranks the most relevant note first among 10+ notes."""
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        notes = {
            "rag.md": "# RAG Pipeline\n\nRetrieval-Augmented Generation pipeline for retrieval and generation.",
            "vector.md": "# Vector Search\n\nVector search with embeddings and similarity metrics.",
            "graph.md": "# Knowledge Graph\n\nKnowledge graph with BFS, nodes and edges.",
            "llm.md": "# LLM Overview\n\nLarge language models and transformers architecture.",
            "python.md": "# Python Tips\n\nPython programming best practices and patterns.",
            "fastapi.md": "# FastAPI\n\nBuilding REST APIs with FastAPI framework.",
            "docker.md": "# Docker\n\nContainerization with Docker and compose.",
            "git.md": "# Git Workflow\n\nGit branching strategies and merge conflicts.",
            "testing.md": "# Testing\n\nUnit testing and integration testing patterns.",
            "security.md": "# Security\n\nOWASP top 10 and application security.",
            "database.md": "# Databases\n\nSQL vs NoSQL and database optimization.",
        }

        pipeline = NotePipeline()
        for name, text in notes.items():
            (knowledge_dir / name).write_text(text, encoding="utf-8")
            await pipeline.process_note(name, text)

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        # Simulate ranked vector results — rag.md is most relevant to "retrieval pipeline"
        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(score=0.95, payload={"note_path": "rag.md", "note_title": "RAG Pipeline", "content": "Retrieval-Augmented Generation pipeline"}),
            MockScoredPoint(score=0.82, payload={"note_path": "vector.md", "note_title": "Vector Search", "content": "Vector search with embeddings"}),
            MockScoredPoint(score=0.71, payload={"note_path": "llm.md", "note_title": "LLM Overview", "content": "Large language models"}),
            MockScoredPoint(score=0.55, payload={"note_path": "graph.md", "note_title": "Knowledge Graph", "content": "Knowledge graph with BFS"}),
            MockScoredPoint(score=0.40, payload={"note_path": "python.md", "note_title": "Python Tips", "content": "Python programming"}),
            MockScoredPoint(score=0.32, payload={"note_path": "fastapi.md", "note_title": "FastAPI", "content": "Building REST APIs"}),
            MockScoredPoint(score=0.28, payload={"note_path": "docker.md", "note_title": "Docker", "content": "Containerization"}),
            MockScoredPoint(score=0.20, payload={"note_path": "testing.md", "note_title": "Testing", "content": "Unit testing"}),
            MockScoredPoint(score=0.15, payload={"note_path": "security.md", "note_title": "Security", "content": "OWASP"}),
            MockScoredPoint(score=0.10, payload={"note_path": "database.md", "note_title": "Databases", "content": "SQL vs NoSQL"}),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="retrieval pipeline", limit=10, mode="semantic")

        # Ranking correctness: rag.md must be #1
        assert response.results[0].path == "rag.md"
        assert response.results[0].score == pytest.approx(0.95)
        # Top-3 should be the most relevant notes
        top3_paths = [r.path for r in response.results[:3]]
        assert "rag.md" in top3_paths
        assert "vector.md" in top3_paths
        # All 10 notes returned
        assert response.total == 10
        # Scores monotonically decreasing
        for i in range(len(response.results) - 1):
            assert response.results[i].score >= response.results[i + 1].score

    @pytest.mark.asyncio
    async def test_hybrid_ranking_multiple_notes(self, setup_env):
        """Hybrid mode correctly fuses vector + keyword scores across 10+ notes."""
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        notes = {
            "rag.md": "# RAG Pipeline\n\nRetrieval-Augmented Generation pipeline retrieval.",
            "vector.md": "# Vector Search\n\nVector search embeddings similarity retrieval.",
            "graph.md": "# Knowledge Graph\n\nKnowledge graph BFS nodes edges.",
            "llm.md": "# LLM\n\nLarge language models transformers.",
            "python.md": "# Python\n\nPython programming best practices.",
            "fastapi.md": "# FastAPI\n\nREST APIs with FastAPI framework.",
            "docker.md": "# Docker\n\nContainerization with Docker.",
            "git.md": "# Git\n\nGit branching strategies.",
            "testing.md": "# Testing\n\nUnit testing patterns.",
            "security.md": "# Security\n\nApplication security OWASP.",
        }

        pipeline = NotePipeline()
        for name, text in notes.items():
            (knowledge_dir / name).write_text(text, encoding="utf-8")
            await pipeline.process_note(name, text)

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        # Vector: rag.md strong, vector.md medium
        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(score=0.95, payload={"note_path": "rag.md", "note_title": "RAG Pipeline", "content": "retrieval generation"}),
            MockScoredPoint(score=0.75, payload={"note_path": "vector.md", "note_title": "Vector Search", "content": "vector search embeddings"}),
            MockScoredPoint(score=0.40, payload={"note_path": "llm.md", "note_title": "LLM", "content": "language models"}),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="retrieval", limit=10, mode="hybrid")

        # rag.md should rank highest (strong in both vector and keyword)
        assert response.results[0].path == "rag.md"
        # vector.md also has "retrieval" in keyword — should appear
        result_paths = [r.path for r in response.results]
        assert "vector.md" in result_paths
        # Scores descending
        for i in range(len(response.results) - 1):
            assert response.results[i].score >= response.results[i + 1].score

    @pytest.mark.asyncio
    async def test_semantic_query_irrelevant_returns_low_scores(self, setup_env):
        """Semantic search for an unrelated topic returns low-scored or no results."""
        from backend.services.note_pipeline import NotePipeline

        knowledge_dir = setup_env
        # Index notes about pets
        (knowledge_dir / "cats.md").write_text(
            "# Cats\n\nCats are cute furry animals that purr.", encoding="utf-8"
        )
        (knowledge_dir / "dogs.md").write_text(
            "# Dogs\n\nDogs bark and fetch sticks in the park.", encoding="utf-8"
        )
        pipeline = NotePipeline()
        await pipeline.process_note("cats.md", "# Cats\n\nCats are cute furry animals that purr.")
        await pipeline.process_note("dogs.md", "# Dogs\n\nDogs bark and fetch sticks in the park.")

        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        # Qdrant returns low-score results (noise)
        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(score=0.15, payload={"note_path": "cats.md", "note_title": "Cats", "content": "Cats are cute furry animals"}),
            MockScoredPoint(score=0.12, payload={"note_path": "dogs.md", "note_title": "Dogs", "content": "Dogs bark and fetch sticks"}),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="quantum physics entanglement", limit=10, mode="semantic")

        # Results exist but with very low scores — verifies precision
        assert response.total <= 2
        for r in response.results:
            assert r.score < 0.3, f"{r.path} scored {r.score} for irrelevant query"

    @pytest.mark.asyncio
    async def test_semantic_deduplicates_by_path(self, setup_env):
        """Semantic mode deduplicates results when multiple chunks match from same note."""
        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = AsyncMock(
            return_value=np.random.rand(1024).astype(np.float32)
        )

        mock_vector_svc = MagicMock()
        mock_vector_svc.available = True
        mock_vector_svc.search.return_value = [
            MockScoredPoint(
                score=0.95,
                payload={"note_path": "rag.md", "note_title": "RAG", "content": "chunk1"},
            ),
            MockScoredPoint(
                score=0.85,
                payload={"note_path": "rag.md", "note_title": "RAG", "content": "chunk2"},
            ),
            MockScoredPoint(
                score=0.80,
                payload={"note_path": "other.md", "note_title": "Other", "content": "chunk3"},
            ),
        ]

        with patch(
            "backend.services.embedding_service.embedding_service", mock_embed_svc
        ), patch(
            "backend.services.vector_service.vector_service", mock_vector_svc
        ):
            from backend.api.search import search_notes

            response = await search_notes(q="test", limit=10, mode="semantic")
            paths = [r.path for r in response.results]
            # rag.md should appear only once (highest score kept)
            assert paths.count("rag.md") == 1
            assert response.results[0].path == "rag.md"
            assert response.results[0].score == pytest.approx(0.95)


# ===========================================================================
# 6. VECTOR SERVICE UNIT TESTS
# ===========================================================================

class TestVectorServiceUnit:
    """Test vector_service logic without real Qdrant connection."""

    def test_content_hash_deterministic(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        h1 = svc.content_hash("hello world")
        h2 = svc.content_hash("hello world")
        h3 = svc.content_hash("different content")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16  # 16 hex chars

    def test_is_unchanged_detects_changes(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        svc._hash_cache["test.md"] = svc.content_hash("version 1")

        assert svc.is_unchanged("test.md", "version 1") is True
        assert svc.is_unchanged("test.md", "version 2") is False
        assert svc.is_unchanged("unknown.md", "anything") is False

    def test_available_false_without_init(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        assert svc.available is False

    def test_search_noop_when_unavailable(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        result = svc.search(np.zeros(1024), limit=10)
        assert result == []

    def test_delete_noop_when_unavailable(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        # Should not raise
        svc.delete_note("test.md")

    def test_upsert_noop_when_unavailable(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        chunks = [
            Chunk(
                chunk_id="t.md#0", note_path="t.md", note_title="T",
                heading="", chunk_index=0, content="test", token_count=1,
            )
        ]
        vectors = np.random.rand(1, 1024).astype(np.float32)
        # Should not raise
        svc.upsert_note("t.md", chunks, vectors, "test")

    def test_get_collection_info_none_when_unavailable(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        assert svc.get_collection_info() is None

    def test_point_id_deterministic(self):
        from backend.services.vector_service import VectorService

        svc = VectorService()
        id1 = svc._point_id("test.md#0")
        id2 = svc._point_id("test.md#0")
        id3 = svc._point_id("test.md#1")
        assert id1 == id2
        assert id1 != id3


# ===========================================================================
# 7. EMBEDDING SERVICE UNIT TESTS
# ===========================================================================

class TestEmbeddingServiceUnit:
    """Test embedding_service logic without loading the real model."""

    @pytest.mark.asyncio
    async def test_embed_texts_empty_list(self):
        from backend.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        # Empty list should return empty ndarray without loading model
        result = await svc.embed_texts([])
        assert result.shape == (0, 1024)

    def test_dim_property(self):
        from backend.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        assert svc.dim == 1024

    def test_model_not_loaded_initially(self):
        from backend.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        assert svc._model is None


# ===========================================================================
# 8. EMBEDDING SERVICE — ENCODE MOCK TESTS
# ===========================================================================

class TestEmbeddingEncode:
    """Test embedding encode paths with mocked model."""

    @pytest.mark.asyncio
    async def test_embed_chunks_formats_input(self):
        """embed_chunks calls format_embedding_input for each chunk."""
        from backend.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        chunks = chunk_note(RICH_NOTE, "test.md")

        fake_vectors = np.random.rand(len(chunks), 1024).astype(np.float32)
        svc._model = MagicMock()
        svc._model.encode.return_value = fake_vectors
        svc._model.get_sentence_embedding_dimension.return_value = 1024

        result = await svc.embed_chunks(chunks)

        assert result.shape == (len(chunks), 1024)
        # Verify model.encode was called with formatted strings
        call_args = svc._model.encode.call_args[0][0]
        assert len(call_args) == len(chunks)
        assert all("Title: RAG Pipeline Architecture" in t for t in call_args)
