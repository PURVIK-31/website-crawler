"""Extractor pipeline — runs all registered extractors on parsed pages."""

from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from typing import Any

from app.extractors.text import TextExtractor
from app.extractors.image import ImageExtractor
from app.extractors.link import LinkExtractor

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionResult:
    """Aggregated output from all extractors."""
    text_data: dict[str, Any] = field(default_factory=dict)
    images: list[dict[str, Any]] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)


class ExtractorPipeline:
    """Runs text, image, and link extractors sequentially and returns aggregated results."""

    def __init__(self, output_dir: str, allowed_domains: list[str] | None = None) -> None:
        self.text_extractor = TextExtractor()
        self.image_extractor = ImageExtractor(output_dir=output_dir)
        self.link_extractor = LinkExtractor(allowed_domains=allowed_domains or [])

    async def run(
        self,
        url: str,
        soup: "BeautifulSoup",  # noqa: F821
        readable_text: str,
    ) -> ExtractionResult:
        """Execute all extractors and return combined results."""
        result = ExtractionResult()

        # 1. Text extraction
        try:
            result.text_data = self.text_extractor.extract(soup, readable_text, url)
            logger.debug("text_extracted", url=url, title=result.text_data.get("title"))
        except Exception as exc:
            logger.error("text_extraction_failed", url=url, error=str(exc))

        # 2. Image extraction (async — downloads images)
        try:
            result.images = await self.image_extractor.extract(soup, url)
            logger.debug("images_extracted", url=url, count=len(result.images))
        except Exception as exc:
            logger.error("image_extraction_failed", url=url, error=str(exc))

        # 3. Link extraction
        try:
            internal, external = self.link_extractor.extract(soup, url)
            result.internal_links = internal
            result.external_links = external
            logger.debug(
                "links_extracted", url=url,
                internal=len(internal), external=len(external),
            )
        except Exception as exc:
            logger.error("link_extraction_failed", url=url, error=str(exc))

        return result
