"""Data Structurer — aggregate page/image data into DataFrames and export."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class DataStructurer:
    """Accumulates extraction results and exports structured datasets.

    Supports export to Parquet, CSV, or JSONL format.
    """

    def __init__(self) -> None:
        self._pages: list[dict[str, Any]] = []
        self._images: list[dict[str, Any]] = []
        self._external_links: list[str] = []
        self._errors: list[dict[str, str]] = []
        self._start_time: float = 0.0
        self._end_time: float = 0.0

    def set_start_time(self, t: float) -> None:
        self._start_time = t

    def set_end_time(self, t: float) -> None:
        self._end_time = t

    # ── accumulation ──────────────────────────────────────────────────

    def add_page(self, data: dict[str, Any]) -> None:
        """Add a processed page record."""
        data.setdefault("crawl_date", datetime.now(timezone.utc).isoformat())
        data.setdefault("word_count", len(data.get("content", "").split()))

        # Serialise headings to JSON string for tabular storage
        if isinstance(data.get("headings"), list):
            data["headings"] = json.dumps(data["headings"], ensure_ascii=False)

        self._pages.append(data)

    def add_images(self, images: list[dict[str, Any]]) -> None:
        """Add image metadata records."""
        self._images.extend(images)

    def add_external_links(self, links: list[str]) -> None:
        """Accumulate external links for the report."""
        self._external_links.extend(links)

    def add_error(self, url: str, error: str) -> None:
        """Record a crawl error."""
        self._errors.append({"url": url, "error": error})

    # ── export ────────────────────────────────────────────────────────

    def export(self, output_dir: str, fmt: str = "parquet") -> dict[str, str]:
        """Write datasets and return a mapping of name → file path."""
        os.makedirs(output_dir, exist_ok=True)
        paths: dict[str, str] = {}

        # Pages
        if self._pages:
            cols = ["url", "title", "headings", "content", "meta_description", "crawl_date", "word_count"]
            df = pd.DataFrame(self._pages)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols]
            pages_path = self._write_df(df, output_dir, "pages", fmt)
            paths["pages"] = pages_path
            logger.info("pages_exported", rows=len(df), path=pages_path)

        # Images
        if self._images:
            cols = ["image_path", "source_page", "alt_text", "image_url"]
            df = pd.DataFrame(self._images)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols]
            images_path = self._write_df(df, output_dir, "images", fmt)
            paths["images"] = images_path
            logger.info("images_exported", rows=len(df), path=images_path)

        # Report
        report_path = os.path.join(output_dir, "crawl_report.json")
        report = self.generate_report()
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        paths["report"] = report_path
        logger.info("report_exported", path=report_path)

        # Human-readable Markdown export
        readable_dir = self._export_readable(output_dir)
        paths["readable"] = readable_dir

        return paths

    def generate_report(self) -> dict[str, Any]:
        """Build the crawl summary report."""
        elapsed = self._end_time - self._start_time if self._end_time else 0
        return {
            "total_pages": len(self._pages),
            "failed_pages": len(self._errors),
            "total_images": len(self._images),
            "external_links": len(set(self._external_links)),
            "time_taken_seconds": round(elapsed, 2),
            "errors": self._errors[:100],  # cap for readability
        }

    # ── helpers ───────────────────────────────────────────────────────

    def _export_readable(self, output_dir: str) -> str:
        """Generate human-readable Markdown files from crawled pages.

        Creates:
          - ``readable/<slug>.md`` — one file per page
          - ``readable/all_pages.md`` — combined document
        """
        readable_dir = os.path.join(output_dir, "readable")
        os.makedirs(readable_dir, exist_ok=True)

        combined_parts: list[str] = []

        for i, page in enumerate(self._pages, 1):
            md = self._page_to_markdown(page, i)
            combined_parts.append(md)

            # Individual file
            slug = self._url_to_slug(page.get("url", f"page_{i}"))
            file_path = os.path.join(readable_dir, f"{slug}.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md)

        # Combined file
        combined_path = os.path.join(readable_dir, "all_pages.md")
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(combined_parts))

        logger.info("readable_exported", path=readable_dir, pages=len(self._pages))
        return readable_dir

    @staticmethod
    def _page_to_markdown(page: dict[str, Any], index: int) -> str:
        """Convert a single page record into clean Markdown."""
        title = page.get("title", "Untitled Page")
        url = page.get("url", "")
        meta = page.get("meta_description", "")
        content = page.get("content", "")
        word_count = page.get("word_count", 0)
        crawl_date = page.get("crawl_date", "")

        # Parse headings
        headings_raw = page.get("headings", "[]")
        if isinstance(headings_raw, str):
            try:
                headings = json.loads(headings_raw)
            except (json.JSONDecodeError, TypeError):
                headings = []
        else:
            headings = headings_raw or []

        lines: list[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**URL:** {url}  ")
        if meta:
            lines.append(f"**Description:** {meta}  ")
        lines.append(f"**Words:** {word_count}  |  **Crawled:** {crawl_date}")
        lines.append("")

        # Headings section
        if headings:
            lines.append("## Page Structure")
            lines.append("")
            for h in headings:
                level = h.get("level", 2)
                text = h.get("text", "")
                indent = "  " * max(0, level - 1)
                lines.append(f"{indent}- **h{level}:** {text}")
            lines.append("")

        # Content section
        if content:
            lines.append("## Content")
            lines.append("")
            # Clean up: normalize whitespace, keep paragraph breaks
            paragraphs = re.split(r"\n{2,}", content.strip())
            for para in paragraphs:
                cleaned = " ".join(para.split())
                if cleaned:
                    lines.append(cleaned)
                    lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _url_to_slug(url: str) -> str:
        """Convert a URL to a safe filename slug."""
        parsed = urlparse(url)
        path = parsed.netloc + parsed.path
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").lower()
        return slug[:80] or "index"

    @staticmethod
    def _write_df(df: pd.DataFrame, output_dir: str, name: str, fmt: str) -> str:
        if fmt == "parquet":
            path = os.path.join(output_dir, f"{name}.parquet")
            df.to_parquet(path, index=False, engine="pyarrow")
        elif fmt == "csv":
            path = os.path.join(output_dir, f"{name}.csv")
            df.to_csv(path, index=False, encoding="utf-8")
        elif fmt == "jsonl":
            path = os.path.join(output_dir, f"{name}.jsonl")
            df.to_json(path, orient="records", lines=True, force_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
        return path
