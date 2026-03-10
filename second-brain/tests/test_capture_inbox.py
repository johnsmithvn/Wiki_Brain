"""Tests for CaptureService + InboxService — capture, parse, convert."""

import pytest

from backend.config import settings
from backend.models.schemas import CaptureRequest
from backend.services.capture_service import (
    CaptureService,
    create_entry,
    detect_type,
    format_entry,
)
from backend.services.inbox_service import (
    InboxService,
    generate_note,
    parse_inbox_file,
    slugify,
    unique_path,
)


# ── detect_type ──────────────────────────────────────────────────


class TestDetectType:
    def test_url_param(self):
        assert detect_type("some text", "https://example.com") == "link"

    def test_url_in_content(self):
        assert detect_type("check https://example.com", None) == "link"

    def test_quote(self):
        assert detect_type('"Life is short"', None) == "quote"

    def test_note(self):
        assert detect_type("just a plain thought", None) == "note"


# ── create_entry ─────────────────────────────────────────────────


class TestCreateEntry:
    def test_basic(self):
        req = CaptureRequest(content="hello world", source="telegram")
        entry = create_entry(req)
        assert entry.source == "telegram"
        assert entry.content == "hello world"
        assert entry.type == "note"
        assert len(entry.id) == 19  # YYYYMMDD-HHMMSS-mmm (with milliseconds)

    def test_with_url(self):
        req = CaptureRequest(content="good article", source="browser", url="https://x.com")
        entry = create_entry(req)
        assert entry.type == "link"
        assert entry.url == "https://x.com"


# ── format_entry ─────────────────────────────────────────────────


class TestFormatEntry:
    def test_basic_format(self):
        from backend.models.schemas import InboxEntry

        entry = InboxEntry(
            id="20260309-143000",
            time="14:30",
            source="manual",
            type="note",
            content="Test content here",
        )
        formatted = format_entry(entry)
        assert "id: 20260309-143000" in formatted
        assert "source: manual" in formatted
        assert "Test content here" in formatted

    def test_format_with_url(self):
        from backend.models.schemas import InboxEntry

        entry = InboxEntry(
            id="20260309-143000",
            time="14:30",
            source="browser",
            type="link",
            url="https://example.com",
            content="Nice article",
        )
        formatted = format_entry(entry)
        assert "url: https://example.com" in formatted


# ── parse_inbox_file ─────────────────────────────────────────────


class TestParseInboxFile:
    def test_single_entry(self):
        text = """# Inbox — 2026-03-09

---

id: 20260309-143000
time: 14:30
source: manual
type: note

---

This is my note content.
"""
        entries = parse_inbox_file(text)
        assert len(entries) == 1
        assert entries[0].id == "20260309-143000"
        assert entries[0].source == "manual"
        assert "my note content" in entries[0].content

    def test_multiple_entries(self):
        text = """# Inbox — 2026-03-09

---

id: 20260309-143000
time: 14:30
source: telegram
type: link

---

https://example.com

---

id: 20260309-183000
time: 18:30
source: manual
type: note

---

Second entry content.
"""
        entries = parse_inbox_file(text)
        assert len(entries) == 2
        assert entries[0].id == "20260309-143000"
        assert entries[1].id == "20260309-183000"
        assert "example.com" in entries[0].content
        assert "Second entry" in entries[1].content

    def test_entry_with_tags(self):
        text = """# Inbox — 2026-03-09

---

id: 20260309-100000
time: 10:00
source: telegram
type: note
tags: [ai, python]

---

Tagged content.
"""
        entries = parse_inbox_file(text)
        assert len(entries) == 1
        assert entries[0].tags == ["ai", "python"]

    def test_empty_file(self):
        text = "# Inbox — 2026-03-09\n"
        entries = parse_inbox_file(text)
        assert len(entries) == 0


# ── slugify ──────────────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert slugify("My Great Note") == "my-great-note"

    def test_special_chars(self):
        assert slugify("Hello! @World#") == "hello-world"

    def test_empty(self):
        assert slugify("") == "untitled"

    def test_max_length(self):
        long_title = "A" * 200
        assert len(slugify(long_title)) <= 80


# ── unique_path ──────────────────────────────────────────────────


class TestUniquePath:
    def test_no_collision(self, tmp_path):
        result = unique_path(tmp_path, "test")
        assert result.name == "test.md"

    def test_collision(self, tmp_path):
        (tmp_path / "test.md").write_text("exists")
        result = unique_path(tmp_path, "test")
        assert result.name == "test-1.md"

    def test_multiple_collisions(self, tmp_path):
        (tmp_path / "test.md").write_text("exists")
        (tmp_path / "test-1.md").write_text("exists")
        result = unique_path(tmp_path, "test")
        assert result.name == "test-2.md"


# ── generate_note ────────────────────────────────────────────────


class TestGenerateNote:
    def test_basic_note(self):
        from backend.models.schemas import InboxEntry

        entry = InboxEntry(
            id="20260309-143000",
            time="14:30",
            source="manual",
            type="note",
            content="My captured thought",
        )
        result = generate_note(entry, "My Note", ["ai", "thought"])
        assert "title: My Note" in result
        assert "tags: [ai, thought]" in result
        assert "My captured thought" in result
        assert "captured: 2026-03-09" in result

    def test_note_with_url(self):
        from backend.models.schemas import InboxEntry

        entry = InboxEntry(
            id="20260309-143000",
            time="14:30",
            source="browser",
            type="link",
            url="https://example.com",
            content="Good article about AI",
        )
        result = generate_note(entry, "AI Article", [])
        assert "source: https://example.com" in result
        assert "## Source" in result


# ── CaptureService (integration) ────────────────────────────────


class TestCaptureServiceIntegration:
    @pytest.fixture
    def setup_inbox(self, tmp_path):
        original = settings.KNOWLEDGE_DIR
        settings.KNOWLEDGE_DIR = tmp_path / "knowledge"
        settings.KNOWLEDGE_DIR.mkdir()
        (settings.KNOWLEDGE_DIR / "inbox").mkdir()
        yield
        settings.KNOWLEDGE_DIR = original

    @pytest.mark.asyncio
    async def test_capture_creates_inbox_file(self, setup_inbox):
        svc = CaptureService()
        req = CaptureRequest(content="test capture", source="manual")
        entry, date_str = await svc.capture(req)

        inbox_file = settings.KNOWLEDGE_DIR / "inbox" / f"{date_str}.md"
        assert inbox_file.exists()
        text = inbox_file.read_text(encoding="utf-8")
        assert "test capture" in text
        assert entry.id in text


# ── InboxService (integration) ───────────────────────────────────


class TestInboxServiceIntegration:
    @pytest.fixture
    def setup_inbox(self, tmp_path):
        original = settings.KNOWLEDGE_DIR
        settings.KNOWLEDGE_DIR = tmp_path / "knowledge"
        settings.KNOWLEDGE_DIR.mkdir()
        inbox_dir = settings.KNOWLEDGE_DIR / "inbox"
        inbox_dir.mkdir()

        # Create a sample inbox file
        (inbox_dir / "2026-03-09.md").write_text(
            """# Inbox — 2026-03-09

---

id: 20260309-143000
time: 14:30
source: telegram
type: note

---

First entry content.

---

id: 20260309-183000
time: 18:30
source: manual
type: link
url: https://example.com

---

Second entry with URL.
""",
            encoding="utf-8",
        )
        yield
        settings.KNOWLEDGE_DIR = original

    def test_list_dates(self, setup_inbox):
        svc = InboxService()
        dates = svc.list_dates()
        assert len(dates) == 1
        assert dates[0].date == "2026-03-09"
        assert dates[0].count == 2

    def test_get_entries(self, setup_inbox):
        svc = InboxService()
        entries = svc.get_entries("2026-03-09")
        assert len(entries) == 2
        assert entries[0].source == "telegram"
        assert entries[1].url == "https://example.com"

    @pytest.mark.asyncio
    async def test_delete_entry(self, setup_inbox):
        svc = InboxService()
        deleted = await svc.delete_entry("2026-03-09", "20260309-143000")
        assert deleted is True

        # Verify only one entry remains
        entries = svc.get_entries("2026-03-09")
        assert len(entries) == 1
        assert entries[0].id == "20260309-183000"

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, setup_inbox):
        svc = InboxService()
        deleted = await svc.delete_entry("2026-03-09", "nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_convert_entry(self, setup_inbox):
        svc = InboxService()
        note_path = await svc.convert_entry_to_note(
            date_str="2026-03-09",
            entry_id="20260309-143000",
            title="Converted Note",
            folder="",
            tags=["test"],
        )
        assert note_path is not None
        assert note_path.endswith(".md")

        # Verify note file was created
        full_path = settings.KNOWLEDGE_DIR / note_path
        assert full_path.exists()
        content = full_path.read_text(encoding="utf-8")
        assert "title: Converted Note" in content
        assert "First entry content" in content

        # Verify entry was removed from inbox
        entries = svc.get_entries("2026-03-09")
        assert len(entries) == 1
