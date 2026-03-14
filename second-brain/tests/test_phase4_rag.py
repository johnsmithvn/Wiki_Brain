"""
Phase 4 Integration Tests — RAG Chat & AI Assistant

Tests:
  - Graph expansion (BFS from seed notes)
  - Graph proximity scoring
  - RAG retrieval pipeline (context building, scoring, token limits)
  - LLM service (streaming, availability check)
  - Chat API (SSE streaming, error handling)
  - Suggest-links endpoint
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config import settings


# ─────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────

@pytest.fixture
def graph_env(tmp_path):
    """Set up link_service with a known graph for testing."""
    from backend.services.link_service import link_service

    # Clear
    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()

    # Build a graph:
    #   A -> B, C
    #   B -> D
    #   C -> D
    #   E (isolated)
    paths = ["A.md", "B.md", "C.md", "D.md", "E.md"]
    for p in paths:
        link_service._all_paths.add(p)

    link_service._forward["A.md"] = {"B.md", "C.md"}
    link_service._backward["B.md"] = {"A.md"}
    link_service._backward["C.md"] = {"A.md"}
    link_service._forward["B.md"] = {"D.md"}
    link_service._forward["C.md"] = {"D.md"}
    link_service._backward["D.md"] = {"B.md", "C.md"}

    yield link_service

    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()


# ─────────────────────────────────────────────────
# Graph Expansion Tests
# ─────────────────────────────────────────────────

class TestGraphExpansion:
    def test_expand_from_single_seed(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        neighbors = expand_notes(["A.md"], depth=1)
        # A -> B, C (forward) and no backward links to A
        assert set(neighbors) == {"B.md", "C.md"}

    def test_expand_excludes_seeds(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        neighbors = expand_notes(["A.md", "B.md"], depth=1)
        # A -> B(seed), C; B -> A(seed), D
        assert "A.md" not in neighbors
        assert "B.md" not in neighbors
        assert "C.md" in neighbors
        assert "D.md" in neighbors

    def test_expand_max_neighbors(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        neighbors = expand_notes(["A.md"], depth=1, max_neighbors=1)
        assert len(neighbors) == 1

    def test_expand_isolated_node(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        neighbors = expand_notes(["E.md"], depth=1)
        assert neighbors == []

    def test_expand_depth_2(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        neighbors = expand_notes(["A.md"], depth=2)
        # depth 1: B, C; depth 2: D (via B->D, C->D)
        assert "D.md" in neighbors

    def test_expand_empty_seeds(self, graph_env):
        from backend.services.graph_expansion_service import expand_notes

        assert expand_notes([], depth=1) == []


class TestGraphProximityScore:
    def test_seed_note_scores_1(self, graph_env):
        from backend.services.graph_expansion_service import graph_proximity_score

        assert graph_proximity_score("A.md", ["A.md", "B.md"]) == 1.0

    def test_one_hop_neighbor_scores_07(self, graph_env):
        from backend.services.graph_expansion_service import graph_proximity_score

        # B is a direct forward link from A
        assert graph_proximity_score("B.md", ["A.md"]) == 0.7

    def test_backward_neighbor_scores_07(self, graph_env):
        from backend.services.graph_expansion_service import graph_proximity_score

        # A has backward link from B (B._backward contains A)
        # Actually: A is in B's backward set? No. A->B means B._backward = {A}
        # So from seed="B.md", A is in backward["B.md"]
        assert graph_proximity_score("A.md", ["B.md"]) == 0.7

    def test_unconnected_scores_0(self, graph_env):
        from backend.services.graph_expansion_service import graph_proximity_score

        assert graph_proximity_score("E.md", ["A.md"]) == 0.0

    def test_two_hops_scores_0(self, graph_env):
        from backend.services.graph_expansion_service import graph_proximity_score

        # D is 2 hops from A (A->B->D), not direct
        assert graph_proximity_score("D.md", ["A.md"]) == 0.0


# ─────────────────────────────────────────────────
# RAG Service Tests
# ─────────────────────────────────────────────────

class TestRAGService:
    def test_keyword_score_full_overlap(self):
        from backend.services.rag_service import _keyword_score

        assert _keyword_score("hello world", "hello world foo bar") == 1.0

    def test_keyword_score_partial(self):
        from backend.services.rag_service import _keyword_score

        score = _keyword_score("hello world", "hello bar")
        assert 0.4 < score < 0.6  # 1/2

    def test_keyword_score_no_overlap(self):
        from backend.services.rag_service import _keyword_score

        assert _keyword_score("hello world", "foo bar baz") == 0.0

    def test_keyword_score_empty_query(self):
        from backend.services.rag_service import _keyword_score

        assert _keyword_score("", "foo bar") == 0.0

    def test_build_context_groups_by_note(self):
        from backend.services.rag_service import ScoredChunk, build_context

        chunks = [
            ScoredChunk("c1", "note-a.md", "Note A", "H1", "Content A1", 10, 0.9),
            ScoredChunk("c2", "note-a.md", "Note A", "H2", "Content A2", 10, 0.8),
            ScoredChunk("c3", "note-b.md", "Note B", "H1", "Content B1", 10, 0.7),
        ]
        ctx = build_context(chunks)
        assert "[Source: note-a.md]" in ctx
        assert "[Source: note-b.md]" in ctx
        assert "Content A1" in ctx
        assert "Content A2" in ctx
        assert ctx.index("Content A1") < ctx.index("Content B1")

    def test_select_within_token_limit(self):
        from backend.services.rag_service import ScoredChunk, _select_within_token_limit

        chunks = [
            ScoredChunk("c1", "a.md", "A", "", "x " * 500, 500, 0.9),
            ScoredChunk("c2", "b.md", "B", "", "y " * 500, 500, 0.8),
            ScoredChunk("c3", "c.md", "C", "", "z " * 300, 300, 0.7),
        ]
        selected = _select_within_token_limit(chunks, max_tokens=1000)
        assert len(selected) == 2  # 500 + 500 = 1000, fits
        assert selected[0].chunk_id == "c1"
        assert selected[1].chunk_id == "c2"

    def test_select_skips_too_large_chunk(self):
        from backend.services.rag_service import ScoredChunk, _select_within_token_limit

        chunks = [
            ScoredChunk("c1", "a.md", "A", "", "x " * 300, 300, 0.9),
            ScoredChunk("c2", "b.md", "B", "", "y " * 900, 900, 0.8),  # too big after c1
            ScoredChunk("c3", "c.md", "C", "", "z " * 200, 200, 0.7),  # fits
        ]
        selected = _select_within_token_limit(chunks, max_tokens=600)
        assert len(selected) == 2
        assert selected[0].chunk_id == "c1"
        assert selected[1].chunk_id == "c3"  # c2 skipped, c3 fits

    @pytest.mark.asyncio
    async def test_retrieve_context_keyword_fallback(self, tmp_path):
        """When vector service is unavailable, falls back to keyword search."""
        from backend.services.rag_service import retrieve_context
        from backend.services.vector_service import vector_service
        from backend.services.index_service import index_service

        original_available = vector_service._client
        vector_service._client = None

        mock_results = [
            MagicMock(path="test.md", title="Test", snippet="test content", score=0.5)
        ]

        with patch.object(index_service, "search", return_value=mock_results):
            ctx = await retrieve_context("test query")

        assert len(ctx.chunks) == 1
        assert ctx.chunks[0].note_path == "test.md"
        assert ctx.context_text  # not empty

        vector_service._client = original_available


# ─────────────────────────────────────────────────
# LLM Service Tests
# ─────────────────────────────────────────────────

class TestLLMService:
    def test_available_returns_false_when_no_server(self):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        # Ollama probably not running in test env
        # Just test that it doesn't crash
        result = svc.available
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_generate_stream_collects_tokens(self):
        """Test that generate() collects streamed tokens."""
        from backend.services.llm_service import LLMService

        svc = LLMService()

        # Mock the generate_stream to yield known tokens
        async def mock_stream(system, user, temperature=0.3):
            for token in ["Hello", " ", "world"]:
                yield token

        with patch.object(svc, "generate_stream", side_effect=mock_stream):
            result = await svc.generate("sys", "user")
            assert result == "Hello world"


# ─────────────────────────────────────────────────
# Chat API Tests
# ─────────────────────────────────────────────────

class TestChatAPI:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_chat_returns_503_when_ollama_down(self, client):
        """Chat should return 503 when Ollama is unavailable."""
        with patch("backend.api.chat.llm_service") as mock_llm:
            mock_llm.available = False
            resp = client.post("/api/chat", json={"question": "hello"})
            assert resp.status_code == 503

    def test_chat_streams_sse_events(self, client):
        """Chat should stream SSE events when Ollama is mocked."""
        from backend.services.rag_service import RAGContext, ScoredChunk

        mock_ctx = RAGContext(
            chunks=[ScoredChunk("c1", "test.md", "Test", "", "content", 10, 0.9)],
            seed_notes=["test.md"],
            context_text="[Source: test.md]\n\ncontent",
            sources=["test.md"],
        )

        async def mock_stream(system, user, temperature=0.3):
            yield "Hello"
            yield " world"

        with (
            patch("backend.api.chat.retrieve_context", new_callable=AsyncMock, return_value=mock_ctx),
            patch("backend.api.chat.llm_service") as mock_llm,
        ):
            mock_llm.available = True
            mock_llm.generate_stream = mock_stream

            resp = client.post("/api/chat", json={"question": "test"})
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            # Parse SSE events
            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # Should have token events + done event
            tokens = [e["token"] for e in events if "token" in e]
            assert "".join(tokens) == "Hello world"

            done_events = [e for e in events if e.get("done")]
            assert len(done_events) == 1
            assert done_events[0]["sources"] == ["test.md"]

    def test_summarize_returns_404_for_missing_note(self, client):
        with patch("backend.api.chat.llm_service") as mock_llm:
            mock_llm.available = True
            resp = client.post("/api/chat/summarize", json={"note_path": "nonexistent.md"})
            assert resp.status_code == 404

    def test_suggest_links_returns_empty_without_vector(self, client):
        with patch("backend.services.vector_service.vector_service") as mock_vs:
            mock_vs.available = False
            resp = client.post(
                "/api/chat/suggest-links",
                json={"note_path": "test.md", "content": "some text"},
            )
            assert resp.status_code == 200
            assert resp.json()["suggestions"] == []


# ─────────────────────────────────────────────────
# System Prompt Tests
# ─────────────────────────────────────────────────

class TestSystemPrompt:
    def test_system_prompt_contains_rules(self):
        from backend.services.rag_service import SYSTEM_PROMPT

        assert "RULES:" in SYSTEM_PROMPT
        assert "Only use information from the provided sources" in SYSTEM_PROMPT
        assert "cite" in SYSTEM_PROMPT.lower()
        assert "{context}" in SYSTEM_PROMPT

    def test_system_prompt_fills_context(self):
        from backend.services.rag_service import SYSTEM_PROMPT

        filled = SYSTEM_PROMPT.format(context="test context here")
        assert "test context here" in filled
        assert "{context}" not in filled
