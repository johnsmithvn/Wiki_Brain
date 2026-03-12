"""
Embedding Service — Chunks → vector embeddings via sentence-transformers.

Loads BGE-M3 model (1024-dim, multilingual).  Runs encode in a thread
to avoid blocking the async event loop.

Design ref: docs/DESIGN-chunking-retrieval.md §5
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

from backend.config.retrieval import EMBED_BATCH_SIZE

if TYPE_CHECKING:
    from backend.services.chunker_service import Chunk

logger = logging.getLogger(__name__)

# Default model — multilingual, 1024-dim, good for VN + EN
_DEFAULT_MODEL = "BAAI/bge-m3"
_EMBEDDING_DIM = 1024


class EmbeddingService:
    """Lazy-loaded embedding model with batch encode."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None
        self._dim = _EMBEDDING_DIM

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_model(self) -> None:
        """Lazy load model on first use."""
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s ...", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Embedding model loaded: dim=%d, device=%s",
            self._dim,
            self._model.device,
        )

    def load_model(self) -> None:
        """Explicit model load (call during startup lifespan)."""
        self._ensure_model()

    def _encode_sync(self, texts: list[str], normalize: bool = True) -> np.ndarray:
        """Synchronous encode — call via to_thread from async context."""
        self._ensure_model()
        return self._model.encode(
            texts,
            normalize_embeddings=normalize,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=False,
        )

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts asynchronously.

        Returns np.ndarray of shape (len(texts), dim).
        """
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        return await asyncio.to_thread(self._encode_sync, texts)

    async def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string.

        Returns np.ndarray of shape (dim,).
        """
        result = await asyncio.to_thread(self._encode_sync, [query])
        return result[0]

    async def embed_chunks(self, chunks: list[Chunk]) -> np.ndarray:
        """Embed a list of Chunk objects using formatted input.

        Returns np.ndarray of shape (len(chunks), dim).
        """
        from backend.services.chunker_service import format_embedding_input

        texts = [format_embedding_input(c) for c in chunks]
        return await self.embed_texts(texts)


# Singleton
embedding_service = EmbeddingService()
