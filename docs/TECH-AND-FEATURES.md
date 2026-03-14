# TECHNOLOGY & FEATURES — AI Knowledge OS (Second Brain)

> **Version:** v0.8.0
> **Cập nhật:** 2026-03-14
> **Platform:** Web (local server) — Desktop-first
> **Target:** Single-user personal knowledge management

---

## 1. Toàn bộ công nghệ sử dụng

### 1.1 Backend

| Component | Technology | Version | Mục đích |
|-----------|-----------|---------|----------|
| Web framework | FastAPI | 0.115.6 | REST API + SSE streaming |
| ASGI server | uvicorn | latest | Async HTTP server |
| Async file I/O | aiofiles | latest | Non-blocking filesystem |
| HTTP client | httpx | 0.28.1 | Async outbound requests (Ollama, URLs) |
| URL scraper | trafilatura | 2.0.0 | Article extraction from web pages |
| File watcher | watchdog | 6.0.0 | Detect external file changes |
| Keyword search | SQLite FTS5 | built-in | Full-text search (porter + unicode61) |
| Markdown parser | markdown-it-py | 4.0.0 | AST-based semantic chunking |
| Embedding model | sentence-transformers (BGE-M3) | 5.3.0 | 1024-dim multilingual embeddings |
| Vector database | Qdrant (qdrant-client) | 1.17.0 | Semantic search, related notes |
| LLM runtime | Ollama | external | Local LLM inference |
| LLM model | Qwen2.5 7B Q4_K_M | — | RAG chat, summary, suggestions |
| Telegram bot | python-telegram-bot | 21.x | Message capture (planned) |

### 1.2 Frontend

| Component | Technology | Mục đích |
|-----------|-----------|----------|
| Core | Vanilla JS (ES6 modules) | No build step, lightweight |
| Graph visualization | D3.js | Force-directed knowledge graph |
| Markdown rendering | marked.js | Wiki-link aware preview |
| Styling | Vanilla CSS | Custom theming (light/dark) |

### 1.3 Infrastructure

| Component | Technology | Mục đích |
|-----------|-----------|----------|
| Container | Docker Compose | Deployment (Phase 6) |
| Tunnel | Cloudflare Tunnel | HTTPS external access (Phase 6) |
| OS | Ubuntu (home server) | 32GB RAM + RTX 4060 Ti 16GB |

### 1.4 Explicitly NOT Used

| Technology | Lý do bỏ |
|------------|----------|
| Prometheus / Grafana | Quá nặng cho single-user |
| Redis / Dramatiq | Single process đủ, asyncio.Queue thay thế |
| Reranker (cross-encoder) | Vault < 5000 notes thì vector search đủ |
| React / Vue / Next.js | Vanilla JS đủ cho UI này, no build step needed |
| PostgreSQL | Markdown files = source of truth, SQLite FTS5 đủ |
| WebSocket | SSE đơn giản hơn cho one-way streaming |

---

## 2. Toàn bộ tính năng hiện tại

### 2.1 📝 Editor

| Tính năng | Chi tiết |
|-----------|----------|
| Markdown editor | Full-featured with toolbar |
| Toolbar buttons | Bold, Italic, Code, Heading, Quote, HR, Lists, Checkbox, Link, Image |
| Slash commands | `/todo`, `/code`, `/callout`, `/table`, `/heading`, `/divider`, `/quote`, `/image`, `/link` |
| Image paste | `Ctrl+V` clipboard → upload `_assets/` → insert markdown |
| Auto-save | Debounce-based, non-blocking |
| Split view | Editor + Preview side-by-side |
| Frontmatter | YAML frontmatter editing |
| Wiki-link autocomplete | Type `[[` → dropdown suggestions |

### 2.2 📂 Sidebar & Navigation

| Tính năng | Chi tiết |
|-----------|----------|
| File tree | Collapsible folder tree with note listing |
| Tab system | Files \| Inbox \| Tags |
| Drag & Drop | Move notes between folders |
| Inline rename | Double-click → rename in-place (`Enter`/`Esc`) |
| Context menu | Right-click file/folder/blank area |
| Quick add | New file/folder from sidebar |
| Tag explorer | Click tag → show notes, expand/collapse |
| Search sort | Files sorted alphabetically + by create time |

### 2.3 🔍 Search & Discovery

| Tính năng | Chi tiết |
|-----------|----------|
| Command palette | `Ctrl+K` — search, recent notes, commands |
| Keyword search | SQLite FTS5 (porter tokenizer) |
| Semantic search | Qdrant vector search (BGE-M3 embeddings) |
| Hybrid search | 0.7 × vector + 0.3 × keyword (weighted fusion) |
| Search mode toggle | Keyword / Semantic / Hybrid (3-button UI) |
| Related notes | Top-5 semantically similar notes per note |
| Backlinks | Notes that link to current note |
| Table of Contents | Auto-generated from headings |

### 2.4 🕸️ Knowledge Graph

| Tính năng | Chi tiết |
|-----------|----------|
| Graph visualization | D3.js force-directed |
| Graph filters | Filter by tags, folders, depth (1/2/3 hops) |
| Node interaction | Click → open note, hover → preview |
| RAG source highlight | Notes used in AI answer highlighted on graph |
| `[[wiki-links]]` | Bidirectional link parsing and resolution |
| Rename propagation | Rename note → update all `[[links]]` across vault |

### 2.5 📥 Capture & Inbox

| Tính năng | Chi tiết |
|-----------|----------|
| Quick Capture | `Ctrl+Shift+N` modal → routes through `/api/capture` |
| Capture API | `POST /api/capture` — accepts text/URL from any source |
| Browser bookmarklet | Captures URL + page title + selected text |
| Auto-type detection | `link` / `quote` / `note` (UI hint only) |
| URL scraping | Auto-extract article content via trafilatura |
| Inbox UI | Browse entries by date, expand/collapse |
| Convert to Note | Title, folder, tags → organized note in vault |
| Archive / Delete | Entry lifecycle management |
| Keyboard shortcuts | `Enter` convert, `A` archive, `D` delete, `↑/↓` navigate |
| Concurrent protection | asyncio.Lock per-file for inbox writes |
| Telegram Bot | Planned (T17, deferred) |

### 2.6 🤖 AI Assistant (RAG Chat)

| Tính năng | Chi tiết |
|-----------|----------|
| RAG Chat | Ask questions about your vault, get cited answers |
| SSE streaming | Real-time token-by-token response display |
| Source citations | Clickable note links at end of response |
| Graph+Vector retrieval | Vector search → graph expansion → hybrid scoring |
| Scoring formula | `0.6 × vector + 0.3 × graph_proximity + 0.1 × keyword` |
| Context budget | ≤ 2000 tokens, grouped by note path |
| Hallucination guard | Strict system prompt: "Only use sources, admit gaps" |
| Summary mode | Summarize any note via LLM |
| Auto-link suggestion | AI suggests `[[wiki-links]]` to related notes |
| Mode selector | Chat / Summary / Suggest Links dropdown |
| Graceful degradation | 503 when Ollama down, keyword fallback without Qdrant |
| LLM | Qwen2.5 7B Q4_K_M (local GPU, ~5GB VRAM) |
| Embedding | BGE-M3 (1024-dim, multilingual VN+EN, ~2.5GB VRAM) |

### 2.7 🎨 UI/UX Design

| Tính năng | Chi tiết |
|-----------|----------|
| Layout | 4-panel: Sidebar \| Editor \| AI Chat \| Graph |
| Theme | Dark (charcoal + amber/gold accent) + Light mode |
| Theme toggle | `Ctrl+Shift+T` |
| Panel toggles | `Ctrl+B` sidebar, `Alt+C` AI chat, `Alt+G` graph |
| Toast notifications | User feedback for actions |
| Status bar | Word/char count, save status |
| Custom dialogs | Modal-based confirm/prompt (no native dialogs) |
| Keyboard-first | Comprehensive shortcut system |

### 2.8 📝 Note Management

| Tính năng | Chi tiết |
|-----------|----------|
| Template notes | `Ctrl+N` → choose template from `knowledge/template/` |
| Daily notes | `Alt+D` → auto-create `daily/YYYY-MM-DD.md` |
| Note metadata | Created, modified, words, chars, tags, links, backlinks |
| YAML frontmatter | title, source, captured, tags |
| Folder management | Create, rename, move via UI |
| Path traversal guard | `Path.relative_to()` enforcement |

### 2.9 ⚙️ System

| Tính năng | Chi tiết |
|-----------|----------|
| File watcher | watchdog → async queue → note_pipeline |
| External change sync | Auto-reload open note when clean |
| Conflict detection | Toast when unsaved edits + external change |
| Health endpoint | `GET /api/health` — index, vector, watcher readiness |
| Incremental indexing | Only changed notes re-indexed/re-embedded |
| Content hash dedup | SHA256 hash skip for unchanged notes |
| Embedding debounce | 2s window to batch rapid saves |
| Cache-Control | `no-cache` middleware for dev updates |

---

## 3. Keyboard Shortcuts (Complete)

| Category | Shortcut | Action |
|----------|----------|--------|
| **Navigation** | `Ctrl+K` | Command palette / search |
| | `Alt+B` / `Ctrl+B` | Toggle sidebar |
| | `Alt+C` | Toggle AI chat panel |
| | `Alt+G` | Toggle graph view |
| | `Alt+D` | Open daily note |
| | `Alt+/` | Keyboard shortcuts popup |
| **Editor** | `Ctrl+S` | Save note |
| | `Ctrl+N` / `Alt+N` | New note from template |
| | `Alt+E` | Toggle editor/preview |
| | `/` | Slash menu (inside editor) |
| **Capture** | `Ctrl+Shift+N` | Quick Capture |
| **Inbox** | `Enter` | Convert entry |
| | `A` | Archive entry |
| | `D` | Delete entry |
| | `↑/↓` | Navigate entries |
| | `Alt+I` | Switch to Inbox tab |
| **AI Chat** | `Enter` | Send message |
| | `Shift+Enter` | New line in chat input |
| **Theme** | `Ctrl+Shift+T` | Toggle dark/light |
| **Sidebar** | `Enter` | Confirm inline rename |
| | `Esc` | Cancel rename / close popup |

---

## 4. API Endpoints (Complete)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/health` | Service readiness |
| `GET` | `/api/notes/tree` | File tree |
| `GET` | `/api/notes/{path}` | Read note |
| `PUT` | `/api/notes/{path}` | Update note |
| `POST` | `/api/notes` | Create note |
| `DELETE` | `/api/notes/{path}` | Delete note |
| `GET` | `/api/notes/{path}/meta` | Note metadata |
| `GET` | `/api/notes/{path}/related` | Related notes (semantic) |
| `POST` | `/api/notes/{path}/rename` | Rename with link propagation |
| `POST` | `/api/notes/{path}/move` | Move note |
| `POST` | `/api/notes/folder` | Create folder |
| `GET` | `/api/search` | Search (`?q=...&mode=hybrid`) |
| `GET` | `/api/graph` | Graph data (`?tags=...&folders=...&depth=...`) |
| `GET` | `/api/tags` | All tags |
| `GET` | `/api/tags/{tag}` | Notes by tag |
| `GET` | `/api/daily` | Daily note list |
| `GET` | `/api/daily/today` | Today's daily note |
| `POST` | `/api/capture` | Zero-friction capture |
| `GET` | `/api/inbox` | Inbox dates |
| `GET` | `/api/inbox/{date}` | Inbox entries |
| `POST` | `/api/inbox/{date}/{id}/convert` | Convert to vault note |
| `DELETE` | `/api/inbox/{date}/{id}` | Delete entry |
| `POST` | `/api/inbox/{date}/{id}/archive` | Archive entry |
| `POST` | `/api/chat` | RAG chat (SSE streaming) |
| `POST` | `/api/chat/summarize` | Note summary (SSE streaming) |
| `POST` | `/api/chat/suggest-links` | Auto-link suggestions |
| `GET` | `/api/templates` | Template list |
| `GET` | `/api/templates/{path}` | Template content |
| `POST` | `/api/assets` | Image upload |

---

## 5. Test Coverage

| Phase | Test file | Count | Coverage |
|-------|-----------|-------|----------|
| 1 | `test_file_service.py`, `test_link_service.py`, etc. | 43 | Core services |
| 2 | `test_capture_inbox.py`, `test_note_pipeline.py` | 29 | Capture, inbox, pipeline |
| 3 | `test_chunker_service.py` | 23 | Chunking, embedding |
| 4 | `test_phase4_rag.py` | 27 | RAG, graph expansion, LLM |
| Hardening | Various fixes | — | ID format, security |
| **Total** | | **179** | |

---

## 6. Upcoming (Not Yet Implemented)

| Phase | Feature | Status |
|-------|---------|--------|
| **5** | Research threads (persistent conversations) | ⬜ Planned |
| **5** | Short-term memory (last 10 messages) | ⬜ Planned |
| **5** | Long-term memory (AI-learned preferences) | ⬜ Planned |
| **5** | Weekly synthesis notes | ⬜ Planned |
| **5** | Topic clustering on graph | ⬜ Planned |
| **5** | Low-connected notes detection | ⬜ Planned |
| **6** | Docker Compose deployment | ⬜ Planned |
| **6** | Cloudflare Tunnel (HTTPS) | ⬜ Planned |
| **6** | RAG eval loop | ⬜ Planned |
| **6** | LRU cache for repeated queries | ⬜ Planned |
| **2** | Telegram Bot (T17) | ⬜ Deferred |
