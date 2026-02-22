# Website Ingestion Pipeline

A modular web crawling and data extraction pipeline that crawls websites using breadth-first search, extracts structured content, and exports datasets in multiple formats.

---

## Overview

The pipeline provides two interfaces — a command-line tool and a REST API — for crawling websites and producing structured, analysis-ready datasets. It handles the full lifecycle: URL discovery, content fetching, text and image extraction, and export to Parquet, CSV, or JSONL.

Key capabilities:

- **Breadth-first crawl engine** with configurable depth, page limits, and rate limiting
- **Robots.txt compliance** with crawl-delay support
- **Content extraction** covering titles, headings, meta descriptions, body text, images, and links
- **Dynamic rendering** via Playwright/Chromium for JavaScript-heavy pages
- **Multiple export formats** — Parquet, CSV, and JSONL
- **Raw HTML archival** with gzip compression and metadata sidecars
- **Image downloading** with async fetching and perceptual deduplication
- **Human-readable Markdown** exports alongside structured data
- **REST API** for submitting and managing crawl jobs over HTTP
- **Docker deployment** with a single command

---

## Quick Start

### Using Docker

```bash
docker compose up -d
```

The API server starts on `http://localhost:8000`. Submit a crawl job:

```bash
curl -X POST http://localhost:8000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 2, "page_limit": 50}'
```

### Using the CLI

```bash
docker compose exec pipeline-api /entrypoint.sh crawl \
  --url https://example.com --depth 2 --limit 50
```

### Running Locally

```bash
pip install -r requirements.txt
playwright install chromium
python main.py --url https://example.com
```

See [Getting Started](getting-started.md) for full installation and setup instructions.

---

## Documentation

| Section | Description |
|---|---|
| [Getting Started](getting-started.md) | Installation, setup, and first crawl walkthrough |
| [CLI Reference](cli-reference.md) | Complete command-line option documentation |
| [API Reference](api-reference.md) | REST API endpoints, schemas, and examples |
| [Output Format](output-format.md) | Dataset structure and field definitions |
| [Architecture](architecture.md) | System design, module overview, and configuration |
