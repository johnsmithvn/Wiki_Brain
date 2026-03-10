# PLAN — AI Knowledge OS (Master Plan)

> **Ngày tạo:** 2026-03-08
> **Cập nhật lần cuối:** 2026-03-10
> **Trạng thái:** Phase 2b DONE (T17 deferred) — Sprint 4.5 Prep + Sprint 4.6 Hardening DONE — Phase 3 NEXT

---

## 1. Tầm nhìn dự án

```
Knowledge Collector + Knowledge Vault + AI Reasoning System
```

- **Capture** kiến thức zero-friction (Telegram, browser, web UI)
- **Organize** thủ công + AI gợi ý (user luôn quyết định)
- **Retrieve** bằng keyword, semantic, graph reasoning
- **Reason** — AI tổng hợp, phân tích từ toàn bộ vault + knowledge graph

**Nguyên tắc:** Manual workflow LUÔN hoạt động. AI chỉ **augment**, không **replace**.

---

## 2. Nguyên tắc kiến trúc (Chốt)

| # | Nguyên tắc | Lý do |
|---|-----------|-------|
| 1 | **Markdown = Source of Truth** | Text-first, không vendor lock-in, AI đọc tốt |
| 2 | **AI = Layer bổ sung** | Manual workflow luôn hoạt động, AI không auto move/delete |
| 3 | **Capture = Zero friction** | Ném vào Telegram/browser → tự append inbox |
| 4 | **Schema-first** | Design entry schema từ đầu → không migrate khi thêm AI |
| 5 | **Home Server** | Ubuntu 32GB RAM + RTX 4060 Ti 16GB, local AI miễn phí |
| 6 | **Infra giản lược** | Docker Compose + Ollama + Qdrant + FastAPI. Không Prometheus/Grafana sớm |
| 7 | **Service Boundaries** | API → Service → Storage. Never reverse. Xem `docs/BACKEND-SERVICE-BOUNDARIES.md` |

---

## 3. Kiến trúc tổng thể

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
│                                                              │
│  LLM: Ollama + Qwen2.5 7B (local GPU)                       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                      MEMORY LAYER                            │
│  Short-term (conversation) │ Session (research thread)       │
│  Long-term (user insights stored in knowledge/memory/)       │
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

## 4. Data Schema (Chốt — không migrate sau này)

### 4.1 Inbox Entry Schema

File: `knowledge/inbox/YYYY-MM-DD.md`

```markdown
# Inbox — 2026-03-08

---

id: 20260308-142135
time: 14:21
source: telegram

---

bài này giải thích RAG pipeline khá rõ

https://example.com

---

id: 20260308-183022
time: 18:30
source: telegram
type: note

---

Động lực không đến từ cảm xúc nhất thời.
Nó đến từ việc hiểu rõ mục tiêu của bạn.
```

### 4.2 Entry Metadata Fields

| Field | Required | Mô tả |
|-------|----------|-------|
| `id` | Yes | `YYYYMMDD-HHmmss-mmm` (unique per entry, ms suffix) |
| `time` | Yes | `HH:mm` |
| `source` | Yes | `telegram` / `browser` / `manual` / `quick-capture` |
| `type` | No | `link` / `quote` / `note` (auto-detect, UI hint only) |
| `tags` | No | `[tag1, tag2]` (AI gợi ý sau) |
| `url` | No | URL nếu có |

### 4.3 Organized Note Schema

```markdown
---
title: Claude Reasoning Architecture
source: https://example.com
captured: 2026-03-08
tags: [ai, llm, claude]
---

## Summary
Bài viết giải thích...

## Notes
Điểm quan trọng...

## Content
[Nội dung đầy đủ]
```

### 4.4 Chunk Metadata Schema (cho Qdrant)

```json
{
  "chunk_id": "ai/rag.md#2",
  "note_path": "ai/rag.md",
  "heading": "Retrieval",
  "chunk_index": 2,
  "tags": ["ai", "rag"],
  "links": ["vector-search.md", "embedding.md"],
  "token_count": 312
}
```

**Embedding input format:**
```
Title: RAG Pipeline
Section: Retrieval

Content:
...actual chunk text...
```

---

## 5. Tech Stack

### Phase 1 (DONE ✅)
| Component | Technology |
|-----------|------------|
| Backend | FastAPI 0.115.6 |
| Search | SQLite FTS5 (porter + unicode61) |
| Frontend | Vanilla JS (ES modules) |
| Graph | D3.js |
| Markdown | marked.js |
| Watcher | watchdog 6.0.0 |
| File I/O | aiofiles |
| Tests | pytest (72 tests) |

### Phase 2 thêm
| Component | Technology |
|-----------|------------|
| Telegram Bot | python-telegram-bot 21.x |
| URL Scraper | trafilatura |
| HTTP Client | httpx |

### Phase 3 thêm
| Component | Technology |
|-----------|------------|
| Embedding | sentence-transformers + BGE-M3 |
| Vector DB | Qdrant (self-hosted) |
| Markdown AST | markdown-it-py (chunker) |

### Phase 4 thêm
| Component | Technology |
|-----------|------------|
| LLM Runtime | Ollama |
| LLM Model | Qwen2.5 7B Q4_K_M |
| Streaming | SSE (Server-Sent Events) |

### Phase 6 thêm (giản lược per chot.md)
| Component | Technology |
|-----------|------------|
| Container | Docker Compose |
| Background | asyncio.Queue + background tasks |

> **Đã bỏ:** Prometheus, Grafana, Dramatiq, Redis — quá nặng cho single-user.
> **Reranker:** Deferred — vault < 5000 notes thì vector search đủ tốt.

---

## 6. VRAM Budget (RTX 4060 Ti 16GB)

| Component | VRAM | Phase |
|-----------|------|-------|
| Embedding (BGE-M3) | ~2.5GB | 3 |
| LLM (Qwen2.5 7B Q4) | ~5GB | 4 |
| CUDA overhead | ~1GB | — |
| **Tổng** | **~8.5GB** | Phase 4 |
| **Còn trống** | **~7.5GB** | Headroom |

---

## 7. Feasibility Assessment (Code Scan)

> Đã scan toàn bộ codebase Phase 1 — **không có blocking issue nào**.

### Extension Points sẵn có

| Tính năng mới | Extension Point | Nỗ lực |
|---------------|-----------------|--------|
| Capture API | `app.include_router()` trong main.py | Thấp |
| Embedding queue | Hook vào `index_service.index_note()` | Trung bình |
| Graph expansion | `link_service.get_local_graph(path, depth)` đã có BFS | Thấp |
| Watcher → embedding | Hook vào `watcher_service._upsert_note()` | Trung bình |
| Qdrant integration | Thêm `qdrant-client`, tạo `vector_service.py` | Trung bình |
| Ollama integration | Thêm `httpx`, tạo `llm_service.py` | Trung bình |
| New frontend panels | Thêm DOM + `switchView()` case + JS module | Thấp |
| Telegram bot | `asyncio.create_task()` trong lifespan startup | Trung bình |

### Tech Debt cần fix trước Phase 2 (Sprint 2.5 — Refactor)

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | **Duplicated update pipeline** (tags→links→index) ở 4 chỗ | **High** | Extract `note_pipeline()` function |
| 2 | Sync startup blocking `_build_initial_index()` | Medium | Chuyển sang async |
| 3 | Watcher chạy sync trong watchdog thread | Medium | Offload sang async queue |
| 4 | `conftest.py` `_connection` → `_conn` typo | Low | Fix attribute name |
| 5 | Thiếu `GET /api/health` endpoint | Low | Thêm health check |
| 6 | Thiếu API integration tests | Medium | Thêm TestClient tests |

---

## 8. Phase 1: Solid Knowledge Base ✅ COMPLETE

> **43/43 tests pass. All 8 tasks verified.**

- [x] **T01:** Baseline + dependency hardening
- [x] **T02:** Template discovery API + model
- [x] **T03:** Template chooser UI + `Ctrl+N`
- [x] **T04:** File watcher + auto-reindex
- [x] **T05:** Rename propagation for `[[wiki-links]]`
- [x] **T06:** Advanced graph filter API (tags, folders, depth)
- [x] **T07:** Graph filter controls UI
- [x] **T08:** Unit tests + CI/CD (43 tests)

---

## 9. Phase 2: Refactor + Capture Layer & Inbox System

**Mục tiêu:** Fix tech debt, xây pipeline capture zero-friction
**Thời gian:** 3-4 tuần
**Design doc:** `docs/DESIGN-ingestion-pipeline.md`

### Sprint 2.5: Pre-Phase Refactor (3-5 ngày) — DONE ✅

| Task | Mô tả | INPUT → OUTPUT → VERIFY | Status |
|------|-------|------------------------|--------|
| **T09** | Extract `note_pipeline()` | INPUT: 4 nơi duplicated pipeline → OUTPUT: 1 `NotePipeline` class shared → VERIFY: 43 tests still pass | ✅ Done |
| **T10** | Async background task queue | INPUT: sync watcher → OUTPUT: `asyncio.Queue` + background worker in lifespan → VERIFY: watcher triggers async handler | ✅ Done |
| **T11** | Health check endpoint | INPUT: none → OUTPUT: `GET /api/health` → VERIFY: returns 200 | ✅ Done |
| **T12** | Fix conftest `_conn` typo | INPUT: `_connection` → OUTPUT: `_conn` → VERIFY: tests still pass | ✅ Done |
| **T12b** | Viết `BACKEND-SERVICE-BOUNDARIES.md` | INPUT: service list → OUTPUT: dependency graph + async rules + concurrency rules → VERIFY: no circular deps | ✅ Done (prev sprint) |

### Sprint 3: Capture Backend (1 tuần) — DONE ✅

| Task | Mô tả | INPUT → OUTPUT → VERIFY | Status |
|------|-------|------------------------|--------|
| **T13** | Capture API endpoint | INPUT: `POST /api/capture` body → OUTPUT: entry appended to `inbox/YYYY-MM-DD.md` → VERIFY: curl returns 201, file contains entry | ✅ Done |
| **T14** | Capture service | INPUT: raw text/URL → OUTPUT: parsed entry with id, time, source, auto-detect type + **`asyncio.Lock` per-file write** → VERIFY: unit tests, concurrent write test | ✅ Done |
| **T15** | Inbox folder config | INPUT: config → OUTPUT: `inbox` in `INDEX_EXCLUDED_FOLDERS`, auto-create dir → VERIFY: inbox notes excluded from search | ✅ Done |
| **T16** | URL scraper service | INPUT: URL → OUTPUT: title + article markdown via **`asyncio.to_thread(trafilatura)`** → VERIFY: test with real URL, confirm non-blocking | ✅ Done |

### Sprint 4: Capture Sources + Inbox UI (1-2 tuần) — IN PROGRESS

| Task | Mô tả | INPUT → OUTPUT → VERIFY | Status |
|------|-------|------------------------|--------|
| **T17** | Telegram Bot | INPUT: message on Telegram → OUTPUT: capture API called → VERIFY: message appears in inbox | ⬜ |
| **T18** | Inbox API endpoints | INPUT: `GET /api/inbox`, `GET /api/inbox/{date}`, `POST .../convert`, `DELETE`, `POST .../archive` → OUTPUT: parsed entries → VERIFY: API returns entry list | ✅ Done |
| **T19** | Inbox UI panel | INPUT: click Inbox tab → OUTPUT: entries by date, expand/collapse, preview → VERIFY: visual test | ✅ Done |
| **T20** | Inbox → Vault workflow | INPUT: click "Convert" → OUTPUT: organized note created, entry archived → VERIFY: note in vault, entry removed | ✅ Done |
| **T21** | Browser bookmarklet | INPUT: bookmarklet click → OUTPUT: URL + selected text → capture API → VERIFY: entry in inbox | ✅ Done |

**Verification checklist:**
- [x] `POST /api/capture` với text + URL → inbox entry ✅
- [ ] Telegram message → inbox entry
- [x] Inbox UI hiển thị entries, keyboard shortcuts (Enter/A/D) ✅
- [x] Convert entry → organized note with schema ✅
- [x] Bookmarklet capture thành công ✅
- [x] Test coverage cho capture_service, inbox API ✅ (27 + 2 = 29 new tests)
- [x] Quick Capture routes through `/api/capture` → inbox ✅
- [x] Scraper service integrated into capture flow ✅
- [x] Sidebar tabs: Files | Inbox | Tags ✅

---

## 9b. Sprint 4.5: Pre-Phase 3 Prep (5-6 giờ)

> **Mục tiêu:** 3 small fixes trước khi bắt đầu Phase 3 để tránh tech debt lớn.
> **Nguyên tắc:** Đừng refactor lớn. Chỉ adjust config + design cho embedding pipeline smooth.

| Task | Mô tả | INPUT → OUTPUT → VERIFY | Status |
|------|-------|------------------------|--------|
| **T17b** | Fix chunk size config | INPUT: design doc 500/350/100 → OUTPUT: 450/300/120 in `chunker_service.py` config → VERIFY: tighter embedding quality, less noise | ✅ Done (design docs updated) |
| **T17c** | Embedding debounce design | INPUT: watcher → embed on every save → OUTPUT: `EMBED_DEBOUNCE_SECONDS = 2` in watcher/embed worker → VERIFY: rapid saves batch into 1 embed call | ✅ Done (design docs + retrieval.py) |
| **T17d** | Retrieval config file | INPUT: hardcoded 0.6/0.3/0.1 weights → OUTPUT: `backend/config/retrieval.py` with `VECTOR_WEIGHT`, `GRAPH_WEIGHT`, `KEYWORD_WEIGHT` → VERIFY: tunable without code changes | ✅ Done |

**Rationale:**
- **T17b:** BGE-M3 embedding quality peaks at 250-400 token range. 450 max reduces noise.
- **T17c:** Without debounce, rapid edits spam GPU embedding queue. 2-second window batches saves.
- **T17d:** Retrieval weights will need tuning after Phase 3. Config file avoids scattered hardcoded values.

**Verification checklist:**
- [x] Chunk size params updated in design doc + code
- [x] Debounce logic documented, ready for Phase 3 implementation
- [x] Retrieval weights extractable, referenced in DESIGN docs

---

## 9c. Sprint 4.6: Code Hardening (DONE ✅)

> **Mục tiêu:** Fix all HIGH/MEDIUM issues from full code review before Phase 3.
> **Scope:** 11 fixes across backend (7) + frontend (4). No new features.
> **72/72 tests pass after all fixes.**

### Backend Fixes

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| H1 | **Capture ID collision** (same-second captures get same ID) | HIGH | Added millisecond suffix: `YYYYMMDD-HHmmss-mmm` |
| H2 | **Path traversal in inbox convert** (`folder` param unchecked) | HIGH/SECURITY | Added `.resolve()` + `.relative_to()` guard in `inbox_service.convert_entry_to_note()` |
| H3 | **Blocking sync I/O in watcher** (`read_text()` blocks event loop) | HIGH | Wrapped with `asyncio.to_thread()` in `watcher_service._worker()` |
| H4 | **Deprecated `asyncio.get_event_loop()`** | MEDIUM | Changed to `asyncio.get_running_loop()` in `watcher_service.start()` |
| H5 | **SQLite RLock blocking async** (all DB calls block event loop) | MEDIUM | Wrapped `index_note()` and `search()` with `asyncio.to_thread()` at call sites (`note_pipeline.py`, `search.py`) |
| H6 | **Scraper dead code** (unused xmltei extraction + broken metadata API) | MEDIUM | Removed xmltei call, fixed to `trafilatura.extract_metadata()` |
| H7 | **Unbounded `_recent` dict in watcher** (memory leak) | LOW | Added pruning when len > 500 |

### Frontend Fixes

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| H8 | **Inbox keyboard shortcuts fire in inputs** (type 'a'→archive, 'd'→delete) | HIGH | Added `activeElement` guard (INPUT/TEXTAREA/contentEditable check) in `app.js` |
| H9 | **11 undefined CSS variables** (`--border`, `--radius`, `--bg-secondary`) | HIGH | Mapped to actual design tokens (`--border-default`, `--radius-sm`, `--bg-hover`) in `graph-filter.css` |
| H10 | **Modal keydown handler leak** (confirm/alert handlers not cleaned on overlay click) | MEDIUM | Moved `removeEventListener` into shared `cleanup()` function in `modal.js` |
| H11 | **No delete confirmation for inbox entries** | MEDIUM | Added `showConfirm()` dialog before delete in `inbox.js` |

### Known Issues Deferred to Phase 3+

| Issue | Severity | Reason |
|-------|----------|--------|
| `escapeHtml()` duplicated in 8 files | LOW | Refactor when adding shared utils module |
| No ARIA roles / focus trap in modals | LOW | Accessibility sprint after Phase 3 |
| No upload file size limit | LOW | Add when implementing asset upload |
| No responsive layout | LOW | Desktop-first, mobile via Phase 6 tunnel |
| `include_scraped` dead param in schema | LOW | Clean up when extending scraper features |

---

## 10. Phase 3: Semantic Search Layer

**Mục tiêu:** Tìm kiếm theo ngữ nghĩa + related notes
**Thời gian:** 2-3 tuần
**Design doc:** `docs/DESIGN-chunking-retrieval.md`

### Sprint 5: Embedding Pipeline (1-2 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T22** | Chunking service | INPUT: markdown note → OUTPUT: semantic chunks (heading+paragraph, **120-450 tokens**, no overlap — paragraph boundary đủ semantic) → VERIFY: unit tests |
| **T23** | Embedding service | INPUT: chunk list → OUTPUT: vectors via BGE-M3, batch_size=32 → VERIFY: embeddings shape correct |
| **T24** | Qdrant integration | INPUT: vectors + metadata → OUTPUT: upsert to Qdrant collection → VERIFY: search returns results |
| **T25** | Incremental indexing | INPUT: file change → OUTPUT: delete old chunks + re-embed note only → VERIFY: modify 1 note, only that note re-embedded |
| **T26** | Document summary embedding | INPUT: note → OUTPUT: title+summary embedded separately → VERIFY: doc-level search works |

### Sprint 6: Hybrid Search + Related Notes (1 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T27** | Hybrid search API | INPUT: `GET /api/search?q=...&mode=hybrid` → OUTPUT: `score = 0.7*norm(vector) + 0.3*norm(keyword)` (min-max normalize trước fusion) → VERIFY: hybrid > FTS-only |
| **T28** | Related notes API | INPUT: `GET /api/notes/{path}/related` → OUTPUT: top-5 by average chunk similarity → VERIFY: meaningful |
| **T29** | Related notes UI | INPUT: open note → OUTPUT: "Related Notes" in right panel → VERIFY: click → open |
| **T30** | Search mode toggle | INPUT: UI toggle → OUTPUT: keyword / semantic / hybrid → VERIFY: different results |

**Verification checklist:**
- [ ] Toàn bộ vault chunked + embedded + Qdrant
- [ ] Semantic search trả kết quả đúng ngữ nghĩa
- [ ] Hybrid search tốt hơn single-mode
- [ ] Related notes gợi ý đúng topic
- [ ] Incremental indexing chỉ re-embed changed notes
- [ ] Doc summary embedding helps recall

---

## 11. Phase 4: RAG Chat & AI Assistant

**Mục tiêu:** Chat với vault, AI trả lời có citation
**Thời gian:** 2-3 tuần
**Design doc:** `docs/DESIGN-graph-vector-reasoning.md`

### Sprint 7: RAG Core (1-2 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T31** | Ollama integration | INPUT: prompt → OUTPUT: streaming response via Ollama API → VERIFY: stream works |
| **T32** | Graph+Vector retrieval | INPUT: query → OUTPUT: vector top-10 → extract notes → BFS 1-hop → chunk selection → VERIFY: better recall |
| **T33** | RAG pipeline | INPUT: query → OUTPUT: retrieve → context (≤2000 tokens) → prompt → generate → cite → VERIFY: answer + sources |
| **T34** | Chat API | INPUT: `POST /api/chat` → OUTPUT: SSE stream + source links → VERIFY: streaming |
| **T35** | Chat UI panel | INPUT: AI panel → OUTPUT: chat with source links → VERIFY: click source → open note |

### Sprint 8: Multi-mode AI (1 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T36** | Summary mode | INPUT: note path → OUTPUT: AI summary markdown → VERIFY: giữ ý chính |
| **T37** | Auto-link suggestion | INPUT: note save → OUTPUT: AI gợi ý `[[links]]` → VERIFY: suggestions relevant |
| **T38** | Mode selector UI | INPUT: dropdown → OUTPUT: Chat / Summary / Explore → VERIFY: each mode works |

**Verification checklist:**
- [ ] Chat trả lời đúng + citation click được
- [ ] Graph expansion cải thiện recall
- [ ] Không hallucinate
- [ ] Streaming response
- [ ] Summary đúng
- [ ] Auto-link suggestion relevant

---

## 12. Phase 5: AI Intelligence & Knowledge Insights

**Mục tiêu:** AI chủ động gợi ý, tổng hợp
**Thời gian:** 2-3 tuần
**Design doc:** `docs/DESIGN-memory-layer.md`

### Sprint 9: Research Threads + Memory (1-2 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T39** | Research thread system | INPUT: create thread → OUTPUT: track notes + questions + concepts → VERIFY: persisted |
| **T40** | Session memory | INPUT: chat → OUTPUT: AI remembers within session → VERIFY: follow-up works |
| **T41** | Long-term memory | INPUT: AI insights → OUTPUT: `knowledge/memory/` notes → VERIFY: AI recalls |
| **T42** | Research threads UI | INPUT: sidebar → OUTPUT: thread list, click → filtered view → VERIFY: visual |

### Sprint 10: Knowledge Insights (1 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T43** | Weekly synthesis | INPUT: trigger → OUTPUT: weekly summary note → VERIFY: note with links |
| **T44** | Topic clustering | INPUT: vault → OUTPUT: cluster on graph (color-coded) → VERIFY: meaningful |
| **T45** | Low-connected notes | INPUT: graph → OUTPUT: orphaned notes highlighted → VERIFY: accurate |

**Verification checklist:**
- [ ] Research thread track notes + questions
- [ ] Memory persists across sessions
- [ ] Weekly synthesis có ý nghĩa
- [ ] Topic clustering trên graph
- [ ] Low-connected notes detection accurate

---

## 13. Phase 6: Infrastructure & Deploy

**Mục tiêu:** Docker deploy, eval, cache
**Thời gian:** 1-2 tuần

### Sprint 11: Deploy (1-2 tuần)

| Task | Mô tả | INPUT → OUTPUT → VERIFY |
|------|-------|------------------------|
| **T46** | Docker Compose | INPUT: yml → OUTPUT: FastAPI + Qdrant + Ollama → VERIFY: `docker compose up` |
| **T47** | Cloudflare Tunnel | INPUT: config → OUTPUT: HTTPS external → VERIFY: phone access |
| **T48** | RAG eval loop | INPUT: questions.json → OUTPUT: relevance scores → VERIFY: logged |
| **T49** | Cache strategy | INPUT: repeated queries → OUTPUT: LRU cache → VERIFY: faster repeat |

---

## 14. Dependency Graph

```
Phase 1 (DONE ✅)
    │
    ▼
Sprint 2.5: Refactor (T09-T12) ← DONE ✅
    │
    ▼
Sprint 3: Capture Backend (T13-T16) ← DONE ✅
    │
    ▼
Sprint 4: Sources + Inbox UI (T17-T21) ← 4/5 DONE (T17 Telegram deferred)
    │
    ▼
Sprint 4.5: Pre-Phase 3 Prep (T17b-T17d) ← DONE ✅
    │
    ▼
Sprint 4.6: Code Hardening (H1-H11) ← DONE ✅ (11 fixes, 72 tests)
    │
    ▼
Phase 3: Semantic Search (T22-T30) ← NEXT
    │
    ▼
Phase 4: RAG Chat (T31-T38)
    │
    ├────────────────────┐
    ▼                    ▼
Phase 5 (T39-T45)    Phase 6 (T46-T49)
```

---

## 15. Sprint Timeline

| Sprint | Phase | Nội dung | Thời gian |
|--------|-------|----------|-----------|
| 1-2 | Phase 1 | Solid Knowledge Base | **DONE** ✅ |
| 2.5 | Refactor | Pipeline + async queue | **DONE** ✅ |
| 3 | Phase 2a | Capture API + Scraper | **DONE** ✅ |
| 4 | Phase 2b | Telegram + Inbox UI | **4/5 DONE** (T17 deferred) |
| 4.5 | Pre-Phase 3 | Chunk config + Debounce + Retrieval config | **DONE** ✅ |
| 4.6 | Hardening | 11 bug/security fixes from code review | **DONE** ✅ |
| 5 | Phase 3a | Chunking + Embedding + Qdrant | 1-2 tuần |
| 6 | Phase 3b | Hybrid Search + Related Notes | 1 tuần |
| 7 | Phase 4a | Ollama + Graph+Vector RAG | 1-2 tuần |
| 8 | Phase 4b | Summary + Auto-link + Modes | 1 tuần |
| 9 | Phase 5a | Research Threads + Memory | 1-2 tuần |
| 10 | Phase 5b | Clustering + Insights | 1 tuần |
| 11 | Phase 6 | Docker + Tunnel + Eval | 1-2 tuần |

**Tổng: ~13-16 tuần. Solo evenings/weekends: ~4-6 tháng.**

---

## 16. Anti-scope

- ❌ Notion clone (database views, kanban)
- ❌ Multi-user / collaborative editing
- ❌ Mobile native app
- ❌ Cloud deploy phức tạp
- ❌ Prometheus/Grafana (quá sớm)
- ❌ Reranker (vault < 5000 notes)
- ❌ AI auto-organize
- ❌ Tag suggestion (thay bằng auto-link)

---

## 17. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Capture spam inbox | Daily rotate, limit entry size |
| URL scraping fail | Fallback: lưu URL + user context |
| Embedding OOM | Batch 32, CPU fallback |
| LLM hallucinate | Strict RAG prompt + citation |
| Watcher + embedding race | Async queue sequential |
| Feature creep | Verify phase trước khi mở phase mới |
| Graph expansion noisy | depth=1, max_neighbors=5 |
| **Concurrent inbox write** | **`asyncio.Lock()` per-file** (không lock global) |
| **trafilatura block event loop** | **`asyncio.to_thread()` cho CPU-heavy sync calls** |
| **Circular service deps** | **Xem `BACKEND-SERVICE-BOUNDARIES.md`** |
| **Watcher re-embed mỗi keystroke** | **Debounce 2s** cho embedding queue (note_pipeline vẫn 500ms) |
| **Embedding model cold start** | **Warm model on startup** (`embedding_service.load_model()` in lifespan) |

---

## 18. Design Documents

| Document | Mô tả | Phase |
|----------|-------|-------|
| `docs/DESIGN-ingestion-pipeline.md` | Capture → Inbox → Vault pipeline | 2 |
| `docs/DESIGN-chunking-retrieval.md` | Chunking + Hybrid search + RAG prompt | 3 |
| `docs/DESIGN-graph-vector-reasoning.md` | Graph expansion + Hybrid reasoning | 4 |
| `docs/DESIGN-ui-layout.md` | 4-panel layout, wireframes | 2-4 |
| `docs/DESIGN-memory-layer.md` | Memory + Research threads | 5 |
| `docs/BACKEND-SERVICE-BOUNDARIES.md` | Dependency graph, async rules, concurrency | Pre-Phase 2 |

---

## 19. Tóm tắt quyết định

```
✅ Markdown = source of truth
✅ Capture = append markdown entry → zero friction
✅ Schema chốt từ đầu → không migrate
✅ AI = augment, manual luôn hoạt động
✅ Home server (Ubuntu + RTX 4060 Ti)
✅ Qdrant vector search (self-hosted)
✅ Ollama + Qwen2.5 RAG (local, tiếng Việt)
✅ Graph + Vector hybrid reasoning
✅ Hybrid search: 0.7v + 0.3k weighted fusion (configurable via retrieval config)
✅ Chunk: heading + paragraph, 120-450 tokens (tighter range for BGE-M3)
✅ Embedding debounce: 2s window to batch rapid saves
✅ Bỏ reranker, bỏ Prometheus (quá sớm)
✅ Auto-link suggestion thay tag suggestion
✅ Service boundaries: API → Service → Storage, never reverse
✅ asyncio.Lock() per-file cho inbox concurrent write
✅ asyncio.to_thread() cho CPU-heavy sync (trafilatura, embedding)
✅ Inbox type = UI hint only (link/quote/note), AI đọc content
✅ Low-connected notes thay knowledge gap detection
✅ Infra: Docker Compose only
```
