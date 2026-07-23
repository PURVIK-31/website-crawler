"""Process-local key locks; v2 deliberately runs as one worker."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator


class KeyLocks:
    def __init__(self) -> None:
        self._master = Lock()
        self._locks: dict[str, Lock] = {}

    @contextmanager
    def hold(self, key: str) -> Iterator[None]:
        with self._master:
            lock = self._locks.setdefault(key, Lock())
        with lock:
            yield
