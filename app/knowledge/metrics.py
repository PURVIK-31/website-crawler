"""Metrics boundary with a no-op local default."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator, Protocol


class MetricsRecorder(Protocol):
    def counter(self, name: str, value: int = 1, **labels: str) -> None: ...
    def histogram(self, name: str, value: float, **labels: str) -> None: ...
    def gauge(self, name: str, value: float, **labels: str) -> None: ...
    def timer(self, name: str, **labels: str) -> Iterator[None]: ...


class NoopMetricsRecorder:
    def counter(self, name: str, value: int = 1, **labels: str) -> None:
        return None

    def histogram(self, name: str, value: float, **labels: str) -> None:
        return None

    def gauge(self, name: str, value: float, **labels: str) -> None:
        return None

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        start = perf_counter()
        try:
            yield
        finally:
            self.histogram(name, perf_counter() - start, **labels)
