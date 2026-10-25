from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx

from .config import Settings
from .db import Database
from .extraction import parse_directory, parse_page
from .gemma import GemmaClient, input_hash


class Crawler:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.gemma = GemmaClient(settings)
        self.client = httpx.Client(headers={"User-Agent": settings.user_agent, "Accept": "text/html"}, timeout=settings.crawl_timeout_seconds, follow_redirects=True)

    def fetch(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(min(2.0, 0.5 * (2 ** attempt)))
        assert last_error is not None
        raise last_error

    def crawl(self, limit: int | None = None, enrich: bool = False) -> dict[str, int]:
        directory_html = self.fetch(self.settings.directory_url)
        organizations = parse_directory(directory_html, self.settings.directory_url)
        if limit:
            organizations = organizations[:limit]
        counts = {"discovered": len(organizations), "processed": 0, "enriched": 0, "failed": 0}
        for org in organizations:
            try:
                detail_html = self.fetch(org["directory_url"])
                page = parse_page(detail_html, org["directory_url"])
                description = page["text"][:4000]
                org["description"] = description
                self.db.upsert_organization(org)
                self.db.save_source(org["id"], {"url": org["directory_url"], "source_type": "ucsd_directory", "content_hash": page["content_hash"], "raw_text": page["text"]})
                self.db.save_social_links(org["id"], page["links"])
                if enrich:
                    payload, raw, error = self.gemma.enrich(org["official_name"], description, page["text"], org["directory_url"])
                    status = "enriched" if error is None else "pending_enrichment"
                    self.db.save_enrichment(org["id"], payload, raw, self.settings.gemma_model, input_hash(page["text"]), status, error)
                    counts["enriched"] += int(error is None)
                counts["processed"] += 1
            except Exception:
                counts["failed"] += 1
            time.sleep(self.settings.crawl_delay_seconds)
        return counts

    def enrich_pending(self, limit: int = 50) -> dict[str, int]:
        done = 0
        failed = 0
        for org in self.db.pending_enrichment(limit):
            try:
                html = self.fetch(org["directory_url"])
                page = parse_page(html, org["directory_url"])
                payload, raw, error = self.gemma.enrich(org["official_name"], org["description"], page["text"], org["directory_url"])
                self.db.save_enrichment(org["id"], payload, raw, self.settings.gemma_model, input_hash(page["text"]), "enriched" if error is None else "pending_enrichment", error)
                done += 1
            except Exception:
                failed += 1
        return {"enriched": done, "failed": failed}
