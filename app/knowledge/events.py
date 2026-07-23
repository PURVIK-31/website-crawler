"""Typed, in-process stage events for manifest, logs, and metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from pydantic import Field

from app.knowledge.models import FrozenModel


class StageEvent(FrozenModel):
    stage: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageStarted(StageEvent):
    pass


class CacheHit(StageEvent):
    key: str
    record_id: str | None = None


class CacheMiss(StageEvent):
    key: str
    record_id: str | None = None


class ChunkCreated(StageEvent):
    chunk_id: str
    page_id: str


class EmbeddingGenerated(StageEvent):
    chunk_id: str
    profile_id: str


class ProviderFailed(StageEvent):
    provider: str
    message: str
    retryable: bool = False


class PageSkipped(StageEvent):
    page_id: str
    reason: str


class StageCompleted(StageEvent):
    output_count: int


class StageFailed(StageEvent):
    message: str
    retryable: bool = False


class EventSink(Protocol):
    def emit(self, event: StageEvent) -> None: ...


class NullEventSink:
    def emit(self, event: StageEvent) -> None:
        return None
