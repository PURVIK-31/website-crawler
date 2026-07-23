"""Unit tests for deterministic knowledge-ingestion primitives."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.knowledge.assets import AssetStore
from app.knowledge.cache import CacheStore
from app.knowledge.context import ProcessorContext
from app.knowledge.events import NullEventSink
from app.knowledge.metrics import NoopMetricsRecorder
from app.knowledge.models import AssetManifest, AssetStatus, PageAsset
from app.knowledge.processors import ChunkProcessor, EmbeddingProcessor
from app.knowledge.providers import FakeEmbeddingProvider
from app.knowledge.run_logger import create_run_logger
from app.knowledge.settings import KnowledgeSettings
from app.knowledge.pipeline import KnowledgePipeline
from app.config import CrawlConfig
from app.knowledge.vectors import LanceDBIndexer


def _context(tmp_path) -> ProcessorContext:
    return ProcessorContext(
        asset_id="asset", asset_version="v1", run_id="run",
        settings=KnowledgeSettings(storage_root=tmp_path, chunk_size_words=3, chunk_overlap_words=1),
        logger=create_run_logger("run", "asset"), metrics=NoopMetricsRecorder(), events=NullEventSink(),
    )


@pytest.mark.asyncio
async def test_chunking_is_deterministic(tmp_path):
    page = PageAsset(
        page_id="page", canonical_url="https://example.com", content="one two three four five",
        crawled_at=datetime.now(timezone.utc), content_hash="sha", fast_content_hash="fast",
    )
    first = await ChunkProcessor().process([page], _context(tmp_path))
    second = await ChunkProcessor().process([page], _context(tmp_path))
    assert first == second
    assert [chunk.text for chunk in first] == ["one two three", "three four five"]


@pytest.mark.asyncio
async def test_embeddings_are_cached(tmp_path):
    context = _context(tmp_path)
    page = PageAsset(
        page_id="page", canonical_url="https://example.com", content="one two three",
        crawled_at=datetime.now(timezone.utc), content_hash="sha", fast_content_hash="fast",
    )
    chunks = await ChunkProcessor().process([page], context)
    processor = EmbeddingProcessor(FakeEmbeddingProvider(), CacheStore(tmp_path / "cache"))
    first = await processor.process(chunks, context)
    second = await processor.process(chunks, context)
    assert first == second
    assert first[0].dimension == 8


def test_asset_manifest_is_versioned_and_durable(tmp_path):
    store = AssetStore(tmp_path)
    store.create_version("asset", "v1")
    now = datetime.now(timezone.utc)
    manifest = AssetManifest(
        asset_id="asset", asset_version="v1", run_id="run", status=AssetStatus.QUEUED,
        created_at=now, updated_at=now, crawl_config_hash="hash", source_scope=("example.com",),
    )
    store.write_manifest(manifest)
    assert store.read_manifest("asset", "v1") == manifest
    with pytest.raises(Exception):
        store.create_version("asset", "v1")


def test_empty_page_assets_write_valid_parquet(tmp_path):
    store = AssetStore(tmp_path)
    store.create_version("asset", "v1")
    artifact = store.write_pages("asset", "v1", [])
    assert artifact.rows == 0
    assert (tmp_path / artifact.path).exists()


@pytest.mark.asyncio
async def test_lancedb_is_a_rebuildable_asset_index(tmp_path):
    context = _context(tmp_path)
    page = PageAsset(
        page_id="page", canonical_url="https://example.com", title="Example", content="one two three",
        crawled_at=datetime.now(timezone.utc), content_hash="sha", fast_content_hash="fast",
    )
    chunks = await ChunkProcessor().process([page], context)
    embeddings = await EmbeddingProcessor(FakeEmbeddingProvider(), CacheStore(tmp_path / "cache")).process(chunks, context)
    index = LanceDBIndexer(tmp_path / "vectors", "fake-v1")
    index.index("asset", "v1", [page], chunks, embeddings)
    rows = index.search("asset", "v1", embeddings[0].vector, 5)
    assert rows[0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_pipeline_ingest_preserves_legacy_export_and_writes_assets(tmp_path, monkeypatch):
    class FakeCrawler:
        def __init__(self, config, structurer):
            self.structurer = structurer

        async def crawl(self):
            self.structurer.set_start_time(0)
            self.structurer.add_page({
                "url": "https://example.com/", "title": "Example", "headings": [],
                "content": "one two three four", "meta_description": "",
            })
            self.structurer.set_end_time(1)

    monkeypatch.setattr("app.knowledge.pipeline.Crawler", FakeCrawler)
    settings = KnowledgeSettings(storage_root=tmp_path / "storage", chunk_size_words=3, chunk_overlap_words=1)
    config = CrawlConfig(start_url="https://example.com", output_dir=str(tmp_path / "legacy"))
    report, manifest = await KnowledgePipeline(settings).ingest(config, asset_id="asset")
    assert report["total_pages"] == 1
    assert manifest.status is AssetStatus.COMPLETED
    assert (tmp_path / "legacy" / "pages.parquet").exists()
    assert (tmp_path / "storage" / "assets" / "asset" / "v1" / "chunks.parquet").exists()
