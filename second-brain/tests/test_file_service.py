"""Tests for FileService — file operations and path safety."""

import pytest

from backend.services.file_service import FileService
from backend.config import settings


@pytest.fixture
def file_svc(tmp_path):
    """Create a FileService with a temp root directory."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    original_root = settings.KNOWLEDGE_DIR
    settings.KNOWLEDGE_DIR = knowledge_dir

    svc = FileService()
    svc.root = knowledge_dir

    yield svc

    settings.KNOWLEDGE_DIR = original_root


class TestPathSafety:
    def test_path_traversal_blocked(self, file_svc):
        with pytest.raises(ValueError, match="traversal"):
            file_svc._absolute("../../etc/passwd")

    def test_normal_path_allowed(self, file_svc):
        path = file_svc._absolute("notes/test.md")
        assert path.name == "test.md"


class TestCRUD:
    @pytest.mark.asyncio
    async def test_write_and_read(self, file_svc):
        meta = await file_svc.write_file("test.md", "# Hello World")
        assert meta.path == "test.md"
        content = await file_svc.read_file("test.md")
        assert content == "# Hello World"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, file_svc):
        meta = await file_svc.write_file("deep/nested/note.md", "content")
        assert meta.path == "deep/nested/note.md"
        content = await file_svc.read_file("deep/nested/note.md")
        assert content == "content"

    @pytest.mark.asyncio
    async def test_delete_file(self, file_svc):
        await file_svc.write_file("to-delete.md", "bye")
        await file_svc.delete_file("to-delete.md")
        with pytest.raises(FileNotFoundError):
            await file_svc.read_file("to-delete.md")

    @pytest.mark.asyncio
    async def test_rename_file(self, file_svc):
        await file_svc.write_file("old-name.md", "# Note")
        meta = await file_svc.rename_file("old-name.md", "new-name.md")
        assert meta.path == "new-name.md"
        content = await file_svc.read_file("new-name.md")
        assert content == "# Note"

    @pytest.mark.asyncio
    async def test_rename_to_existing_raises(self, file_svc):
        await file_svc.write_file("a.md", "a")
        await file_svc.write_file("b.md", "b")
        with pytest.raises(FileExistsError):
            await file_svc.rename_file("a.md", "b.md")


class TestFileTree:
    @pytest.mark.asyncio
    async def test_tree_structure(self, file_svc):
        await file_svc.write_file("root.md", "root")
        await file_svc.write_file("folder/nested.md", "nested")
        tree = file_svc.get_file_tree()
        names = [item.name for item in tree]
        assert "folder" in names
        assert "root" in names

    @pytest.mark.asyncio
    async def test_hidden_files_excluded(self, file_svc):
        await file_svc.write_file(".hidden.md", "hidden")
        await file_svc.write_file("visible.md", "visible")
        tree = file_svc.get_file_tree()
        names = [item.name for item in tree]
        assert "visible" in names
        assert ".hidden" not in names


class TestExists:
    @pytest.mark.asyncio
    async def test_exists_true(self, file_svc):
        await file_svc.write_file("exists.md", "yes")
        assert file_svc.exists("exists.md") is True

    @pytest.mark.asyncio
    async def test_exists_false(self, file_svc):
        assert file_svc.exists("nope.md") is False
