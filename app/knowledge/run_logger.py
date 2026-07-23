"""Run-scoped structured logging without per-call correlation boilerplate."""

from __future__ import annotations

from typing import Any, Protocol

import structlog


class RunLogger(Protocol):
    def info(self, event: str, **values: Any) -> None: ...
    def warning(self, event: str, **values: Any) -> None: ...
    def error(self, event: str, **values: Any) -> None: ...


def create_run_logger(run_id: str, asset_id: str, stage: str | None = None) -> RunLogger:
    values: dict[str, str] = {"run_id": run_id, "asset_id": asset_id}
    if stage:
        values["stage"] = stage
    return structlog.get_logger(__name__).bind(**values)
