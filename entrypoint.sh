#!/bin/bash
set -e

# ── Website Ingestion Pipeline — Entrypoint ──────────────────────────
#
# Modes:
#   serve   → Start FastAPI server (default)
#   crawl   → Run CLI crawl (pass --url and other flags)
#   shell   → Drop into bash shell
#   *       → Pass through to any command

case "${1}" in
  serve)
    shift
    echo "🚀 Starting API server on port ${PORT:-8000}..."
    exec uvicorn app.api:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --workers "${WORKERS:-1}" \
      "$@"
    ;;
  crawl)
    shift
    echo "🕷️  Starting crawl..."
    exec python main.py "$@"
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    exec "$@"
    ;;
esac
