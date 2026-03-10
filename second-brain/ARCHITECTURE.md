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
6. `notes.py` updates `tag_service`, `link_service`, and `index_service` with the new content.
7. Frontend updates status bar with successful save.

## Security Considerations
- **Path Traversal Protection**: `file_service.py` enforces that all manipulated paths fall strictly under the `KNOWLEDGE_DIR` root using Python's `Path.relative_to()`. Hidden folders (e.g., `_assets/`) are excluded from file tree views.
- **Cache-Control**: FastAPI sets `Cache-Control: no-cache` middleware during development to prevent aggressive browser caching masking recent JS updates.

## Upcoming: Phase 3 — Semantic Search

The next phase adds semantic search capabilities. Key new components (not yet implemented):

| File | Purpose |
|------|---------|
| `backend/services/chunker_service.py` | Markdown → semantic chunks (heading/paragraph, 120-450 tokens) |
| `backend/services/embedding_service.py` | Chunks → vectors via BGE-M3 (batch, GPU) |
| `backend/services/vector_service.py` | Qdrant CRUD (upsert, search, delete) |
| `backend/config/retrieval.py` | Tunable retrieval fusion weights (vector/graph/keyword) |

Key design decisions documented in `docs/DESIGN-chunking-retrieval.md`:
- Embedding debounce (2s) to avoid GPU spam on rapid saves
- Retrieval weights configurable, not hardcoded
- Chunk sizes: MAX=450, TARGET=300, MIN=120 tokens
