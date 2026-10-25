from __future__ import annotations

import hashlib
import time
from urllib.parse import urlparse
from typing import Any

import httpx

from .config import Settings
from .db import Database
from .gemma import GemmaClient

BRIGHTDATA_URL = "https://api.brightdata.com/datasets/v3/scrape"


def _post_id(post: dict[str, Any]) -> str:
    value = str(post.get("id") or post.get("url") or "")
    return value or hashlib.sha256(repr(post).encode()).hexdigest()


def _posts_from_response(data: Any) -> list[dict[str, Any]]:
    """Bright Data returns account records with a nested `posts` list."""
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    records = data if isinstance(data, list) else data.get("data", data.get("results", [])) if isinstance(data, dict) else []
    if isinstance(records, dict):
        records = [records]
    posts: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        nested = record.get("posts")
        if isinstance(nested, list):
            posts.extend(post for post in nested if isinstance(post, dict))
        elif record.get("url") and (record.get("caption") is not None or record.get("image_url")):
            posts.append(record)
        elif record.get("error"):
            raise RuntimeError(str(record["error"]))
    return posts


class InstagramIngestor:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.gemma = GemmaClient(settings)
        self.client = httpx.Client(timeout=settings.brightdata_timeout_seconds, follow_redirects=True)

    @property
    def configured(self) -> bool:
        return bool(self.settings.brightdata_api_key)

    def fetch_account_posts(self, account: dict[str, Any], posts_per_account: int | None = None) -> list[dict[str, Any]]:
        if not self.configured:
            raise RuntimeError("BRIGHTDATA_API_KEY is not configured")
        handle = str(account.get("handle", "")).strip().lstrip("@")
        parsed = urlparse(str(account.get("url", "")))
        if not handle and parsed.hostname and parsed.hostname.lower().endswith("instagram.com"):
            handle = parsed.path.strip("/").split("/")[0]
        if not handle:
            return []
        profile_url = f"https://www.instagram.com/{handle}/"
        response = self.client.post(
            BRIGHTDATA_URL,
            params={"dataset_id": self.settings.brightdata_dataset_id, "notify": "false",
                    "include_errors": "true", "type": "discover_new", "discover_by": "url"},
            headers={"Authorization": f"Bearer {self.settings.brightdata_api_key}"},
            json={"input": [{"url": profile_url, "num_of_posts": posts_per_account or self.settings.instagram_posts_per_account,
                             "start_date": "", "end_date": "", "post_type": ""}], "limit_per_input": None},
        )
        response.raise_for_status()
        posts = _posts_from_response(response.json())
        normalized = []
        for post in posts:
            post_url = str(post.get("url") or "").strip()
            if not post_url:
                continue
            location_data = post.get("location")
            location = location_data.get("name") if isinstance(location_data, dict) else location_data
            normalized.append({"id": _post_id(post), "post_url": post_url,
                               "image_url": post.get("image_url"), "caption": str(post.get("caption") or ""),
                               "posted_at": post.get("datetime"), "location": location})
        return normalized

    def fetch_posts(self, account_limit: int | None = None, posts_per_account: int | None = None) -> dict[str, int]:
        accounts = self.db.instagram_accounts(account_limit)
        counts = {"accounts": len(accounts), "posts_received": 0, "posts_saved": 0, "failed": 0}
        for account in accounts:
            try:
                posts = self.fetch_account_posts(account, posts_per_account)
                counts["posts_received"] += len(posts)
                for post in posts:
                    post.update({"event_data": {}, "extraction_status": "pending"})
                    self.db.save_social_post(account["organization_id"], post)
                    counts["posts_saved"] += 1
            except Exception:
                counts["failed"] += 1
            time.sleep(self.settings.crawl_delay_seconds)
        return counts

    def _download_image(self, image_url: str | None) -> tuple[bytes | None, str]:
        if not image_url:
            return None, "image/jpeg"
        parsed = urlparse(image_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (host == "cdninstagram.com" or host.endswith(".cdninstagram.com")):
            return None, "image/jpeg"
        chunks: list[bytes] = []
        size = 0
        with self.client.stream("GET", image_url) as response:
            response.raise_for_status()
            mime_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            if not mime_type.startswith("image/"):
                return None, "image/jpeg"
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > self.settings.image_max_bytes:
                    return None, "image/jpeg"
                chunks.append(chunk)
        return b"".join(chunks), mime_type

    def process_pending(self, limit: int = 50) -> dict[str, int]:
        posts = self.db.pending_posts(limit)
        counts = {"processed": 0, "events": 0, "failed": 0}
        for post in posts:
            try:
                try:
                    image, mime_type = self._download_image(post.get("image_url"))
                except httpx.HTTPError:
                    # Signed CDN URLs can expire; the caption can still contain an event.
                    image, mime_type = None, "image/jpeg"
                event, _, error = self.gemma.extract_event(post["official_name"], post["caption"], post["post_url"], image, mime_type)
                self.db.save_social_post(post["organization_id"], {**post, "event_data": event,
                    "extraction_status": "processed" if error is None else "failed", "extraction_error": error})
                counts["processed"] += 1
                counts["events"] += int(bool(event.get("is_event")))
                counts["failed"] += int(error is not None)
            except Exception:
                counts["failed"] += 1
        return counts

    def sync(self, account_limit: int | None = None, posts_per_account: int | None = None, process_limit: int = 500) -> dict[str, int]:
        fetched = self.fetch_posts(account_limit, posts_per_account)
        processed = self.process_pending(process_limit)
        return {**fetched, **processed}
