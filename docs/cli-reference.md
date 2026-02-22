# CLI Reference

The pipeline provides two commands: `crawl` (default) for running a crawl, and `serve` for starting the REST API server.

---

## Crawl Command

Crawl a website and export structured datasets.

```
python main.py --url <URL> [OPTIONS]
```

When running inside Docker:

```
docker compose exec pipeline-api /entrypoint.sh crawl --url <URL> [OPTIONS]
```

### Options

| Option | Short | Default | Description |
|---|---|---|---|
| `--url` | `-u` | *(required)* | Starting URL to crawl. Must begin with `http://` or `https://`. |
| `--depth` | `-d` | `3` | Maximum crawl depth. The crawler uses breadth-first search; this controls how many link-hops from the seed URL are followed. Range: 1--20. |
| `--limit` | `-l` | `100` | Maximum number of pages to crawl. The crawler stops after processing this many pages, even if the frontier is not exhausted. Range: 1--10,000. |
| `--rate-limit` | `-r` | `1.0` | Minimum delay in seconds between consecutive HTTP requests. Helps avoid overloading target servers. |
| `--output-dir` | `-o` | `site_dataset` | Directory where output files are written. Created automatically if it does not exist. |
| `--format` | `-f` | `parquet` | Export format for tabular data. Accepted values: `parquet`, `csv`, `jsonl`. |
| `--no-raw-html` | | `false` | Skip saving gzip-compressed raw HTML files. Reduces disk usage. |
| `--no-images` | | `false` | Skip downloading images from crawled pages. |
| `--no-dynamic` | | `false` | Disable the Playwright/Chromium fallback for JavaScript-heavy pages. Use this if Playwright is not installed or not needed. |
| `--log-level` | | `INFO` | Logging verbosity. Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `--json-logs` | | `false` | Output structured JSON log lines instead of human-readable console output. Useful for log aggregation systems. |

### Examples

Basic crawl with defaults:

```bash
python main.py --url https://example.com
```

Crawl with limited scope and CSV output:

```bash
python main.py --url https://example.com --depth 1 --limit 10 --format csv
```

Fast crawl without images or raw HTML:

```bash
python main.py --url https://example.com --no-images --no-raw-html --rate-limit 0.5
```

Verbose debug logging:

```bash
python main.py --url https://example.com --log-level DEBUG
```

---

## Serve Command

Start the FastAPI REST API server.

```
python main.py serve [OPTIONS]
```

When running inside Docker, the container starts in `serve` mode by default:

```bash
docker compose up -d
```

### Options

| Option | Short | Default | Description |
|---|---|---|---|
| `--host` | `-h` | `0.0.0.0` | Network interface to bind to. Use `127.0.0.1` to restrict to localhost. |
| `--port` | `-p` | `8000` | Port number for the HTTP server. |
| `--reload` | | `false` | Enable auto-reload on file changes. Intended for development only. |
| `--log-level` | | `INFO` | Logging verbosity. Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

### Examples

Start the server on the default port:

```bash
python main.py serve
```

Start on a custom port with auto-reload:

```bash
python main.py serve --port 9000 --reload
```

---

## Entrypoint Modes (Docker)

The Docker container uses an entrypoint script that accepts the following modes:

| Mode | Command | Description |
|---|---|---|
| `serve` | `docker compose exec pipeline-api /entrypoint.sh serve` | Start the API server (default) |
| `crawl` | `docker compose exec pipeline-api /entrypoint.sh crawl [OPTIONS]` | Run a one-off crawl via the CLI |
| `shell` | `docker compose exec pipeline-api /entrypoint.sh shell` | Open an interactive bash shell inside the container |
