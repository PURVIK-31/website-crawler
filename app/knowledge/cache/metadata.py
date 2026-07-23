"""SQLite lookup metadata for immutable cache objects."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class CacheMetadata:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY, object_path TEXT NOT NULL,
                sha256 TEXT NOT NULL, created_at TEXT NOT NULL)"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def get(self, key: str) -> tuple[str, str] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT object_path, sha256 FROM cache_entries WHERE cache_key = ?", (key,)
            ).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def put(self, key: str, object_path: str, sha256: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries(cache_key, object_path, sha256, created_at) VALUES (?, ?, ?, ?)",
                (key, object_path, sha256, datetime.now(timezone.utc).isoformat()),
            )
