# Second Brain

A personal knowledge base web app with wiki-style linking and graph visualization.  
Notes are stored as Markdown files on disk and indexed for fast search.

## Features

### Editor
- Markdown editor with toolbar (bold, italic, code, heading, quote, lists, checkbox, link, image).
- Slash commands in editor (`/todo`, `/code`, `/callout`, `/table`, `/heading`, `/divider`).
- Image paste upload from clipboard (`Ctrl+V`).
- Auto-save with debounce.

### Notes and Sidebar
- Template-based note creation (`Ctrl+N`, `Alt+N` alias).
- Daily notes (`Alt+D`) and Quick Capture (`Ctrl+Shift+N`).
- Drag and drop note move between folders.
- Quick add file/folder from sidebar.
- Inline rename directly in sidebar:
  - double-click file/folder label to rename
  - `Enter` to save, `Esc` to cancel
- Context menu on note/folder and blank area in file tree.

### Search and Navigation
- Command palette (`Ctrl+K`) with recent notes and command actions.
- Full-text search via SQLite FTS5.
- Semantic search via Qdrant vector (BGE-M3, 1024-dim).
- Hybrid search: weighted fusion (0.7 vector + 0.3 keyword).
- Search mode toggle (Keyword / Semantic / Hybrid).
- Backlinks and Table of Contents panel.
- Tag explorer.
- Related notes (top-5 semantically similar).

### AI Assistant
- RAG Chat — ask questions about your vault, get cited answers.
- SSE streaming responses with clickable source links.
- Graph+Vector hybrid retrieval (BFS 1-hop expansion).
- Note summary mode — LLM summarizes any note.
- Auto-link suggestion — AI suggests `[[wiki-links]]` to related notes.
- Mode selector: Chat / Summary / Suggest Links.
- Graceful degradation when Ollama/Qdrant unavailable.

### Visualization
- D3 force-directed graph view with tag/folder/depth filters.
- RAG source highlighting on graph.
- Note metadata panel.

### System
- Filesystem watcher (`watchdog`) for external file changes.
- Template directory excluded from search/graph indexing.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New note from template |
| `Alt+N` | New note from template (alias) |
| `Ctrl+K` | Open command palette |
| `Ctrl+Shift+N` | Quick Capture |
| `Ctrl+S` | Save note |
| `Alt+C` | Toggle AI chat panel |
| `Alt+/` | Open keyboard shortcuts popup |
| `Alt+D` | Open daily note |
| `Alt+E` | Toggle editor/preview |
| `Alt+G` | Open graph view |
| `Alt+B` | Toggle sidebar |
| `/` | Open slash menu (inside editor) |
| `Enter` | Confirm inline rename in sidebar |
| `Esc` | Cancel inline rename / close popup |

## Quick Start

### 1. Create virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Qdrant (optional — for semantic search)

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

> Without Qdrant the app still works — search falls back to keyword mode (SQLite FTS5).

### 4. Run the server

```bash
python -m uvicorn backend.main:app --reload
```

Open: `http://localhost:8000`

### 5. Run tests

```bash
python -m pytest tests/ -v
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, uvicorn, aiofiles |
| Storage | Local Markdown files |
| Search | SQLite FTS5 + Qdrant vector search (hybrid) |
| Embeddings | sentence-transformers (BGE-M3, 1024-dim) |
| Chunking | markdown-it-py (AST-based semantic chunking) |
| LLM | Ollama + Qwen2.5 7B Q4_K_M (local GPU) |
| Frontend | Vanilla JS (ES modules), HTML, CSS |
| Graph | D3.js |
| Markdown | marked.js |

## Version

Current release: `v0.8.0` — Phase 4 complete (see `CHANGELOG.md`).
