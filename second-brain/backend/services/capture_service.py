"""
Capture Service — Parse raw captures and append to inbox files.

Flow: raw text/URL → InboxEntry → append to knowledge/inbox/YYYY-MM-DD.md
Concurrent writes protected by per-file asyncio.Lock.
"""

import logging
import re
from asyncio import Lock
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import aiofiles

from backend.config import settings
from backend.models.schemas import CaptureRequest, InboxEntry

logger = logging.getLogger(__name__)

# Per-file locks — prevent concurrent writes corrupting inbox markdown.
# Bounded by number of unique date files (practical max ~365/year).
_inbox_locks: dict[str, Lock] = defaultdict(Lock)

URL_PATTERN = re.compile(r"https?://\S+")


def detect_type(content: str, url: str | None) -> str:
    """Detect entry type. Simple rules, type is UI hint only."""
    if url:
        return "link"
    if content.strip().startswith('"') or content.strip().startswith("\u201c"):
        return "quote"
    if URL_PATTERN.search(content):
        return "link"
    return "note"


def create_entry(request: CaptureRequest) -> InboxEntry:
    """Create a structured inbox entry from a capture request."""
    now = datetime.now()
    # Include microseconds to avoid ID collisions for same-second captures
    entry_id = now.strftime("%Y%m%d-%H%M%S") + f"-{now.microsecond // 1000:03d}"
    entry_type = detect_type(request.content, request.url)

    return InboxEntry(
        id=entry_id,
        time=now.strftime("%H:%M"),
        source=request.source,
        type=entry_type,
        url=request.url,
        content=request.content,
    )


def format_entry(entry: InboxEntry) -> str:
    """Format an inbox entry as markdown block."""
    lines = [
        "\n---\n",
        f"id: {entry.id}\n",
        f"time: {entry.time}\n",
        f"source: {entry.source}\n",
        f"type: {entry.type}\n",
    ]
    if entry.url:
        lines.append(f"url: {entry.url}\n")
    if entry.tags:
        lines.append(f"tags: [{', '.join(entry.tags)}]\n")
    lines.append("\n---\n\n")
    lines.append(entry.content + "\n")
    return "".join(lines)


def _get_inbox_dir() -> Path:
    """Return inbox directory, creating if needed."""
    inbox_dir = settings.KNOWLEDGE_DIR / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def _get_inbox_file(date_str: str | None = None) -> Path:
    """Return path to today's (or specific date's) inbox file."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return _get_inbox_dir() / f"{date_str}.md"


async def append_to_inbox(entry: InboxEntry) -> str:
    """Append entry to today's inbox file. Returns the date string.

    Thread-safe via per-file asyncio.Lock.
    """
    date_str = entry.id[:4] + "-" + entry.id[4:6] + "-" + entry.id[6:8]
    file_path = _get_inbox_file(date_str)

    async with _inbox_locks[str(file_path)]:
        if not file_path.exists():
            # Create new inbox file with header
            header = f"# Inbox — {date_str}\n"
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(header)

        formatted = format_entry(entry)
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(formatted)

    logger.info("Captured entry %s to inbox/%s.md", entry.id, date_str)
    return date_str


class CaptureService:
    """Orchestrate capture flow: parse → append → (optional) scrape."""

    async def capture(self, request: CaptureRequest) -> tuple[InboxEntry, str]:
        """Process a capture request.

        If a URL is provided OR detected in content, attempts to scrape
        article content and enriches the entry. Scraping failure is non-blocking.

        Returns:
            Tuple of (entry, date_string).
        """
        entry = create_entry(request)

        # Try to scrape URL if present
        url = request.url
        if not url:
            # Check if content itself contains a URL
            match = URL_PATTERN.search(request.content)
            if match:
                url = match.group(0)

        if url and entry.type == "link":
            try:
                from backend.services.scraper_service import scrape_url

                article = await scrape_url(url)
                if article and article.content:
                    scraped_section = f"\n\n---\n**Scraped: {article.title or 'Untitled'}**"
                    if article.author:
                        scraped_section += f"\nAuthor: {article.author}"
                    if article.reading_time:
                        scraped_section += f" · {article.reading_time} min read"
                    scraped_section += f"\n\n{article.content[:2000]}"
                    if len(article.content) > 2000:
                        scraped_section += "\n\n[...truncated]"
                    entry.content = entry.content + scraped_section
                    logger.info("Scraped article enrichment for %s", url)
            except Exception as e:
                logger.warning("Scraping failed for %s: %s (non-blocking)", url, e)

        date_str = await append_to_inbox(entry)
        return entry, date_str


capture_service = CaptureService()
