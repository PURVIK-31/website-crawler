"""Text extractor — title, headings, meta description, main content."""

from __future__ import annotations

import re
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class TextExtractor:
    """Extract structured text data from a parsed HTML page.

    Returns a dict with keys:
        - title (str)
        - headings (list[dict]): Each ``{level: int, text: str}``
        - content (str): Cleaned main body text
        - meta_description (str)
    """

    def extract(self, soup: BeautifulSoup, readable_text: str, url: str) -> dict[str, Any]:
        """Run text extraction on *soup* / *readable_text*."""
        return {
            "url": url,
            "title": self._get_title(soup),
            "headings": self._get_headings(soup),
            "content": self._clean_text(readable_text),
            "meta_description": self._get_meta_description(soup),
        }

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _get_title(soup: BeautifulSoup) -> str:
        tag = soup.find("title")
        if tag:
            return tag.get_text(strip=True)
        # Fallback to first h1
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    @staticmethod
    def _get_headings(soup: BeautifulSoup) -> list[dict[str, Any]]:
        headings: list[dict[str, Any]] = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                text = tag.get_text(strip=True)
                if text:
                    headings.append({"level": level, "text": text})
        return headings

    @staticmethod
    def _get_meta_description(soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if meta and meta.get("content"):
            return str(meta["content"]).strip()
        # Try og:description
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            return str(og["content"]).strip()
        return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalise whitespace and remove noise from extracted text."""
        if not text:
            return ""
        # Collapse whitespace
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip cookie / consent patterns (basic)
        noise = re.compile(
            r"(accept\s+cookies?|cookie\s+policy|we\s+use\s+cookies|"
            r"privacy\s+policy|terms\s+of\s+(service|use)|"
            r"subscribe\s+to\s+newsletter|sign\s+up\s+for)",
            re.IGNORECASE,
        )
        lines = text.split("\n")
        cleaned = [l for l in lines if not noise.search(l)]
        return "\n".join(cleaned).strip()
