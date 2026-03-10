# DESIGN — Memory Layer

> **Phase:** 5 (Polish & Advanced Features)
> **Depends on:** Phase 4 (RAG Chat operational)
> **Files affected:** `memory_service.py`, `thread_service.py`, `chat.py`

---

## 1. Tổng quan

AI của hệ thống cần 3 loại memory:

```
┌────────────────────────────────────────────┐
│              Memory Architecture            │
├──────────┬──────────────┬──────────────────┤
│ Short    │ Session      │ Long-term         │
│ (chat)   │ (thread)     │ (notes)           │
├──────────┼──────────────┼──────────────────┤
│ Last 10  │ Per thread   │ knowledge/memory/ │
│ messages │ conversation │ permanent notes   │
│          │ + explored   │                   │
│ RAM only │ notes list   │ Markdown files    │
│          │              │ indexed + embedded│
│ Expires  │ JSON file    │ Never expires     │
│ on close │ per thread   │                   │
└──────────┴──────────────┴──────────────────┘
```

---

## 2. Short-term Memory

### 2.1 Định nghĩa

Conversation context trong 1 chat session. Giữ last 10 messages.

### 2.2 Implementation

```python
# backend/services/memory_service.py

from collections import defaultdict

class ShortTermMemory:
    """In-memory conversation history. Lost on restart."""

    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages
        self._conversations: dict[str, list[dict]] = defaultdict(list)

    def add_message(self, conversation_id: str, role: str, content: str):
        messages = self._conversations[conversation_id]
        messages.append({"role": role, "content": content})
        # Trim old messages
        if len(messages) > self.max_messages:
            self._conversations[conversation_id] = messages[-self.max_messages:]

    def get_history(self, conversation_id: str) -> list[dict]:
        return self._conversations[conversation_id]

    def get_context_string(self, conversation_id: str) -> str:
        messages = self.get_history(conversation_id)
        return "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in messages
        )

    def clear(self, conversation_id: str):
        self._conversations.pop(conversation_id, None)
```

### 2.3 Tích hợp vào RAG

```python
async def chat_with_memory(conversation_id: str, question: str):
    # 1. Get chat history
    history = short_term.get_context_string(conversation_id)

    # 2. Retrieve context (use question + history for better retrieval)
    enhanced_query = f"{history}\n{question}" if history else question
    context = await rag_service.retrieve_context(enhanced_query)

    # 3. Build prompt with history
    system = SYSTEM_PROMPT.format(
        context=build_context(context.chunks),
        history=history,
    )

    # 4. Generate
    full_response = ""
    async for token in llm_service.generate_stream(system, question):
        yield token
        full_response += token

    # 5. Save to memory
    short_term.add_message(conversation_id, "user", question)
    short_term.add_message(conversation_id, "assistant", full_response)
```

### 2.4 Prompt với History

```python
SYSTEM_PROMPT = """You are answering questions using the user's personal knowledge vault.

Previous conversation:
{history}

Available sources:
{context}

RULES:
1. Only use information from the provided sources
2. Cite source notes
3. Reference previous conversation when relevant
4. Answer in the same language as the question"""
```

---

## 3. Session Memory (Research Threads)

### 3.1 Định nghĩa

Một "research thread" = topic-focused conversation + explored notes. Persist giữa sessions.

**Use case:**
1. Bạn đang research "RAG Pipeline" trong 3 ngày
2. Mỗi lần mở lại, AI nhớ context trước
3. Notes đã explore, insights extracted, questions asked

### 3.2 Thread Data Model

```python
@dataclass
class ResearchThread:
    id: str                    # uuid4
    topic: str                 # "RAG Pipeline Design"
    created_at: str            # ISO datetime
    updated_at: str            # ISO datetime
    messages: list[dict]       # full conversation history
    explored_notes: list[str]  # note paths explored
    key_insights: list[str]    # extracted insights
    status: str                # "active" | "archived"
```

### 3.3 Storage

Lưu dạng JSON file, KHÔNG lưu database.

```
knowledge/memory/threads/
  {thread_id}.json
```

**Mỗi thread = 1 JSON file:**

```json
{
  "id": "a1b2c3d4",
  "topic": "RAG Pipeline Design",
  "created_at": "2026-03-08T14:00:00",
  "updated_at": "2026-03-08T18:30:00",
  "messages": [
    {"role": "user", "content": "How does RAG work?", "timestamp": "..."},
    {"role": "assistant", "content": "RAG gồm 3 bước...", "timestamp": "..."}
  ],
  "explored_notes": [
    "ai/rag.md",
    "ai/vector-search.md",
    "ai/chunking.md"
  ],
  "key_insights": [
    "Hybrid search > pure vector for personal vault",
    "Graph expansion adds related context"
  ],
  "status": "active"
}
```

### 3.4 Thread Service

```python
# backend/services/thread_service.py

import json
import threading
from pathlib import Path
from collections import defaultdict

class ThreadService:
    def __init__(self, memory_dir: Path):
        self.threads_dir = memory_dir / "threads"
        self.threads_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def create_thread(self, topic: str) -> ResearchThread:
        thread = ResearchThread(
            id=str(uuid4())[:8],
            topic=topic,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            messages=[],
            explored_notes=[],
            key_insights=[],
            status="active",
        )
        self._save(thread)
        return thread

    def get_thread(self, thread_id: str) -> ResearchThread | None:
        path = self.threads_dir / f"{thread_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ResearchThread(**data)

    def list_threads(self, status: str = "active") -> list[ResearchThread]:
        threads = []
        for path in self.threads_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") == status:
                threads.append(ResearchThread(**data))
        return sorted(threads, key=lambda t: t.updated_at, reverse=True)

    def add_message(self, thread_id: str, role: str, content: str):
        with self._locks[thread_id]:  # per-thread lock
            thread = self.get_thread(thread_id)
            if not thread:
                return
            thread.messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            thread.updated_at = datetime.now().isoformat()
            self._save(thread)

    def add_explored_note(self, thread_id: str, note_path: str):
        thread = self.get_thread(thread_id)
        if not thread:
            return
        if note_path not in thread.explored_notes:
            thread.explored_notes.append(note_path)
            self._save(thread)

    def archive_thread(self, thread_id: str):
        thread = self.get_thread(thread_id)
        if thread:
            thread.status = "archived"
            self._save(thread)

    def _save(self, thread: ResearchThread):
        """Atomic write: temp file + rename to prevent corruption.
        Per-thread lock prevents concurrent overwrite."""
        path = self.threads_dir / f"{thread.id}.json"
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(asdict(thread), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)  # atomic on same filesystem
```

### 3.5 Thread API

```python
# backend/api/threads.py

@router.get("/threads")
async def list_threads():
    return thread_service.list_threads()

@router.post("/threads")
async def create_thread(body: CreateThreadRequest):
    thread = thread_service.create_thread(body.topic)
    return thread

@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    return thread_service.get_thread(thread_id)

@router.post("/threads/{thread_id}/chat")
async def chat_in_thread(thread_id: str, body: ChatRequest):
    """RAG chat within a research thread context."""
    thread = thread_service.get_thread(thread_id)

    # Build context from thread history + RAG
    thread_context = "\n".join(
        f"{m['role']}: {m['content']}" for m in thread.messages[-10:]
    )

    enhanced_query = f"{thread_context}\n{body.question}"
    rag_context = await rag_service.retrieve_context(enhanced_query)

    # Track explored notes
    for chunk, _ in rag_context.chunks:
        thread_service.add_explored_note(thread_id, chunk.payload["note_path"])

    # Generate response + save
    ...

@router.post("/threads/{thread_id}/export")
async def export_thread(thread_id: str):
    """Export thread to a permanent note."""
    thread = thread_service.get_thread(thread_id)
    note = generate_thread_note(thread)
    # Save to knowledge/research/{topic-slug}.md
    ...
```

---

## 4. Long-term Memory

### 4.1 Định nghĩa

Permanent knowledge, lưu dạng markdown files trong vault. AI có thể đọc VÀ ghi.

```
knowledge/memory/
  preferences.md        # User preferences learned by AI
  patterns.md           # Patterns AI noticed
  vocabulary.md         # Key terms used frequently
```

### 4.2 Memory Note Format

```markdown
---
title: AI Memory — Preferences
type: memory
updated: 2026-03-08
---

## Communication Preferences
- User prefers Vietnamese for documentation
- User likes code examples in all explanations
- User prefers practical over theoretical

## Topic Interests
- RAG and retrieval systems
- Personal knowledge management
- Python backend architecture

## Writing Style
- Uses informal tone
- Frequently references chot.md design docs
```

### 4.3 Memory Write (AI can append)

```python
async def save_to_long_term(category: str, content: str):
    """AI can save learned preferences/patterns to memory notes."""
    memory_dir = settings.KNOWLEDGE_DIR / "memory"
    memory_dir.mkdir(exist_ok=True)

    file_path = memory_dir / f"{category}.md"

    if file_path.exists():
        existing = file_path.read_text(encoding="utf-8")
        # Append new content
        updated = existing + f"\n\n## {datetime.now().strftime('%Y-%m-%d')}\n{content}"
        file_path.write_text(updated, encoding="utf-8")
    else:
        # Create new memory note
        note = f"---\ntitle: AI Memory — {category.title()}\ntype: memory\nupdated: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n{content}"
        file_path.write_text(note, encoding="utf-8")
```

### 4.4 Memory Read (trong RAG prompt)

```python
async def get_long_term_context() -> str:
    """Load memory notes for system prompt."""
    memory_dir = settings.KNOWLEDGE_DIR / "memory"
    if not memory_dir.exists():
        return ""

    context = ""
    for md_file in memory_dir.glob("*.md"):
        if md_file.stat().st_size < 5000:  # limit
            context += f"\n[Memory: {md_file.stem}]\n"
            context += md_file.read_text(encoding="utf-8")[:1000]
            context += "\n"

    return context
```

### 4.5 Tích hợp vào System Prompt

```python
SYSTEM_PROMPT = """You are answering questions using the user's personal knowledge vault.

Your memory (preferences, patterns you've learned):
{long_term_memory}

Previous conversation:
{history}

Available sources:
{context}

RULES:
1. Only use information from sources
2. Apply user preferences from memory
3. If you learn a new preference, save it"""
```

---

## 5. Memory Flow Summary

```
User asks question
    ↓
Load long-term memory (knowledge/memory/*.md)
    ↓
Load short-term (last 10 messages)
    ↓
Load session (current thread, if any)
    ↓
Combine all context
    ↓
RAG search (enhanced by history)
    ↓
LLM generate
    ↓
Save to short-term memory
Save to thread (if in thread)
Extract & save preferences (if detected) → long-term memory
```

---

## 6. Low-connected Notes (Phase 5)

> **Per chot.md:** Thay "knowledge gap detection" phức tạp bằng "low-connected notes".

### 6.1 Định nghĩa

Notes có ít connections (links + backlinks ≤ 1) = potential orphans.

### 6.2 Implementation

```python
def get_low_connected_notes(threshold: int = 1) -> list[str]:
    """Return notes with <= threshold connections."""
    all_notes = file_service.list_all_notes()
    low = []

    for note_path in all_notes:
        forward = len(link_service._forward.get(note_path, set()))
        backward = len(link_service._backward.get(note_path, set()))
        total = forward + backward

        if total <= threshold:
            low.append({
                "path": note_path,
                "connections": total,
            })

    return sorted(low, key=lambda x: x["connections"])
```

### 6.3 API

```python
@router.get("/notes/low-connected")
async def get_low_connected(threshold: int = 1):
    return link_service.get_low_connected_notes(threshold)
```

### 6.4 UI

Show in sidebar Tags tab (bottom section) + periodic AI suggestion:
```
💡 These notes might need more connections:
- orphan-note.md (0 links)
- random-idea.md (1 link)
Consider adding [[wiki links]] to related notes.
```

---

## 7. Data Boundaries

| Layer | Storage | Lifetime | Size limit |
|-------|---------|----------|------------|
| Short-term | RAM (dict) | Session | 10 messages |
| Session/Thread | JSON files | Permanent | ~50KB per thread |
| Long-term | Markdown files | Permanent | ~5KB per file |
| Vault (source) | Markdown files | Permanent | No limit |
| Embeddings | Qdrant | Rebuilt on demand | ~5000 vectors |

---

## 8. File Structure

```
backend/
  services/
    memory_service.py         # ShortTermMemory class
    thread_service.py         # ResearchThread CRUD
  api/
    threads.py                # Thread endpoints

knowledge/
  memory/
    preferences.md            # AI-learned preferences
    patterns.md               # AI-noticed patterns
    threads/
      {thread_id}.json        # Research thread data

tests/
  test_memory_service.py
  test_thread_service.py
```
