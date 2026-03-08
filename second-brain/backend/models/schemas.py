from datetime import datetime
from pydantic import BaseModel, Field


class NoteMetadata(BaseModel):
    path: str
    title: str
    created_at: datetime | None = None
    modified_at: datetime | None = None
    size: int = 0
    tags: list[str] = Field(default_factory=list)


class NoteContent(BaseModel):
    path: str
    title: str
    content: str
    created_at: datetime | None = None
    modified_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    backlinks: list[str] = Field(default_factory=list)
    forward_links: list[str] = Field(default_factory=list)


class NoteMetaResponse(BaseModel):
    path: str
    modified_at: datetime | None = None
    size: int = 0


class NoteCreate(BaseModel):
    path: str
    content: str = ""


class NoteUpdate(BaseModel):
    content: str


class NoteRename(BaseModel):
    new_path: str


class FolderCreate(BaseModel):
    path: str


class FolderRename(BaseModel):
    old_path: str
    new_path: str


class FileTreeItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    created_at: float | None = None
    children: list["FileTreeItem"] = Field(default_factory=list)


class SearchResult(BaseModel):
    path: str
    title: str
    snippet: str
    score: float = 0.0


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


class GraphNode(BaseModel):
    id: str
    label: str
    group: str = "default"
    size: int = 1


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TagInfo(BaseModel):
    name: str
    count: int


class TagListResponse(BaseModel):
    tags: list[TagInfo]
    total: int


class TemplateInfo(BaseModel):
    path: str
    name: str
    title: str
    modified_at: datetime | None = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateInfo]
    total: int


class TemplateContent(BaseModel):
    path: str
    title: str
    content: str
    modified_at: datetime | None = None
