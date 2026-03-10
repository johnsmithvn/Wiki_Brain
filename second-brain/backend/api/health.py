"""Health check endpoint — exposes service readiness."""

from fastapi import APIRouter

from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.watcher_service import watcher_service

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    """Return readiness status for all services."""
    index_ok = index_service._conn is not None
    links_ok = True  # in-memory, always ready
    watcher_ok = watcher_service._observer is not None and watcher_service._observer.is_alive()

    status = "ok" if (index_ok and links_ok and watcher_ok) else "degraded"

    return {
        "status": status,
        "services": {
            "index": "ok" if index_ok else "down",
            "links": "ok" if links_ok else "down",
            "watcher": "ok" if watcher_ok else "down",
            # Phase 3+: vector, embedding
            # Phase 4+: llm
        },
    }
