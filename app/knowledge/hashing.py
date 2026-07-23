"""Fast change detection and canonical integrity hashing."""

from __future__ import annotations

import hashlib


def fast_content_hash(value: str) -> str:
    """Return XXH3-128 when installed, with a deterministic local fallback."""
    try:
        import xxhash
        return xxhash.xxh3_128_hexdigest(value.encode("utf-8"))
    except ImportError:
        return hashlib.blake2b(value.encode("utf-8"), digest_size=16).hexdigest()


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
