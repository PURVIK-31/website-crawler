"""Atomic payload storage for cache objects."""

from __future__ import annotations

import os
from pathlib import Path


class ObjectFilesystem:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def read_text(self, key: str) -> str | None:
        path = self.path_for(key)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def write_text(self, key: str, payload: str) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        return path
