from fastapi import APIRouter, Query

from backend.models.schemas import SearchResponse
from backend.services.index_service import index_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_notes(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    results = index_service.search(q, limit=limit)
    return SearchResponse(query=q, results=results, total=len(results))
