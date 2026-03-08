from fastapi import APIRouter

from backend.models.schemas import NoteMetadata, TagInfo, TagListResponse
from backend.services.file_service import file_service
from backend.services.tag_service import tag_service

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=TagListResponse)
async def get_all_tags():
    tag_counts = tag_service.get_all_tags()
    tags = [TagInfo(name=name, count=count) for name, count in tag_counts.items()]
    return TagListResponse(tags=tags, total=len(tags))


@router.get("/{tag}", response_model=list[NoteMetadata])
async def get_notes_by_tag(tag: str):
    paths = tag_service.get_notes_by_tag(tag)
    notes: list[NoteMetadata] = []
    for path in paths:
        try:
            notes.append(file_service.get_metadata(path))
        except FileNotFoundError:
            continue
    return notes
