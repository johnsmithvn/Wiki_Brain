# Changelog

## v0.6.2 (2026-03-10) — Sprint 4.6: Code Hardening

### Security
- **Path traversal fix**: `inbox_service.convert_entry_to_note()` now validates `folder` param with `.resolve()` + `.relative_to()` guard

### Bug Fixes — Backend
- **Capture ID collision**: Added millisecond suffix (`YYYYMMDD-HHmmss-mmm`) to prevent same-second duplicates
- **Blocking I/O in watcher**: `read_text()` wrapped with `asyncio.to_thread()` to avoid stalling event loop
- **Deprecated API**: `asyncio.get_event_loop()` → `asyncio.get_running_loop()` in watcher startup
- **SQLite blocking async**: `index_note()` and `search()` now wrapped with `asyncio.to_thread()` at call sites
- **Scraper dead code**: Removed unused `xmltei` extraction, fixed metadata API to `trafilatura.extract_metadata()`
- **Unbounded `_recent` dict**: Watcher debounce map now pruned when exceeding 500 entries

### Bug Fixes — Frontend
- **Inbox keyboard guard**: Shortcuts (a/d/Enter) no longer fire when user is typing in inputs/textareas
- **CSS undefined variables**: Fixed 11 broken references in `graph-filter.css` (`--border` → `--border-default`, `--radius` → `--radius-sm`, `--bg-secondary` → `--bg-hover`)
- **Modal keydown leak**: Confirm/alert handlers now properly cleaned up on overlay click via shared `cleanup()`
- **Delete confirmation**: Inbox delete now shows `showConfirm()` danger dialog before proceeding

### Tests
- 72/72 tests passing (updated ID length assertion for new millisecond format)

## v0.6.1 (2026-03-10) — Pre-Phase 3 Documentation Prep

### Updated Design Docs
- **PLAN**: Added Sprint 4.5 (T17b/T17c/T17d) — 3 prep tasks before Phase 3
- **DESIGN-chunking-retrieval.md**: Chunk sizes 500/350/100 → 450/300/120, added §5.4 Embedding Debounce (2s window), hybrid search weights now reference config
- **DESIGN-graph-vector-reasoning.md**: Retrieval weights reference `backend/config/retrieval.py` instead of hardcoded 0.6/0.3/0.1, added §14 Retrieval Config section
- **DESIGN-ingestion-pipeline.md**: Pipeline flow updated with debounced embed step
- **ARCHITECTURE.md**: Added “Upcoming Phase 3” section with new services + design decisions

### Rationale
- Tighter chunk sizes (450 max) improve BGE-M3 embedding quality
- 2s embedding debounce prevents GPU queue spam on rapid edits
- Extractable retrieval weights allow post-Phase 3 tuning without code scatter

## v0.6.0 (2026-03-10) — Sprint 4 (Phase 2b: Inbox UI + Capture Sources)

### Added — Sprint 4: Inbox UI & Capture Sources
- **Inbox UI panel** (`inbox.js` + `inbox.css`): Full sidebar tab with date-grouped entries, expand/collapse, entry selection, keyboard navigation (↑/↓/Enter/A/D)
- **Sidebar Tabs**: Restructured sidebar with Files | Inbox | Tags tab system, switchable via click or `Alt+I` for inbox
- **Convert Dialog**: Modal for converting inbox entry to vault note — title, folder, tags fields with content preview
- **Browser Bookmarklet** (`bookmarklet.html`): Self-hosted setup page with drag-to-bookmarks-bar installation, captures URL + page title + selected text to inbox
- **Inbox API client**: `api.js` methods for `capture()`, `getInboxDates()`, `getInboxEntries()`, `convertEntry()`, `deleteEntry()`, `archiveEntry()`
- **Scraper integration**: `capture_service.py` now calls `scraper_service.scrape_url()` for link-type captures, enriching entry content with article text (non-blocking, failure-safe)

### Changed
- **Quick Capture → Inbox**: `quick-capture.js` now routes through `POST /api/capture` instead of directly appending to daily note. All captures land in inbox for review
- **Keyboard Shortcuts**: Updated shortcuts modal with inbox-specific shortcuts (Alt+I, Enter, A, D, ↑/↓)
- `index.html` restructured sidebar DOM to support tab navigation

### Architecture Improvements
- Scraper service no longer dead code — integrated into capture pipeline
- Quick Capture aligned with Capture API → unified inbox funnel

## v0.5.0 (2026-03-09) — Sprint 2.5 + Sprint 3 (Phase 2a)

### Added — Sprint 2.5: Refactor
- **Note Pipeline** (`note_pipeline.py`): Single orchestrator for tags → links → index, eliminates 5 duplicated call sites
- **Async Watcher Queue**: Watcher events now bridge from watchdog sync thread → `asyncio.Queue` → async worker calling `note_pipeline`
- **Health Endpoint**: `GET /api/health` returns service readiness (`index`, `links`, `watcher`)
- **Fix**: `conftest.py` typo `_connection` → `_conn` (was silently failing cleanup)

### Added — Sprint 3: Capture Backend
- **Capture API**: `POST /api/capture` — zero-friction endpoint for text/URL capture from any source
- **Capture Service** (`capture_service.py`): Entry creation, type auto-detection (link/quote/note), per-file `asyncio.Lock` for concurrent writes
- **Inbox Service** (`inbox_service.py`): State-machine parser for inbox markdown, entry CRUD, convert-to-note with slug generation
- **Inbox API**: `GET /api/inbox` (dates), `GET /api/inbox/{date}` (entries), `POST .../convert`, `DELETE`, `POST .../archive`
- **Scraper Service** (`scraper_service.py`): `httpx` async fetch + `trafilatura` content extraction via `asyncio.to_thread()`
- **Schemas**: `CaptureRequest`, `CaptureResponse`, `InboxEntry`, `InboxDateSummary`, `ConvertRequest`, `ScrapedArticle`
- **Inbox Exclusion**: `inbox` folder added to `INDEX_EXCLUDED_FOLDERS` — inbox entries don't pollute FTS search
- **Auto-create `inbox/` dir** on startup via `ensure_dirs()`

### Changed
- `notes.py`, `daily.py`, `rename_service.py` refactored to use `note_pipeline` (removed 15+ duplicated lines)
- `watcher_service.py` fully rewritten with async queue architecture
- `requirements.txt` updated with `httpx==0.28.1`, `trafilatura==2.0.0`

### Tests
- **72 tests** total (43 original + 29 new)
- New: `test_capture_inbox.py` — 27 tests for capture, inbox parsing, slugify, convert
- New: `test_note_pipeline.py` — 2 tests for process_note and remove_note

## v0.4.0 (2026-03-08) — Phase 1 Complete

### Added
- **Rename Link Propagation**: Renaming a note auto-updates all `[[wiki-links]]` across the vault
- **Graph Filter API**: `GET /api/graph?tags=X&folders=Y&depth=N` filters graph nodes by tags, folders, and hop depth
- **Graph Filter UI**: Interactive filter panel with tag chips, folder dropdown, depth slider, and Apply/Reset
- **Unit Test Suite**: 43 pytest tests covering `file_service`, `link_service`, `tag_service`, `rename_service`
- **CI/CD Pipeline**: GitHub Actions workflow with Ruff lint + pytest on push/PR to main

### Changed
- `graph.js` rewritten to support filter state management and dynamic panel reconstruction
- `api.js` `getGraph()` now accepts filter params object

## v0.3.2 (2026-03-08)

### Fixed
- Clicking `#tag` in note preview now runs tag-aware search in command palette instead of FTS-only query

## v0.3.1 (2026-03-08)

### Added
- Sidebar keyboard shortcuts help popup (table format) via topbar button and `Alt+/`
- Inline rename directly in sidebar for files and folders (double-click label, `Enter` save, `Esc` cancel)

### Fixed
- Right-click on blank space under file list now opens context menu
- Quick add folder/file now supports immediate inline rename flow without prompt modal

## v0.3.0 (2026-03-08)

### Added
- **Template Notes** with `GET /api/templates` and `GET /api/templates/{path}` sourced from `knowledge/template/`
- **Template Create Modal** for New Note flow with `Ctrl+N` shortcut and Blank template option
- **Note Metadata Endpoint** `GET /api/notes/{path}/meta` for lightweight change detection
- **Filesystem Watcher** (watchdog) for incremental reindex on external create/modify/delete/move changes
- **External Change Sync** in UI: auto-reload open note when clean, conflict toast when unsaved edits exist

### Changed
- New Note button now opens the template flow (Alt+N kept as alias)
- Template files are excluded from note tree indexing/search/graph pipelines
- `POST /api/notes` now returns `409` if a note path already exists instead of overwriting

## v0.2.1 (2026-03-08)

### Fixed
- `[object PointerEvent]` phantom folder creation bug and removed corrupted folder from disk
- Fixed browser caching of static `.js` files by adding `Cache-Control` middleware
- Fixed `ReferenceError: escapeHtml is not defined` that was crashing note opening
- Fixed broad `try...catch` silencing UI rendering errors in `app.js`

## v0.2.0 (2026-03-08)

### Added
- **Daily Notes** — Auto-create today's note (`daily/YYYY-MM-DD.md`) with `Alt+D`
- **Quick Capture** — `Ctrl+Shift+N` popup appends ideas to daily note
- **Editor Toolbar** — Bold, Italic, Code, Heading, Quote, HR, Lists, Checkbox, Link, Image
- **Drag & Drop** — Drag notes in sidebar to reorganize into folders
- **Slash Commands** — Type `/` in editor: todo, code, callout, table, heading, divider, quote, image, link
- **Image Paste** — `Ctrl+V` clipboard images uploaded to `_assets/` and inserted as markdown
- **Tag Explorer** — Click tag in sidebar to see notes inline with expand/collapse
- **Note Metadata** — Right panel shows created, modified, words, chars, tags, links, backlinks
- **Command Palette Upgrade** — Recent notes on open, `/` prefix for commands
- **Assets API** — Image upload endpoint with unique filenames

## v0.1.1 (2026-03-08)

### Fixed
- TOC click now scrolls to correct heading position (custom `marked` heading ID renderer)
- Keyboard shortcuts no longer conflict with Chrome (changed from `Ctrl` to `Alt` for N/B/E/G)
- Tags overflow — shows max 3 rows (~9 tags) with `+N more` expand/collapse
- Fixed `[object PointerEvent]` folder creation bug when clicking New Note button

### Changed
- Replaced all native `prompt()` and `confirm()` dialogs with custom popup modals
- Added proper `.gitignore` for Python/IDE/OS/application data

## v0.1.0 (2026-03-08)

### Added
- FastAPI backend with file-based markdown storage
- SQLite FTS5 full-text search with porter tokenizer
- Bi-directional `[[wiki-link]]` parsing and resolution
- Tag extraction from YAML frontmatter and inline `#tags`
- Graph view with D3.js force-directed visualization
- Markdown editor with Tab key support and auto-save
- Markdown preview with wiki-link and tag rendering
- Split view (editor + preview side-by-side)
- Sidebar file tree with folder toggle and context menus
- Backlinks panel in right sidebar
- Auto-generated Table of Contents from headings
- Dark theme (charcoal + amber/gold accent)
- Command palette search (Ctrl+K)
- Keyboard shortcuts (Ctrl+N/S/E/G/B)
- Toast notifications for user feedback
- Status bar with word/char count and save status
- Welcome note auto-created on first run
