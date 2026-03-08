from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.models.schemas import TemplateContent, TemplateInfo


class TemplateService:
    def __init__(self) -> None:
        self.root = settings.TEMPLATE_DIR
        self.allowed = settings.ALLOWED_EXTENSIONS

    def _is_markdown(self, path: Path) -> bool:
        return path.suffix.lower() in self.allowed

    def _absolute(self, rel_path: str) -> Path:
        normalized = rel_path.replace("\\", "/").strip("/")
        resolved = (self.root / normalized).resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError:
            raise ValueError("Path traversal detected")
        return resolved

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _title_from_path(self, path: Path) -> str:
        return path.stem.replace("-", " ").replace("_", " ")

    def _is_hidden(self, rel_path: str) -> bool:
        return any(part.startswith(".") or part.startswith("_") for part in rel_path.split("/"))

    def list_templates(self, folder: str = "template") -> list[TemplateInfo]:
        if folder != settings.TEMPLATE_FOLDER:
            raise ValueError(f"Unsupported template folder: {folder}")

        templates: list[TemplateInfo] = []
        if not self.root.exists():
            return templates

        for path in sorted(self.root.rglob("*"), key=lambda p: p.as_posix().lower()):
            if not path.is_file() or not self._is_markdown(path):
                continue
            rel = self._relative(path)
            if self._is_hidden(rel):
                continue
            st = path.stat()
            templates.append(
                TemplateInfo(
                    path=rel,
                    name=path.stem,
                    title=self._title_from_path(path),
                    modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
                )
            )
        return templates

    def read_template(self, rel_path: str) -> TemplateContent:
        path = self._absolute(rel_path)
        if not path.exists() or not path.is_file() or not self._is_markdown(path):
            raise FileNotFoundError(f"Template not found: {rel_path}")
        content = path.read_text(encoding="utf-8")
        st = path.stat()
        return TemplateContent(
            path=self._relative(path),
            title=self._title_from_path(path),
            content=content,
            modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        )


template_service = TemplateService()
