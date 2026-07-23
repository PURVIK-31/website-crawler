"""Minimal processor context. Providers and persistence stay outside processors."""

from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.events import EventSink
from app.knowledge.metrics import MetricsRecorder
from app.knowledge.run_logger import RunLogger
from app.knowledge.settings import KnowledgeSettings


@dataclass(frozen=True, slots=True)
class ProcessorContext:
    asset_id: str
    asset_version: str
    run_id: str
    settings: KnowledgeSettings
    logger: RunLogger
    metrics: MetricsRecorder
    events: EventSink
