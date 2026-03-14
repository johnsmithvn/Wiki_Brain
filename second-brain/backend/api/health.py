"""Health check endpoint — exposes service readiness."""

from fastapi import APIRouter

from backend.services.index_service import index_service
from backend.services.watcher_service import watcher_service

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    """Return readiness status for all services."""
    index_ok = index_service._conn is not None
    links_ok = True  # in-memory, always ready
    watcher_ok = watcher_service._observer is not None and watcher_service._observer.is_alive()

    # Phase 3: vector search readiness
    try:
        from backend.services.vector_service import vector_service
        vector_ok = vector_service.available
        vector_info = vector_service.get_collection_info()
    except Exception:
        vector_ok = False
        vector_info = None

    core_ok = index_ok and links_ok and watcher_ok
    status = "ok" if core_ok else "degraded"

    services = {
        "index": "ok" if index_ok else "down",
        "links": "ok" if links_ok else "down",
        "watcher": "ok" if watcher_ok else "down",
        "vector": "ok" if vector_ok else "unavailable",
    }

    result = {"status": status, "services": services}
    if vector_info:
        result["vector_info"] = vector_info

    return result
