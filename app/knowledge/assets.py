"""Atomic versioned asset persistence; Parquet is canonical, vectors are derived."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.knowledge.errors import AssetNotFoundError, StorageError
from app.knowledge.models import ArtifactEntry, AssetManifest, ChunkAsset, EmbeddingAsset, PageAsset


class AssetStore:
    def __init__(self, storage_root: Path) -> None:
        self.root = storage_root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)

    def version_dir(self, asset_id: str, asset_version: str) -> Path:
        return self.root / asset_id / asset_version

    def create_version(self, asset_id: str, asset_version: str) -> Path:
        path = self.version_dir(asset_id, asset_version)
        if path.exists():
            raise StorageError(f"Asset version already exists: {asset_id}/{asset_version}")
        path.mkdir(parents=True)
        return path

    def write_manifest(self, manifest: AssetManifest) -> Path:
        path = self.version_dir(manifest.asset_id, manifest.asset_version) / "manifest.json"
        if not path.parent.exists():
            raise AssetNotFoundError(f"Unknown asset version: {manifest.asset_id}/{manifest.asset_version}")
        self._atomic_json(path, manifest.model_dump(mode="json"))
        return path

    def read_manifest(self, asset_id: str, asset_version: str) -> AssetManifest:
        path = self.version_dir(asset_id, asset_version) / "manifest.json"
        if not path.exists():
            raise AssetNotFoundError(f"Unknown asset version: {asset_id}/{asset_version}")
        return AssetManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def list_manifests(self) -> list[AssetManifest]:
        manifests: list[AssetManifest] = []
        for path in self.root.glob("*/*/manifest.json"):
            manifests.append(AssetManifest.model_validate_json(path.read_text(encoding="utf-8")))
        return sorted(manifests, key=lambda item: item.created_at, reverse=True)

    def write_pages(self, asset_id: str, version: str, records: Iterable[PageAsset]) -> ArtifactEntry:
        return self._write_parquet(asset_id, version, "pages", [item.model_dump(mode="json") for item in records], "1.0")

    def write_chunks(self, asset_id: str, version: str, records: Iterable[ChunkAsset]) -> ArtifactEntry:
        return self._write_parquet(asset_id, version, "chunks", [item.model_dump(mode="json") for item in records], "1.0")

    def write_embeddings(self, asset_id: str, version: str, records: Iterable[EmbeddingAsset]) -> ArtifactEntry:
        return self._write_parquet(asset_id, version, "embeddings", [item.model_dump(mode="json") for item in records], "1.0")

    def _write_parquet(self, asset_id: str, version: str, name: str, rows: list[dict], schema_version: str) -> ArtifactEntry:
        directory = self.version_dir(asset_id, version)
        if not directory.exists():
            raise AssetNotFoundError(f"Unknown asset version: {asset_id}/{version}")
        path = directory / f"{name}.parquet"
        temp = directory / f".{name}.tmp.parquet"
        columns = {
            "pages": ["schema_version", "page_id", "canonical_url", "title", "headings", "content", "meta_description", "crawled_at", "content_hash", "fast_content_hash", "raw_uri", "fetch_method"],
            "chunks": ["schema_version", "chunk_id", "page_id", "ordinal", "text", "heading_path", "token_count", "content_hash"],
            "embeddings": ["schema_version", "chunk_id", "profile_id", "dimension", "vector", "processing_fingerprint"],
        }[name]
        pd.DataFrame(rows, columns=columns).to_parquet(temp, index=False, engine="pyarrow")
        os.replace(temp, path)
        return ArtifactEntry(
            name=name,
            path=path.relative_to(self.root.parent).as_posix(),
            sha256=self._sha256(path),
            rows=len(rows),
            schema_version=schema_version,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _atomic_json(path: Path, value: dict) -> None:
        temp = path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(8192), b""):
                digest.update(block)
        return digest.hexdigest()
