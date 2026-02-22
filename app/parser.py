"""HTML Parser — clean and extract readable content from raw HTML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import chardet
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


@dataclass
class ParsedPage:
    """Result of parsing a raw HTML page."""
    soup: BeautifulSoup
    readable_html: str
    readable_text: str
    encoding: str


class HtmlParser:
    """Cleans raw HTML and extracts readable main content.

    * Removes ``<script>``, ``<style>``, ``<noscript>`` tags.
    * Detects encoding with *chardet* when needed.
    * Uses *readability-lxml* for boilerplate removal.
    """

    # Tags to strip from the DOM before any extraction
    STRIP_TAGS = ("script", "style", "noscript", "iframe", "svg")

    def parse(self, html: str, url: str, declared_encoding: Optional[str] = None) -> ParsedPage:
        """Parse *html* and return cleaned structures.

        Args:
            html: Raw HTML string.
            url: The page URL (used by readability for base URL resolution).
            declared_encoding: Encoding from HTTP headers, if available.
        """
        # ── encoding detection ────────────────────────────────────────
        encoding = declared_encoding or self._detect_encoding(html)

        # ── cleaned soup ──────────────────────────────────────────────
        soup = BeautifulSoup(html, "lxml")
        for tag_name in self.STRIP_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # ── readability for main content ──────────────────────────────
        readable_html, readable_text = self._readability(html, url)

        # ── fallback: if readability stripped too much, use full body ──
        body = soup.find("body")
        body_text = body.get_text(separator="\n", strip=True) if body else ""

        if len(readable_text) < max(100, len(body_text) * 0.15):
            logger.info(
                "readability_too_aggressive",
                url=url,
                readable_len=len(readable_text),
                body_len=len(body_text),
            )
            readable_text = body_text
            readable_html = str(body) if body else html

        return ParsedPage(
            soup=soup,
            readable_html=readable_html,
            readable_text=readable_text,
            encoding=encoding,
        )

    # ── internals ─────────────────────────────────────────────────────

    @staticmethod
    def _detect_encoding(html: str) -> str:
        """Detect encoding of the HTML string (best-effort)."""
        try:
            raw = html.encode("latin-1", errors="replace")
            result = chardet.detect(raw)
            return result.get("encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"

    @staticmethod
    def _readability(html: str, url: str) -> tuple[str, str]:
        """Run readability-lxml to extract main article content."""
        try:
            from readability import Document
            doc = Document(html, url=url)
            readable_html = doc.summary(html_partial=True)
            # Get plain text from readable HTML
            readable_soup = BeautifulSoup(readable_html, "lxml")
            readable_text = readable_soup.get_text(separator="\n", strip=True)
            return readable_html, readable_text
        except Exception as exc:
            logger.warning("readability_failed", url=url, error=str(exc))
            # Fallback: just use body text
            soup = BeautifulSoup(html, "lxml")
            body = soup.find("body")
            text = body.get_text(separator="\n", strip=True) if body else ""
            return html, text
