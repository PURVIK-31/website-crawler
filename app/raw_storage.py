"""Raw HTML storage — save gzipped HTML and metadata sidecars."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


class RawStorage:
    """Persists raw HTML pages to disk in gzipped form.

    Each page is stored as ``raw_html/<domain>/<sha256>.html.gz`` with a
    JSON sidecar ``<sha256>.meta.json`` containing URL, status, and timing.
    """

    def __init__(self, output_dir: str) -> None:
        self.base_dir = os.path.join(output_dir, "raw_html")
        os.makedirs(self.base_dir, exist_ok=True)

    def save(
        self,
        url: str,
        html: str,
        status_code: int = 200,
        response_time: float = 0.0,
    ) -> Optional[str]:
        """Save raw HTML and return the file path, or None on error."""
        try:
            domain = urlparse(url).netloc
            domain_dir = os.path.join(self.base_dir, domain.replace(":", "_"))
            os.makedirs(domain_dir, exist_ok=True)

            content_hash = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()[:16]
            html_path = os.path.join(domain_dir, f"{content_hash}.html.gz")
            meta_path = os.path.join(domain_dir, f"{content_hash}.meta.json")

            # Write gzipped HTML
            with gzip.open(html_path, "wt", encoding="utf-8") as f:
                f.write(html)

            # Write metadata sidecar
            meta = {
                "url": url,
                "content_hash": content_hash,
                "status_code": status_code,
                "response_time": response_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(html.encode("utf-8", errors="replace")),
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            logger.debug("raw_html_saved", url=url, path=html_path)
            return html_path

        except Exception as exc:
            logger.error("raw_html_save_error", url=url, error=str(exc))
            return None
