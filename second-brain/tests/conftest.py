"""
Test fixtures for Second Brain backend tests.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from backend.config import settings


@pytest.fixture
def tmp_knowledge_dir(tmp_path):
    """Create a temporary knowledge directory with sample notes."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    # Create sample notes
    (knowledge_dir / "Note A.md").write_text(
        "# Note A\nThis links to [[Note B]] and [[Note C|alias]].\n#tag-a #shared",
        encoding="utf-8",
    )
    (knowledge_dir / "Note B.md").write_text(
        "# Note B\nThis links back to [[Note A]].\n#tag-b #shared",
        encoding="utf-8",
    )
    (knowledge_dir / "Note C.md").write_text(
        "# Note C\nNo links here.\n#tag-c",
        encoding="utf-8",
    )

    # Create a subfolder with a note
    daily = knowledge_dir / "daily"
    daily.mkdir()
    (daily / "2026-03-08.md").write_text(
        "# Daily Note\nLinked to [[Note A]].\n#daily",
        encoding="utf-8",
    )

    # Save original and patch
    original_root = settings.KNOWLEDGE_DIR
    settings.KNOWLEDGE_DIR = knowledge_dir
    yield knowledge_dir
    settings.KNOWLEDGE_DIR = original_root


@pytest.fixture
def reset_services():
    """Reset singleton services between tests."""
    from backend.services.link_service import link_service
    from backend.services.tag_service import tag_service
    from backend.services.index_service import index_service

    # Clear state
    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()
    tag_service._note_tags.clear()
    if index_service._conn:
        index_service._conn.close()
    index_service._conn = None

    yield

    # Cleanup
    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()
    tag_service._note_tags.clear()


@pytest.fixture
def populated_services(tmp_knowledge_dir, reset_services):
    """Initialize services with sample data from tmp_knowledge_dir."""
    from backend.services.file_service import file_service
    from backend.services.link_service import link_service
    from backend.services.tag_service import tag_service
    from backend.services.index_service import index_service

    # Index all notes
    for path in tmp_knowledge_dir.rglob("*.md"):
        rel = path.relative_to(tmp_knowledge_dir).as_posix()
        content = path.read_text(encoding="utf-8")
        link_service.register_path(rel)

    # Second pass: update links and tags
    for path in tmp_knowledge_dir.rglob("*.md"):
        rel = path.relative_to(tmp_knowledge_dir).as_posix()
        content = path.read_text(encoding="utf-8")
        tags = tag_service.update_tags(rel, content)
        link_service.update_links(rel, content)
        title = path.stem.replace("-", " ").replace("_", " ")
        index_service.index_note(rel, title, content, tags)

    yield {
        "file_service": file_service,
        "link_service": link_service,
        "tag_service": tag_service,
        "index_service": index_service,
    }
