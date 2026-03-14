"""
RAG Service — Graph+Vector hybrid retrieval pipeline.

Combines vector similarity, graph proximity, and keyword overlap
to build optimal context for LLM generation.

Design ref: docs/DESIGN-graph-vector-reasoning.md §5-6
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

from backend.config.retrieval import (
    GRAPH_WEIGHT,
    KEYWORD_WEIGHT,
    VECTOR_WEIGHT,
)
from backend.services.embedding_service import embedding_service
from backend.services.graph_expansion_service import expand_notes, graph_proximity_score
from backend.services.index_service import index_service
from backend.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# --- Context Limits ---
MAX_CONTEXT_TOKENS = 2000

# --- Prompt ---
SYSTEM_PROMPT = """You are answering questions using the user's personal knowledge vault.

RULES:
1. Only use information from the provided sources
2. If the answer is not in the sources, say "I don't have enough information in the vault"
3. Always cite which source note(s) you used
4. Answer in the same language as the question
5. Be concise and direct

Sources:
{context}"""


@dataclass
class ScoredChunk:
    """A chunk with its fused relevance score."""
    chunk_id: str
    note_path: str
    note_title: str
    heading: str
    content: str
    token_count: int
    score: float


@dataclass
class RAGContext:
    """Result of the retrieval pipeline."""
    chunks: list[ScoredChunk] = field(default_factory=list)
    seed_notes: list[str] = field(default_factory=list)
    neighbor_notes: list[str] = field(default_factory=list)
    context_text: str = ""
    sources: list[str] = field(default_factory=list)


def _keyword_score(query: str, content: str) -> float:
    """Simple keyword overlap ratio between query and content."""
    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return 0.0
    content_lower = content.lower()
    matches = sum(1 for w in query_words if w in content_lower)
    return matches / len(query_words)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (words ≈ tokens * 0.75 for English)."""
    return len(text.split())


def _select_within_token_limit(
    chunks: list[ScoredChunk],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> list[ScoredChunk]:
    """Select top chunks that fit within token budget."""
    selected: list[ScoredChunk] = []
    total = 0
    for chunk in chunks:
        if total + chunk.token_count > max_tokens:
            continue
        selected.append(chunk)
        total += chunk.token_count
    return selected


def build_context(chunks: list[ScoredChunk]) -> str:
    """Build context string grouped by note path."""
    by_note: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        by_note[chunk.note_path].append(chunk.content)

    parts: list[str] = []
    for note_path, contents in by_note.items():
        parts.append(f"[Source: {note_path}]\n\n" + "\n\n".join(contents))

    return "\n\n---\n\n".join(parts)


async def retrieve_context(query: str) -> RAGContext:
    """Full RAG retrieval pipeline: vector → graph expand → score → select.

    Falls back gracefully when vector service is unavailable.
    """
    # Fallback: keyword-only if vector search unavailable
    if not vector_service.available:
        keyword_results = await asyncio.to_thread(index_service.search, query, 5)
        chunks = [
            ScoredChunk(
                chunk_id=f"{r.path}#kw",
                note_path=r.path,
                note_title=r.title,
                heading="",
                content=r.snippet,
                token_count=_estimate_tokens(r.snippet),
                score=r.score,
            )
            for r in keyword_results
        ]
        return RAGContext(
            chunks=chunks,
            context_text=build_context(chunks),
            sources=[c.note_path for c in chunks],
        )

    # Step 1: Vector search top-10
    query_vector = await embedding_service.embed_query(query)
    vector_results = vector_service.search(query_vector, limit=10, type_filter="chunk")

    # Step 2: Extract seed notes
    seed_notes = list(dict.fromkeys(
        r.payload["note_path"] for r in vector_results
    ))

    # Step 3: Graph expansion (BFS 1-hop)
    neighbor_notes = expand_notes(seed_notes, depth=1, max_neighbors=5)

    # Step 4: Get chunks from neighbor notes
    neighbor_chunks = vector_service.get_chunks_for_notes(neighbor_notes, max_per_note=2)

    # Step 5: Merge + score all chunks
    seen_ids: set[str] = set()
    all_scored: list[ScoredChunk] = []

    for hit in vector_results:
        cid = hit.payload.get("chunk_id", str(hit.id))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        note_path = hit.payload["note_path"]
        score = (
            VECTOR_WEIGHT * hit.score
            + GRAPH_WEIGHT * graph_proximity_score(note_path, seed_notes)
            + KEYWORD_WEIGHT * _keyword_score(query, hit.payload.get("content", ""))
        )
        all_scored.append(ScoredChunk(
            chunk_id=cid,
            note_path=note_path,
            note_title=hit.payload.get("note_title", ""),
            heading=hit.payload.get("heading", ""),
            content=hit.payload.get("content", ""),
            token_count=hit.payload.get("token_count", _estimate_tokens(hit.payload.get("content", ""))),
            score=score,
        ))

    for hit in neighbor_chunks:
        cid = hit.payload.get("chunk_id", str(hit.id))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        note_path = hit.payload["note_path"]
        # Neighbor chunks: no vector score, use default 0.3
        v_score = hit.score if hasattr(hit, "score") and hit.score else 0.3
        score = (
            VECTOR_WEIGHT * v_score
            + GRAPH_WEIGHT * 0.7  # 1-hop neighbor
            + KEYWORD_WEIGHT * _keyword_score(query, hit.payload.get("content", ""))
        )
        all_scored.append(ScoredChunk(
            chunk_id=cid,
            note_path=note_path,
            note_title=hit.payload.get("note_title", ""),
            heading=hit.payload.get("heading", ""),
            content=hit.payload.get("content", ""),
            token_count=hit.payload.get("token_count", _estimate_tokens(hit.payload.get("content", ""))),
            score=score,
        ))

    # Step 6: Sort by score descending, select within token limit
    all_scored.sort(key=lambda c: -c.score)
    selected = _select_within_token_limit(all_scored)

    context_text = build_context(selected)
    sources = list(dict.fromkeys(c.note_path for c in selected))

    return RAGContext(
        chunks=selected,
        seed_notes=seed_notes,
        neighbor_notes=neighbor_notes,
        context_text=context_text,
        sources=sources,
    )
