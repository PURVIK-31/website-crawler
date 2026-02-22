# API Reference

The REST API runs on port `8000` by default. Interactive Swagger documentation is available at `/docs` when the server is running.

Base URL: `http://localhost:8000`

---

## Health Check

Check that the service is running.

```
GET /
```

**Response:**

```json
{
  "service": "Website Ingestion Pipeline",
  "status": "running",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

## Submit a Crawl Job

Start a new crawl. The request returns immediately with a job ID; the crawl runs in the background.

```
POST /api/crawl
```

**Request body:**

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | *(required)* | Starting URL. Must use `http://` or `https://`. |
| `max_depth` | integer | `3` | Maximum BFS crawl depth (1--20). |
| `page_limit` | integer | `100` | Maximum pages to crawl (1--10,000). |
| `rate_limit` | float | `1.0` | Seconds between requests. |
| `output_format` | string | `"parquet"` | Export format: `parquet`, `csv`, or `jsonl`. |
| `save_raw_html` | boolean | `true` | Save gzip-compressed raw HTML. |
| `download_images` | boolean | `true` | Download images from crawled pages. |
| `dynamic_fallback` | boolean | `true` | Use Playwright for JavaScript-heavy pages. |

**Example:**

```bash
curl -X POST http://localhost:8000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "max_depth": 2,
    "page_limit": 50,
    "rate_limit": 1.0,
    "output_format": "parquet"
  }'
```

**Response:**

```json
{
  "job_id": "a1b2c3d4",
  "status": "queued",
  "message": "Crawl job submitted. Poll /api/jobs/a1b2c3d4 for status."
}
```

---

## List Jobs

List all crawl jobs, optionally filtered by status.

```
GET /api/jobs
GET /api/jobs?status=completed
```

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by job status: `queued`, `running`, `completed`, `failed`. Optional. |

**Response:**

```json
[
  {
    "job_id": "a1b2c3d4",
    "status": "completed",
    "url": "https://example.com",
    "created_at": "2026-02-23T10:00:00Z",
    "completed_at": "2026-02-23T10:01:30Z",
    "report": { ... },
    "error": null
  }
]
```

Jobs are sorted by creation time, most recent first.

---

## Get Job Status

Retrieve the status and report for a specific job.

```
GET /api/jobs/{job_id}
```

**Response:**

```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "url": "https://example.com",
  "created_at": "2026-02-23T10:00:00Z",
  "completed_at": "2026-02-23T10:01:30Z",
  "report": {
    "total_pages": 15,
    "failed_pages": 0,
    "total_images": 42,
    "external_links": 8,
    "time_taken_seconds": 12.5,
    "errors": []
  },
  "error": null
}
```

**Status values:**

| Status | Description |
|---|---|
| `queued` | Job submitted, waiting to start |
| `running` | Crawl is in progress |
| `completed` | Crawl finished successfully |
| `failed` | Crawl terminated with an error |

---

## Download Crawl Report

Download the `crawl_report.json` file for a completed job.

```
GET /api/jobs/{job_id}/report
```

Returns a JSON file download. Only available for completed jobs.

---

## Download Pages Dataset

Download the pages dataset for a completed job.

```
GET /api/jobs/{job_id}/pages
```

Returns the `pages.parquet`, `pages.csv`, or `pages.jsonl` file, depending on the format used when the job was submitted.

---

## Download Images Dataset

Download the images metadata dataset for a completed job.

```
GET /api/jobs/{job_id}/images
```

Returns the `images.parquet`, `images.csv`, or `images.jsonl` file.

---

## Download Full Dataset

Download the entire output directory as a ZIP archive.

```
GET /api/jobs/{job_id}/download
```

The archive is created on demand if it does not already exist. Contains all output files: datasets, report, manifest, readable Markdown, raw HTML, and images.

---

## Delete a Job

Remove a job and delete all associated files from disk.

```
DELETE /api/jobs/{job_id}
```

Running jobs cannot be deleted. Returns:

```json
{
  "message": "Job 'a1b2c3d4' deleted."
}
```

---

## Error Responses

All error responses use the standard format:

```json
{
  "detail": "Description of the error."
}
```

| Status Code | Meaning |
|---|---|
| `400` | Bad request (invalid input, job not in correct state) |
| `404` | Job or file not found |
| `422` | Validation error (malformed request body) |
