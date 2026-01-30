from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SyncMeta:
    etag: Optional[str]
    sha256: Optional[str]
    size: Optional[int]
    updated_at: Optional[str]


class CacheRepo:
    """Pequeno DB local para cache/meta do sync e preview.

    IMPORTANT: o app usa workers (threads) para sync/preview, então esta conexão
    é criada com check_same_thread=False e protegida por lock.
    """

    def __init__(self, db_file: Path):
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_file), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._ensure_schema()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_meta (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    etag TEXT,
                    sha256 TEXT,
                    size INTEGER,
                    updated_at TEXT
                );
                """
            )
            cur.execute(
                """
                INSERT OR IGNORE INTO sync_meta(id, etag, sha256, size, updated_at)
                VALUES (1, NULL, NULL, NULL, NULL);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS preview_cache (
                    slug TEXT PRIMARY KEY,
                    tokens_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            self._conn.commit()

    def get_sync_meta(self) -> SyncMeta:
        with self._lock:
            row = self._conn.execute(
                "SELECT etag, sha256, size, updated_at FROM sync_meta WHERE id=1"
            ).fetchone()
        if not row:
            return SyncMeta(etag=None, sha256=None, size=None, updated_at=None)
        return SyncMeta(
            etag=row["etag"],
            sha256=row["sha256"],
            size=row["size"],
            updated_at=row["updated_at"],
        )

    def set_sync_meta(self, *, etag: Optional[str], sha256: Optional[str], size: Optional[int], updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sync_meta SET etag=?, sha256=?, size=?, updated_at=? WHERE id=1",
                (etag, sha256, size, updated_at),
            )
            self._conn.commit()

    def get_preview_tokens_json(self, slug: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT tokens_json FROM preview_cache WHERE slug=?",
                (slug,),
            ).fetchone()
        return row["tokens_json"] if row else None

    def set_preview_tokens_json(self, slug: str, tokens_json: str, updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO preview_cache(slug, tokens_json, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    tokens_json=excluded.tokens_json,
                    updated_at=excluded.updated_at
                """,
                (slug, tokens_json, updated_at),
            )
            self._conn.commit()
