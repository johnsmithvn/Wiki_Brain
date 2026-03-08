import logging
import sqlite3
from threading import RLock

from backend.config import settings
from backend.models.schemas import SearchResult

logger = logging.getLogger(__name__)


class IndexService:
    def __init__(self) -> None:
        self.db_path = settings.DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._lock = RLock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _reset_db(self) -> None:
        """Delete corrupted DB and recreate from scratch."""
        logger.warning("Resetting corrupted database at %s", self.db_path)
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            try:
                self.db_path.unlink(missing_ok=True)
                # Also remove WAL/SHM files
                wal = self.db_path.with_suffix(".db-wal")
                shm = self.db_path.with_suffix(".db-shm")
                wal.unlink(missing_ok=True)
                shm.unlink(missing_ok=True)
            except Exception:
                logger.exception("Failed to delete DB files")
            self.initialize()

    def initialize(self) -> None:
        settings.ensure_dirs()
        with self._lock:
            try:
                conn = self._get_conn()
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS notes (
                        path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT DEFAULT '',
                        updated_at REAL NOT NULL
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                        path, title, content, tags,
                        content='notes',
                        content_rowid='rowid',
                        tokenize='porter unicode61'
                    );
                    CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                        INSERT INTO notes_fts(rowid, path, title, content, tags)
                        VALUES (new.rowid, new.path, new.title, new.content, new.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                        INSERT INTO notes_fts(notes_fts, rowid, path, title, content, tags)
                        VALUES ('delete', old.rowid, old.path, old.title, old.content, old.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                        INSERT INTO notes_fts(notes_fts, rowid, path, title, content, tags)
                        VALUES ('delete', old.rowid, old.path, old.title, old.content, old.tags);
                        INSERT INTO notes_fts(rowid, path, title, content, tags)
                        VALUES (new.rowid, new.path, new.title, new.content, new.tags);
                    END;
                """)
                conn.commit()
            except sqlite3.DatabaseError:
                logger.exception("Database corrupted during initialize")
                self._conn = None
                try:
                    self.db_path.unlink(missing_ok=True)
                except Exception:
                    pass
                # Retry once with fresh DB
                conn = self._get_conn()
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS notes (
                        path TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT DEFAULT '',
                        updated_at REAL NOT NULL
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                        path, title, content, tags,
                        content='notes',
                        content_rowid='rowid',
                        tokenize='porter unicode61'
                    );
                    CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                        INSERT INTO notes_fts(rowid, path, title, content, tags)
                        VALUES (new.rowid, new.path, new.title, new.content, new.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                        INSERT INTO notes_fts(notes_fts, rowid, path, title, content, tags)
                        VALUES ('delete', old.rowid, old.path, old.title, old.content, old.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                        INSERT INTO notes_fts(notes_fts, rowid, path, title, content, tags)
                        VALUES ('delete', old.rowid, old.path, old.title, old.content, old.tags);
                        INSERT INTO notes_fts(rowid, path, title, content, tags)
                        VALUES (new.rowid, new.path, new.title, new.content, new.tags);
                    END;
                """)
                conn.commit()
                logger.info("Database rebuilt successfully")

    def index_note(self, path: str, title: str, content: str, tags: list[str]) -> None:
        import time
        with self._lock:
            conn = self._get_conn()
            tags_str = " ".join(tags)
            conn.execute(
                """INSERT OR REPLACE INTO notes (path, title, content, tags, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (path, title, content, tags_str, time.time()),
            )
            conn.commit()

    def remove_note(self, path: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM notes WHERE path = ?", (path,))
            conn.commit()

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        with self._lock:
            conn = self._get_conn()
            # Escape special FTS5 characters and add * for prefix matching
            safe_query = query.replace('"', '""')
            fts_query = f'"{safe_query}"*'

            try:
                rows = conn.execute(
                    """SELECT
                            n.path,
                            n.title,
                            snippet(notes_fts, 2, '<mark>', '</mark>', '...', 40) as snippet,
                            rank
                       FROM notes_fts
                       JOIN notes n ON notes_fts.rowid = n.rowid
                       WHERE notes_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
            except sqlite3.DatabaseError:
                logger.exception("Search failed due to corrupted DB, resetting")
                self._reset_db()
                return []

            return [
                SearchResult(path=row[0], title=row[1], snippet=row[2], score=abs(row[3]))
                for row in rows
            ]

    def reindex_all(self, notes: list[dict]) -> None:
        import time
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM notes")
            now = time.time()
            conn.executemany(
                """INSERT INTO notes (path, title, content, tags, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [(n["path"], n["title"], n["content"], " ".join(n.get("tags", [])), now) for n in notes],
            )
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


index_service = IndexService()

