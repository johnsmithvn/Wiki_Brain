# Backend Service Boundaries

> **Mục đích:** Định nghĩa dependency giữa services — tránh circular import, spaghetti code.
> **Rule:** API → Service → Lower Service → Storage. **Never reverse.**

---

## 1. Dependency Graph

```
API Layer (FastAPI routers)
│
├── capture.py      → capture_service, scraper_service
├── inbox.py        → inbox_service, capture_service
├── chat.py         → rag_service
├── threads.py      → thread_service, rag_service
├── notes.py        → file_service, note_pipeline
├── search.py       → index_service, vector_service
├── graph.py        → link_service
├── tags.py         → tag_service
├── daily.py        → file_service
├── templates.py    → template_service
├── assets.py       → file_service
│
▼
Service Layer
│
├─── Capture Group ──────────────────────
│    capture_service   → file I/O (aiofiles)
│    scraper_service   → httpx, trafilatura
│    inbox_service     → file I/O (aiofiles)
│
├─── Pipeline (orchestrator) ────────────
│    note_pipeline     → tag_service
│                      → link_service
│                      → index_service
│                      → embedding_service (Phase 3)
│
├─── Embedding Group ────────────────────
│    chunker_service   → markdown-it-py (pure function)
│    embedding_service → sentence-transformers (BGE-M3)
│    vector_service    → qdrant-client
│
├─── AI Group ───────────────────────────
│    rag_service       → vector_service
│                      → index_service
│                      → link_service (graph expansion)
│                      → embedding_service (embed query)
│                      → llm_service
│    llm_service       → httpx (Ollama API)
│
├─── Memory Group ───────────────────────
│    memory_service    → RAM (dict)
│    thread_service    → file I/O (JSON)
│
├─── Core Group (Phase 1) ──────────────
│    file_service      → aiofiles, pathlib
│    index_service     → sqlite3
│    link_service      → RAM (dict)
│    tag_service       → regex
│    template_service  → file_service
│    rename_service    → file_service, link_service
│    watcher_service   → watchdog, note_pipeline
│
▼
Storage Layer
│
├── Markdown vault     (knowledge/**/*.md)
├── SQLite FTS5        (in-memory, rebuilt on startup)
├── Qdrant             (localhost:6333)
└── JSON files         (knowledge/memory/threads/*.json)
```

---

## 2. Forbidden Dependencies (❌)

| From | To | Lý do |
|------|----|-------|
| `vector_service` | `rag_service` | Circular: rag→vector→rag |
| `embedding_service` | `rag_service` | Circular: rag→embedding→rag |
| `index_service` | `link_service` | Parallel services, no dependency |
| `llm_service` | `rag_service` | LLM is a leaf service, rag calls it |
| `chunker_service` | `embedding_service` | Chunker is pure function, no side effects |
| Any service | API layer | Services never import from `api/` |
| `file_service` | `index_service` | file_service is lower-level than index_service |

---

## 3. Allowed Call Direction

```
capture.py ──→ capture_service ──→ file I/O        ✅
chat.py    ──→ rag_service ──→ vector_service       ✅
chat.py    ──→ rag_service ──→ llm_service          ✅
notes.py   ──→ note_pipeline ──→ tag_service        ✅
notes.py   ──→ note_pipeline ──→ index_service      ✅

rag_service ──→ capture_service                     ❌ WRONG
vector_service ──→ rag_service                      ❌ CIRCULAR
llm_service ──→ vector_service                      ❌ WRONG LEVEL
```

---

## 4. Service Contracts (Interface)

### 4.1 Pure Functions (no state, no I/O)

```
chunker_service.chunk_note(markdown: str) → list[Chunk]
tag_service.extract_tags(content: str) → list[str]
```

### 4.2 Stateful Services (singleton, in-memory state)

```
link_service     → _forward: dict, _backward: dict
index_service    → _conn: sqlite3.Connection
memory_service   → _conversations: dict
```

### 4.3 I/O Services (external system)

```
file_service       → filesystem
vector_service     → Qdrant HTTP
embedding_service  → GPU / sentence-transformers
llm_service        → Ollama HTTP
scraper_service    → httpx → external URLs
```

### 4.4 Orchestrators (coordinate multiple services)

```
note_pipeline    → tags + links + index + embed
rag_service      → vector + graph + keyword + LLM
watcher_service  → detect change → note_pipeline
```

---

## 5. Initialization Order

```python
# backend/main.py lifespan()

# 1. Core (no dependencies)
file_service.init()
tag_service.init()

# 2. Index + Links (depend on file_service)
index_service.build_initial_index()
link_service.build_initial_index()

# 3. Watcher (depends on note_pipeline)
watcher_service.start()

# 4. Vector (depend on Qdrant connection)    — Phase 3
vector_service.init()

# 5. Embedding (depend on model load)        — Phase 3
embedding_service.load_model()

# 5b. Warm embedding model — tránh cold-start latency trên query đầu tiên
embedding_service.embed_query("warmup")

# 6. LLM health check                        — Phase 4
llm_service.check_ollama()

# 6b. Health endpoint — expose readiness for all services
# GET /api/health → {index: ok, vector: ok, llm: ok, ...}

# 7. Telegram bot                             — Phase 2
asyncio.create_task(telegram_bot.start())
```

---

## 6. Async Rules

| Service | sync / async | Lý do |
|---------|-------------|-------|
| `file_service` | **async** | filesystem I/O |
| `capture_service` | **async** | file write + lock |
| `scraper_service` | **async** | httpx + `to_thread(trafilatura)` |
| `index_service` | **sync** (RLock) | sqlite3 not async-safe |
| `link_service` | **sync** | in-memory dict, fast |
| `tag_service` | **sync** | regex, pure function |
| `chunker_service` | **sync** | pure function |
| `embedding_service` | **async** | `to_thread(model.encode)` — CPU heavy |
| `vector_service` | **async** | qdrant HTTP |
| `rag_service` | **async** | orchestrates async services |
| `llm_service` | **async** | httpx streaming |
| `thread_service` | **sync** | JSON file read/write (small) |
| `note_pipeline` | **async** | calls file_service + index_service |

---

## 7. Concurrency Rules

### 7.1 Inbox File Lock (per-file)

```python
from asyncio import Lock
from collections import defaultdict

_inbox_locks: dict[str, Lock] = defaultdict(Lock)

async def append_to_inbox(entry: InboxEntry):
    file_path = get_inbox_file(entry.date)
    async with _inbox_locks[str(file_path)]:
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(format_entry(entry))
```

### 7.2 Embedding Queue (sequential per note)

```python
_embed_queue: asyncio.Queue[str] = asyncio.Queue()

# Worker processes one at a time
async def embed_worker():
    while True:
        note_path = await _embed_queue.get()
        await re_embed_note(note_path)
        _embed_queue.task_done()
```

### 7.3 Watcher Debounce

```python
# watcher_service phải debounce trước khi gọi note_pipeline
# Editor ghi nhiều lần mỗi giây → không re-embed mỗi keystroke

import asyncio
from collections import defaultdict

_pending: dict[str, asyncio.TimerHandle] = {}
DEBOUNCE_MS = 800  # chờ 800ms sau lần save cuối mới xử lý

def on_file_changed(path: str):
    if path in _pending:
        _pending[path].cancel()
    loop = asyncio.get_event_loop()
    _pending[path] = loop.call_later(
        DEBOUNCE_MS / 1000,
        lambda p=path: asyncio.create_task(_process(p)),
    )

async def _process(path: str):
    _pending.pop(path, None)
    await note_pipeline.process(path)
```

### 7.4 Index RLock (existing)

```python
# index_service already uses threading.RLock
# Safe for concurrent reads, exclusive writes
```

---

## 8. Testing Boundaries

| Test file | Tests what | Mocks what |
|-----------|-----------|------------|
| `test_capture_service.py` | entry creation, append | file I/O |
| `test_scraper_service.py` | URL fetch, extract | httpx responses |
| `test_chunker_service.py` | chunk splitting | nothing (pure) |
| `test_rag_service.py` | retrieval pipeline | vector_service, llm_service |
| `test_note_pipeline.py` | orchestration | all sub-services |

---

## Checklist trước khi code mỗi service mới

- [ ] Service nằm đúng group trong dependency graph?
- [ ] Không import ngược lên API layer?
- [ ] Không tạo circular dependency?
- [ ] sync hay async đúng theo bảng trên?
- [ ] Có test riêng với mock đúng boundary?
