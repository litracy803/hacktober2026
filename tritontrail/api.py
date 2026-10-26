from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .crawler import Crawler
from .db import Database
from .instagram import InstagramIngestor
from .pilot import matches_pilot

settings.db_path.parent.mkdir(parents=True, exist_ok=True)
db = Database(settings.db_path)
app = FastAPI(title="TritonTrail", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    configured = bool(settings.gemini_api_key) if settings.gemma_provider == "google" else bool(settings.gemma_base_url)
    return {"ok": True, "database": str(settings.db_path), "gemma_provider": settings.gemma_provider, "gemma_configured": configured}


@app.get("/api/stats")
def stats() -> dict:
    return db.stats()


@app.get("/api/organizations")
def organizations(q: str = "", tag: str | None = None, pilot: bool = False, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    if pilot:
        items = [item for item in db.search(q, tag, 1000, 0) if matches_pilot(item["official_name"])]
        return {"items": items[offset:offset + limit], "limit": limit, "offset": offset, "pilot": True}
    return {"items": db.search(q, tag, limit, offset), "limit": limit, "offset": offset, "pilot": False}


@app.get("/api/events")
def events(tag: str | None = None, limit: int = Query(100, ge=1, le=500)) -> dict:
    return {"items": db.events(tag, limit), "limit": limit, "tag": tag}


@app.get("/api/instagram/issues")
def instagram_issues(include_recovered: bool = False, limit: int = Query(200, ge=1, le=1000)) -> dict:
    return {"items": db.instagram_issues(include_recovered, limit), "limit": limit}


@app.post("/api/instagram/issues/{issue_id}/retry")
def retry_instagram_issue(issue_id: int) -> dict:
    if not db.retry_instagram_issue(issue_id):
        raise HTTPException(status_code=404, detail="Instagram account issue not found")
    return {"accepted": True, "message": "Account will be attempted on the next Instagram sync", "issue_id": issue_id}


@app.get("/api/organizations/{organization_id}")
def organization(organization_id: str) -> dict:
    result = db.get(organization_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return result


def run_crawl(limit: int | None, enrich: bool) -> None:
    Crawler(settings, db).crawl(limit=limit, enrich=enrich)


@app.post("/api/crawl", status_code=202)
def crawl(background_tasks: BackgroundTasks, limit: int | None = Query(None, ge=1, le=1000), enrich: bool = True) -> dict:
    background_tasks.add_task(run_crawl, limit, enrich)
    return {"accepted": True, "message": "Crawl queued", "limit": limit, "enrich": enrich}


def run_instagram_sync(account_limit: int | None, posts_per_account: int | None) -> None:
    InstagramIngestor(settings, db).sync(account_limit, posts_per_account)


@app.post("/api/instagram/sync", status_code=202)
def instagram_sync(background_tasks: BackgroundTasks,
                   account_limit: int | None = Query(None, ge=1, le=1000),
                   posts_per_account: int | None = Query(None, ge=1, le=100)) -> dict:
    if not settings.brightdata_api_key:
        raise HTTPException(status_code=503, detail="BRIGHTDATA_API_KEY is not configured")
    if not settings.gemma_base_url:
        raise HTTPException(status_code=503, detail="GEMMA_BASE_URL is not configured")
    background_tasks.add_task(run_instagram_sync, account_limit, posts_per_account)
    return {"accepted": True, "message": "Instagram fetch and event extraction queued", "account_limit": account_limit, "posts_per_account": posts_per_account}
