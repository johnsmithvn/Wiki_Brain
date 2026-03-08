# Changelog

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
