"""Immutable data contracts for the knowledge ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AssetStatus(str, Enum):
    QUEUED = "queued"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactEntry(FrozenModel):
    name: str
    path: str
    sha256: str
    rows: int | None = None
    schema_version: str
    created_at: datetime


class ErrorEntry(FrozenModel):
    category: str
    stage: str
    message: str
    retryable: bool = False
    record_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageRecord(FrozenModel):
    name: str
    version: str
    status: StageStatus = StageStatus.PENDING
    input_fingerprint: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    output_count: int = 0
    error: ErrorEntry | None = None


class PageAsset(FrozenModel):
    schema_version: str = "1.0"
    page_id: str
    canonical_url: str
    title: str = ""
    headings: tuple[dict[str, Any], ...] = ()
    content: str = ""
    meta_description: str = ""
    crawled_at: datetime
    content_hash: str
    fast_content_hash: str
    raw_uri: str | None = None
    fetch_method: str | None = None


class ChunkAsset(FrozenModel):
    schema_version: str = "1.0"
    chunk_id: str
    page_id: str
    ordinal: int
    text: str
    heading_path: tuple[str, ...] = ()
    token_count: int
    content_hash: str


class EmbeddingAsset(FrozenModel):
    schema_version: str = "1.0"
    chunk_id: str
    profile_id: str
    dimension: int
    vector: tuple[float, ...]
    processing_fingerprint: str


class AssetManifest(FrozenModel):
    manifest_version: str = "1.0"
    schema_versions: dict[str, str] = Field(
        default_factory=lambda: {"page": "1.0", "chunk": "1.0", "embedding": "1.0"}
    )
    asset_id: str
    asset_version: str
    run_id: str
    status: AssetStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    crawl_config_hash: str
    source_scope: tuple[str, ...]
    artifacts: tuple[ArtifactEntry, ...] = ()
    stages: tuple[StageRecord, ...] = ()
    errors: tuple[ErrorEntry, ...] = ()
    provider_profiles: tuple[str, ...] = ()
