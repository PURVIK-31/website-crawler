"""FastAPI REST API for the Website Ingestion Pipeline.

Provides endpoints for:
- Submitting crawl jobs
- Checking job status
- Downloading results
- Listing past jobs

Run with:  uvicorn app.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

from app.config import CrawlConfig
from app.dataset_storage import DatasetStorage
from app.knowledge.assets import AssetStore
from app.knowledge.errors import AssetNotFoundError, ConfigurationError
from app.knowledge.pipeline import KnowledgePipeline
from app.knowledge.settings import KnowledgeSettings
from app.knowledge.vectors import LanceDBIndexer
from app.logger import setup_logging

# ── setup ─────────────────────────────────────────────────────────────

setup_logging(level="INFO")
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="🌐 Website Ingestion Pipeline API",
    description="Crawl websites, extract structured data, and download reusable datasets.",
    version="1.0.0",
)

# Allow all origins for desktop/web GUI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── data directory ────────────────────────────────────────────────────

DATA_DIR = os.environ.get("PIPELINE_DATA_DIR", "jobs")
os.makedirs(DATA_DIR, exist_ok=True)
KNOWLEDGE_SETTINGS = KnowledgeSettings.from_env()
KNOWLEDGE_PIPELINE = KnowledgePipeline(KNOWLEDGE_SETTINGS)


# ── models ────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlRequest(BaseModel):
    """Request body for submitting a crawl job."""
    url: str = Field(..., description="Starting URL to crawl.")
    max_depth: int = Field(default=3, ge=1, le=20)
    page_limit: int = Field(default=100, ge=1, le=10_000)
    rate_limit: float = Field(default=1.0, gt=0)
    output_format: str = Field(default="parquet", description="parquet | csv | jsonl")
    save_raw_html: bool = Field(default=True)
    download_images: bool = Field(default=True)
    dynamic_fallback: bool = Field(default=True)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v.strip())
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must start with http:// or https://")
        if not parsed.netloc:
            raise ValueError("Invalid URL")
        return v.strip()


class CrawlResponse(BaseModel):
    """Response after submitting a crawl job."""
    job_id: str
    status: JobStatus
    message: str


class JobInfo(BaseModel):
    """Detailed job information."""
    job_id: str
    status: JobStatus
    url: str
    created_at: str
    completed_at: Optional[str] = None
    report: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class SearchRequest(BaseModel):
    asset_id: str = Field(..., min_length=1)
    asset_version: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class AskRequest(BaseModel):
    asset_id: str = Field(..., min_length=1)
    asset_version: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


# ── in-memory job registry ────────────────────────────────────────────

_jobs: dict[str, dict[str, Any]] = {}


def _get_job(job_id: str, require_completed: bool = False) -> dict[str, Any]:
    """Look up a job, raising the appropriate HTTP error if unavailable."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if require_completed and job["status"] != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job status is '{job['status']}', not completed.")
    return job


def _dataset_file_response(job: dict[str, Any], name: str) -> FileResponse:
    """Serve a dataset file (pages/images) in whichever format it was exported."""
    for ext in ("parquet", "csv", "jsonl"):
        path = os.path.join(job["output_dir"], f"{name}.{ext}")
        if os.path.exists(path):
            return FileResponse(path, filename=f"{name}.{ext}")
    raise HTTPException(status_code=404, detail=f"{name.capitalize()} file not found.")


# ── background crawl task ─────────────────────────────────────────────

async def _run_crawl(job_id: str, config: CrawlConfig) -> None:
    """Execute a crawl job in the background."""
    _jobs[job_id]["status"] = JobStatus.RUNNING
    logger.info("job_started", job_id=job_id, url=config.start_url)

    try:
        report, manifest = await KNOWLEDGE_PIPELINE.ingest(config, asset_id=job_id)
        _jobs[job_id]["status"] = JobStatus.COMPLETED
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _jobs[job_id]["report"] = report
        _jobs[job_id]["asset_version"] = manifest.asset_version
        logger.info("job_completed", job_id=job_id, report=report, asset_id=manifest.asset_id)

    except Exception as exc:
        _jobs[job_id]["status"] = JobStatus.FAILED
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.error("job_failed", job_id=job_id, error=str(exc))


# ── endpoints ─────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Health check."""
    return {
        "service": "Website Ingestion Pipeline",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.post("/api/crawl", response_model=CrawlResponse, tags=["Crawl"])
async def submit_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Submit a new crawl job. Returns immediately with a job ID.

    The crawl runs in the background — poll ``/api/jobs/{job_id}`` for status.
    """
    job_id = str(uuid.uuid4())[:8]
    output_dir = os.path.join(DATA_DIR, job_id)

    config = CrawlConfig(
        start_url=request.url,
        max_depth=request.max_depth,
        page_limit=request.page_limit,
        rate_limit=request.rate_limit,
        output_dir=output_dir,
        output_format=request.output_format,
        save_raw_html=request.save_raw_html,
        download_images=request.download_images,
        dynamic_fallback=request.dynamic_fallback,
    )

    _jobs[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "url": request.url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "report": None,
        "error": None,
        "output_dir": output_dir,
    }

    background_tasks.add_task(_run_crawl, job_id, config)

    return CrawlResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"Crawl job submitted. Poll /api/jobs/{job_id} for status.",
    )


@app.get("/api/jobs", tags=["Jobs"])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
):
    """List all crawl jobs, optionally filtered by status."""
    jobs = list(_jobs.values())
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    # Strip internal fields
    return [
        {k: v for k, v in j.items() if k != "output_dir"}
        for j in sorted(jobs, key=lambda j: j["created_at"], reverse=True)
    ]


@app.get("/api/jobs/{job_id}", response_model=JobInfo, tags=["Jobs"])
async def get_job(job_id: str):
    """Get the status and report for a specific job."""
    job = _get_job(job_id)
    return JobInfo(
        job_id=job["job_id"],
        status=job["status"],
        url=job["url"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        report=job.get("report"),
        error=job.get("error"),
    )


@app.get("/api/jobs/{job_id}/report", tags=["Results"])
async def get_report(job_id: str):
    """Download the crawl_report.json for a completed job."""
    job = _get_job(job_id, require_completed=True)
    report_path = os.path.join(job["output_dir"], "crawl_report.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report file not found.")
    return FileResponse(report_path, media_type="application/json", filename="crawl_report.json")


@app.get("/api/jobs/{job_id}/pages", tags=["Results"])
async def get_pages(job_id: str):
    """Download the pages dataset for a completed job."""
    job = _get_job(job_id, require_completed=True)
    return _dataset_file_response(job, "pages")


@app.get("/api/jobs/{job_id}/images", tags=["Results"])
async def get_images(job_id: str):
    """Download the images dataset for a completed job."""
    job = _get_job(job_id, require_completed=True)
    return _dataset_file_response(job, "images")


@app.get("/api/jobs/{job_id}/download", tags=["Results"])
async def download_dataset(job_id: str):
    """Download the entire dataset as a ZIP archive."""
    job = _get_job(job_id, require_completed=True)
    output_dir = job["output_dir"]
    zip_path = output_dir + ".zip"

    if not os.path.exists(zip_path):
        ds = DatasetStorage(output_dir)
        ds.compress(fmt="zip")

    return FileResponse(zip_path, media_type="application/zip", filename=f"{job_id}_dataset.zip")


@app.get("/api/assets", tags=["Knowledge"])
async def list_assets():
    """List durable v2 asset manifests."""
    return [manifest.model_dump(mode="json") for manifest in AssetStore(KNOWLEDGE_SETTINGS.storage_root).list_manifests()]


@app.get("/api/assets/{asset_id}/{asset_version}/manifest", tags=["Knowledge"])
async def get_asset_manifest(asset_id: str, asset_version: str):
    """Return a versioned knowledge asset manifest."""
    try:
        return AssetStore(KNOWLEDGE_SETTINGS.storage_root).read_manifest(asset_id, asset_version).model_dump(mode="json")
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/search", tags=["Knowledge"])
async def search(request: SearchRequest):
    """Search one explicit knowledge asset/version using its embedding profile."""
    if not KNOWLEDGE_SETTINGS.enable_embeddings:
        raise HTTPException(status_code=503, detail="Embeddings are disabled for this deployment.")
    try:
        manifest = AssetStore(KNOWLEDGE_SETTINGS.storage_root).read_manifest(request.asset_id, request.asset_version)
        if not manifest.provider_profiles:
            raise HTTPException(status_code=409, detail="This asset has no embeddings.")
        profile_id = manifest.provider_profiles[0]
        deployment_profile = KNOWLEDGE_PIPELINE.embedding_provider.profile_id
        if profile_id != deployment_profile:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "embedding_profile_mismatch",
                    "message": "Query embedding profile does not match the asset's index.",
                    "requested_profile": deployment_profile,
                    "asset_profile": profile_id,
                },
            )
        vector = (await KNOWLEDGE_PIPELINE.embedding_provider.embed([request.query]))[0]
        rows = await asyncio.to_thread(
            LanceDBIndexer(KNOWLEDGE_SETTINGS.storage_root / "vectors", profile_id).search,
            request.asset_id, request.asset_version, vector, request.limit,
        )
        return {"asset_id": request.asset_id, "asset_version": request.asset_version, "results": rows}
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/ask", tags=["Knowledge"])
async def ask(request: AskRequest):
    """Reserved grounded-answer endpoint until an LLM provider is configured."""
    raise HTTPException(status_code=503, detail="No LLM provider is configured for grounded answers.")


@app.delete("/api/jobs/{job_id}", tags=["Jobs"])
async def delete_job(job_id: str):
    """Delete a completed/failed job and its data."""
    job = _get_job(job_id)
    if job["status"] == JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete a running job.")

    # Clean up files
    output_dir = job.get("output_dir", "")
    if output_dir:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        zip_path = output_dir + ".zip"
        if os.path.exists(zip_path):
            os.remove(zip_path)

    del _jobs[job_id]
    return {"message": f"Job '{job_id}' deleted."}
