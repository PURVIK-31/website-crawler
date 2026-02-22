"""Unit tests for text, link, and image extractors."""

from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

from app.extractors.text import TextExtractor
from app.extractors.link import LinkExtractor
from app.extractors.image import ImageExtractor


class TestTextExtractor:
    """Tests for TextExtractor.extract()."""

    def setup_method(self):
        self.extractor = TextExtractor()

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def test_title(self, sample_html: str):
        soup = self._soup(sample_html)
        result = self.extractor.extract(soup, "body text", "https://example.com/page")
        assert result["title"] == "Test Page Title"

    def test_headings(self, sample_html: str):
        soup = self._soup(sample_html)
        result = self.extractor.extract(soup, "body text", "https://example.com/page")
        headings = result["headings"]
        assert isinstance(headings, list)
        assert len(headings) >= 3
        levels = [h["level"] for h in headings]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_meta_description(self, sample_html: str):
        soup = self._soup(sample_html)
        result = self.extractor.extract(soup, "body text", "https://example.com/page")
        assert result["meta_description"] == "This is a test meta description."

    def test_content_cleaning(self):
        result = TextExtractor._clean_text("Hello   World\n\n\n\nFoo")
        assert "   " not in result
        assert "\n\n\n" not in result

    def test_no_title_fallback(self):
        html = "<html><body><h1>Fallback Title</h1></body></html>"
        soup = self._soup(html)
        result = self.extractor.extract(soup, "", "https://example.com/page")
        assert result["title"] == "Fallback Title"


class TestLinkExtractor:
    """Tests for LinkExtractor.extract()."""

    def setup_method(self):
        self.extractor = LinkExtractor(allowed_domains=["example.com"])

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def test_internal_links(self, sample_html: str):
        soup = self._soup(sample_html)
        internal, external = self.extractor.extract(soup, "https://example.com/")
        # /about, /contact, /page2 should be internal
        internal_paths = [u for u in internal]
        assert any("/about" in u for u in internal_paths)
        assert any("/page2" in u for u in internal_paths)

    def test_external_links(self, sample_html: str):
        soup = self._soup(sample_html)
        internal, external = self.extractor.extract(soup, "https://example.com/")
        assert any("external.com" in u for u in external)

    def test_filters_login(self, sample_html: str):
        soup = self._soup(sample_html)
        internal, external = self.extractor.extract(soup, "https://example.com/")
        all_links = internal + external
        assert not any("/login" in u for u in all_links)

    def test_filters_mailto(self, sample_html: str):
        soup = self._soup(sample_html)
        internal, external = self.extractor.extract(soup, "https://example.com/")
        all_links = internal + external
        assert not any("mailto:" in u for u in all_links)

    def test_filters_pdf(self, sample_html: str):
        soup = self._soup(sample_html)
        internal, external = self.extractor.extract(soup, "https://example.com/")
        all_links = internal + external
        assert not any(".pdf" in u for u in all_links)

    def test_dedup(self):
        html = '<html><body><a href="/dup">A</a><a href="/dup">B</a></body></html>'
        soup = self._soup(html)
        internal, _ = self.extractor.extract(soup, "https://example.com/")
        dup_count = sum(1 for u in internal if "/dup" in u)
        assert dup_count == 1


class TestImageExtractor:
    """Tests for ImageExtractor URL finding (no actual downloads)."""

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def test_find_image_urls(self, sample_html: str, tmp_path):
        extractor = ImageExtractor(output_dir=str(tmp_path), download=False)
        soup = self._soup(sample_html)
        urls = extractor._find_image_urls(soup, "https://example.com/page")
        # Should find /images/photo.jpg and cdn banner, skip data: URI
        found_urls = [u for u, _ in urls]
        assert any("photo.jpg" in u for u in found_urls)
        assert any("banner.png" in u for u in found_urls)
        assert not any("data:" in u for u in found_urls)

    def test_alt_text(self, sample_html: str, tmp_path):
        extractor = ImageExtractor(output_dir=str(tmp_path), download=False)
        soup = self._soup(sample_html)
        urls = extractor._find_image_urls(soup, "https://example.com/page")
        alt_texts = [alt for _, alt in urls]
        assert "A test photo" in alt_texts

    def test_extension_guessing(self):
        assert ImageExtractor._guess_ext("https://example.com/img.png", b"") == ".png"
        assert ImageExtractor._guess_ext("https://example.com/img.webp", b"") == ".webp"
        # Magic bytes
        assert ImageExtractor._guess_ext("https://example.com/img", b"\x89PNG\r\n\x1a\n") == ".png"
        assert ImageExtractor._guess_ext("https://example.com/img", b"\xff\xd8rest") == ".jpg"
