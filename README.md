# Website Ingestion Pipeline

A modular web crawling and data extraction pipeline that crawls websites using breadth-first search, extracts structured content, and exports datasets in multiple formats. Supports both a command-line interface and a REST API.

---

## Features

- **BFS Crawl Engine** — Configurable depth, page limits, and rate limiting
- **Robots.txt Compliance** — Respects crawl rules and crawl-delay directives
- **Content Extraction** — Titles, headings, meta descriptions, body text, images, and links
- **Dynamic Rendering** — Playwright/Chromium fallback for JavaScript-heavy pages
- **Multiple Export Formats** — Parquet, CSV, and JSONL
- **Raw HTML Archival** — Gzip-compressed HTML with metadata sidecars
- **Image Downloading** — Async download with perceptual deduplication
- **Readable Output** — Markdown exports for human consumption
- **REST API** — Submit and manage crawl jobs over HTTP
- **Docker Support** — Single-command containerized deployment

---

## Requirements

- Docker and Docker Compose
- Alternatively, Python 3.11+ for local execution

---

## Quick Start

### Using Docker (recommended)

```bash
docker compose up -d
```

The API server starts on `http://localhost:8000`. Interactive documentation is available at `/docs`.

### Submit a crawl via API

```bash
curl -X POST http://localhost:8000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 2, "page_limit": 50}'
```

### Using the CLI inside the container

```bash
docker compose exec pipeline-api /entrypoint.sh crawl \
  --url https://example.com \
  --depth 2 \
  --limit 50 \
  --format parquet
```

### Local execution (without Docker)

```bash
pip install -r requirements.txt
playwright install chromium

# Run a crawl
python main.py --url https://example.com --depth 2 --limit 50

# Start the API server
python main.py serve --port 8000
```

---

## CLI Reference

```
python main.py [OPTIONS]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--url` | `-u` | *(required)* | Starting URL to crawl |
| `--depth` | `-d` | `3` | Maximum crawl depth (BFS) |
| `--limit` | `-l` | `100` | Maximum number of pages |
| `--rate-limit` | `-r` | `1.0` | Seconds between requests |
| `--output-dir` | `-o` | `site_dataset` | Output directory path |
| `--format` | `-f` | `parquet` | Export format: `parquet`, `csv`, `jsonl` |
| `--no-raw-html` | | `false` | Skip saving raw HTML files |
| `--no-images` | | `false` | Skip downloading images |
| `--no-dynamic` | | `false` | Disable Playwright fallback |
| `--log-level` | | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--json-logs` | | `false` | Output structured JSON logs |

```
python main.py serve [OPTIONS]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--host` | `-h` | `0.0.0.0` | Server bind address |
| `--port` | `-p` | `8000` | Server port |
| `--reload` | | `false` | Auto-reload on code changes |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/crawl` | Submit a new crawl job |
| `GET` | `/api/jobs` | List all jobs (optional `?status=` filter) |
| `GET` | `/api/jobs/{id}` | Get job status and report |
| `GET` | `/api/jobs/{id}/report` | Download crawl report (JSON) |
| `GET` | `/api/jobs/{id}/pages` | Download pages dataset |
| `GET` | `/api/jobs/{id}/images` | Download images dataset |
| `GET` | `/api/jobs/{id}/download` | Download full dataset (ZIP) |
| `DELETE` | `/api/jobs/{id}` | Delete a job and its data |

Full interactive documentation is available at `http://localhost:8000/docs` when the server is running.

---

## Output Structure

Each crawl produces the following directory structure:

```
output_dir/
├── pages.parquet            # Structured page data
├── images.parquet           # Image metadata
├── crawl_report.json        # Summary statistics
├── manifest.json            # File listing with checksums
├── readable/
│   ├── all_pages.md         # Combined readable export
│   └── {page_slug}.md       # Individual page exports
├── raw_html/
│   └── {domain}/
│       ├── {hash}.html.gz   # Compressed HTML
│       └── {hash}.meta.json # Fetch metadata
└── images/
    └── {domain}/
        └── {hash}.{ext}     # Downloaded images
```

**Page fields:** `url`, `title`, `headings`, `content`, `meta_description`, `crawl_date`, `word_count`

**Image fields:** `image_path`, `source_page`, `alt_text`, `image_url`

---

## Configuration

The `POST /api/crawl` endpoint accepts the following request body:

```json
{
  "url": "https://example.com",
  "max_depth": 3,
  "page_limit": 100,
  "rate_limit": 1.0,
  "output_format": "parquet",
  "save_raw_html": true,
  "download_images": true,
  "dynamic_fallback": true
}
```

All fields except `url` are optional and use sensible defaults.

---

## Architecture

```
main.py                     CLI + API entry point
├── app/
│   ├── api.py              FastAPI REST interface
│   ├── job_manager.py      Job orchestration
│   ├── crawler.py          BFS crawl engine
│   ├── fetcher.py          Async HTTP + Playwright fetcher
│   ├── frontier.py         URL queue and deduplication
│   ├── robots.py           Robots.txt compliance
│   ├── parser.py           HTML parsing (readability-lxml)
│   ├── structurer.py       Data aggregation and export
│   ├── raw_storage.py      Raw HTML archival
│   ├── dataset_storage.py  Manifest and ZIP packaging
│   ├── config.py           Pydantic configuration models
│   ├── logger.py           Structured logging (structlog)
│   └── extractors/
│       ├── text.py         Title, headings, meta extraction
│       ├── link.py         Internal/external link classification
│       └── image.py        Image download and deduplication
├── Dockerfile              Multi-stage build (python:3.11-slim)
├── docker-compose.yml      Container orchestration
└── entrypoint.sh           Container entrypoint
```

---

## Docker Configuration

The `docker-compose.yml` exposes port `8000` and mounts two volumes:

- `crawler_data` — Persistent storage for API job data (`/app/jobs`)
- Host Downloads folder — Bind mount for CLI output (`/app/downloads`)

Resource limits are set to 2 GB memory with a 512 MB reservation.

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `PIPELINE_DATA_DIR` | `/app/jobs` | Internal job storage path |
| `PORT` | `8000` | API server port |
| `WORKERS` | `1` | Uvicorn worker count |
| `PURUCRAWLER_DOWNLOADS` | `C:/Users/.../Downloads/PuruCrawler` | Host path for CLI output |

---

## Testing

```bash
pip install -r requirements.txt
pytest tests/
```

---

## Dependencies

| Package | Purpose |
|---|---|
| aiohttp | Async HTTP client |
| beautifulsoup4, lxml | HTML parsing |
| readability-lxml | Content extraction |
| pandas, pyarrow | Data processing and Parquet export |
| Pillow, imagehash | Image processing and deduplication |
| playwright | Dynamic page rendering |
| fastapi, uvicorn | REST API server |
| typer, rich | CLI interface |
| structlog | Structured logging |
| pydantic | Configuration validation |
| chardet | Encoding detection |

---

## License

This project is provided as-is for educational and personal use.
