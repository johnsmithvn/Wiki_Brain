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
- Backlinks and Table of Contents panel.
- Tag explorer.

### Visualization
- D3 force-directed graph view.
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
| `Alt+/` | Open keyboard shortcuts popup |
| `Alt+D` | Open daily note |
| `Alt+E` | Toggle editor/preview |
| `Alt+G` | Open graph view |
| `Alt+B` | Toggle sidebar |
| `/` | Open slash menu (inside editor) |
| `Enter` | Confirm inline rename in sidebar |
| `Esc` | Cancel inline rename / close popup |

## Quick Start

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open: `http://localhost:8000`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, aiofiles |
| Storage | Local Markdown files |
| Search | SQLite FTS5 |
| Frontend | Vanilla JS (ES modules), HTML, CSS |
| Graph | D3.js |
| Markdown | marked.js |

## Version

Current documented release line: `v0.3.x` (see `CHANGELOG.md`).
