"""Capture API — Zero-friction knowledge capture endpoint."""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import CaptureRequest, CaptureResponse
from backend.services.capture_service import capture_service

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.post("", response_model=CaptureResponse, status_code=201)
async def capture(body: CaptureRequest):
    """Capture raw text/URL → append to inbox.

    Accepts content from any source (Telegram, browser, Web UI, quick-capture).
    Entry is appended to knowledge/inbox/YYYY-MM-DD.md.
    """
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    entry, date_str = await capture_service.capture(body)
    return CaptureResponse(id=entry.id, date=date_str)
