from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .crawler import Crawler
from .db import Database

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
    return {"ok": True, "database": str(settings.db_path), "gemma_configured": bool(settings.gemma_base_url)}


@app.get("/api/stats")
def stats() -> dict:
    return db.stats()


@app.get("/api/organizations")
def organizations(q: str = "", tag: str | None = None, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    return {"items": db.search(q, tag, limit, offset), "limit": limit, "offset": offset}


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
