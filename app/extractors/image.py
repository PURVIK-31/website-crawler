"""Image extractor — find, download, and deduplicate images."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from io import BytesIO
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

# Try to import image processing libs (optional but recommended)
try:
    from PIL import Image
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False


class ImageExtractor:
    """Extract, download, and deduplicate images from a page.

    Images are saved to ``<output_dir>/images/<domain>/``, named by content
    hash to avoid duplicates.
    """

    MIN_DIMENSION = 100  # default min width/height in px

    def __init__(
        self,
        output_dir: str,
        min_size: int = 100,
        download: bool = True,
    ) -> None:
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        self.min_size = min_size
        self.download = download
        self._seen_hashes: set[str] = set()  # perceptual hashes for dedup
        self._seen_urls: set[str] = set()

    async def extract(self, soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
        """Find images in *soup*, download them, and return metadata dicts."""
        image_urls = self._find_image_urls(soup, page_url)
        if not image_urls:
            return []

        results: list[dict[str, Any]] = []
        tasks = [self._process_image(url, page_url, alt) for url, alt in image_urls]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, dict):
                results.append(outcome)
            elif isinstance(outcome, Exception):
                logger.debug("image_process_error", error=str(outcome))

        return results

    # ── finding image URLs ────────────────────────────────────────────

    def _find_image_urls(self, soup: BeautifulSoup, page_url: str) -> list[tuple[str, str]]:
        """Return list of (absolute_url, alt_text) for images in the page."""
        found: list[tuple[str, str]] = []

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            if not src or src.startswith("data:"):
                continue
            abs_url = urljoin(page_url, src)
            alt = img.get("alt", "") or ""
            if abs_url not in self._seen_urls:
                self._seen_urls.add(abs_url)
                found.append((abs_url, alt.strip()))

        return found

    # ── downloading + dedup ──────────────────────────────────────────

    async def _process_image(self, url: str, page_url: str, alt: str) -> Optional[dict[str, Any]]:
        """Download a single image, check size/dedup, save to disk."""
        if not self.download:
            return {"image_url": url, "source_page": page_url, "alt_text": alt, "image_path": ""}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.read()

            if not data:
                return None

            # Size filter
            if HAS_IMAGEHASH:
                try:
                    img = Image.open(BytesIO(data))
                    w, h = img.size
                    if w < self.min_size or h < self.min_size:
                        return None

                    # Perceptual dedup
                    phash = str(imagehash.phash(img))
                    if phash in self._seen_hashes:
                        logger.debug("image_dedup_skip", url=url, phash=phash)
                        return None
                    self._seen_hashes.add(phash)
                except Exception:
                    pass  # If PIL fails, keep the image anyway

            # Save
            domain = urlparse(page_url).netloc
            domain_dir = os.path.join(self.images_dir, domain.replace(":", "_"))
            os.makedirs(domain_dir, exist_ok=True)

            content_hash = hashlib.sha256(data).hexdigest()[:16]
            ext = self._guess_ext(url, data)
            filename = f"{content_hash}{ext}"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, "wb") as f:
                f.write(data)

            return {
                "image_path": filepath,
                "source_page": page_url,
                "alt_text": alt,
                "image_url": url,
            }

        except Exception as exc:
            logger.debug("image_download_error", url=url, error=str(exc))
            return None

    @staticmethod
    def _guess_ext(url: str, data: bytes) -> str:
        """Best-effort extension from URL path or magic bytes."""
        path = urlparse(url).path.lower()
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"):
            if path.endswith(ext):
                return ext
        # Magic bytes fallback
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        if data[:2] == b"\xff\xd8":
            return ".jpg"
        if data[:4] == b"GIF8":
            return ".gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        return ".jpg"  # safe default
