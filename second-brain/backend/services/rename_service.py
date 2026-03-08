"""
Rename Service — Wiki-Link Propagation

When a note is renamed, this service finds all notes referencing the old name
via [[wiki-links]] and rewrites them to point to the new name.

Handles:
- [[OldName]] → [[NewName]]
- [[OldName|alias]] → [[NewName|alias]]
- Skips content inside code blocks (``` ... ```)
- Case-insensitive stem matching
"""

import logging
import re

from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

logger = logging.getLogger(__name__)


def _stem_from_path(path: str) -> str:
    """Extract filename stem from a relative path (e.g. 'folder/My Note.md' → 'My Note')."""
    return path.rsplit("/", 1)[-1].replace(".md", "")


def _build_rewrite_pattern(old_stem: str) -> re.Pattern:
    """Build a regex that matches [[old_stem]] and [[old_stem|alias]] case-insensitively."""
    escaped = re.escape(old_stem)
    return re.compile(
        rf"\[\[({escaped})(\|[^\]]+)?\]\]",
        re.IGNORECASE,
    )


def _rewrite_content(content: str, old_stem: str, new_stem: str) -> tuple[str, int]:
    """Rewrite wiki-links in content, skipping code blocks.

    Returns:
        Tuple of (new_content, number_of_replacements).
    """
    pattern = _build_rewrite_pattern(old_stem)
    lines = content.split("\n")
    in_code_block = False
    total_replacements = 0
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block

        if in_code_block:
            result_lines.append(line)
            continue

        def replacer(match: re.Match) -> str:
            nonlocal total_replacements
            total_replacements += 1
            alias_part = match.group(2) or ""
            return f"[[{new_stem}{alias_part}]]"

        result_lines.append(pattern.sub(replacer, line))

    return "\n".join(result_lines), total_replacements


class RenameService:
    async def propagate_rename(self, old_path: str, new_path: str) -> int:
        """After a note is renamed, update all wiki-links pointing to it.

        Args:
            old_path: Original relative path (e.g. 'folder/OldNote.md')
            new_path: New relative path (e.g. 'folder/NewNote.md')

        Returns:
            Number of files that were updated.
        """
        old_stem = _stem_from_path(old_path)
        new_stem = _stem_from_path(new_path)

        if old_stem.lower() == new_stem.lower():
            return 0

        # Find all notes that had backlinks to the old path
        backlinkers = link_service.get_backlinks(old_path)
        if not backlinkers:
            # Also check by stem in case backward map was already cleaned
            backlinkers = self._find_references_by_stem(old_stem)

        updated_count = 0

        for ref_path in backlinkers:
            if ref_path == new_path:
                continue

            try:
                content = await file_service.read_file(ref_path)
                new_content, replacements = _rewrite_content(content, old_stem, new_stem)

                if replacements > 0:
                    await file_service.write_file(ref_path, new_content)
                    # Re-index the updated note
                    tags = tag_service.update_tags(ref_path, new_content)
                    link_service.update_links(ref_path, new_content)
                    metadata = file_service.get_metadata(ref_path)
                    index_service.index_note(ref_path, metadata.title, new_content, tags)
                    updated_count += 1
                    logger.info(
                        "Updated %d link(s) in '%s': [[%s]] → [[%s]]",
                        replacements, ref_path, old_stem, new_stem,
                    )
            except FileNotFoundError:
                logger.warning("Backlink source not found, skipping: %s", ref_path)
            except Exception:
                logger.exception("Failed to update links in '%s'", ref_path)

        return updated_count

    def _find_references_by_stem(self, stem: str) -> list[str]:
        """Fallback: scan all known paths for forward links matching the stem."""
        stem_lower = stem.lower().replace(" ", "-")
        refs: list[str] = []
        with link_service._lock:
            for source, targets in link_service._forward.items():
                for target in targets:
                    target_stem = _stem_from_path(target).lower().replace(" ", "-")
                    if target_stem == stem_lower:
                        refs.append(source)
                        break
        return refs


rename_service = RenameService()
