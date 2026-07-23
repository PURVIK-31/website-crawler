"""LanceDB is a derived index that can be rebuilt from embedding artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from app.knowledge.errors import ConfigurationError
from app.knowledge.models import ChunkAsset, EmbeddingAsset, PageAsset


class VectorFilter:
    """Builds LanceDB SQL-filter expressions with all quoting centralised here.

    LanceDB's ``where`` takes a raw SQL string, so any user-supplied value must be
    escaped exactly once. Constructing filters only through this class keeps that
    logic in a single place rather than scattered ``value.replace(...)`` calls.
    """

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @classmethod
    def asset(cls, asset_id: str, asset_version: str) -> str:
        return f"asset_id = {cls._quote(asset_id)} AND asset_version = {cls._quote(asset_version)}"


class LanceDBIndexer:
    def __init__(self, root: Path, profile_id: str) -> None:
        self.root = root
        self.profile_id = profile_id
        self.table_name = "chunks_" + re.sub(r"[^a-zA-Z0-9_]", "_", profile_id)

    def index(
        self,
        asset_id: str,
        asset_version: str,
        pages: Sequence[PageAsset],
        chunks: Sequence[ChunkAsset],
        embeddings: Sequence[EmbeddingAsset],
    ) -> None:
        try:
            import lancedb
        except ImportError as exc:
            raise ConfigurationError("Install lancedb to enable vector indexing.") from exc
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        page_by_id = {page.page_id: page for page in pages}
        rows = []
        for embedding in embeddings:
            chunk = chunk_by_id[embedding.chunk_id]
            page = page_by_id[chunk.page_id]
            rows.append({
                "id": f"{asset_id}:{asset_version}:{chunk.chunk_id}",
                "asset_id": asset_id,
                "asset_version": asset_version,
                "chunk_id": chunk.chunk_id,
                "page_id": chunk.page_id,
                "url": page.canonical_url,
                "title": page.title,
                "ordinal": chunk.ordinal,
                "text": chunk.text,
                "content_hash": chunk.content_hash,
                "profile_id": embedding.profile_id,
                "vector": list(embedding.vector),
            })
        if not rows:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(self.root))
        try:
            table = db.open_table(self.table_name)
            exists = True
        except Exception:
            table = db.create_table(self.table_name, rows)
            exists = False
        if exists:
            table.add(rows)

    def search(self, asset_id: str, asset_version: str, vector: Sequence[float], limit: int) -> list[dict]:
        try:
            import lancedb
        except ImportError as exc:
            raise ConfigurationError("Install lancedb to search vectors.") from exc
        db = lancedb.connect(str(self.root))
        try:
            table = db.open_table(self.table_name)
        except Exception:
            return []
        return (
            table
            .search(list(vector))
            .where(VectorFilter.asset(asset_id, asset_version))
            .limit(limit)
            .to_list()
        )
