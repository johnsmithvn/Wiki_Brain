import asyncio
from collections import defaultdict

from fastapi import APIRouter, Query

from backend.config.retrieval import HYBRID_KEYWORD_WEIGHT, HYBRID_VECTOR_WEIGHT
from backend.models.schemas import SearchResponse, SearchResult
from backend.services.index_service import index_service

router = APIRouter(prefix="/api/search", tags=["search"])


def _min_max_normalize(scores: list[float]) -> list[float]:
    """Normalize scores to [0, 1] range."""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


@router.get("", response_model=SearchResponse)
async def search_notes(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    mode: str = Query("keyword", regex="^(keyword|semantic|hybrid)$"),
):
    """Search notes with keyword, semantic, or hybrid mode."""

    # Keyword search (always available)
    if mode == "keyword":
        results = await asyncio.to_thread(index_service.search, q, limit)
        return SearchResponse(query=q, results=results, total=len(results))

    # Semantic or hybrid — requires embedding + vector services
    from backend.services.embedding_service import embedding_service
    from backend.services.vector_service import vector_service

    if not vector_service.available:
        # Fallback to keyword when Qdrant is unavailable
        results = await asyncio.to_thread(index_service.search, q, limit)
        return SearchResponse(query=q, results=results, total=len(results))

    # Embed query
    query_vector = await embedding_service.embed_query(q)

    if mode == "semantic":
        # Pure vector search
        vector_hits = vector_service.search(query_vector, limit=limit, type_filter="chunk")
        results = [
            SearchResult(
                path=hit.payload["note_path"],
                title=hit.payload.get("note_title", ""),
                snippet=hit.payload.get("content", "")[:200],
                score=hit.score,
            )
            for hit in vector_hits
        ]
        # Deduplicate by path (keep highest score)
        seen = set()
        deduped = []
        for r in results:
            if r.path not in seen:
                seen.add(r.path)
                deduped.append(r)
        return SearchResponse(query=q, results=deduped[:limit], total=len(deduped))

    # Hybrid mode: weighted fusion of vector + keyword
    vector_hits = vector_service.search(query_vector, limit=20, type_filter="chunk")
    keyword_hits = await asyncio.to_thread(index_service.search, q, 20)

    # Normalize scores
    v_scores = _min_max_normalize([h.score for h in vector_hits])
    k_scores = _min_max_normalize([h.score for h in keyword_hits])

    # Fusion by note_path
    combined: dict[str, dict] = {}
    for hit, norm_score in zip(vector_hits, v_scores):
        path = hit.payload["note_path"]
        if path not in combined:
            combined[path] = {
                "path": path,
                "title": hit.payload.get("note_title", ""),
                "snippet": hit.payload.get("content", "")[:200],
                "score": 0.0,
            }
        combined[path]["score"] += HYBRID_VECTOR_WEIGHT * norm_score

    for hit, norm_score in zip(keyword_hits, k_scores):
        path = hit.path
        if path not in combined:
            combined[path] = {
                "path": path,
                "title": hit.title,
                "snippet": hit.snippet,
                "score": 0.0,
            }
        combined[path]["score"] += HYBRID_KEYWORD_WEIGHT * norm_score

    sorted_results = sorted(combined.values(), key=lambda x: -x["score"])[:limit]
    results = [
        SearchResult(path=r["path"], title=r["title"], snippet=r["snippet"], score=r["score"])
        for r in sorted_results
    ]
    return SearchResponse(query=q, results=results, total=len(results))
