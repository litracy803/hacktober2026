from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx

from .config import Settings
from .db import Database
from .extraction import GENERIC_SOCIAL_HANDLES, parse_directory, parse_page
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
                description = self._description(org["official_name"], page["text"])
                org["description"] = description
                self.db.upsert_organization(org)
                self.db.save_source(org["id"], {"url": org["directory_url"], "source_type": "ucsd_directory", "content_hash": page["content_hash"], "raw_text": page["text"]})
                self.db.save_social_links(org["id"], page["links"])
                self._discover_from_official_sites(org["id"], org["official_name"], page.get("external_links", []))
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

    @staticmethod
    def _description(name: str, text: str) -> str:
        """Trim directory chrome and keep the organization-specific portion."""
        normalized = text.strip()
        marker = normalized.find(name)
        if marker >= 0:
            normalized = normalized[marker:]
        for end_marker in (" Previous Student Organizations", " Contact Information"):
            if end_marker in normalized:
                normalized = normalized.split(end_marker, 1)[0]
        return normalized[:4000]

    def _discover_from_official_sites(self, organization_id: str, organization_name: str, urls: list[str]) -> None:
        """Follow a few explicitly linked official sites, never social platforms themselves."""
        visited: set[str] = set()
        for url in urls[:3]:
            if url in visited or any(host in url.lower() for host in ("instagram.com", "facebook.com", "tiktok.com", "youtube.com", "linkedin.com", "discord.gg", "linktr.ee")):
                continue
            visited.add(url)
            try:
                html = self.fetch(url)
                page = parse_page(html, url, include_chrome_links=True)
                self.db.save_source(organization_id, {"url": url, "source_type": "official_club_website", "content_hash": page["content_hash"], "raw_text": page["text"]})
                links = []
                for link in page.get("links", []):
                    handle = (link.get("handle") or "").lower()
                    name_tokens = {token for token in organization_name.lower().replace("@", " ").split() if len(token) > 2 and token not in {"the", "and", "at", "san", "diego", "ucsd", "university", "student", "organization", "club", "association"}}
                    relevant = handle in name_tokens or any(token in handle for token in name_tokens)
                    if handle not in GENERIC_SOCIAL_HANDLES and relevant:
                        links.append(dict(link, verification="official_site_link"))
                self.db.save_social_links(organization_id, links)
            except Exception:
                continue
            time.sleep(self.settings.crawl_delay_seconds)

    def enrich_pending(self, limit: int = 50) -> dict[str, int]:
        done = 0
        failed = 0
        for org in self.db.pending_enrichment(limit):
            try:
                html = self.fetch(org["directory_url"])
                page = parse_page(html, org["directory_url"])
                self._discover_from_official_sites(org["id"], org["official_name"], page.get("external_links", []))
                payload, raw, error = self.gemma.enrich(org["official_name"], org["description"], page["text"], org["directory_url"])
                self.db.save_enrichment(org["id"], payload, raw, self.settings.gemma_model, input_hash(page["text"]), "enriched" if error is None else "pending_enrichment", error)
                done += 1
            except Exception:
                failed += 1
        return {"enriched": done, "failed": failed}

    def discover_socials(self, limit: int = 100) -> dict[str, int]:
        processed = 0
        discovered = 0
        for org in self.db.organizations(limit):
            try:
                html = self.fetch(org["directory_url"])
                page = parse_page(html, org["directory_url"])
                before = self.db.get(org["id"]) or {}
                old_count = len(before.get("social_accounts", []))
                self.db.save_social_links(org["id"], page.get("links", []))
                self.db.clear_social_links(org["id"], "official_site_link")
                self._discover_from_official_sites(org["id"], org["official_name"], page.get("external_links", []))
                after = self.db.get(org["id"]) or {}
                discovered += max(0, len(after.get("social_accounts", [])) - old_count)
                processed += 1
            except Exception:
                continue
        return {"processed": processed, "new_social_accounts": discovered}
