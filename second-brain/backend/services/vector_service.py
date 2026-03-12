"""
Vector Service — Qdrant CRUD for chunk embeddings.

Manages collection lifecycle, upsert/delete per note, and vector search.

Design ref: docs/DESIGN-chunking-retrieval.md §6
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

if TYPE_CHECKING:
    import numpy as np
    from backend.services.chunker_service import Chunk

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "knowledge_chunks"
_DEFAULT_URL = "http://localhost:6333"


class VectorService:
    """Qdrant vector database interface for knowledge chunks."""

    def __init__(self, url: str = _DEFAULT_URL, collection: str = _COLLECTION_NAME) -> None:
        self._url = url
        self._collection = collection
        self._client: QdrantClient | None = None
        self._dim: int = 1024  # Updated on init
        # Content hash cache: note_path → hash (avoid re-embedding unchanged notes)
        self._hash_cache: dict[str, str] = {}

    def init(self, dim: int = 1024) -> None:
        """Initialize Qdrant client and ensure collection exists."""
        self._dim = dim
        try:
            self._client = QdrantClient(url=self._url, timeout=10)
            self._ensure_collection()
            logger.info("Qdrant connected: %s, collection=%s", self._url, self._collection)
        except Exception as e:
            logger.warning("Qdrant connection failed: %s — vector search disabled", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = [c.name for c in self._client.get_collections().collections]
        if self._collection in collections:
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=self._dim,
                distance=Distance.COSINE,
            ),
        )
        # Payload indexes for filtering
        for field in ("note_path", "tags", "type"):
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema="keyword",
            )
        logger.info("Created Qdrant collection: %s (dim=%d)", self._collection, self._dim)

    @staticmethod
    def content_hash(content: str) -> str:
        """SHA-256 hash (first 16 hex chars) for content dedup."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def is_unchanged(self, note_path: str, content: str) -> bool:
        """Check if note content hash matches cached value."""
        new_hash = self.content_hash(content)
        return self._hash_cache.get(note_path) == new_hash

    def _point_id(self, chunk_id: str) -> str:
        """Deterministic UUID-like ID from chunk_id for Qdrant point."""
        # Qdrant supports string IDs
        return hashlib.sha256(chunk_id.encode()).hexdigest()[:32]

    def upsert_note(
        self,
        note_path: str,
        chunks: list[Chunk],
        vectors: "np.ndarray",
        content: str,
        doc_summary_vector: "np.ndarray | None" = None,
        doc_summary_text: str = "",
    ) -> None:
        """Replace all vectors for a note with new chunks.

        1. Delete old points for this note_path
        2. Upsert new chunk points
        3. Optionally upsert doc-level summary point
        4. Update hash cache
        """
        if not self._client:
            return

        # Delete old
        self.delete_note(note_path)

        # Build points
        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                PointStruct(
                    id=self._point_id(chunk.chunk_id),
                    vector=vector.tolist(),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "note_path": chunk.note_path,
                        "note_title": chunk.note_title,
                        "heading": chunk.heading,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "tags": chunk.tags,
                        "links": chunk.links,
                        "token_count": chunk.token_count,
                        "content_hash": self.content_hash(content),
                        "type": "chunk",
                    },
                )
            )

        # Doc-level summary point (T26)
        if doc_summary_vector is not None:
            doc_chunk_id = f"{note_path}#doc"
            points.append(
                PointStruct(
                    id=self._point_id(doc_chunk_id),
                    vector=doc_summary_vector.tolist(),
                    payload={
                        "chunk_id": doc_chunk_id,
                        "note_path": note_path,
                        "note_title": chunks[0].note_title if chunks else "",
                        "heading": "",
                        "chunk_index": -1,
                        "content": doc_summary_text,
                        "tags": chunks[0].tags if chunks else [],
                        "links": [],
                        "token_count": len(doc_summary_text.split()),
                        "content_hash": self.content_hash(content),
                        "type": "document",
                    },
                )
            )

        if points:
            self._client.upsert(
                collection_name=self._collection,
                points=points,
            )

        # Update hash cache
        self._hash_cache[note_path] = self.content_hash(content)
        logger.debug("Upserted %d vectors for %s", len(points), note_path)

    def delete_note(self, note_path: str) -> None:
        """Delete all vectors for a specific note."""
        if not self._client:
            return

        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="note_path", match=MatchValue(value=note_path))]
            ),
        )
        self._hash_cache.pop(note_path, None)

    def search(
        self,
        query_vector: "np.ndarray",
        limit: int = 10,
        type_filter: str | None = None,
    ) -> list:
        """Vector similarity search.

        Returns list of Qdrant ScoredPoint objects.
        """
        if not self._client:
            return []

        query_filter = None
        if type_filter:
            query_filter = Filter(
                must=[FieldCondition(key="type", match=MatchValue(value=type_filter))]
            )

        return self._client.query_points(
            collection_name=self._collection,
            query=query_vector.tolist(),
            query_filter=query_filter,
            limit=limit,
        ).points

    def get_chunks_for_notes(
        self,
        note_paths: list[str],
        max_per_note: int = 2,
    ) -> list:
        """Retrieve top chunks for each note path (for graph expansion)."""
        if not self._client or not note_paths:
            return []

        results = []
        for path in note_paths:
            points = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="note_path", match=MatchValue(value=path)),
                        FieldCondition(key="type", match=MatchValue(value="chunk")),
                    ]
                ),
                limit=max_per_note,
            )[0]  # scroll returns (points, next_offset)
            results.extend(points)

        return results

    def get_collection_info(self) -> dict | None:
        """Get basic stats about the collection."""
        if not self._client:
            return None
        try:
            info = self._client.get_collection(self._collection)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value,
            }
        except Exception:
            return None


# Singleton
vector_service = VectorService()
