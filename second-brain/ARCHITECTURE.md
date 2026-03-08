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

### 2. Service Layer (`backend/services/`)
This layer contains the core business logic, decoupled from HTTP concerns.
- `file_service.py`: Safely interacts with the filesystem using `aiofiles`. It prevents path traversal and parses markdown files.
- `index_service.py`: In-memory SQLite FTS5 database for fast full-text search capability. Rebuilds index on startup and keeps it synchronized.
- `link_service.py`: Parses and resolves `[[wiki-links]]` to maintain bidirectional connectivity between notes.
- `tag_service.py`: Extracts `#tags` and YAML frontmatter tags from markdown content.

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
- `editor.js`: The central text editor overlaying basic markdown features with toolbar and image pasting integration.
- `preview.js`: Renders markdown to HTML using `marked.js`, resolving internal wiki-links and inline tags.
- `graph.js`: Renders the D3.js force-directed graph.
- `search.js` & `slash-menu.js`: Implements the command palette and editor slash commands logic.
- `quick-capture.js`: A specialized modal for appending items to the daily note.
- `toolbar.js`: Logic for bold, italic, code-blocks and heading manipulation in the editor.
- `toc.js`: Dynamically generates the table of contents from markdown headings.

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
