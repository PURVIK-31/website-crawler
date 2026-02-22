"""Unit tests for the URL Frontier."""

from __future__ import annotations

import pytest
from app.frontier import URLFrontier


class TestURLNormalization:
    """Tests for URLFrontier.normalize_url()."""

    def test_strip_fragment(self):
        result = URLFrontier.normalize_url("https://example.com/page#section")
        assert result == "https://example.com/page"

    def test_strip_utm_params(self):
        result = URLFrontier.normalize_url("https://example.com/page?utm_source=google&utm_medium=cpc&id=5")
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=5" in result

    def test_strip_fbclid(self):
        result = URLFrontier.normalize_url("https://example.com/?fbclid=abc123")
        assert "fbclid" not in result

    def test_lowercase_host(self):
        result = URLFrontier.normalize_url("https://Example.COM/Page")
        assert "example.com" in result
        # Path casing should be preserved
        assert "/Page" in result

    def test_collapse_slashes(self):
        result = URLFrontier.normalize_url("https://example.com///path//to///page")
        assert "///" not in result.split("://", 1)[-1]

    def test_rejects_non_http(self):
        assert URLFrontier.normalize_url("ftp://example.com/file") is None
        assert URLFrontier.normalize_url("javascript:void(0)") is None
        assert URLFrontier.normalize_url("mailto:test@test.com") is None

    def test_rejects_empty(self):
        assert URLFrontier.normalize_url("") is None

    def test_valid_url_passes(self):
        result = URLFrontier.normalize_url("https://example.com/path?q=value")
        assert result == "https://example.com/path?q=value"


class TestURLFrontier:
    """Tests for the URLFrontier queue and dedup logic."""

    def test_add_and_get(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=3)
        assert f.add_url("https://example.com/", depth=0)
        result = f.get_next()
        assert result is not None
        url, depth = result
        assert "example.com" in url
        assert depth == 0

    def test_dedup(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=3)
        assert f.add_url("https://example.com/page", depth=0)
        assert not f.add_url("https://example.com/page", depth=0)  # duplicate

    def test_visited_not_returned(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=3)
        f.add_url("https://example.com/page", depth=0)
        f.mark_visited("https://example.com/page")
        assert f.get_next() is None

    def test_depth_limit(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=2)
        assert not f.add_url("https://example.com/deep", depth=3)

    def test_domain_filtering(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=5)
        assert f.add_url("https://example.com/allowed", depth=0)
        assert not f.add_url("https://other.com/blocked", depth=0)

    def test_priority_ordering(self):
        """Shallower URLs should come out first."""
        f = URLFrontier(allowed_domains=["example.com"], max_depth=5)
        f.add_url("https://example.com/deep", depth=3)
        f.add_url("https://example.com/shallow", depth=1)
        f.add_url("https://example.com/mid", depth=2)

        result = f.get_next()
        assert result is not None
        _, depth = result
        assert depth == 1

    def test_empty_frontier(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=3)
        assert f.get_next() is None

    def test_visited_count(self):
        f = URLFrontier(allowed_domains=["example.com"], max_depth=3)
        f.mark_visited("https://example.com/a")
        f.mark_visited("https://example.com/b")
        assert f.visited_count == 2
