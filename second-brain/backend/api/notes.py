from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    FileTreeItem,
    FolderCreate,
    FolderRename,
    NoteContent,
    NoteCreate,
    NoteMetaResponse,
    NoteMetadata,
    NoteRename,
    NoteUpdate,
)
from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.note_pipeline import note_pipeline
from backend.services.rename_service import rename_service
from backend.services.tag_service import tag_service

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("/tree", response_model=list[FileTreeItem])
async def get_file_tree():
    return file_service.get_file_tree()


@router.get("/list", response_model=list[NoteMetadata])
async def list_notes():
    notes = file_service.list_all_notes()
    for note in notes:
        note.tags = tag_service.get_tags_for_note(note.path)
    return notes


@router.get("/{path:path}/meta", response_model=NoteMetaResponse)
async def get_note_meta(path: str):
    try:
        metadata = file_service.get_metadata(path)
        return NoteMetaResponse(path=metadata.path, modified_at=metadata.modified_at, size=metadata.size)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{path:path}", response_model=NoteContent)
async def get_note(path: str):
    try:
        content = await file_service.read_file(path)
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
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=NoteMetadata, status_code=201)
async def create_note(data: NoteCreate):
    try:
        requested_path = data.path if data.path.endswith(".md") else f"{data.path}.md"
        if file_service.exists(requested_path):
            raise HTTPException(status_code=409, detail=f"Note already exists: {requested_path}")
        metadata = await file_service.write_file(data.path, data.content)
        tags = await note_pipeline.process_note(metadata.path, data.content)
        metadata.tags = tags
        return metadata
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{path:path}", response_model=NoteMetadata)
async def update_note(path: str, data: NoteUpdate):
    try:
        metadata = await file_service.write_file(path, data.content)
        tags = await note_pipeline.process_note(path, data.content)
        metadata.tags = tags
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{path:path}", status_code=204)
async def delete_note(path: str):
    try:
        await file_service.delete_file(path)
        note_pipeline.remove_note(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")


@router.patch("/{path:path}/rename", response_model=NoteMetadata)
async def rename_note(path: str, data: NoteRename):
    try:
        content = await file_service.read_file(path)
        # Propagate wiki-link rewrites BEFORE removing old index entries
        updated_count = await rename_service.propagate_rename(path, data.new_path)

        metadata = await file_service.rename_file(path, data.new_path)
        # Remove old index entries, re-index under new path
        note_pipeline.remove_note(path)
        tags = await note_pipeline.process_note(metadata.path, content)
        metadata.tags = tags
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/folder", status_code=201)
async def create_folder(data: FolderCreate):
    try:
        file_service.create_folder(data.path)
        return {"path": data.path}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/folder-rename")
async def rename_folder(data: FolderRename):
    try:
        new_path = file_service.rename_folder(data.old_path, data.new_path)
        return {"path": new_path}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Folder not found: {data.old_path}")
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
