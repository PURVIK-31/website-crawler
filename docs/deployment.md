# Deployment

Container and runtime configuration for the pipeline. Design rationale lives in
the [ADRs](adr/index.md); the component diagrams live in [Architecture](architecture.md).

---

## Container

The Dockerfile uses a multi-stage build on `python:3.11-slim`:

1. **Builder stage** — installs build dependencies and compiles Python packages.
2. **Runtime stage** — copies compiled packages, installs runtime system libraries
   (libxml2, libjpeg, libpng, Chromium dependencies, fonts), and installs the
   Playwright Chromium browser.

The container exposes port `8000` and uses `/entrypoint.sh` as its entrypoint.

---

## Docker Compose

The `docker-compose.yml` defines a single service:

| Setting | Value |
|---|---|
| Container name | `web-crawler-api` |
| Default command | `serve` |
| Port mapping | `8000:8000` |
| Memory limit | 2 GB (512 MB reserved) |
| Restart policy | `unless-stopped` |
| Health check | HTTP request to `localhost:8000` every 30 seconds |

---

## Volumes

| Mount | Container Path | Purpose |
|---|---|---|
| `crawler_data` (named volume) | `/app/jobs` | Persistent storage for API job data |
| Host Downloads folder | `/app/downloads` | Bind mount for CLI crawl output |

!!! note "Job state is not durable"
    The API job registry is in memory and does not survive a restart. Job
    *files* persist under `PIPELINE_DATA_DIR`, but status/history do not. See
    [ADR-0004](adr/0004-ephemeral-jobs-durable-assets.md).

---

## Environment Variables

### Runtime

| Variable | Default | Description |
|---|---|---|
| `PIPELINE_DATA_DIR` | `/app/jobs` | Base directory for API job storage |
| `PORT` | `8000` | API server port |
| `WORKERS` | `1` | Number of Uvicorn worker processes |
| `PYTHONUNBUFFERED` | `1` | Disable Python output buffering |
| `PURUCRAWLER_DOWNLOADS` | *(user-specific)* | Host path for the Downloads bind mount |

### Knowledge ingestion (v2)

| Variable | Default | Description |
|---|---|---|
| `KNOWLEDGE_STORAGE_ROOT` | `storage` | Root directory for versioned assets and vectors |
| `KNOWLEDGE_ENABLE_EMBEDDINGS` | `false` | Enable the embedding + vector-index stage |
| `KNOWLEDGE_EMBEDDING_PROFILE` | `fake-v1` | Embedding profile identifier |
| `KNOWLEDGE_CHUNK_SIZE_WORDS` | `300` | Words per chunk |
| `KNOWLEDGE_CHUNK_OVERLAP_WORDS` | `40` | Overlap between adjacent chunks |
| `KNOWLEDGE_BATCH_SIZE` | `64` | Embedding batch size |

!!! warning "Single worker"
    v2 is designed for `WORKERS=1`. Cache locking is process-local and the
    pipeline is single-node by design — see
    [ADR-0003](adr/0003-single-node-v2-scope.md).

---

## Dependencies

| Package | Role |
|---|---|
| aiohttp | Async HTTP client for page fetching |
| beautifulsoup4 + lxml | HTML parsing and DOM traversal |
| readability-lxml | Main content extraction from HTML |
| pandas + pyarrow | DataFrame operations and Parquet export |
| Pillow + imagehash | Image processing and perceptual deduplication |
| playwright | Headless Chromium for dynamic page rendering |
| fastapi + uvicorn | REST API server |
| typer + rich | CLI framework and terminal formatting |
| structlog | Structured, key-value logging |
| pydantic | Configuration validation and serialization |
| chardet | Character encoding detection |
| lancedb | Vector index for knowledge search (optional) |
| sentence-transformers | Embedding provider (optional) |
