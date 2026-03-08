from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from backend.config import settings
from backend.models.schemas import FileTreeItem, NoteMetadata


class FileService:
    def __init__(self) -> None:
        self.root = settings.KNOWLEDGE_DIR
        self.allowed = settings.ALLOWED_EXTENSIONS

    def _is_markdown(self, path: Path) -> bool:
        return path.suffix.lower() in self.allowed

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _absolute(self, rel_path: str) -> Path:
        resolved = (self.root / rel_path).resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError:
            raise ValueError("Path traversal detected")
        return resolved

    def _title_from_path(self, path: Path) -> str:
        return path.stem.replace("-", " ").replace("_", " ")

    def _is_hidden_or_excluded(self, rel_path: str) -> bool:
        parts = rel_path.replace("\\", "/").split("/")
        if not parts:
            return False
        if settings.is_excluded_from_index(rel_path):
            return True
        for part in parts:
            if part.startswith(".") or part.startswith("_"):
                return True
        return False

    def _get_metadata(self, path: Path) -> NoteMetadata:
        st = path.stat()
        return NoteMetadata(
            path=self._relative(path),
            title=self._title_from_path(path),
            created_at=datetime.fromtimestamp(st.st_ctime, tz=timezone.utc),
            modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
            size=st.st_size,
        )

    def get_file_tree(self) -> list[FileTreeItem]:
        return self._build_tree(self.root)

    def _build_tree(self, directory: Path) -> list[FileTreeItem]:
        items: list[FileTreeItem] = []
        if not directory.exists():
            return items

        entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for entry in entries:
            rel = self._relative(entry)
            if self._is_hidden_or_excluded(rel):
                continue
            if entry.is_dir():
                children = self._build_tree(entry)
                items.append(FileTreeItem(
                    name=entry.name,
                    path=self._relative(entry),
                    is_dir=True,
                    children=children,
                ))
            elif self._is_markdown(entry):
                items.append(FileTreeItem(
                    name=entry.stem,
                    path=self._relative(entry),
                    is_dir=False,
                ))
        return items

    def list_all_notes(self) -> list[NoteMetadata]:
        notes: list[NoteMetadata] = []
        for path in self.root.rglob("*"):
            if not self._is_markdown(path):
                continue
            rel = self._relative(path)
            if self._is_hidden_or_excluded(rel):
                continue
            if path.name.startswith("."):
                continue
            if path.is_file():
                notes.append(self._get_metadata(path))
        return notes

    async def read_file(self, rel_path: str) -> str:
        path = self._absolute(rel_path)
        if not path.exists() or not self._is_markdown(path):
            raise FileNotFoundError(f"Note not found: {rel_path}")
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()

    async def write_file(self, rel_path: str, content: str) -> NoteMetadata:
        path = self._absolute(rel_path)
        if not self._is_markdown(path):
            rel_path = rel_path + ".md"
            path = self._absolute(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)
        return self._get_metadata(path)

    async def delete_file(self, rel_path: str) -> None:
        path = self._absolute(rel_path)
        if not path.exists():
            raise FileNotFoundError(f"Note not found: {rel_path}")
        path.unlink()
        # Clean up empty parent directories
        parent = path.parent
        while parent != self.root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    async def rename_file(self, old_path: str, new_path: str) -> NoteMetadata:
        src = self._absolute(old_path)
        if not src.exists() or not src.is_file() or not self._is_markdown(src):
            raise FileNotFoundError(f"Note not found: {old_path}")
        if not new_path.endswith(".md"):
            new_path += ".md"
        dst = self._absolute(new_path)
        if src == dst:
            return self._get_metadata(src)
        if dst.exists():
            raise FileExistsError(f"Destination already exists: {new_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return self._get_metadata(dst)

    def create_folder(self, rel_path: str) -> None:
        path = self._absolute(rel_path)
        if path.exists():
            raise FileExistsError(f"Folder already exists: {rel_path}")
        path.mkdir(parents=True, exist_ok=True)

    def rename_folder(self, old_path: str, new_path: str) -> str:
        src = self._absolute(old_path)
        if src == self.root:
            raise ValueError("Cannot rename root folder")
        if not src.exists() or not src.is_dir():
            raise FileNotFoundError(f"Folder not found: {old_path}")

        dst = self._absolute(new_path)
        if src == dst:
            return self._relative(src)
        if dst.exists():
            raise FileExistsError(f"Destination already exists: {new_path}")

        try:
            dst.relative_to(src)
        except ValueError:
            pass
        else:
            raise ValueError("Cannot move a folder into itself")

        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return self._relative(dst)

    def exists(self, rel_path: str) -> bool:
        path = self._absolute(rel_path)
        if not self._is_markdown(path):
            path = self._absolute(rel_path + ".md")
        return path.exists() and path.is_file()

    def get_metadata(self, rel_path: str) -> NoteMetadata:
        path = self._absolute(rel_path)
        if not path.exists():
            raise FileNotFoundError(f"Note not found: {rel_path}")
        return self._get_metadata(path)


file_service = FileService()
