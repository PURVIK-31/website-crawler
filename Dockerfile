# ── Stage 1: Builder ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="Purvik Sharma"
LABEL description="Website Ingestion & Structuring Pipeline — crawl, extract, and export website data"

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    libpng16-16 \
    # Playwright/Chromium dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libnspr4 \
    fonts-liberation \
    fonts-noto-color-emoji \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Install Playwright Chromium browser
RUN playwright install chromium && \
    playwright install-deps chromium 2>/dev/null || true

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/jobs

# ── Configuration ────────────────────────────────────────────────────
EXPOSE 8000

ENV PIPELINE_DATA_DIR=/app/jobs
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# ── Entrypoint ───────────────────────────────────────────────────────
# Default: run the API server
# CLI:  docker run --rm -v ./data:/app/jobs web-crawler python main.py --url https://example.com
# API:  docker compose up -d
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
