# DESIGN — Chunking & Retrieval Pipeline

> **Phase:** 3 (Semantic Search Layer)
> **Depends on:** Phase 2 complete, Qdrant running
> **Files affected:** `chunker_service.py`, `embedding_service.py`, `vector_service.py`, `search.py`

---

## 1. Tổng quan

Pipeline chuyển markdown notes → semantic chunks → vector embeddings → Qdrant.

```
markdown note
    ↓
AST parse (markdown-it-py)
    ↓
semantic chunking (heading + paragraph)
    ↓
chunk metadata enrichment
    ↓
batch embedding (BGE-M3, GPU)
    ↓
Qdrant upsert
```

---

## 2. Chunking Strategy

### 2.1 Nguyên tắc

**KHÔNG split theo fixed token count.** Split theo **semantic boundary**.

```
❌ Sai: cắt mỗi 500 tokens bất kể nội dung
✅ Đúng: cắt theo heading → paragraph → list → code block
```

### 2.2 Algorithm

```python
def chunk_note(markdown_text: str, note_path: str) -> list[Chunk]:
    """
    Step 1: Parse markdown AST
    Step 2: Group by section (heading boundaries)
    Step 3: Split large sections by paragraph
    Step 4: Merge small consecutive chunks
    """
```

**Step 1 — Parse AST:**
```
markdown-it-py parse → tokens:
  heading, paragraph, list, code_block, blockquote
```

**Step 2 — Group by section:**
```
# RAG Pipeline        → section boundary
  paragraph 1         → accumulate
  paragraph 2         → accumulate
## Retrieval           → NEW section boundary
  paragraph 3         → accumulate into new chunk
  code block           → keep attached to section
## Augmentation        → NEW section boundary
  ...
```

**Step 3 — Split if section > 500 tokens:**
```python
if section_tokens > MAX_TOKENS:  # 500
    split_by_paragraph(section)
    # each paragraph chunk targets 300-400 tokens
```

**Step 4 — Merge small chunks:**
```python
if chunk_tokens < MIN_TOKENS:  # 100
    merge_with_previous_chunk()
```

### 2.3 Chunk Size Parameters

```python
MAX_TOKENS = 500
TARGET_TOKENS = 350
MIN_TOKENS = 100
OVERLAP_TOKENS = 50
```

**Lý do 300-500 tokens:**
- Vector quality tốt nhất ở range này
- Context retrieval đủ meaningful
- Không quá nhỏ (thiếu context) hay quá lớn (noise)

### 2.4 Overlap

Chunks liên tiếp overlap 50 tokens ở đầu/cuối. Đảm bảo không mất context giữa 2 chunks.

```
Chunk 1: [tokens 1-350]
Chunk 2: [tokens 300-650]  ← overlap 50 tokens
Chunk 3: [tokens 600-950]
```

### 2.5 Special Handling

| Element | Xử lý |
|---------|--------|
| Code block | Giữ nguyên, không split giữa block |
| List | Giữ nguyên list, không cắt giữa items |
| Blockquote | Attach vào paragraph trước |
| Frontmatter (YAML) | Extract metadata, không chunk |
| Heading | Luôn là boundary cho chunk mới |

---

## 3. Chunk Metadata Schema

Mỗi chunk lưu vào Qdrant với payload:

```python
@dataclass
class Chunk:
    chunk_id: str       # "ai/rag.md#2"
    note_path: str      # "ai/rag.md"
    note_title: str     # "RAG Pipeline"
    heading: str        # "Retrieval"
    chunk_index: int    # 2
    content: str        # actual text
    tags: list[str]     # ["ai", "rag"]
    links: list[str]    # ["vector-search.md"]
    token_count: int    # 312
```

### 3.1 Embedding Input Format

**KHÔNG chỉ embed content.** Thêm title + heading cho context:

```
Title: RAG Pipeline
Section: Retrieval

Content:
RAG pipeline gồm 3 bước chính:
retrieval, augmentation, generation.
Retrieval sử dụng vector search...
```

**Lý do:** Embedding có context → similarity tốt hơn.

---

## 4. Document Summary Embedding

Mỗi note THÊM 1 doc-level embedding:

```python
doc_summary = f"Title: {title}\nTags: {tags}\nSummary: {first_200_words}"
doc_vector = embed(doc_summary)
```

Lưu riêng trong Qdrant (hoặc collection riêng):
```
chunk_id: "ai/rag.md#doc"
type: "document"
```

**Retrieval 2-level:**
```
doc-level search → tìm đúng note
chunk-level search → tìm đúng đoạn
```

Giúp recall tốt hơn khi query chung chung.

---

## 5. Embedding Pipeline

### 5.1 Model: BGE-M3

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")
# Dimensions: 1024
# VRAM: ~2.5GB
# Multilingual: VN + EN
```

### 5.2 Batch Embedding

```python
BATCH_SIZE = 32  # GPU optimal

def embed_chunks(chunks: list[Chunk]) -> list[np.ndarray]:
    texts = [format_embedding_input(c) for c in chunks]
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        batch_vectors = model.encode(batch, normalize_embeddings=True)
        vectors.extend(batch_vectors)
    return vectors
```

### 5.3 Incremental Indexing

```
file changed (watcher detect)
    ↓
async queue
    ↓
delete old chunks for this note
    ↓
re-chunk note
    ↓
re-embed chunks
    ↓
upsert to Qdrant
```

**Hash comparison:** Store `content_hash` per note. Only re-embed if hash changed.

```python
import hashlib

def note_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

---

## 6. Qdrant Schema

### 6.1 Collection

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="knowledge_chunks",
    vectors_config=VectorParams(
        size=1024,  # BGE-M3
        distance=Distance.COSINE,
    ),
)
```

### 6.2 Payload Schema

```json
{
  "chunk_id": "ai/rag.md#2",
  "note_path": "ai/rag.md",
  "note_title": "RAG Pipeline",
  "heading": "Retrieval",
  "chunk_index": 2,
  "tags": ["ai", "rag"],
  "links": ["vector-search.md"],
  "token_count": 312,
  "content_hash": "a1b2c3d4",
  "type": "chunk"  // or "document" for doc-level
}
```

### 6.3 Payload Indexes

```python
client.create_payload_index(
    collection_name="knowledge_chunks",
    field_name="note_path",
    field_schema="keyword",
)
client.create_payload_index(
    collection_name="knowledge_chunks",
    field_name="tags",
    field_schema="keyword",
)
client.create_payload_index(
    collection_name="knowledge_chunks",
    field_name="type",
    field_schema="keyword",
)
```

---

## 7. Hybrid Search (Retrieval)

### 7.1 Pipeline

```
query
    ↓
embed query (BGE-M3)
    ↓
┌─────────────────┬──────────────────┐
│ Vector search    │ Keyword search    │
│ Qdrant top-20    │ FTS5 top-20       │
└────────┬────────┴────────┬─────────┘
         │                 │
         ▼                 ▼
    Weighted Fusion
    score = 0.7 * vector_score + 0.3 * keyword_score
         │
         ▼
    Deduplicate by note_path
         │
         ▼
    Top-10 chunks
```

### 7.2 Weighted Fusion (đơn giản hơn RRF)

```python
def hybrid_search(query: str, limit: int = 10) -> list[SearchResult]:
    # Vector search
    query_vector = model.encode(query, normalize_embeddings=True)
    vector_results = qdrant.search(
        collection_name="knowledge_chunks",
        query_vector=query_vector,
        limit=20,
    )

    # Keyword search
    keyword_results = index_service.search(query, limit=20)

    # Normalize scores to [0, 1]
    # Fusion
    combined = {}
    for r in vector_results:
        combined[r.chunk_id] = 0.7 * r.score
    for r in keyword_results:
        chunk_id = find_chunk_for_note(r.path)
        if chunk_id in combined:
            combined[chunk_id] += 0.3 * r.score
        else:
            combined[chunk_id] = 0.3 * r.score

    # Sort and return top-N
    return sorted(combined.items(), key=lambda x: -x[1])[:limit]
```

> **Per chot.md:** Weighted sum đơn giản hơn RRF. Đủ tốt cho solo project.

### 7.3 Search Modes

| Mode | Behavior |
|------|----------|
| `keyword` | FTS5 only (existing) |
| `semantic` | Qdrant vector only |
| `hybrid` | Weighted fusion (default) |

API: `GET /api/search?q=...&mode=hybrid`

---

## 8. Related Notes Algorithm

**Per chot.md:** Dùng average chunk similarity, không note-level.

```python
def get_related_notes(note_path: str, limit: int = 5) -> list:
    # Lấy 3 chunks đại diện từ note
    note_chunks = get_chunks_for_note(note_path)
    sample_chunks = note_chunks[:3]  # first 3

    # Vector search cho mỗi chunk
    hit_counter = defaultdict(float)
    for chunk in sample_chunks:
        results = qdrant.search(
            query_vector=chunk.vector,
            limit=10,
            filter={"must_not": [{"key": "note_path", "match": {"value": note_path}}]}
        )
        for r in results:
            hit_counter[r.payload["note_path"]] += r.score

    # Average score per note, sort
    for path in hit_counter:
        hit_counter[path] /= len(sample_chunks)

    return sorted(hit_counter.items(), key=lambda x: -x[1])[:limit]
```

---

## 9. Performance Estimates

| Metric | Estimate |
|--------|----------|
| Vault size | 1000 notes |
| Chunks | ~5000 |
| Embedding time (full vault) | ~2-5 min (GPU) |
| Single note re-embed | ~100ms |
| Qdrant search latency | 5-20ms |
| FTS5 search latency | 1-5ms |
| Hybrid search total | 20-40ms |

---

## 10. Sai lầm cần tránh

| ❌ Sai | ✅ Đúng |
|--------|---------|
| Chunk theo fixed tokens | Chunk theo semantic boundary |
| Không có metadata | Rich metadata per chunk |
| Chỉ vector search | Hybrid search |
| Context quá dài | ≤ 2000 tokens |
| top_k quá nhỏ | top_k = 20, fusion lọc 10 |
| Embed chỉ content | Embed title + section + content |

---

## 11. File Structure

```
backend/services/
  chunker_service.py     # markdown → chunks
  embedding_service.py   # chunks → vectors (BGE-M3)
  vector_service.py      # Qdrant CRUD

backend/api/
  search.py              # updated: add mode=hybrid param

tests/
  test_chunker_service.py
  test_embedding_service.py
```
