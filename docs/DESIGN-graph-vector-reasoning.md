# DESIGN — Graph + Vector Hybrid Reasoning

> **Phase:** 4 (RAG Chat & AI Assistant)
> **Depends on:** Phase 3 (Qdrant + embeddings operational)
> **Files affected:** `rag_service.py`, `llm_service.py`, `graph_expansion_service.py`, `chat.py`

---

## 1. Tổng quan

RAG bình thường chỉ **vector search → chunks → LLM**. Hệ này có lợi thế lớn: **wiki links + knowledge graph**. Ta kết hợp cả hai để AI reasoning tốt hơn.

```
RAG bình thường:     query → vector → chunks → LLM
Hệ này:             query → vector → graph expansion → chunk selection → LLM
```

---

## 2. Vấn đề của RAG bình thường

Hỏi: *"Claude reasoning khác gì RAG?"*

Vector search có thể trả:
```
rag.md          (high similarity)
vector-search.md (medium similarity)
```

Nhưng **bỏ lỡ**:
```
claude-reasoning.md   (text rất khác, nhưng link đến cùng concepts)
```

**Giải pháp:** Sau vector search → expand theo graph → thu thập neighbor notes.

---

## 3. Retrieval Pipeline (Graph + Vector)

```
query
    ↓
embed query (BGE-M3)
    ↓
vector search top-10 chunks
    ↓
extract unique note_paths
    ↓
graph expansion (BFS 1-hop từ mỗi note)
    ↓
collect neighbor notes (max 5 neighbors)
    ↓
get top chunks từ neighbor notes (max 2 per note)
    ↓
merge + deduplicate by chunk_id
    ↓
score = VECTOR_WEIGHT*vector + GRAPH_WEIGHT*graph_proximity + KEYWORD_WEIGHT*keyword
    ↓
select top-5 chunks (≤ 2000 tokens)
    ↓
build context
    ↓
LLM generate + cite sources
```

---

## 4. Graph Expansion

### 4.1 Implementation

```python
# backend/services/graph_expansion_service.py

from backend.services.link_service import link_service

def expand_notes(
    seed_notes: list[str],
    depth: int = 1,
    max_neighbors: int = 5
) -> list[str]:
    """
    Từ seed notes, BFS expand 1-hop → trả danh sách neighbor paths.
    """
    neighbors = set()
    for note_path in seed_notes:
        forward = link_service._forward.get(note_path, set())
        backward = link_service._backward.get(note_path, set())
        neighbors.update(forward | backward)

    # Remove seeds from neighbors
    neighbors -= set(seed_notes)

    # Limit
    return list(neighbors)[:max_neighbors]
```

### 4.2 Depth Rule

```
depth = 1 (chỉ neighbors trực tiếp)
max_neighbors = 5
```

**Tại sao depth=1:** Depth=2 tạo quá nhiều noise. Vault cá nhân 1-hop đủ cover related concepts.

### 4.3 Graph Proximity Scoring

```python
def graph_proximity_score(note_path: str, seed_notes: list[str]) -> float:
    """
    same note = 1.0
    1 hop = 0.7
    2 hops = 0.4
    not connected = 0.0
    """
    if note_path in seed_notes:
        return 1.0

    for seed in seed_notes:
        forward = link_service._forward.get(seed, set())
        backward = link_service._backward.get(seed, set())
        if note_path in (forward | backward):
            return 0.7

    return 0.0
```

---

## 5. Full Retrieval Flow (Code)

```python
# backend/services/rag_service.py

async def retrieve_context(query: str) -> RAGContext:
    # Step 1: Vector search
    query_vector = embedding_service.embed_query(query)
    vector_results = vector_service.search(query_vector, limit=10)

    # Step 2: Extract seed notes
    seed_notes = list(set(r.payload["note_path"] for r in vector_results))

    # Step 3: Graph expansion
    neighbor_notes = graph_expansion_service.expand_notes(
        seed_notes, depth=1, max_neighbors=5
    )

    # Step 4: Get chunks from neighbors (max 2 per note to ensure coverage)
    neighbor_chunks = vector_service.get_chunks_for_notes(
        neighbor_notes, max_per_note=2
    )

    # Step 5: Merge + deduplicate by chunk_id
    seen_chunk_ids = set()
    all_chunks = []

    # Import weights from retrieval config
    from backend.config.retrieval import VECTOR_WEIGHT, GRAPH_WEIGHT, KEYWORD_WEIGHT

    for chunk in vector_results:
        cid = chunk.payload.get("chunk_id", chunk.id)
        if cid in seen_chunk_ids:
            continue
        seen_chunk_ids.add(cid)
        score = (
            VECTOR_WEIGHT * chunk.score +
            GRAPH_WEIGHT * graph_proximity_score(chunk.payload["note_path"], seed_notes) +
            KEYWORD_WEIGHT * keyword_score(query, chunk.payload.get("content", ""))
        )
        all_chunks.append((chunk, score))

    for chunk in neighbor_chunks:
        cid = chunk.payload.get("chunk_id", chunk.id)
        if cid in seen_chunk_ids:
            continue
        seen_chunk_ids.add(cid)
        score = (
            VECTOR_WEIGHT * (chunk.score if hasattr(chunk, 'score') else 0.3) +
            GRAPH_WEIGHT * 0.7 +  # 1-hop neighbor
            KEYWORD_WEIGHT * keyword_score(query, chunk.payload.get("content", ""))
        )
        all_chunks.append((chunk, score))

    # Step 6: Select top-5, limit 2000 tokens
    all_chunks.sort(key=lambda x: -x[1])
    selected = select_within_token_limit(all_chunks, max_tokens=2000)

    return RAGContext(
        chunks=selected,
        seed_notes=seed_notes,
        neighbor_notes=neighbor_notes,
    )
```

---

## 6. Context Building

### 6.1 Context Format

Group chunks by note for LLM clarity:

```
[Source: ai/rag.md]

RAG gồm 3 bước:
retrieval, augmentation, generation.

---

[Source: ai/vector-search.md]

Vector search sử dụng embedding similarity...

---

[Source: ai/claude-reasoning.md]  ← graph expansion found this!

Claude reasoning khác RAG ở chỗ...
```

### 6.2 Context Size

```
Max context: 2000 tokens
Target: 1500 tokens (leave room for question + system prompt)
```

### 6.3 Code

```python
def build_context(chunks: list[ScoredChunk]) -> str:
    """Build context string grouped by note path."""
    by_note = defaultdict(list)
    for chunk, score in chunks:
        by_note[chunk.payload["note_path"]].append(chunk.payload["content"])

    context = ""
    for note_path, contents in by_note.items():
        context += f"[Source: {note_path}]\n\n"
        context += "\n\n".join(contents)
        context += "\n\n---\n\n"

    return context.strip()
```

---

## 7. Prompt Template

```python
SYSTEM_PROMPT = """You are answering questions using the user's personal knowledge vault.

RULES:
1. Only use information from the provided sources
2. If the answer is not in the sources, say "I don't have enough information in the vault"
3. Always cite which source note(s) you used
4. Answer in the same language as the question
5. Be concise and direct

Sources:
{context}"""

USER_PROMPT = """{question}"""
```

### 7.1 Citation Format

AI response:

```
RAG gồm 3 bước: retrieval, augmentation, generation. Claude reasoning
khác ở chỗ nó có internal chain-of-thought trước khi trả lời.

Sources:
- ai/rag.md
- ai/claude-reasoning.md
```

Frontend parse sources → clickable links.

---

## 8. Ollama Integration

### 8.1 LLM Service

```python
# backend/services/llm_service.py

import httpx

class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL  # "http://localhost:11434"
        self.model = settings.LLM_MODEL      # "qwen2.5:7b-instruct-q4_K_M"

    async def generate_stream(
        self, system: str, user: str
    ) -> AsyncGenerator[str, None]:
        """Stream response from Ollama."""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    data = json.loads(line)
                    if "message" in data:
                        yield data["message"].get("content", "")
```

### 8.2 Config

```python
class Settings(BaseSettings):
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
```

---

## 9. Chat API

### 9.1 SSE Streaming Endpoint

```python
# backend/api/chat.py

from fastapi.responses import StreamingResponse

@router.post("/chat")
async def chat(body: ChatRequest):
    """RAG chat with SSE streaming."""
    # Retrieve context
    context = await rag_service.retrieve_context(body.question)

    # Build prompt
    system = SYSTEM_PROMPT.format(context=build_context(context.chunks))
    user = body.question

    # Stream response
    async def event_stream():
        async for token in llm_service.generate_stream(system, user):
            yield f"data: {json.dumps({'token': token})}\n\n"

        # Send sources at end
        sources = list(set(c.payload["note_path"] for c, _ in context.chunks))
        yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### 9.2 ChatRequest Schema

```python
class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None  # for session memory
    mode: str = "chat"  # "chat" | "summary" | "explore"
```

---

## 10. Multi-mode AI

### 10.1 Summary Mode

```python
async def summarize_note(note_path: str) -> str:
    content = await file_service.read_file(note_path)
    system = "Summarize the following note. Keep key points. Be concise."
    async for token in llm_service.generate_stream(system, content):
        yield token
```

### 10.2 Auto-link Suggestion

```python
async def suggest_links(note_path: str, content: str) -> list[str]:
    """Suggest [[wiki links]] to existing notes."""
    # Get related notes via embedding
    related = await get_related_notes(note_path, limit=10)

    # Check which related notes are NOT already linked
    existing_links = link_service.get_links(note_path)
    suggestions = [r for r in related if r not in existing_links]

    return suggestions[:5]
```

> **Per chot.md:** Auto-link suggestion hữu ích hơn tag suggestion. AI gợi ý `[[connections]]` thay vì tags.

---

## 11. Conversation Memory (Short-term)

```python
# Store last 10 messages per conversation
conversations: dict[str, list[dict]] = {}

def get_conversation_context(conversation_id: str) -> str:
    messages = conversations.get(conversation_id, [])
    return "\n".join(
        f"{m['role']}: {m['content']}" for m in messages[-10:]
    )
```

---

## 12. Performance

| Metric | Estimate |
|--------|----------|
| Vector search | 5-20ms |
| Graph expansion | ~1ms (in-memory) |
| Context building | ~5ms |
| LLM first token | 200-500ms |
| LLM full response | 1-3 seconds |
| **Total RAG latency** | **1-3 seconds** |

> **⚠️ Cold-start:** Lần đầu tiên gọi `embedding_service.embed_query()` mất 2-5 giây
> vì sentence-transformers load model vào RAM/VRAM.
> **Fix:** Gọi `embed_query("warmup")` trong lifespan startup (xem BACKEND-SERVICE-BOUNDARIES.md §5b).

---

## 13. UI: Source Highlighting

```
Chat answer:
  "RAG gồm 3 bước..."

  Sources:
  [ai/rag.md] [ai/vector-search.md] [ai/claude-reasoning.md]
       ↓              ↓                    ↓
    click          click               click → open note
```

Graph view can highlight notes used in answer.

---

## 14. Retrieval Config

> **Sprint 4.5 (T17d):** Extraction of tunable weights into a config file.

```python
# backend/config/retrieval.py

# --- Retrieval Fusion Weights ---
# Used in rag_service.py for Graph+Vector hybrid scoring.
# Also referenced by hybrid_search in DESIGN-chunking-retrieval.md.
# Tunable after Phase 3 eval loop.

VECTOR_WEIGHT = 0.6    # Semantic similarity (Qdrant cosine)
GRAPH_WEIGHT  = 0.3    # Graph proximity (wiki-link BFS)
KEYWORD_WEIGHT = 0.1   # Keyword overlap (FTS5 BM25)

# --- Hybrid Search Weights (no graph) ---
# Used in search.py for plain hybrid search (Phase 3).
HYBRID_VECTOR_WEIGHT = 0.7
HYBRID_KEYWORD_WEIGHT = 0.3
```

**Lý do:** Hardcoded weights scattered across `rag_service.py`, `search.py`, design docs. Single config → tune once after eval.

---

## 15. File Structure

```
backend/
  api/
    chat.py                      # POST /api/chat (SSE)
  config/
    retrieval.py                 # Tunable retrieval weights
  services/
    llm_service.py               # Ollama client, streaming
    rag_service.py               # retrieve → context → generate
    graph_expansion_service.py   # BFS neighbor expansion

frontend/js/
  chat.js                        # Chat UI panel
frontend/css/
  chat.css                       # Chat styling
```
