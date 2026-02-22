"""Dataset storage — organise output folder and create manifest."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DatasetStorage:
    """Manages the final dataset output folder.

    Creates a structured ``site_dataset/`` folder (or custom name) with:
    - Exported data files (parquet/csv/jsonl)
    - ``images/`` folder with downloaded images
    - ``raw_html/`` folder with gzipped pages
    - ``manifest.json`` listing all files with sizes and hashes
    """

    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_manifest(self) -> str:
        """Walk the output directory and create a manifest.json.

        Returns the path to the manifest.
        """
        files: list[dict[str, Any]] = []
        for root, _dirs, filenames in os.walk(self.output_dir):
            for name in filenames:
                if name == "manifest.json":
                    continue
                filepath = os.path.join(root, name)
                rel = os.path.relpath(filepath, self.output_dir)
                size = os.path.getsize(filepath)
                files.append({
                    "path": rel.replace("\\", "/"),
                    "size_bytes": size,
                    "sha256": self._file_hash(filepath),
                })

        manifest = {
            "created": datetime.now(timezone.utc).isoformat(),
            "total_files": len(files),
            "files": files,
        }

        manifest_path = os.path.join(self.output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info("manifest_created", path=manifest_path, total_files=len(files))
        return manifest_path

    def compress(self, fmt: str = "zip") -> str:
        """Compress the output directory into an archive.

        Args:
            fmt: Archive format (``zip``, ``tar``, ``gztar``).

        Returns:
            Path to the archive file.
        """
        archive_path = shutil.make_archive(
            base_name=self.output_dir,
            format=fmt,
            root_dir=os.path.dirname(self.output_dir),
            base_dir=os.path.basename(self.output_dir),
        )
        logger.info("dataset_compressed", path=archive_path)
        return archive_path

    @staticmethod
    def _file_hash(path: str) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
