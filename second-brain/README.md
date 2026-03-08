# 🧠 Second Brain

A personal knowledge base web app with Wiki + Obsidian-like interface. Store your notes as `.md` files on disk, link them with `[[wiki-links]]`, and visualize connections with an interactive graph.

## Features

- ✍️ **Markdown Editor** — Write with full markdown support
- 🔗 **Bi-directional Links** — Connect ideas with `[[wiki-links]]`
- 🕸️ **Graph View** — D3.js force-directed knowledge graph
- 🔍 **Full-text Search** — SQLite FTS5 with `Ctrl+K` command palette
- 📁 **File Tree** — Folders, context menus, drag-and-drop
- 🏷️ **Tags** — YAML frontmatter + inline `#tag` support
- 📋 **Table of Contents** — Auto-generated from headings
- 🔙 **Backlinks** — See what links to the current note
- 🌙 **Dark Mode** — Obsidian-inspired dark theme
- ⌨️ **Keyboard Shortcuts** — `Ctrl+K/N/B/E/G/S`

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python -m uvicorn backend.main:app --reload

# Open in browser
http://localhost:8000
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI |
| Storage | Markdown files on disk |
| Search | SQLite FTS5 |
| Editor | Textarea (markdown) |
| Preview | marked.js |
| Graph | D3.js force-directed |
| Icons | Lucide |
| Styling | Vanilla CSS (dark mode) |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Search / Command Palette |
| `Alt+N` | New Note |
| `Ctrl+S` | Save Note |
| `Alt+E` | Toggle Editor/Preview |
| `Alt+G` | Graph View |
| `Alt+B` | Toggle Sidebar |

## Project Structure

```
second-brain/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── api/                 # REST API routes
│   ├── services/            # Business logic
│   └── models/              # Pydantic schemas
├── frontend/
│   ├── index.html           # SPA shell
│   ├── css/                 # Design system
│   └── js/                  # Modular JS
├── knowledge/               # Your markdown vault
├── data/                    # SQLite search index
└── requirements.txt
```

## Version

**v0.1.0** — Initial release
