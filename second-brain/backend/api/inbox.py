"""Inbox API — Browse, convert, and manage captured entries."""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ConvertRequest, InboxDateSummary, InboxEntry
from backend.services.inbox_service import inbox_service
from backend.services.note_pipeline import note_pipeline

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


@router.get("", response_model=list[InboxDateSummary])
async def list_inbox_dates():
    """Return list of inbox dates with entry count."""
    return inbox_service.list_dates()


@router.get("/{date}", response_model=list[InboxEntry])
async def get_inbox_entries(date: str):
    """Parse inbox file → return structured entries."""
    entries = inbox_service.get_entries(date)
    if not entries:
        raise HTTPException(status_code=404, detail=f"No inbox entries for {date}")
    return entries


@router.post("/{date}/{entry_id}/convert")
async def convert_entry(date: str, entry_id: str, body: ConvertRequest):
    """Convert inbox entry → organized note in vault."""
    note_path = await inbox_service.convert_entry_to_note(
        date_str=date,
        entry_id=entry_id,
        title=body.title,
        folder=body.folder,
        tags=body.tags,
    )
    if not note_path:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found in {date}")

    # Run note pipeline on the new note
    from backend.services.file_service import file_service

    content = await file_service.read_file(note_path)
    await note_pipeline.process_note(note_path, content)

    return {"path": note_path, "message": "Entry converted to note"}


@router.delete("/{date}/{entry_id}", status_code=204)
async def delete_entry(date: str, entry_id: str):
    """Remove entry from inbox file."""
    deleted = await inbox_service.delete_entry(date, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found in {date}")


@router.post("/{date}/{entry_id}/archive", status_code=204)
async def archive_entry(date: str, entry_id: str):
    """Mark entry as archived (remove from active inbox)."""
    archived = await inbox_service.archive_entry(date, entry_id)
    if not archived:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found in {date}")
