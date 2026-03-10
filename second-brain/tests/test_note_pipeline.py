"""Tests for NotePipeline — single entry point for note indexing."""

import pytest

from backend.config import settings
from backend.services.note_pipeline import NotePipeline


@pytest.fixture
def setup_env(tmp_path):
    """Set up temp knowledge dir and reset services."""
    from backend.services.index_service import index_service
    from backend.services.link_service import link_service
    from backend.services.tag_service import tag_service

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    original = settings.KNOWLEDGE_DIR
    original_db = settings.DB_PATH
    settings.KNOWLEDGE_DIR = knowledge_dir
    settings.DB_PATH = tmp_path / "data" / "index.db"

    # Clear service state
    link_service._forward.clear()
    link_service._backward.clear()
    link_service._all_paths.clear()
    tag_service._note_tags.clear()
    if index_service._conn:
        index_service._conn.close()
    index_service._conn = None
    index_service.db_path = settings.DB_PATH

    # Init index
    settings.ensure_dirs()
    index_service.initialize()

    yield knowledge_dir

    # Restore
    if index_service._conn:
        index_service._conn.close()
    index_service._conn = None
    settings.KNOWLEDGE_DIR = original
    settings.DB_PATH = original_db


class TestNotePipeline:
    @pytest.mark.asyncio
    async def test_process_note(self, setup_env):
        from backend.services.file_service import file_service
        from backend.services.index_service import index_service
        from backend.services.link_service import link_service
        from backend.services.tag_service import tag_service

        knowledge_dir = setup_env
        file_svc = file_service
        file_svc.root = knowledge_dir

        # Write a note
        await file_svc.write_file("test.md", "# Test\n#python\nSome content about [[Other]]")

        pipeline = NotePipeline()
        tags = await pipeline.process_note("test.md", "# Test\n#python\nSome content about [[Other]]")

        assert "python" in tags
        assert tag_service.get_tags_for_note("test.md") == ["python"]
        results = index_service.search("Test")
        assert any(r.path == "test.md" for r in results)

    @pytest.mark.asyncio
    async def test_remove_note(self, setup_env):
        from backend.services.file_service import file_service
        from backend.services.index_service import index_service
        from backend.services.tag_service import tag_service

        knowledge_dir = setup_env
        file_svc = file_service
        file_svc.root = knowledge_dir

        await file_svc.write_file("to-remove.md", "# Remove Me\n#temp")

        pipeline = NotePipeline()
        await pipeline.process_note("to-remove.md", "# Remove Me\n#temp")
        assert tag_service.get_tags_for_note("to-remove.md") == ["temp"]

        pipeline.remove_note("to-remove.md")
        assert tag_service.get_tags_for_note("to-remove.md") == []
        results = index_service.search("Remove")
        assert not any(r.path == "to-remove.md" for r in results)
