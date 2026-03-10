"""
Inbox Service — Parse inbox files and manage entries.

Inbox files are markdown files at knowledge/inbox/YYYY-MM-DD.md
with a specific entry format. Uses a state machine parser (not regex split)
because content may contain --- separators.
"""

import logging
import re
import unicodedata
from pathlib import Path

import aiofiles

from backend.config import settings
from backend.models.schemas import InboxDateSummary, InboxEntry

logger = logging.getLogger(__name__)

# Metadata key pattern: "key: value"
META_LINE = re.compile(r"^([a-z_]+):\s*(.+)$")


def _get_inbox_dir() -> Path:
    inbox_dir = settings.KNOWLEDGE_DIR / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def parse_inbox_file(text: str) -> list[InboxEntry]:
    """Parse markdown inbox file → structured entries.

    Uses state machine to handle --- separators robustly.
    States: SCAN → META → CONTENT
    """
    lines = text.split("\n")
    entries: list[InboxEntry] = []

    state = "SCAN"  # SCAN | META | CONTENT
    meta: dict[str, str] = {}
    content_lines: list[str] = []

    def _flush():
        if meta.get("id"):
            tags_raw = meta.get("tags", "")
            tags = []
            if tags_raw.startswith("[") and tags_raw.endswith("]"):
                tags = [t.strip().strip("'\"") for t in tags_raw[1:-1].split(",") if t.strip()]

            entries.append(InboxEntry(
                id=meta.get("id", ""),
                time=meta.get("time", ""),
                source=meta.get("source", "manual"),
                type=meta.get("type", "note"),
                url=meta.get("url"),
                tags=tags,
                content="\n".join(content_lines).strip(),
            ))

    for line in lines:
        stripped = line.strip()

        if state == "SCAN":
            if stripped == "---":
                # Check if next non-empty line looks like metadata
                state = "META"
                meta = {}
                content_lines = []
            # else skip (title line, blank lines)

        elif state == "META":
            if stripped == "---":
                # End of metadata block → start content
                state = "CONTENT"
            else:
                m = META_LINE.match(stripped)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
                # else: malformed meta line, ignore

        elif state == "CONTENT":
            if stripped == "---":
                # Could be start of next entry's metadata OR a --- in content
                # Peek: if we already have an id, flush and start new META
                if meta.get("id"):
                    _flush()
                    state = "META"
                    meta = {}
                    content_lines = []
                else:
                    content_lines.append(line)
            else:
                content_lines.append(line)

    # Flush last entry
    _flush()

    return entries


class InboxService:
    """Manage inbox entries: list, parse, delete, convert."""

    def list_dates(self) -> list[InboxDateSummary]:
        """Return list of inbox dates with entry counts."""
        inbox_dir = _get_inbox_dir()
        summaries: list[InboxDateSummary] = []

        for f in sorted(inbox_dir.glob("*.md"), reverse=True):
            date_str = f.stem  # YYYY-MM-DD
            try:
                text = f.read_text(encoding="utf-8")
                entries = parse_inbox_file(text)
                summaries.append(InboxDateSummary(date=date_str, count=len(entries)))
            except Exception as e:
                logger.warning("Failed to parse inbox file %s: %s", f, e)

        return summaries

    def get_entries(self, date_str: str) -> list[InboxEntry]:
        """Parse and return all entries for a specific date."""
        file_path = _get_inbox_dir() / f"{date_str}.md"
        if not file_path.exists():
            return []
        text = file_path.read_text(encoding="utf-8")
        return parse_inbox_file(text)

    async def delete_entry(self, date_str: str, entry_id: str) -> bool:
        """Remove an entry from the inbox file by rewriting without it."""
        file_path = _get_inbox_dir() / f"{date_str}.md"
        if not file_path.exists():
            return False

        text = file_path.read_text(encoding="utf-8")
        entries = parse_inbox_file(text)
        remaining = [e for e in entries if e.id != entry_id]

        if len(remaining) == len(entries):
            return False  # entry not found

        await self._rewrite_inbox_file(file_path, date_str, remaining)
        return True

    async def archive_entry(self, date_str: str, entry_id: str) -> bool:
        """Archive = remove from inbox (same as delete for now)."""
        return await self.delete_entry(date_str, entry_id)

    async def convert_entry_to_note(
        self, date_str: str, entry_id: str, title: str, folder: str, tags: list[str]
    ) -> str | None:
        """Convert an inbox entry to an organized vault note.

        Returns the new note path, or None if entry not found.
        """
        entries = self.get_entries(date_str)
        entry = next((e for e in entries if e.id == entry_id), None)
        if not entry:
            return None

        # Generate slug and file path
        slug = slugify(title)
        rel_folder = folder.strip("/") if folder else ""
        if rel_folder:
            note_dir = settings.KNOWLEDGE_DIR / rel_folder
        else:
            note_dir = settings.KNOWLEDGE_DIR

        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = unique_path(note_dir, slug)
        rel_path = note_path.relative_to(settings.KNOWLEDGE_DIR).as_posix()

        # Generate note content
        content = generate_note(entry, title, tags)
        async with aiofiles.open(note_path, "w", encoding="utf-8") as f:
            await f.write(content)

        # Remove entry from inbox
        await self.delete_entry(date_str, entry_id)

        return rel_path

    async def _rewrite_inbox_file(
        self, file_path: Path, date_str: str, entries: list[InboxEntry]
    ) -> None:
        """Rewrite inbox file with remaining entries."""
        from backend.services.capture_service import format_entry

        if not entries:
            # No entries left — remove file
            file_path.unlink(missing_ok=True)
            return

        header = f"# Inbox — {date_str}\n"
        parts = [header]
        for entry in entries:
            parts.append(format_entry(entry))

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write("".join(parts))


def slugify(title: str) -> str:
    """Convert title to file-safe slug."""
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80] or "untitled"


def unique_path(folder: Path, slug: str) -> Path:
    """Return unique file path. Append -1, -2... if slug already exists."""
    candidate = folder / f"{slug}.md"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = folder / f"{slug}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def generate_note(entry: InboxEntry, title: str, tags: list[str]) -> str:
    """Generate an organized note from an inbox entry."""
    tag_str = ", ".join(tags) if tags else ""
    date_str = entry.id[:4] + "-" + entry.id[4:6] + "-" + entry.id[6:8]

    lines = ["---\n"]
    lines.append(f"title: {title}\n")
    if entry.url:
        lines.append(f"source: {entry.url}\n")
    lines.append(f"captured: {date_str}\n")
    if tag_str:
        lines.append(f"tags: [{tag_str}]\n")
    lines.append("---\n\n")

    if entry.url:
        lines.append(f"## Source\n\n{entry.url}\n\n")

    lines.append(f"## Notes\n\n{entry.content}\n")

    return "".join(lines)


inbox_service = InboxService()
