"""
Watcher Service — Filesystem monitoring with async processing queue.

Watchdog runs in a background thread. Events are debounced and pushed
onto an asyncio.Queue, consumed by an async worker that calls note_pipeline.
"""

import asyncio
import logging
import time
from pathlib import Path
from threading import Lock

from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers import Observer

from backend.config import settings
from backend.services.file_service import file_service
from backend.services.note_pipeline import note_pipeline

logger = logging.getLogger(__name__)


class _VaultEventHandler(FileSystemEventHandler):
    """Debounce filesystem events and enqueue for async processing."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, debounce_ms: int = 800) -> None:
        super().__init__()
        self._queue = queue
        self._loop = loop
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
            # Prune stale entries every 100 checks to prevent unbounded growth
            if len(self._recent) > 500:
                cutoff = now - self._debounce_s * 10
                self._recent = {k: v for k, v in self._recent.items() if v > cutoff}

            last = self._recent.get(key)
            if last is not None and now - last < self._debounce_s:
                return False
            self._recent[key] = now
            return True

    def _enqueue(self, action: str, rel_path: str) -> None:
        """Thread-safe enqueue into the asyncio event loop."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (action, rel_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"created:{rel}"):
            return
        self._enqueue("upsert", rel)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"modified:{rel}"):
            return
        self._enqueue("upsert", rel)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._normalize_rel_path(event.src_path)
        if not rel or not self._should_process(f"deleted:{rel}"):
            return
        self._enqueue("delete", rel)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        if event.is_directory:
            return
        src_rel = self._normalize_rel_path(event.src_path)
        dst_rel = self._normalize_rel_path(event.dest_path)

        if src_rel and self._should_process(f"moved-src:{src_rel}"):
            self._enqueue("delete", src_rel)
        if dst_rel and self._should_process(f"moved-dst:{dst_rel}"):
            self._enqueue("upsert", dst_rel)


class WatcherService:
    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._queue: asyncio.Queue | None = None
        self._worker_task: asyncio.Task | None = None

    async def _worker(self) -> None:
        """Async worker: consume queue items and run note_pipeline."""
        while True:
            action, rel_path = await self._queue.get()
            try:
                if action == "upsert":
                    try:
                        abs_path = file_service._absolute(rel_path)
                        content = await asyncio.to_thread(
                            abs_path.read_text, encoding="utf-8"
                        )
                        await note_pipeline.process_note(rel_path, content)
                        logger.info("Watcher reindexed note: %s", rel_path)
                    except FileNotFoundError:
                        note_pipeline.remove_note(rel_path)
                        logger.info("Watcher removed (not found): %s", rel_path)
                elif action == "delete":
                    note_pipeline.remove_note(rel_path)
                    logger.info("Watcher removed note from indexes: %s", rel_path)
            except Exception as e:
                logger.warning("Watcher worker failed on %s %s: %s", action, rel_path, e)
            finally:
                self._queue.task_done()

    def start(self) -> None:
        if self._observer and self._observer.is_alive():
            return

        loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._worker_task = loop.create_task(self._worker())

        handler = _VaultEventHandler(self._queue, loop)
        observer = Observer()
        observer.schedule(handler, str(settings.KNOWLEDGE_DIR), recursive=True)
        observer.start()
        self._observer = observer
        logger.info("Filesystem watcher started at %s (async queue)", settings.KNOWLEDGE_DIR)

    def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None
        if not self._observer:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        logger.info("Filesystem watcher stopped")


watcher_service = WatcherService()
