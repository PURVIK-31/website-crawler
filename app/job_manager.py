"""Job Manager — validates inputs, creates config, and launches the crawl."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import structlog

from app.config import CrawlConfig
from app.crawler import Crawler
from app.dataset_storage import DatasetStorage
from app.structurer import DataStructurer

logger = structlog.get_logger(__name__)


class JobManager:
    """Entry point that orchestrates an entire crawl job.

    1. Validate inputs → build ``CrawlConfig``.
    2. Create output directories.
    3. Launch the ``Crawler``.
    4. Export structured data (Parquet/CSV/JSONL).
    5. Create manifest and print summary.
    """

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
        """Synchronous entry — runs the async pipeline and returns the report."""
        return asyncio.run(self.run_async())

    async def run_async(self) -> dict:
        """Async entry — performs the full crawl lifecycle."""
        cfg = self.config
        logger.info(
            "job_started",
            start_url=cfg.start_url,
            max_depth=cfg.max_depth,
            page_limit=cfg.page_limit,
            rate_limit=cfg.rate_limit,
            output_dir=cfg.output_dir,
        )

        # ── prepare output ────────────────────────────────────────────
        os.makedirs(cfg.output_dir, exist_ok=True)

        structurer = DataStructurer()

        # ── crawl ─────────────────────────────────────────────────────
        crawler = Crawler(config=cfg, structurer=structurer)
        await crawler.crawl()

        # ── export ────────────────────────────────────────────────────
        paths = structurer.export(output_dir=cfg.output_dir, fmt=cfg.output_format)
        logger.info("data_exported", paths=paths)

        # ── manifest ──────────────────────────────────────────────────
        ds = DatasetStorage(cfg.output_dir)
        ds.create_manifest()

        # ── report ────────────────────────────────────────────────────
        report = structurer.generate_report()
        logger.info("job_complete", report=report)
        return report
