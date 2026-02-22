"""Link extractor — classify internal vs external, filter noise."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

# URL patterns to skip (login pages, auth, admin, social, etc.)
_SKIP_PATTERNS = re.compile(
    r"(login|logout|signin|signup|register|auth|admin|"
    r"cart|checkout|account|password|reset|unsubscribe|"
    r"facebook\.com|twitter\.com|instagram\.com|linkedin\.com|"
    r"youtube\.com|mailto:|tel:|javascript:|#$)",
    re.IGNORECASE,
)

# File extensions to skip
_SKIP_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv",
    ".exe", ".dmg", ".apk",
}


class LinkExtractor:
    """Extract and classify links from a page.

    Returns:
        - Internal links (same domain) → for re-enqueue into the frontier.
        - External links → logged for the crawl report.
    """

    def __init__(self, allowed_domains: list[str]) -> None:
        self.allowed_domains: set[str] = {d.lower() for d in allowed_domains}

    def extract(self, soup: BeautifulSoup, page_url: str) -> tuple[list[str], list[str]]:
        """Return ``(internal_links, external_links)``."""
        internal: list[str] = []
        external: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href:
                continue

            # Resolve relative URLs
            abs_url = urljoin(page_url, href)
            parsed = urlparse(abs_url)

            # Only HTTP(S)
            if parsed.scheme not in ("http", "https"):
                continue

            # Skip noisy / irrelevant URLs
            if _SKIP_PATTERNS.search(abs_url):
                continue

            # Skip binary files
            ext = self._get_extension(parsed.path)
            if ext in _SKIP_EXTENSIONS:
                continue

            # Classify
            domain = parsed.netloc.lower()
            bare_domain = re.sub(r"^www\.", "", domain)
            if domain in self.allowed_domains or bare_domain in self.allowed_domains:
                internal.append(abs_url)
            else:
                external.append(abs_url)

        # Deduplicate while preserving order
        internal = list(dict.fromkeys(internal))
        external = list(dict.fromkeys(external))

        return internal, external

    @staticmethod
    def _get_extension(path: str) -> str:
        """Extract lowercase file extension from a URL path."""
        if "." in path.split("/")[-1]:
            return "." + path.rsplit(".", 1)[-1].lower()
        return ""
