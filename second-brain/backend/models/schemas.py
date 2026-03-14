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


# ── Capture & Inbox (Phase 2) ────────────────────────────────────


class CaptureRequest(BaseModel):
    """Body for POST /api/capture."""
    content: str
    source: str = "manual"  # telegram | browser | manual | quick-capture
    url: str | None = None


class CaptureResponse(BaseModel):
    id: str
    date: str


class InboxEntry(BaseModel):
    """Single parsed inbox entry."""
    id: str
    time: str
    source: str
    type: str = "note"  # link | quote | note (UI hint only)
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    content: str = ""


class InboxDateSummary(BaseModel):
    date: str
    count: int


class ConvertRequest(BaseModel):
    """Body for POST /api/inbox/{date}/{entry_id}/convert."""
    title: str
    folder: str = ""
    tags: list[str] = Field(default_factory=list)
    include_scraped: bool = True


class ScrapedArticle(BaseModel):
    title: str
    content: str
    author: str | None = None
    date: str | None = None
    word_count: int = 0
    reading_time: int = 0  # minutes


# ── Chat & RAG (Phase 4) ─────────────────────────────────────────


class ChatRequest(BaseModel):
    """Body for POST /api/chat."""
    question: str
    conversation_id: str | None = None
    mode: str = "chat"  # "chat" | "summary" | "suggest-links"


class ChatSource(BaseModel):
    path: str
    title: str = ""


class SummarizeRequest(BaseModel):
    """Body for POST /api/chat/summarize."""
    note_path: str


class SuggestLinksRequest(BaseModel):
    """Body for POST /api/chat/suggest-links."""
    note_path: str
    content: str


