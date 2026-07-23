"""Compatibility facade for the legacy CLI crawl command."""

from __future__ import annotations

import asyncio

import structlog

from app.config import CrawlConfig
from app.knowledge.pipeline import KnowledgePipeline

logger = structlog.get_logger(__name__)


class JobManager:
    """Build a legacy crawl configuration and delegate to KnowledgePipeline."""

    def __init__(
        self,
        start_url: str,
        max_depth: int = 3,
        page_limit: int = 100,
        rate_limit: float = 1.0,
        output_dir: str = "site_dataset",
        output_format: str = "parquet",
        save_raw_html: bool = True,
        dynamic_fallback: bool = True,
        download_images: bool = True,
    ) -> None:
        self.config = CrawlConfig(
            start_url=start_url,
            max_depth=max_depth,
            page_limit=page_limit,
            rate_limit=rate_limit,
            output_dir=output_dir,
            output_format=output_format,
            save_raw_html=save_raw_html,
            dynamic_fallback=dynamic_fallback,
            download_images=download_images,
        )

    def run(self) -> dict:
        """Synchronous CLI entry point."""
        return asyncio.run(self.run_async())

    async def run_async(self) -> dict:
        """Run legacy crawl/export plus optional knowledge asset ingestion."""
        report, manifest = await KnowledgePipeline().ingest(self.config)
        logger.info("job_complete", report=report, asset_id=manifest.asset_id)
        return report
