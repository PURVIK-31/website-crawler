# Website Ingestion Pipeline

> Crawl a website, extract reusable content and media metadata, and export an analysis-ready dataset.

Website Ingestion Pipeline is a Python web crawler for small-to-medium, same-site crawls. It follows links breadth-first from a seed URL, extracts readable content, images, and link information, then writes the result as Parquet, CSV, or JSONL. Use it from the command line, through a FastAPI service, or in Docker.

## Capabilities

- Same-domain breadth-first crawling with URL normalization, tracking-parameter removal, deduplication, depth limits, and page limits.
- `robots.txt` checks, user-agent rotation, configurable request delays, and exponential retry backoff.
- Static HTTP fetching plus optional Playwright/Chromium rendering for likely JavaScript-heavy pages.
- Text extraction: title, headings, meta description, readable body text, timestamp, and word count.
- Image metadata and optional downloads with minimum-size filtering and perceptual deduplication.
- Parquet, CSV, or JSONL datasets; raw-HTML archives; Markdown exports; crawl reports; and SHA-256 manifests.
- A FastAPI service for creating jobs, checking their status, and downloading results.

## Tech stack

| Area | Technology |
|---|---|
| Runtime and CLI | Python 3.11+, Typer, Rich |
| Crawling | aiohttp, urllib.robotparser |
| Parsing | Beautiful Soup, lxml, readability-lxml, chardet |
| Dynamic rendering | Playwright and Chromium |
| Data and images | pandas, PyArrow, Pillow, imagehash |
| API and validation | FastAPI, Uvicorn, Pydantic |
| Logging and deployment | structlog, Docker, Docker Compose |

## Quick start

### Docker API

```bash
docker compose up -d
curl http://localhost:8000/
```

Interactive API documentation: `http://localhost:8000/docs`.

### Local CLI

```bash
python -m venv .venv
pip install -r requirements.txt
playwright install chromium
python main.py --url https://example.com --depth 2 --limit 50
```

Use `--no-dynamic` when Chromium is not installed.

## Main options

| Option | Default |
|---|---:|
| `--depth`, `--limit` | 3, 100 |
| `--rate-limit` | 1.0 seconds |
| `--format` | parquet |
| `--output-dir` | site_dataset |
| `--no-raw-html`, `--no-images` | off |

Run `python main.py --help` for all CLI options.

## API

| Method | Endpoint |
|---|---|
| POST | `/api/crawl` |
| GET | `/api/jobs`, `/api/jobs/{job_id}` |
| GET | `/api/jobs/{job_id}/<result>` |
| DELETE | `/api/jobs/{job_id}` |

Jobs run in the background. Download endpoints require a completed job.
Available result names are `report`, `pages`, `images`, and `download`.

## Output

Each crawl writes an output directory containing tabular `pages` and (when available) `images` data in the selected format, `crawl_report.json`, `manifest.json`, readable Markdown, raw HTML archives, and downloaded images. The pages schema is `url`, `title`, `headings`, `content`, `meta_description`, `crawl_date`, and `word_count`.

See [Output Format](docs/output-format.md) for fields and directory details.

## Important notes

- Crawl only sites you are authorized to access; choose conservative limits and delays.
- The crawler checks `robots.txt`, but its advertised crawl-delay is read, not automatically enforced; `--rate-limit` is the enforced delay.
- API job status is in memory and does not survive a service restart, although job files persist in `PIPELINE_DATA_DIR`.
- The API has permissive CORS and no authentication. Restrict it before production use.

## Development

```bash
pip install -r requirements.txt
pytest tests/
```

The suite (43 tests) covers the extractors, URL frontier, HTML parser, and the
knowledge ingestion pipeline (chunking, caching, and asset persistence).

Extended guides: [Getting Started](docs/getting-started.md), [CLI Reference](docs/cli-reference.md), [API Reference](docs/api-reference.md), and [Architecture](docs/architecture.md).
