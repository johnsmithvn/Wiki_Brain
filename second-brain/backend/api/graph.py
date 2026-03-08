from fastapi import APIRouter

from backend.models.schemas import GraphData
from backend.services.link_service import link_service

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("", response_model=GraphData)
async def get_full_graph():
    return link_service.get_graph_data()


@router.get("/{path:path}", response_model=GraphData)
async def get_local_graph(path: str, depth: int = 1):
    return link_service.get_local_graph(path, depth=depth)
