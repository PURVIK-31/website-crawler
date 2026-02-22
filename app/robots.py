"""Robots.txt checker — honours Disallow / Allow rules and Crawl-delay."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse
from typing import Optional

import aiohttp
import structlog

from app.config import BOT_USER_AGENT

logger = structlog.get_logger(__name__)


class RobotsChecker:
    """Per-domain robots.txt cache and query interface.

    Usage::

        checker = RobotsChecker()
        if await checker.can_fetch(url):
            ...
    """

    def __init__(self, user_agent: str = BOT_USER_AGENT) -> None:
        self.user_agent = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._delays: dict[str, Optional[float]] = {}

    async def can_fetch(self, url: str) -> bool:
        """Return True if *url* may be fetched according to robots.txt."""
        rp = await self._get_parser(url)
        if rp is None:
            return True  # fail-open when robots.txt is unavailable
        return rp.can_fetch(self.user_agent, url)

    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """Return the Crawl-delay for the domain, or None."""
        domain = self._domain(url)
        if domain not in self._delays:
            await self._get_parser(url)  # populates _delays
        return self._delays.get(domain)

    # ── internals ─────────────────────────────────────────────────────

    async def _get_parser(self, url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        domain = self._domain(url)
        if domain in self._cache:
            return self._cache[domain]

        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        rp.parse(text.splitlines())
                        self._cache[domain] = rp
                        try:
                            delay = rp.crawl_delay(self.user_agent)
                            self._delays[domain] = float(delay) if delay else None
                        except Exception:
                            self._delays[domain] = None
                        logger.info("robots_loaded", domain=domain)
                        return rp
                    else:
                        logger.info("robots_not_found", domain=domain, status=resp.status)
        except Exception as exc:
            logger.warning("robots_fetch_error", domain=domain, error=str(exc))

        # Cache None so we don't retry
        self._cache[domain] = None  # type: ignore[assignment]
        self._delays[domain] = None
        return None

    @staticmethod
    def _domain(url: str) -> str:
        return urlparse(url).netloc.lower()
