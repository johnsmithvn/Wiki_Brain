"""
Note Pipeline — Single entry point for note indexing.

Eliminates duplicated tags → links → index calls scattered across
notes.py, daily.py, watcher_service.py, and rename_service.py.

Phase 3 addition: schedules embedding after FTS indexing with debounce.

Usage:
    from backend.services.note_pipeline import note_pipeline

    # After creating/updating a note:
    tags = await note_pipeline.process_note(rel_path, content)

    # After deleting a note:
    note_pipeline.remove_note(rel_path)
"""

import asyncio
import logging

from backend.config.retrieval import EMBED_DEBOUNCE_SECONDS
from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

logger = logging.getLogger(__name__)


class NotePipeline:
    """Orchestrator: coordinates tag extraction, link parsing, FTS indexing, and embedding."""

    def __init__(self) -> None:
        self._embed_timers: dict[str, asyncio.TimerHandle] = {}

    async def process_note(self, rel_path: str, content: str) -> list[str]:
        """Run full indexing pipeline for a note.

        Args:
            rel_path: Relative path from knowledge root (e.g. "daily/2026-03-08.md").
            content: Full markdown content of the note.

        Returns:
            Extracted tags list.
        """
        tags = tag_service.update_tags(rel_path, content)
        link_service.update_links(rel_path, content)
        metadata = file_service.get_metadata(rel_path)
        # Wrap blocking SQLite call to avoid stalling the event loop
        await asyncio.to_thread(
            index_service.index_note, rel_path, metadata.title, content, tags
        )
        logger.debug("Pipeline processed: %s (%d tags)", rel_path, len(tags))

        # Schedule debounced embedding (Phase 3)
        self._schedule_embed(rel_path, content, tags)

        return tags

    def _schedule_embed(self, rel_path: str, content: str, tags: list[str]) -> None:
        """Debounced embedding: wait EMBED_DEBOUNCE_SECONDS after last save."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No event loop (e.g. in sync tests)

        # Cancel previous timer for this note
        if rel_path in self._embed_timers:
            self._embed_timers[rel_path].cancel()

        # Schedule new timer
        self._embed_timers[rel_path] = loop.call_later(
            EMBED_DEBOUNCE_SECONDS,
            lambda p=rel_path, c=content, t=tags: loop.create_task(
                self._do_embed(p, c, t)
            ),
        )

    async def _do_embed(self, rel_path: str, content: str, tags: list[str]) -> None:
        """Chunk + embed + upsert a note into Qdrant."""
        self._embed_timers.pop(rel_path, None)

        try:
            from backend.services.chunker_service import chunk_note
            from backend.services.embedding_service import embedding_service
            from backend.services.vector_service import vector_service

            if not vector_service.available:
                return

            # Skip if content unchanged
            if vector_service.is_unchanged(rel_path, content):
                logger.debug("Embedding skipped (unchanged): %s", rel_path)
                return

            # Chunk
            chunks = chunk_note(content, rel_path)
            if not chunks:
                vector_service.delete_note(rel_path)
                return

            # Enrich chunks with tags and links
            forward_links = link_service.get_forward_links(rel_path)
            for c in chunks:
                c.tags = tags
                c.links = forward_links

            # Embed chunks
            vectors = await embedding_service.embed_chunks(chunks)

            # Doc-level summary embedding (T26)
            title = chunks[0].note_title if chunks else "Untitled"
            words = content.split()[:200]
            doc_summary = f"Title: {title}\nTags: {', '.join(tags)}\nSummary: {' '.join(words)}"
            doc_vector = await embedding_service.embed_query(doc_summary)

            # Upsert
            vector_service.upsert_note(
                note_path=rel_path,
                chunks=chunks,
                vectors=vectors,
                content=content,
                doc_summary_vector=doc_vector,
                doc_summary_text=doc_summary,
            )
            logger.info("Embedded %d chunks for %s", len(chunks), rel_path)

        except Exception as e:
            logger.warning("Embedding failed for %s: %s", rel_path, e)

    def remove_note(self, rel_path: str) -> None:
        """Remove a note from all indexes."""
        index_service.remove_note(rel_path)
        link_service.remove_note(rel_path)
        tag_service.remove_note(rel_path)

        # Remove from Qdrant (Phase 3)
        try:
            from backend.services.vector_service import vector_service
            vector_service.delete_note(rel_path)
        except Exception:
            pass

        # Cancel pending embed timer
        timer = self._embed_timers.pop(rel_path, None)
        if timer:
            timer.cancel()

        logger.debug("Pipeline removed: %s", rel_path)


note_pipeline = NotePipeline()
