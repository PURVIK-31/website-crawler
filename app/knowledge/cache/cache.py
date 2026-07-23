"""Cache facade that keeps payload, metadata, and locking concerns separate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.knowledge.cache.filesystem import ObjectFilesystem
from app.knowledge.cache.locks import KeyLocks
from app.knowledge.cache.metadata import CacheMetadata


class CacheStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = ObjectFilesystem(root / "objects")
        self.metadata = CacheMetadata(root / "metadata.sqlite")
        self.locks = KeyLocks()

    @staticmethod
    def fingerprint(*parts: str) -> str:
        value = "\x1f".join(parts).encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    def get_json(self, key: str) -> dict[str, Any] | None:
        entry = self.metadata.get(key)
        if not entry:
            return None
        text = self.objects.read_text(key)
        if text is None or hashlib.sha256(text.encode("utf-8")).hexdigest() != entry[1]:
            return None
        return json.loads(text)

    def put_json(self, key: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self.locks.hold(key):
            path = self.objects.write_text(key, payload)
            self.metadata.put(key, str(path), checksum)
