# Output Format

Each crawl produces a self-contained output directory with structured datasets, raw archives, and human-readable exports.

---

## Directory Structure

```
output_dir/
├── pages.parquet              Structured page data
├── images.parquet             Image metadata
├── crawl_report.json          Crawl summary statistics
├── manifest.json              File listing with checksums
├── readable/
│   ├── all_pages.md           Combined readable export
│   └── {page_slug}.md         Individual page exports
├── raw_html/
│   └── {domain}/
│       ├── {hash}.html.gz     Gzip-compressed HTML
│       └── {hash}.meta.json   Fetch metadata sidecar
└── images/
    └── {domain}/
        └── {hash}.{ext}       Downloaded images
```

The tabular files (`pages`, `images`) use the format specified at crawl time: `.parquet`, `.csv`, or `.jsonl`.

---

## Pages Dataset

The `pages` file contains one row per successfully crawled page.

| Field | Type | Description |
|---|---|---|
| `url` | string | Canonical URL of the crawled page |
| `title` | string | Page title extracted from `<title>` or the first `<h1>` |
| `headings` | string (JSON) | JSON array of `{"level": int, "text": string}` objects for h1--h6 elements |
| `content` | string | Cleaned body text with HTML tags, scripts, and styles removed |
| `meta_description` | string | Content of the `<meta name="description">` or `og:description` tag |
| `crawl_date` | string (ISO 8601) | UTC timestamp of when the page was crawled |
| `word_count` | integer | Number of whitespace-delimited words in `content` |

---

## Images Dataset

The `images` file contains one row per image found across all crawled pages.

| Field | Type | Description |
|---|---|---|
| `image_path` | string | Local file path relative to the output directory (empty if downloading was disabled) |
| `source_page` | string | URL of the page where the image was found |
| `alt_text` | string | Alt text from the `<img>` tag |
| `image_url` | string | Original absolute URL of the image |

Images are deduplicated using perceptual hashing. Files are named by their SHA-256 content hash to avoid duplicates on disk.

---

## Crawl Report

The `crawl_report.json` file contains summary statistics for the crawl.

```json
{
  "total_pages": 15,
  "failed_pages": 2,
  "total_images": 42,
  "external_links": 8,
  "time_taken_seconds": 12.5,
  "errors": [
    {
      "url": "https://example.com/broken",
      "error": "HTTP 404: Bad status"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `total_pages` | integer | Number of pages successfully crawled |
| `failed_pages` | integer | Number of pages that failed (fetch, parse, or extraction errors) |
| `total_images` | integer | Total images found across all pages |
| `external_links` | integer | Count of unique external links discovered |
| `time_taken_seconds` | float | Wall-clock time for the crawl in seconds |
| `errors` | array | List of error records (capped at 100). Each contains `url` and `error`. |

---

## Manifest

The `manifest.json` file lists every file in the output directory with its size and checksum.

```json
{
  "created_at": "2026-02-23T10:01:30Z",
  "total_files": 8,
  "files": [
    {
      "path": "pages.parquet",
      "size_bytes": 12345,
      "sha256": "e3b0c44298fc1c14..."
    }
  ]
}
```

This file can be used to verify data integrity after transfer or archival.

---

## Readable Markdown

The `readable/` directory contains human-readable Markdown renderings of each crawled page.

- **`{page_slug}.md`** — Individual page. Includes title, URL, meta description, word count, page structure (headings), and cleaned body content.
- **`all_pages.md`** — All pages combined into a single document, separated by horizontal rules.

Page slugs are derived from the URL: the domain and path are converted to lowercase alphanumeric characters with underscores, truncated to 80 characters.

---

## Raw HTML

The `raw_html/` directory stores the original HTML responses, organized by domain.

- **`{hash}.html.gz`** — Gzip-compressed HTML. The hash is the SHA-256 of the response body, ensuring deduplication.
- **`{hash}.meta.json`** — Sidecar file containing fetch metadata: URL, HTTP status code, response time, and content size.

This directory is only created if raw HTML saving is enabled (the default). Disable it with `--no-raw-html` or `"save_raw_html": false`.

---

## Downloaded Images

The `images/` directory contains downloaded image files, organized by source domain.

- Files are named by their SHA-256 content hash with the original file extension.
- Images smaller than 100px (configurable) are excluded.
- Perceptual hashing is used to detect and skip near-duplicate images.

This directory is only created if image downloading is enabled (the default). Disable it with `--no-images` or `"download_images": false`.
