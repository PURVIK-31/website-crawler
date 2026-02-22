"""Shared test fixtures for the website pipeline tests."""

from __future__ import annotations

import pytest


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Test Page Title</title>
    <meta name="description" content="This is a test meta description.">
    <script>console.log("noise");</script>
    <style>body { color: red; }</style>
</head>
<body>
    <header>
        <nav><a href="/about">About</a> <a href="/contact">Contact</a></nav>
    </header>
    <main>
        <h1>Main Heading</h1>
        <p>This is the main content of the page. It contains useful information.</p>
        <h2>Sub Heading One</h2>
        <p>More detail about the sub topic with substantial text here.</p>
        <img src="/images/photo.jpg" alt="A test photo">
        <img src="https://cdn.example.com/banner.png" alt="External banner">
        <img src="data:image/gif;base64,R0lGOD..." alt="Inline">
        <h3>Sub Sub Heading</h3>
        <p>Even more content in the third level.</p>
        <a href="/page2">Internal Link</a>
        <a href="https://external.com/resource">External Link</a>
        <a href="/login">Login</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="/docs/file.pdf">PDF Download</a>
    </main>
    <footer>
        <p>&copy; 2024 Test Site</p>
    </footer>
</body>
</html>"""


SAMPLE_HTML_MINIMAL = """<html><body><p>Hello World</p></body></html>"""


SAMPLE_HTML_NO_BODY = """<html><head><title>No Body</title></head></html>"""


@pytest.fixture
def sample_html() -> str:
    return SAMPLE_HTML


@pytest.fixture
def sample_html_minimal() -> str:
    return SAMPLE_HTML_MINIMAL


@pytest.fixture
def sample_html_no_body() -> str:
    return SAMPLE_HTML_NO_BODY
