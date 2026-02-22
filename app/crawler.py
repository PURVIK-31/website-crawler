"""Crawler engine — BFS crawl loop with async fetching and extraction."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from app.config import CrawlConfig
from app.fetcher import PageFetcher
from app.frontier import URLFrontier
from app.parser import HtmlParser
from app.raw_storage import RawStorage
from app.robots import RobotsChecker
from app.extractors import ExtractorPipeline
from app.structurer import DataStructurer

logger = structlog.get_logger(__name__)


class Crawler:
    """Async BFS web crawler.

    Orchestrates the full crawl loop:
    1. Pop URL from frontier.
    2. Check robots.txt.
    3. Fetch page (static, with dynamic fallback).
    4. Save raw HTML (optional).
    5. Parse → extract text/images/links.
    6. Enqueue discovered internal links.
    7. Accumulate data in the structurer.
    """

    def __init__(self, config: CrawlConfig, structurer: DataStructurer) -> None:
        self.config = config
        self.structurer = structurer
        self.frontier = URLFrontier(
            allowed_domains=config.allowed_domains,
            max_depth=config.max_depth,
        )
        self.robots = RobotsChecker()
        self.parser = HtmlParser()
        self.raw_storage: RawStorage | None = None
        self.extractor_pipeline = ExtractorPipeline(
            output_dir=config.output_dir,
            allowed_domains=config.allowed_domains,
        )

        if config.save_raw_html:
            self.raw_storage = RawStorage(config.output_dir)

    async def crawl(self) -> None:
        """Run the BFS crawl loop."""
        # Seed the frontier
        self.frontier.add_url(self.config.start_url, depth=0)
        self.structurer.set_start_time(time.monotonic())

        async with PageFetcher(self.config) as fetcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[green]{task.fields[status]}"),
            ) as progress:
                task = progress.add_task(
                    "Crawling",
                    total=self.config.page_limit,
                    status="starting...",
                )

                pages_crawled = 0

                while pages_crawled < self.config.page_limit:
                    entry = self.frontier.get_next()
                    if entry is None:
                        logger.info("frontier_exhausted", pages_crawled=pages_crawled)
                        break

                    url, depth = entry
                    progress.update(
                        task,
                        advance=0,
                        status=f"[depth={depth}] {url[:60]}...",
                    )

                    # Process the URL
                    success = await self._process_url(url, depth, fetcher)
                    if success:
                        pages_crawled += 1
                        progress.update(task, advance=1)

                    self.frontier.mark_visited(url)

        self.structurer.set_end_time(time.monotonic())
        logger.info(
            "crawl_complete",
            pages_crawled=pages_crawled,
            visited=self.frontier.visited_count,
        )

    async def _process_url(self, url: str, depth: int, fetcher: PageFetcher) -> bool:
        """Fetch, parse, extract, and enqueue for a single URL.

        Returns True if the page was successfully processed.
        """
        # ── robots check ──────────────────────────────────────────────
        if self.config.respect_robots:
            try:
                allowed = await self.robots.can_fetch(url)
                if not allowed:
                    logger.info("robots_blocked", url=url)
                    return False
            except Exception as exc:
                logger.warning("robots_check_error", url=url, error=str(exc))

        # ── fetch ─────────────────────────────────────────────────────
        try:
            result = await fetcher.fetch(url)
        except Exception as exc:
            self.structurer.add_error(url, f"Fetch error: {exc}")
            logger.error("fetch_error", url=url, error=str(exc))
            return False

        if not result.ok:
            self.structurer.add_error(url, f"HTTP {result.status_code}: {result.error or 'Bad status'}")
            logger.warning("fetch_failed", url=url, status=result.status_code)
            return False

        # ── raw storage ───────────────────────────────────────────────
        if self.raw_storage:
            self.raw_storage.save(
                url=url, html=result.html,
                status_code=result.status_code,
                response_time=result.response_time,
            )

        # ── parse ─────────────────────────────────────────────────────
        try:
            declared_enc = result.headers.get("Content-Type", "")
            enc = None
            if "charset=" in declared_enc:
                enc = declared_enc.split("charset=")[-1].split(";")[0].strip()
            parsed = self.parser.parse(result.html, url, declared_encoding=enc)
        except Exception as exc:
            self.structurer.add_error(url, f"Parse error: {exc}")
            logger.error("parse_error", url=url, error=str(exc))
            return False

        # ── extract ───────────────────────────────────────────────────
        try:
            extraction = await self.extractor_pipeline.run(
                url=url,
                soup=parsed.soup,
                readable_text=parsed.readable_text,
            )
        except Exception as exc:
            self.structurer.add_error(url, f"Extraction error: {exc}")
            logger.error("extraction_error", url=url, error=str(exc))
            return False

        # ── accumulate data ───────────────────────────────────────────
        if extraction.text_data:
            self.structurer.add_page(extraction.text_data)

        if extraction.images:
            self.structurer.add_images(extraction.images)

        if extraction.external_links:
            self.structurer.add_external_links(extraction.external_links)

        # ── enqueue discovered internal links ─────────────────────────
        for link in extraction.internal_links:
            self.frontier.add_url(link, depth=depth + 1)

        logger.info(
            "page_processed", url=url, depth=depth,
            links_found=len(extraction.internal_links),
            images=len(extraction.images),
        )
        return True
