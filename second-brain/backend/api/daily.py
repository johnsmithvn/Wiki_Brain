from datetime import date

from fastapi import APIRouter

from backend.models.schemas import NoteContent, NoteMetadata
from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

router = APIRouter(prefix="/api/daily", tags=["daily"])

DAILY_FOLDER = "daily"
DAILY_TEMPLATE = """# {title}

> 📅 {date}

## Notes


## Tasks

- [ ] 

## Ideas

"""


@router.get("/today", response_model=NoteContent)
async def get_today():
    today = date.today()
    filename = today.strftime("%Y-%m-%d")
    path = f"{DAILY_FOLDER}/{filename}.md"
    title = today.strftime("%A, %B %d, %Y")

    try:
        content = await file_service.read_file(path)
    except FileNotFoundError:
        # Auto-create today's note
        content = DAILY_TEMPLATE.format(title=title, date=filename)
        await file_service.write_file(path, content)
        tags = tag_service.update_tags(path, content)
        link_service.update_links(path, content)
        index_service.index_note(path, title, content, tags)

    metadata = file_service.get_metadata(path)
    return NoteContent(
        path=metadata.path,
        title=metadata.title,
        content=content,
        created_at=metadata.created_at,
        modified_at=metadata.modified_at,
        tags=tag_service.extract_tags(content),
        backlinks=link_service.get_backlinks(path),
        forward_links=link_service.get_forward_links(path),
    )


@router.get("/list", response_model=list[NoteMetadata])
async def list_daily_notes():
    notes = file_service.list_all_notes()
    daily = [n for n in notes if n.path.startswith(DAILY_FOLDER + "/")]
    daily.sort(key=lambda n: n.path, reverse=True)
    return daily
