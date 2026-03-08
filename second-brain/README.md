# 🧠 Second Brain

A personal knowledge base web app with Wiki + Obsidian-like interface. Store your notes as `.md` files on disk, link them with `[[wiki-links]]`, and visualize connections with an interactive graph.

## Features

### ✍️ Editor
- **Markdown Editor** with formatting toolbar (Bold, Italic, Code, Heading, Quote, Lists, Checkbox, Link, Image)
- **Slash Commands** — Type `/` in editor for quick insert: `/todo`, `/code`, `/callout`, `/table`, `/heading`, `/divider`
- **Image Paste** — `Ctrl+V` to paste clipboard images directly into notes
- **Auto-save** with debounced saving

### 📝 Notes
- **Daily Notes** — Auto-created daily journal with `Alt+D`
- **Quick Capture** — `Ctrl+Shift+N` popup to capture ideas to daily note
- **Drag & Drop** — Reorganize notes by dragging files to folders
- **Bi-directional Links** — Connect ideas with `[[wiki-links]]`
- **Tags** — YAML frontmatter + inline `#tag` support

### 🔍 Search & Navigate
- **Command Palette** — `Ctrl+K` with search, recent notes, and `/commands`
- **Full-text Search** — SQLite FTS5 instant search
- **Tag Explorer** — Click tags in sidebar to see related notes
- **Table of Contents** — Auto-generated, click to scroll
- **Backlinks** — See what links to the current note

### 📊 Visualization
- **Graph View** — D3.js force-directed knowledge graph
- **Note Metadata** — Created, modified, word count, links, tags in right panel

### 🎨 Interface
- **Dark Mode** — Obsidian-inspired dark theme
- **File Tree** — Folders with collapsible tree and context menus
- **Keyboard-first** — Full shortcut support

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
| Editor | Textarea + toolbar |
| Preview | marked.js |
| Graph | D3.js force-directed |
| Icons | Lucide |
| Styling | Vanilla CSS (dark mode) |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Search / Command Palette |
| `Ctrl+S` | Save Note |
| `Ctrl+Shift+N` | Quick Capture |
| `Alt+N` | New Note |
| `Alt+D` | Daily Note |
| `Alt+E` | Toggle Editor/Preview |
| `Alt+G` | Graph View |
| `Alt+B` | Toggle Sidebar |
| `/` (in editor) | Slash commands menu |

## Project Structure

```
second-brain/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── api/
│   │   ├── notes.py         # Notes CRUD
│   │   ├── search.py        # Full-text search
│   │   ├── graph.py         # Graph data
│   │   ├── tags.py          # Tag management
│   │   ├── daily.py         # Daily notes
│   │   └── assets.py        # Image upload
│   ├── services/            # Business logic
│   └── models/              # Pydantic schemas
├── frontend/
│   ├── index.html           # SPA shell
│   ├── css/
│   │   ├── variables.css    # Design tokens
│   │   ├── base.css         # Reset & typography
│   │   ├── layout.css       # App layout
│   │   ├── editor.css       # Editor styles
│   │   ├── graph.css        # Graph view
│   │   ├── components.css   # UI components
│   │   └── toolbar.css      # Toolbar + quick capture + slash menu
│   └── js/
│       ├── app.js           # Main controller
│       ├── api.js           # API client
│       ├── sidebar.js       # File tree + tags + drag & drop
│       ├── editor.js        # Editor + image paste
│       ├── preview.js       # Markdown rendering
│       ├── search.js        # Command palette
│       ├── graph.js         # Graph visualization
│       ├── toc.js           # Table of contents
│       ├── modal.js         # Custom dialogs
│       ├── toolbar.js       # Formatting toolbar
│       ├── quick-capture.js # Quick note capture
│       └── slash-menu.js    # Slash commands
├── knowledge/               # Your markdown vault
├── data/                    # SQLite search index
├── .gitignore
├── CHANGELOG.md
└── requirements.txt
```

## Version

**v0.2.0** — Feature upgrade (Daily notes, Quick capture, Editor toolbar, Drag & Drop, Slash commands, Image paste, Tag explorer, Metadata panel, Command palette)
