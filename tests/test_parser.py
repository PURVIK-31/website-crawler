"""Unit tests for the HTML parser."""

from __future__ import annotations

import pytest
from app.parser import HtmlParser


class TestHtmlParser:
    """Tests for HtmlParser.parse()."""

    def setup_method(self):
        self.parser = HtmlParser()

    def test_strips_scripts(self, sample_html: str):
        parsed = self.parser.parse(sample_html, "https://example.com/page")
        scripts = parsed.soup.find_all("script")
        assert len(scripts) == 0

    def test_strips_styles(self, sample_html: str):
        parsed = self.parser.parse(sample_html, "https://example.com/page")
        styles = parsed.soup.find_all("style")
        assert len(styles) == 0

    def test_readable_text_not_empty(self, sample_html: str):
        parsed = self.parser.parse(sample_html, "https://example.com/page")
        assert len(parsed.readable_text) > 0

    def test_encoding_detection(self, sample_html: str):
        parsed = self.parser.parse(sample_html, "https://example.com/page")
        assert parsed.encoding is not None

    def test_declared_encoding(self, sample_html: str):
        parsed = self.parser.parse(sample_html, "https://example.com/page", declared_encoding="utf-8")
        assert parsed.encoding == "utf-8"

    def test_minimal_html(self, sample_html_minimal: str):
        parsed = self.parser.parse(sample_html_minimal, "https://example.com/page")
        assert "Hello World" in parsed.readable_text

    def test_no_body_html(self, sample_html_no_body: str):
        parsed = self.parser.parse(sample_html_no_body, "https://example.com/page")
        # Should not crash even without a body
        assert parsed.soup is not None
