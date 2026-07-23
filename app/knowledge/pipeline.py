"""The single public orchestration entry point for knowledge ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone

from app.config import CrawlConfig
from app.crawler import Crawler
from app.dataset_storage import DatasetStorage
from app.structurer import DataStructurer
from app.knowledge.assets import AssetStore
from app.knowledge.cache import CacheStore
from app.knowledge.context import ProcessorContext
from app.knowledge.events import EventSink, StageCompleted, StageEvent, StageStarted
from app.knowledge.hashing import fast_content_hash
from app.knowledge.metrics import MetricsRecorder, NoopMetricsRecorder
from app.knowledge.models import AssetManifest, AssetStatus, ErrorEntry, PageAsset, StageRecord, StageStatus
from app.knowledge.processors import ChunkProcessor, EmbeddingProcessor
from app.knowledge.providers import EmbeddingProvider, FakeEmbeddingProvider
from app.knowledge.run_logger import create_run_logger
from app.knowledge.settings import KnowledgeSettings
from app.knowledge.vectors import LanceDBIndexer


class PipelineEventSink(EventSink):
    def __init__(self, logger, metrics: MetricsRecorder) -> None:
        self.events: list[StageEvent] = []
        self.logger = logger
        self.metrics = metrics

    def emit(self, event: StageEvent) -> None:
        self.events.append(event)
        self.logger.info("knowledge_stage_event", event_type=event.__class__.__name__, stage=event.stage)
        self.metrics.counter("knowledge_events_total", event_type=event.__class__.__name__, stage=event.stage)


class KnowledgePipeline:
    """Crawl, persist canonical assets, then optionally enrich/index them."""

    def __init__(
        self,
        settings: KnowledgeSettings | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self.settings = settings or KnowledgeSettings.from_env()
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider()
        self.metrics = metrics or NoopMetricsRecorder()
        self.store = AssetStore(self.settings.storage_root)
        self.cache = CacheStore(self.settings.storage_root / "cache")

    async def ingest(
        self,
        config: CrawlConfig,
        asset_id: str | None = None,
        asset_version: str = "v1",
    ) -> tuple[dict, AssetManifest]:
        asset_id = asset_id or uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        config_hash = hashlib.sha256(json.dumps(config.model_dump(mode="json"), sort_keys=True).encode("utf-8")).hexdigest()
        self.store.create_version(asset_id, asset_version)
        manifest = AssetManifest(
            asset_id=asset_id, asset_version=asset_version, run_id=run_id,
            status=AssetStatus.QUEUED, created_at=now, updated_at=now,
            crawl_config_hash=config_hash, source_scope=tuple(config.allowed_domains),
        )
        self.store.write_manifest(manifest)
        logger = create_run_logger(run_id, asset_id)
        sink = PipelineEventSink(logger, self.metrics)
        context = ProcessorContext(asset_id, asset_version, run_id, self.settings, logger, self.metrics, sink)
        try:
            manifest = self._with_status(manifest, AssetStatus.CRAWLING)
            self.store.write_manifest(manifest)
            structurer = DataStructurer()
            await Crawler(config, structurer).crawl()
            structurer.export(config.output_dir, config.output_format)
            DatasetStorage(config.output_dir).create_manifest()
            report = structurer.generate_report()
            pages = [self._to_page_asset(record) for record in structurer.page_records]
            page_artifact = self.store.write_pages(asset_id, asset_version, pages)
            manifest = self._with_status(manifest, AssetStatus.PROCESSING, artifacts=(page_artifact,))
            self.store.write_manifest(manifest)
            sink.emit(StageStarted(stage="chunk"))
            chunks = await ChunkProcessor().process(pages, context)
            chunk_artifact = self.store.write_chunks(asset_id, asset_version, chunks)
            sink.emit(StageCompleted(stage="chunk", output_count=len(chunks)))
            artifacts = (page_artifact, chunk_artifact)
            stages = (StageRecord(name="chunk", version="1.0", status=StageStatus.COMPLETED, output_count=len(chunks)),)
            if self.settings.enable_embeddings:
                sink.emit(StageStarted(stage="embedding"))
                embeddings = await EmbeddingProcessor(self.embedding_provider, self.cache).process(chunks, context)
                embedding_artifact = self.store.write_embeddings(asset_id, asset_version, embeddings)
                await asyncio.to_thread(
                    LanceDBIndexer(self.settings.storage_root / "vectors", self.embedding_provider.profile_id).index,
                    asset_id, asset_version, pages, chunks, embeddings,
                )
                sink.emit(StageCompleted(stage="embedding", output_count=len(embeddings)))
                artifacts += (embedding_artifact,)
                stages += (StageRecord(name="embedding", version="1.0", status=StageStatus.COMPLETED, output_count=len(embeddings)),)
            manifest = self._with_status(manifest, AssetStatus.COMPLETED, artifacts=artifacts, stages=stages, provider_profiles=(self.embedding_provider.profile_id,) if self.settings.enable_embeddings else ())
            self.store.write_manifest(manifest)
            return report, manifest
        except asyncio.CancelledError:
            manifest = self._with_status(manifest, AssetStatus.ABORTED)
            self.store.write_manifest(manifest)
            raise
        except Exception as exc:
            manifest = self._with_status(
                manifest,
                AssetStatus.FAILED,
                errors=(ErrorEntry(category=exc.__class__.__name__, stage="pipeline", message=str(exc)),),
            )
            self.store.write_manifest(manifest)
            raise

    @staticmethod
    def _to_page_asset(record: dict) -> PageAsset:
        headings = record.get("headings", [])
        if isinstance(headings, str):
            try:
                headings = json.loads(headings)
            except json.JSONDecodeError:
                headings = []
        url = str(record["url"])
        content = str(record.get("content", ""))
        return PageAsset(
            page_id=uuid.uuid5(uuid.NAMESPACE_URL, url).hex,
            canonical_url=url,
            title=str(record.get("title", "")),
            headings=tuple(headings),
            content=content,
            meta_description=str(record.get("meta_description", "")),
            crawled_at=datetime.fromisoformat(record["crawl_date"]),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            fast_content_hash=fast_content_hash(content),
        )

    @staticmethod
    def _with_status(manifest: AssetManifest, status: AssetStatus, **changes) -> AssetManifest:
        values = manifest.model_dump()
        values.update(changes)
        values["status"] = status
        values["updated_at"] = datetime.now(timezone.utc)
        if status == AssetStatus.COMPLETED:
            values["completed_at"] = values["updated_at"]
        return AssetManifest.model_validate(values)
