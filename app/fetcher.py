"""Page Fetcher — async HTTP + optional headless browser fallback."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import structlog

from app.config import CrawlConfig

logger = structlog.get_logger(__name__)


@dataclass
class FetchResult:
    """Outcome of fetching a single URL."""
    url: str
    status_code: int
    html: str
    headers: dict[str, str] = field(default_factory=dict)
    response_time: float = 0.0
    method: str = "static"  # "static" or "dynamic"
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400 and self.html and not self.error


class PageFetcher:
    """Async page fetcher with rate limiting, retries, and optional Playwright fallback.

    Usage::

        async with PageFetcher(config) as fetcher:
            result = await fetcher.fetch(url)
    """

    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(1)  # single concurrency for politeness
        self._last_request_time: float = 0.0
        self._playwright = None
        self._browser = None

    async def __aenter__(self) -> "PageFetcher":
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session:
            await self._session.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── public API ────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        """Fetch *url*, using static first then falling back to dynamic if needed."""
        result = await self._fetch_with_retries(url)

        # Heuristic: if content looks JS-heavy, retry with browser
        if result.ok and self.config.dynamic_fallback and self._looks_js_heavy(result.html):
            logger.info("dynamic_fallback_triggered", url=url)
            dyn_result = await self._fetch_dynamic(url)
            if dyn_result.ok:
                return dyn_result

        return result

    # ── static fetching ───────────────────────────────────────────────

    async def _fetch_with_retries(self, url: str, retries: Optional[int] = None) -> FetchResult:
        max_retries = retries if retries is not None else self.config.max_retries
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                return await self._fetch_static(url)
            except Exception as exc:
                last_error = str(exc)
                wait = min(2 ** attempt, 30)  # exponential backoff, cap 30s
                logger.warning(
                    "fetch_retry", url=url, attempt=attempt + 1,
                    max_retries=max_retries, wait=wait, error=last_error,
                )
                await asyncio.sleep(wait)

        return FetchResult(url=url, status_code=0, html="", error=last_error)

    async def _fetch_static(self, url: str) -> FetchResult:
        """Single aiohttp GET with rate limiting."""
        await self._rate_limit()
        async with self._semaphore:
            ua = random.choice(self.config.user_agents)
            headers = {"User-Agent": ua}
            start = time.monotonic()
            assert self._session is not None
            async with self._session.get(url, headers=headers, allow_redirects=True) as resp:
                html = await resp.text(errors="replace")
                elapsed = time.monotonic() - start
                resp_headers = {k: v for k, v in resp.headers.items()}
                logger.debug("fetch_static_ok", url=url, status=resp.status, time=f"{elapsed:.2f}s")
                return FetchResult(
                    url=str(resp.url),
                    status_code=resp.status,
                    html=html,
                    headers=resp_headers,
                    response_time=elapsed,
                    method="static",
                )

    # ── dynamic fetching (Playwright) ─────────────────────────────────

    async def _fetch_dynamic(self, url: str) -> FetchResult:
        """Render page in headless Chromium."""
        try:
            if self._playwright is None:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)

            assert self._browser is not None
            page = await self._browser.new_page()
            start = time.monotonic()
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=self.config.request_timeout * 1000)
                html = await page.content()
                elapsed = time.monotonic() - start
                status = response.status if response else 200
                logger.debug("fetch_dynamic_ok", url=url, status=status, time=f"{elapsed:.2f}s")
                return FetchResult(
                    url=url, status_code=status, html=html,
                    response_time=elapsed, method="dynamic",
                )
            finally:
                await page.close()
        except Exception as exc:
            logger.error("fetch_dynamic_error", url=url, error=str(exc))
            return FetchResult(url=url, status_code=0, html="", method="dynamic", error=str(exc))

    # ── helpers ───────────────────────────────────────────────────────

    async def _rate_limit(self) -> None:
        """Sleep to honour the configured rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.config.rate_limit:
            await asyncio.sleep(self.config.rate_limit - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _looks_js_heavy(html: str) -> bool:
        """Simple heuristic: if body text is very short relative to total HTML,
        the page is likely JS-rendered."""
        if not html:
            return False
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        if body is None:
            return True
        text = body.get_text(separator=" ", strip=True)
        ratio = len(text) / max(len(html), 1)
        # Also check for heavy script presence
        scripts = soup.find_all("script")
        return ratio < 0.05 and len(scripts) > 5
