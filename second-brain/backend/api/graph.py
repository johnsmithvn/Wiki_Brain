from fastapi import APIRouter, Query

from backend.models.schemas import GraphData
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("", response_model=GraphData)
async def get_full_graph(
    tags: list[str] = Query(default=[]),
    folders: list[str] = Query(default=[]),
    depth: int = Query(default=0, ge=0, le=5),
):
    """Get the full knowledge graph, optionally filtered.

    Query params:
        tags: Filter nodes that have at least one of these tags.
        folders: Filter nodes whose path starts with one of these folder prefixes.
        depth: Expand filtered set by N hops of connections (0 = exact match only).
    """
    has_filters = bool(tags) or bool(folders)
    if not has_filters:
        return link_service.get_graph_data()

    # Build tag lookup from tag_service for filtering
    tag_lookup: dict[str, set[str]] = {}
    with tag_service._lock:
        for path, note_tags in tag_service._note_tags.items():
            tag_lookup[path] = set(note_tags)

    return link_service.get_filtered_graph(
        tags=tags,
        folders=folders,
        depth=depth,
        tag_lookup=tag_lookup,
    )


@router.get("/{path:path}", response_model=GraphData)
async def get_local_graph(path: str, depth: int = 1):
    return link_service.get_local_graph(path, depth=depth)
