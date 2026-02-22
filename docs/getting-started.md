# Getting Started

This guide covers installation, initial setup, and running your first crawl.

---

## Prerequisites

- **Docker** and **Docker Compose** (recommended), or
- **Python 3.11+** for local execution

---

## Docker Setup

### 1. Clone the repository

```bash
git clone https://github.com/PURVIK-31/website-crawler.git
cd website-crawler
```

### 2. Build and start the container

```bash
docker compose up -d
```

This builds the image (first run takes a few minutes) and starts the API server on port `8000`. The container includes all dependencies, Playwright, and Chromium.

### 3. Verify the service is running

```bash
docker compose ps
```

The container should show a status of `Up` and `(healthy)`. You can also check the health endpoint:

```bash
curl http://localhost:8000/
```

Expected response:

```json
{
  "service": "Website Ingestion Pipeline",
  "status": "running",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

## Local Setup

If you prefer running without Docker:

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

!!! note
    Playwright is optional. If you skip this step, the pipeline will still work for static pages. Pass `--no-dynamic` to disable the Playwright fallback entirely.

---

## First Crawl

### Via the CLI (Docker)

```bash
docker compose exec pipeline-api /entrypoint.sh crawl \
  --url https://example.com \
  --depth 2 \
  --limit 20 \
  --format parquet
```

### Via the CLI (local)

```bash
python main.py --url https://example.com --depth 2 --limit 20
```

### Via the API

```bash
curl -X POST http://localhost:8000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 2, "page_limit": 20}'
```

This returns a job ID. Poll the status endpoint until the job completes:

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

---

## Expected Output

After a successful crawl, the output directory contains:

```
site_dataset/
├── pages.parquet
├── images.parquet
├── crawl_report.json
├── manifest.json
├── readable/
│   ├── all_pages.md
│   └── example_com.md
├── raw_html/
│   └── example.com/
└── images/
    └── example.com/
```

See [Output Format](output-format.md) for a full description of each file and its schema.

---

## Stopping the Service

```bash
docker compose down
```

Add `-v` to also remove the persistent data volume:

```bash
docker compose down -v
```
