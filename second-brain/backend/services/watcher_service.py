import logging
import time
from pathlib import Path
from threading import Lock

from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers import Observer

from backend.config import settings
from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service

logger = logging.getLogger(__name__)


class _VaultEventHandler(FileSystemEventHandler):
    def __init__(self, debounce_ms: int = 800) -> None:
        super().__init__()
        self._debounce_s = debounce_ms / 1000
        self._recent: dict[str, float] = {}
        self._lock = Lock()

    def _normalize_rel_path(self, raw_path: str) -> str | None:
        try:
            abs_path = Path(raw_path).resolve()
            rel = abs_path.relative_to(settings.KNOWLEDGE_DIR.resolve()).as_posix()
        except Exception:
            return None

        if settings.is_excluded_from_index(rel):
            return None

        if abs_path.suffix.lower() not in settings.ALLOWED_EXTENSIONS:
            return None

        return rel

    def _should_process(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._recent.get(key)
            if last is not None and now - last < self._debounce_s:
                return False
            self._recent[key] = now
            return True

    def _upsert_note(self, rel_path: str) -> None:
        try:
            content = file_service._absolute(rel_path).read_text(encoding="utf-8")
            metadata = file_service.get_metadata(rel_path)
            tags = tag_service.update_tags(rel_path, content)
            link_service.update_links(rel_path, content)
            index_service.index_note(rel_path, metadata.title, content, tags)
            logger.info("Watcher reindexed note: %s", rel_path)
        except FileNotFoundError:
            self._delete_note(rel_path)
        except Exception as e:
            logger.warning("Watcher failed to index %s: %s", rel_path, e)

    def _delete_note(self, rel_path: str) -> None:
        try:
            index_service.remove_note(rel_path)
            link_service.remove_note(rel_path)
            tag_service.remove_note(rel_path)
            logger.info("Watcher removed note from indexes: %s", rel_path)
        except Exception as e:
            logger.warning("Watcher failed to remove %s: %s", rel_path, e)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"created:{rel}"):
            return
        self._upsert_note(rel)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"modified:{rel}"):
            return
        self._upsert_note(rel)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"deleted:{rel}"):
            return
        self._delete_note(rel)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        if event.is_directory:
            return
        src_rel = self._normalize_rel_path(event.src_path)
        dst_rel = self._normalize_rel_path(event.dest_path)

        # Moved out of watched index scope.
        if src_rel and self._should_process(f"moved-src:{src_rel}"):
            self._delete_note(src_rel)
        # Moved into watched index scope.
        if dst_rel and self._should_process(f"moved-dst:{dst_rel}"):
            self._upsert_note(dst_rel)


class WatcherService:
    def __init__(self) -> None:
        self._observer: Observer | None = None

    def start(self) -> None:
        if self._observer and self._observer.is_alive():
            return
        handler = _VaultEventHandler()
        observer = Observer()
        observer.schedule(handler, str(settings.KNOWLEDGE_DIR), recursive=True)
        observer.start()
        self._observer = observer
        logger.info("Filesystem watcher started at %s", settings.KNOWLEDGE_DIR)

    def stop(self) -> None:
        if not self._observer:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        logger.info("Filesystem watcher stopped")


watcher_service = WatcherService()
