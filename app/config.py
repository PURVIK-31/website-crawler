"""Pydantic configuration models for the crawl pipeline."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Default user-agent pool for rotation
DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.0; rv:120.0) Gecko/20100101 Firefox/120.0",
]

BOT_USER_AGENT = "WebsitePipelineBot/1.0 (+https://github.com/website-pipeline)"


class CrawlConfig(BaseModel):
    """Validated configuration for a single crawl job."""

    start_url: str = Field(..., description="The seed URL to begin crawling from.")
    max_depth: int = Field(default=3, ge=1, le=20, description="Maximum BFS depth.")
    page_limit: int = Field(default=100, ge=1, le=10_000, description="Max pages to crawl.")
    rate_limit: float = Field(default=1.0, gt=0, description="Seconds between requests.")
    allowed_domains: list[str] = Field(default_factory=list, description="Domains to stay within.")
    save_raw_html: bool = Field(default=True, description="Whether to save raw HTML files.")
    output_dir: str = Field(default="site_dataset", description="Root output directory.")
    output_format: str = Field(default="parquet", description="Output format: parquet, csv, jsonl.")
    user_agents: list[str] = Field(default_factory=lambda: list(DEFAULT_USER_AGENTS))
    respect_robots: bool = Field(default=True, description="Honour robots.txt rules.")
    dynamic_fallback: bool = Field(default=True, description="Fall back to headless browser for JS-heavy pages.")
    request_timeout: int = Field(default=30, ge=5, le=120, description="HTTP request timeout in seconds.")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retries per URL.")
    min_image_size: int = Field(default=100, ge=0, description="Min image dimension (px) to keep.")
    download_images: bool = Field(default=True, description="Whether to download images.")

    # ── validators ────────────────────────────────────────────────────

    @field_validator("start_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL scheme must be http or https, got '{parsed.scheme}'")
        if not parsed.netloc:
            raise ValueError("URL must have a valid domain.")
        # Basic sanitisation – strip whitespace
        return v.strip()

    @field_validator("output_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("parquet", "csv", "jsonl"):
            raise ValueError(f"output_format must be parquet|csv|jsonl, got '{v}'")
        return v

    @model_validator(mode="after")
    def set_defaults(self) -> "CrawlConfig":
        """Auto-populate allowed_domains from start_url if empty."""
        if not self.allowed_domains:
            domain = urlparse(self.start_url).netloc
            # Strip www. prefix to be more permissive
            bare = re.sub(r"^www\.", "", domain)
            self.allowed_domains = [domain, bare]
            if bare != domain:
                self.allowed_domains.append(f"www.{bare}")
        return self
