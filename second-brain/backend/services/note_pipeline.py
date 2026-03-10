"""
Note Pipeline — Single entry point for note indexing.

Eliminates duplicated tags → links → index calls scattered across
notes.py, daily.py, watcher_service.py, and rename_service.py.

Usage:
    from backend.services.note_pipeline import note_pipeline

    # After creating/updating a note:
    tags = await note_pipeline.process_note(rel_path, content)

    # After deleting a note:
    note_pipeline.remove_note(rel_path)
"""

import logging

from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

logger = logging.getLogger(__name__)


class NotePipeline:
    """Orchestrator: coordinates tag extraction, link parsing, and FTS indexing."""

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
        index_service.index_note(rel_path, metadata.title, content, tags)
        logger.debug("Pipeline processed: %s (%d tags)", rel_path, len(tags))
        return tags

    def remove_note(self, rel_path: str) -> None:
        """Remove a note from all indexes."""
        index_service.remove_note(rel_path)
        link_service.remove_note(rel_path)
        tag_service.remove_note(rel_path)
        logger.debug("Pipeline removed: %s", rel_path)


note_pipeline = NotePipeline()
