"""URL Frontier — priority queue + visited set + URL normalisation."""

from __future__ import annotations

import hashlib
import heapq
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Query parameters to strip during normalisation
_STRIP_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|ref|source|campaign)", re.IGNORECASE)


@dataclass(order=True)
class QueueEntry:
    """Priority-queue entry.  Lower depth = higher priority."""
    depth: int
    url: str = field(compare=False)


class URLFrontier:
    """BFS URL frontier with deduplication and domain filtering.

    Attributes:
        allowed_domains: Set of domains we are allowed to crawl.
        max_depth: Maximum BFS depth.
    """

    def __init__(
        self,
        allowed_domains: list[str],
        max_depth: int = 3,
    ) -> None:
        self.allowed_domains: set[str] = {d.lower() for d in allowed_domains}
        self.max_depth = max_depth
        self._queue: list[QueueEntry] = []
        self._visited: set[str] = set()   # stores URL hashes
        self._enqueued: set[str] = set()  # prevent duplicate queue entries

    # ── public API ────────────────────────────────────────────────────

    def add_url(self, url: str, depth: int = 0) -> bool:
        """Normalise *url* and add it to the queue if eligible.

        Returns True if the URL was actually enqueued, False if skipped.
        """
        norm = self.normalize_url(url)
        if norm is None:
            return False

        url_hash = self._hash(norm)

        if depth > self.max_depth:
            return False
        if url_hash in self._visited or url_hash in self._enqueued:
            return False
        if not self._domain_allowed(norm):
            return False

        heapq.heappush(self._queue, QueueEntry(depth=depth, url=norm))
        self._enqueued.add(url_hash)
        logger.debug("url_enqueued", url=norm, depth=depth)
        return True

    def get_next(self) -> Optional[tuple[str, int]]:
        """Pop the highest-priority URL.  Returns (url, depth) or None."""
        while self._queue:
            entry = heapq.heappop(self._queue)
            url_hash = self._hash(entry.url)
            if url_hash in self._visited:
                continue
            return entry.url, entry.depth
        return None

    def mark_visited(self, url: str) -> None:
        """Register *url* as visited so it won't be fetched again."""
        norm = self.normalize_url(url) or url
        self._visited.add(self._hash(norm))

    def is_visited(self, url: str) -> bool:
        norm = self.normalize_url(url) or url
        return self._hash(norm) in self._visited

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    # ── URL normalisation ─────────────────────────────────────────────

    @staticmethod
    def normalize_url(url: str) -> Optional[str]:
        """Normalise a URL for dedup: lowercase host, strip fragments, remove
        tracking params, collapse slashes, ensure trailing slash on bare paths.

        Returns None if the URL is not a valid HTTP(S) URL.
        """
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return None

        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None

        # Lowercase scheme + host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Clean path — collapse multiple slashes
        path = re.sub(r"/+", "/", parsed.path or "/")
        if not path:
            path = "/"

        # Strip tracking query params
        if parsed.query:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in qs.items() if not _STRIP_PARAMS.match(k)}
            query = urlencode(filtered, doseq=True)
        else:
            query = ""

        # Strip fragment entirely
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))

    # ── internals ─────────────────────────────────────────────────────

    def _domain_allowed(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        # Also match if domain without www. prefix is allowed
        bare = re.sub(r"^www\.", "", domain)
        return domain in self.allowed_domains or bare in self.allowed_domains

    @staticmethod
    def _hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()
