# PROJECT DESIGN SUMMARY — AI Knowledge OS (Second Brain)

> **Version:** v0.8.0 (Phase 4 Complete)
> **Cập nhật:** 2026-03-14

---

## 1. Tổng quan dự án

**AI Knowledge OS** là hệ thống quản lý kiến thức cá nhân chạy local, kết hợp manual workflow + AI augmentation.

```
Knowledge Collector + Knowledge Vault + AI Reasoning System
```

**Nguyên tắc cốt lõi:**
- **Markdown = Source of Truth** — text-first, không vendor lock-in
- **AI = Layer bổ sung** — manual workflow luôn hoạt động, AI không auto move/delete
- **Capture = Zero friction** — ném vào Telegram/browser → tự append inbox
- **Home Server** — Ubuntu 32GB RAM + RTX 4060 Ti 16GB, local AI miễn phí

---

## 2. Kiến trúc hệ thống

```
┌──────────────────────────────────────────────────────────────┐
│                        CAPTURE LAYER                         │
│  Telegram Bot │ Browser Bookmarklet │ Web UI │ Quick Capture │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                       │
│  Entry Parser │ URL Scraper │ Schema Normalizer │ Watcher    │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE VAULT                          │
│              Markdown Filesystem (Source of Truth)            │
│  inbox/ │ daily/ │ {topic folders}/ │ template/ │ _assets/   │
└─────────────────────────┬────────────────────────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  FTS INDEX   │ │  TAG/LINK    │ │  SEMANTIC    │
│  SQLite FTS5 │ │  GRAPH       │ │  INDEX       │
│  (keyword)   │ │  (in-memory) │ │  (Qdrant)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       └────────────────┼────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                     RETRIEVAL LAYER                          │
│  Hybrid Search (FTS + Vector → weighted fusion)              │
│  Graph Expansion (vector → extract notes → BFS neighbors)    │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                       AI LAYER                               │
│  RAG Chat │ Summary │ Related Notes │ Auto-link Suggestion   │
│  Graph+Vector Hybrid Reasoning │ Topic Clustering            │
│  LLM: Ollama + Qwen2.5 7B (local GPU)                       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND                                │
│  4-Panel: Sidebar │ Editor/Preview │ AI Panel │ Graph/Search │
│  Vanilla JS + D3.js + marked.js                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Architecture

### 3.1 Service Boundary Rule

```
API Layer → Service Layer → Storage Layer
Never reverse. Never circular.
```

### 3.2 Service Groups

**Core Group (Phase 1):**
- `file_service.py` — async filesystem I/O (aiofiles, pathlib)
- `index_service.py` — SQLite FTS5 in-memory search
- `link_service.py` — `[[wiki-link]]` bidirectional graph (in-memory dict)
- `tag_service.py` — `#tag` + frontmatter extraction (regex, pure function)
- `template_service.py` — template discovery from `knowledge/template/`
- `rename_service.py` — rename propagation across all wiki-links
- `watcher_service.py` — watchdog → async queue → note_pipeline

**Pipeline (Orchestrator):**
- `note_pipeline.py` — tags → links → FTS index → debounced embedding

**Capture Group (Phase 2):**
- `capture_service.py` — entry creation, type auto-detect, per-file asyncio.Lock
- `scraper_service.py` — httpx + trafilatura (asyncio.to_thread)
- `inbox_service.py` — state-machine parser, entry CRUD, convert-to-note

**Embedding Group (Phase 3):**
- `chunker_service.py` — markdown AST → semantic chunks (120-450 tokens)
- `embedding_service.py` — BGE-M3 model (1024-dim, multilingual VN+EN)
- `vector_service.py` — Qdrant CRUD, content hash dedup

**AI Group (Phase 4):**
- `llm_service.py` — Ollama async streaming client (httpx)
- `graph_expansion_service.py` — BFS 1-hop expansion, proximity scoring
- `rag_service.py` — vector search → graph expand → weighted scoring → context building

### 3.3 API Endpoints

| Router | Endpoints |
|--------|-----------|
| `notes.py` | CRUD, folder, file tree, related notes |
| `daily.py` | Daily note auto-create/list |
| `search.py` | FTS5 + hybrid search (keyword/semantic/hybrid) |
| `graph.py` | D3.js node/link data with filters |
| `tags.py` | Tag listing, notes-by-tag |
| `capture.py` | `POST /api/capture` zero-friction |
| `inbox.py` | Inbox CRUD, convert, archive |
| `chat.py` | RAG chat (SSE), summarize, suggest-links |
| `health.py` | Service readiness check |
| `assets.py` | Image upload |
| `templates.py` | Template discovery |

### 3.4 Async Rules

| Pattern | Khi nào |
|---------|---------|
| `async` native | File I/O, httpx, Qdrant HTTP |
| `asyncio.to_thread()` | CPU-heavy sync: trafilatura, embedding, SQLite |
| `asyncio.Lock()` per-file | Inbox concurrent write |
| `asyncio.Queue` | Watcher → note_pipeline |
| `asyncio.TimerHandle` | Embedding debounce (2s) |

---

## 4. Frontend Architecture

### 4.1 Stack
- **Vanilla JS** (ES modules) — no build step
- **D3.js** — force-directed knowledge graph
- **marked.js** — markdown rendering

### 4.2 Module Structure

| Module | Responsibility |
|--------|----------------|
| `app.js` | Entry controller, global state, keyboard shortcuts |
| `api.js` | Centralized fetch wrapper |
| `editor.js` | Markdown editing, toolbar integration |
| `preview.js` | Markdown → HTML, wiki-link resolution |
| `sidebar.js` | File tree, drag-drop, tabs (Files/Inbox/Tags) |
| `inbox.js` | Inbox panel — browse, convert, archive, delete |
| `chat.js` | AI chat panel — SSE streaming, source links, mode selector |
| `graph.js` | D3.js graph with filters (tags, folders, depth) |
| `search.js` | Command palette + search modes |
| `quick-capture.js` | Quick capture modal |
| `modal.js` | Shared dialog system |
| `toolbar.js` | Editor formatting toolbar |
| `toc.js` | Table of contents generator |
| `slash-menu.js` | Editor slash commands |
| `template-modal.js` | Template-based note creation |
| `shortcuts-modal.js` | Keyboard shortcuts popup |

### 4.3 Layout: 4-Panel

```
┌──────────┬────────────────────────┬──────────┬───────────────┐
│ Sidebar  │   Editor / Preview     │  AI Chat │  Graph/Search │
│ (240px)  │   (flexible)           │  (350px) │  (350px)      │
└──────────┴────────────────────────┴──────────┴───────────────┘
```

---

## 5. Data Flow — Quan trọng

### 5.1 Save Note Flow

```
User types → debounce → api.updateNote() → PUT /api/notes/{path}
  → file_service.write_file() → disk
  → note_pipeline.process_note():
      → tag_service (instant)
      → link_service (instant)
      → index_service (FTS5, instant)
      → schedule_embed (2s debounce):
          → chunker_service → chunks
          → embedding_service → vectors (GPU)
          → vector_service → Qdrant upsert
```

### 5.2 RAG Chat Flow

```
User question
  → POST /api/chat (SSE)
  → rag_service.retrieve_context():
      → embedding_service.embed_query() → query vector
      → vector_service.search() → top-10 chunks
      → extract seed note_paths
      → graph_expansion_service.expand_notes() → BFS 1-hop neighbors
      → vector_service.get_chunks_for_notes(neighbors) → neighbor chunks
      → weighted scoring: 0.6*vector + 0.3*graph + 0.1*keyword
      → select top-5 within 2000-token budget
  → build_context() → group by note_path
  → llm_service.generate_stream() → SSE tokens
  → sources sent at end
```

### 5.3 Capture Flow

```
Source (Telegram/Browser/WebUI)
  → POST /api/capture
  → capture_service.create_entry() → type auto-detect
  → if URL: scraper_service.scrape_url() → enrich
  → append_to_inbox() (asyncio.Lock per-file)
  → knowledge/inbox/YYYY-MM-DD.md
```

---

## 6. Storage Layer

| Storage | Nội dung | Lifecycle |
|---------|----------|-----------|
| Markdown vault (`knowledge/`) | Notes, daily, inbox, templates | Permanent, source of truth |
| SQLite FTS5 (in-memory) | Keyword search index | Rebuilt on startup |
| In-memory dicts | Wiki-link graph, tag index | Rebuilt on startup |
| Qdrant (localhost:6333) | Vector embeddings (BGE-M3 1024-dim) | Rebuilt on demand |
| JSON files (`knowledge/memory/threads/`) | Research threads | Permanent (Phase 5) |

---

## 7. Design Documents Map

| Document | Nội dung | Phase |
|----------|----------|-------|
| `PLAN-ai-knowledge-os.md` | Master plan — phases, tasks, timeline | All |
| `BACKEND-SERVICE-BOUNDARIES.md` | Dependency graph, async rules, concurrency | All |
| `DESIGN-ingestion-pipeline.md` | Capture → Inbox → Vault pipeline | 2 |
| `DESIGN-chunking-retrieval.md` | Chunking + Hybrid search + Embedding | 3 |
| `DESIGN-graph-vector-reasoning.md` | RAG + Graph expansion + LLM | 4 |
| `DESIGN-ui-layout.md` | 4-panel layout, wireframes, shortcuts | 2-5 |
| `DESIGN-memory-layer.md` | Memory types + Research threads | 5 |

---

## 8. Important Files Map

### Backend

```
backend/
├── main.py                     # FastAPI entry, lifespan, middleware
├── config/
│   ├── __init__.py             # Settings (BaseSettings), version
│   └── retrieval.py            # Tunable retrieval weights
├── api/
│   ├── notes.py                # Note CRUD + related notes
│   ├── search.py               # Hybrid search (3 modes)
│   ├── chat.py                 # RAG chat SSE + summarize + suggest-links
│   ├── inbox.py                # Inbox CRUD
│   ├── capture.py              # Zero-friction capture
│   ├── graph.py                # Graph data with filters
│   ├── daily.py                # Daily notes
│   ├── tags.py                 # Tag listing
│   ├── health.py               # Service readiness
│   ├── assets.py               # Image upload
│   └── templates.py            # Template discovery
├── services/
│   ├── file_service.py         # Filesystem I/O (async)
│   ├── index_service.py        # SQLite FTS5
│   ├── link_service.py         # Wiki-link graph
│   ├── tag_service.py          # Tag extraction
│   ├── note_pipeline.py        # Orchestrator: tags→links→index→embed
│   ├── capture_service.py      # Entry creation + inbox append
│   ├── inbox_service.py        # Inbox parser + CRUD
│   ├── scraper_service.py      # URL scraping (httpx + trafilatura)
│   ├── chunker_service.py      # Markdown → semantic chunks
│   ├── embedding_service.py    # BGE-M3 embedding (GPU)
│   ├── vector_service.py       # Qdrant client
│   ├── llm_service.py          # Ollama streaming client
│   ├── rag_service.py          # RAG retrieval pipeline
│   ├── graph_expansion_service.py  # BFS graph expansion
│   ├── rename_service.py       # Rename propagation
│   ├── template_service.py     # Template loading
│   └── watcher_service.py      # Filesystem watcher
└── schemas.py                  # Pydantic models
```

### Frontend

```
frontend/
├── index.html                  # Shell — all panel containers
├── css/
│   ├── variables.css           # Theme tokens (light/dark)
│   ├── layout.css              # 4-panel grid
│   ├── base.css                # Reset + typography
│   ├── components.css          # Shared components
│   ├── editor.css              # Editor styles
│   ├── chat.css                # AI chat panel
│   ├── inbox.css               # Inbox panel
│   ├── graph.css               # Graph view
│   ├── graph-filter.css        # Graph filter panel
│   ├── toolbar.css             # Editor toolbar
│   └── template-modal.css      # Template modal
├── js/
│   ├── app.js                  # Entry controller + state
│   ├── api.js                  # Fetch wrapper
│   ├── editor.js               # Markdown editor
│   ├── preview.js              # Markdown renderer
│   ├── sidebar.js              # File tree + tabs
│   ├── inbox.js                # Inbox panel
│   ├── chat.js                 # AI chat panel
│   ├── graph.js                # D3.js graph
│   ├── search.js               # Command palette
│   ├── quick-capture.js        # Quick capture modal
│   ├── modal.js                # Dialog system
│   ├── toolbar.js              # Formatting toolbar
│   ├── toc.js                  # Table of contents
│   ├── slash-menu.js           # Slash commands
│   ├── template-modal.js       # Template selection
│   └── shortcuts-modal.js      # Shortcuts popup
└── bookmarklet.html            # Browser bookmarklet setup page
```

### Data

```
knowledge/
├── inbox/                      # Captured entries (daily .md files)
├── daily/                      # Daily notes
├── template/                   # Note templates
├── _assets/                    # Uploaded images
├── memory/                     # AI memory (Phase 5)
│   └── threads/                # Research threads (JSON)
└── {topic folders}/            # Organized notes
```

---

## 9. Key Design Decisions

| Decision | Lý do |
|----------|-------|
| Markdown source of truth | Text-first, no vendor lock-in, AI reads well |
| No token overlap in chunks | Paragraph-boundary split preserves semantics |
| Heading propagation instead of overlap | Each chunk carries its heading context |
| Weighted fusion over RRF | Simpler, sufficient for solo project |
| BFS depth=1 for graph expansion | depth=2 creates too much noise |
| 2s embedding debounce | Prevents GPU spam on rapid edits |
| Separate note_pipeline debounce (500ms) | Tags/links/FTS update fast, embedding is expensive |
| Content hash for re-embed skip | Only changed notes re-embedded |
| asyncio.Lock per-file, not global | Concurrent inbox writes for different days |
| Graceful degradation | Core works without Qdrant/Ollama |
| Auto-link suggestion over tag suggestion | `[[connections]]` more useful than tags |
| SSE streaming for chat | Real-time token display, no websocket complexity |

---

## 10. Progress per Phase

| Phase | Status | Version | Mô tả |
|-------|--------|---------|-------|
| **1** | ✅ Done | v0.4.0 | Core knowledge base, editor, graph, FTS, wiki-links |
| **2** | ✅ Done | v0.6.0 | Capture pipeline, inbox, bookmarklet, scraper |
| **2.5** | ✅ Done | v0.5.0 | Refactor: note_pipeline, async queue, health |
| **3** | ✅ Done | v0.7.0 | Semantic search: chunking, embedding, Qdrant, hybrid search |
| **4** | ✅ Done | v0.8.0 | RAG chat, graph+vector reasoning, summary, auto-link |
| **5** | ⬜ Next | — | Research threads, memory layer, insights |
| **6** | ⬜ | — | Docker, Cloudflare Tunnel, eval loop |

---

## 11. VRAM Budget (RTX 4060 Ti 16GB)

| Component | VRAM | Status |
|-----------|------|--------|
| Embedding (BGE-M3) | ~2.5GB | Active |
| LLM (Qwen2.5 7B Q4) | ~5GB | Active |
| CUDA overhead | ~1GB | — |
| **Tổng** | **~8.5GB** | |
| **Còn trống** | **~7.5GB** | Headroom |
