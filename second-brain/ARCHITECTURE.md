# Second Brain Architecture & Codebase Guide

This document outlines the high-level architecture, module flow, and codebase structure for the **Second Brain** application. 

## System Overview

Second Brain is a personal knowledge management system built as a monolithic web application. It follows a client-server architecture:
- **Backend**: Python (FastAPI) providing a purely RESTful JSON API.
- **Frontend**: Vanilla JavaScript (ES modules), HTML, and CSS served as static files by the backend.
- **Storage**: Local filesystem-based Markdown storage. No external database is required.

## Backend Architecture

The backend is built with FastAPI and follows a modular service-oriented architecture.

### 1. API Routing Layer (`backend/api/`)
This layer handles incoming HTTP requests, input validation, and HTTP responses. It delegates business logic to the service layer.
- `notes.py`: CRUD operations for markdown files, folder creation, and retrieving the file tree.
- `daily.py`: Specialized endpoints for daily notes (auto-creation, listing).
- `search.py`: Full-text search and command palette API.
- `graph.py`: Endpoints for generating D3.js compatible node/link graph data.
- `tags.py`: Endpoints for listing all tags and finding notes by tag.
- `assets.py`: Image upload handling with unique filename generation.
- `capture.py`: Zero-friction capture endpoint (`POST /api/capture`) — accepts text/URL from any source (browser, quick-capture, Telegram).
- `inbox.py`: Inbox CRUD — list dates, get entries, convert to note, delete, archive.
- `chat.py`: RAG chat with SSE streaming (`POST /api/chat`), note summarization (`POST /api/chat/summarize`), link suggestions (`POST /api/chat/suggest-links`).
- `health.py`: Service readiness health check.

### 2. Service Layer (`backend/services/`)
This layer contains the core business logic, decoupled from HTTP concerns.
- `file_service.py`: Safely interacts with the filesystem using `aiofiles`. It prevents path traversal and parses markdown files.
- `index_service.py`: In-memory SQLite FTS5 database for fast full-text search capability. Rebuilds index on startup and keeps it synchronized.
- `link_service.py`: Parses and resolves `[[wiki-links]]` to maintain bidirectional connectivity between notes.
- `tag_service.py`: Extracts `#tags` and YAML frontmatter tags from markdown content.
- `note_pipeline.py`: Orchestrates tags → links → index update in a single call, eliminating duplication.
- `capture_service.py`: Entry creation from raw text/URL, type auto-detection, per-file `asyncio.Lock` for concurrent writes, scraper integration for URL enrichment.
- `inbox_service.py`: State-machine parser for inbox markdown files, entry CRUD, convert-to-note with slug generation.
- `scraper_service.py`: Async URL fetch via `httpx` + article extraction via `trafilatura` (CPU-heavy, runs in `asyncio.to_thread()`).
- `watcher_service.py`: Filesystem watcher (watchdog) bridging sync events to async queue for incremental reindexing.
- `template_service.py`: Template discovery and loading from `knowledge/template/`.
- `rename_service.py`: Rename propagation — updates all `[[wiki-links]]` across vault when a note is renamed.
- `chunker_service.py`: Markdown → semantic chunks using markdown-it-py AST. Pure function, no side effects.
- `embedding_service.py`: Singleton BGE-M3 embedding model. Lazy loading, async batch embedding via `asyncio.to_thread()`.
- `vector_service.py`: Qdrant client wrapper. Collection lifecycle, per-note upsert/delete, vector search with filters.
- `llm_service.py`: Ollama LLM client with async SSE streaming. Supports `generate_stream()` and `generate()`.
- `graph_expansion_service.py`: BFS 1-hop expansion from seed notes via wiki-link graph for RAG context enrichment.
- `rag_service.py`: Full RAG retrieval pipeline — vector search → graph expansion → chunk scoring (0.6v + 0.3g + 0.1k) → context building (≤2000 tokens).

### 3. Application Entrypoint (`backend/main.py`)
- Initializes global services during `lifespan` startup.
- Configures generic CORS and Cache-Control middleware (essential for frontend dev updates).
- Mounts API routers and static file directories (`frontend/` and `_assets/`).

## Frontend Architecture

The frontend uses Vanilla Javascript modules (`ES6`) to keep the application lightweight without build steps.

### 1. State Management & Coordination (`frontend/js/app.js`)
- `app.js` is the entry controller. It coordinates all other modules, maintains global state (`state.currentNote`, `state.activeTasks`), handles global keyboard shortcuts, and dispatches UI updates.

### 2. UI Modules
- `sidebar.js`: Handles file tree rendering, drag-and-drop file movement, and tag explorer.
- `inbox.js`: Inbox panel — browse captured entries by date, expand/collapse, convert to note, archive, delete with keyboard shortcuts.
- `editor.js`: The central text editor overlaying basic markdown features with toolbar and image pasting integration.
- `preview.js`: Renders markdown to HTML using `marked.js`, resolving internal wiki-links and inline tags.
- `graph.js`: Renders the D3.js force-directed graph.
- `search.js` & `slash-menu.js`: Implements the command palette and editor slash commands logic.
- `quick-capture.js`: A specialized modal for capturing ideas to the inbox via `POST /api/capture`.
- `toolbar.js`: Logic for bold, italic, code-blocks and heading manipulation in the editor.
- `toc.js`: Dynamically generates the table of contents from markdown headings.
- `shortcuts-modal.js`: Keyboard shortcuts reference popup.

### 3. API Communication (`frontend/js/api.js`)
- Centralized `fetch` wrapper handling API requests, URI encoding, and HTTP error normalization.

## Data Flow Diagram (Saving a Note)

1. User types in `editor.js`.
2. Debouncer triggers `app.saveNote()`.
3. `api.updateNote()` encodes the path and sends `PUT /api/notes/{path}`.
4. FastAPI validates request in `notes.py` and calls `file_service.write_file()`.
5. `file_service` writes markdown to disk.
6. `notes.py` calls `note_pipeline.process_note()` which updates `tag_service`, `link_service`, `index_service`, and schedules embedding.
7. After 2s debounce, `note_pipeline` chunks the note → embeds via BGE-M3 → upserts to Qdrant (if available).
8. Frontend updates status bar with successful save.

## Security Considerations
- **Path Traversal Protection**: `file_service.py` enforces that all manipulated paths fall strictly under the `KNOWLEDGE_DIR` root using Python's `Path.relative_to()`. Hidden folders (e.g., `_assets/`) are excluded from file tree views.
- **Cache-Control**: FastAPI sets `Cache-Control: no-cache` middleware during development to prevent aggressive browser caching masking recent JS updates.

## Phase 4 — RAG Chat & AI Assistant (Complete ✅)

Phase 4 adds local LLM-powered chat with graph-enhanced retrieval.

### New Services

| File | Purpose |
|------|---------|
| `backend/services/llm_service.py` | Ollama async streaming client (httpx). Qwen2.5 7B Q4_K_M default model. |
| `backend/services/graph_expansion_service.py` | BFS 1-hop expansion from wiki-link graph. Graph proximity scoring. |
| `backend/services/rag_service.py` | Full retrieval pipeline: vector search → graph expand → weighted scoring → token-limited context building. |
| `backend/api/chat.py` | SSE streaming chat endpoint, note summarization, auto-link suggestion. |
| `frontend/js/chat.js` | Chat UI module — streaming display, source links, mode selector (Chat/Summary/Suggest). |
| `frontend/css/chat.css` | Chat panel styles. |

### Key Design Decisions

Documented in `docs/DESIGN-graph-vector-reasoning.md`:
- **Graph+Vector hybrid**: Vector search finds semantically similar chunks, graph expansion discovers structurally related (linked) notes that vector search might miss.
- **Scoring formula**: `0.6 * vector_score + 0.3 * graph_proximity + 0.1 * keyword_overlap`
- **Context budget**: ≤2000 tokens, grouped by note path with `[Source: path]` headers.
- **System prompt**: 5 rules — use only sources, admit gaps, cite notes, match language, be concise.
- **Graceful degradation**: Chat returns 503 when Ollama unavailable. Suggest-links returns empty without Qdrant. Keyword fallback when vector unavailable.
- **SSE streaming**: Tokens streamed via `data: {"token": "..."}` events, sources sent at end with `{"sources": [...], "done": true}`.
