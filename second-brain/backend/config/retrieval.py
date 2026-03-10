"""
Retrieval fusion weights — tunable after Phase 3 eval loop.

Used by:
  - rag_service.py  (Graph+Vector retrieval, Phase 4)
  - search.py       (Hybrid search, Phase 3)

See also:
  - docs/DESIGN-graph-vector-reasoning.md §14
  - docs/DESIGN-chunking-retrieval.md §7
"""

# --- Graph+Vector RAG Weights (Phase 4: rag_service.py) ---
VECTOR_WEIGHT: float = 0.6     # Semantic similarity (Qdrant cosine)
GRAPH_WEIGHT: float = 0.3      # Graph proximity (wiki-link BFS 1-hop)
KEYWORD_WEIGHT: float = 0.1    # Keyword overlap (FTS5 BM25)

# --- Hybrid Search Weights (Phase 3: search.py, no graph) ---
HYBRID_VECTOR_WEIGHT: float = 0.7
HYBRID_KEYWORD_WEIGHT: float = 0.3

# --- Chunking Parameters ---
MAX_TOKENS: int = 450       # Max chunk size before split
TARGET_TOKENS: int = 300    # Ideal chunk size target
MIN_TOKENS: int = 120       # Min chunk size before merge

# --- Embedding Debounce ---
EMBED_DEBOUNCE_SECONDS: float = 2.0  # Wait after last save before embedding

# --- Embedding Batch ---
EMBED_BATCH_SIZE: int = 32  # GPU-optimal batch size for BGE-M3
