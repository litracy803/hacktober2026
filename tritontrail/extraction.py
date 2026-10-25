from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

SOCIAL_HOSTS = {
    "instagram.com": "instagram", "www.instagram.com": "instagram",
    "facebook.com": "facebook", "www.facebook.com": "facebook",
    "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",
    "youtube.com": "youtube", "www.youtube.com": "youtube",
    "www.linkedin.com": "linkedin", "linkedin.com": "linkedin",
    "discord.gg": "discord", "linktr.ee": "linktree", "www.linktr.ee": "linktree",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def social_link(url: str, source_url: str, evidence: str = "") -> dict[str, str] | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    platform = SOCIAL_HOSTS.get(host)
    if not platform:
        return None
    path = parsed.path.strip("/")
    handle = path.split("/")[0] if path and platform not in {"linktree", "discord"} else None
    return {"platform": platform, "handle": handle or "", "url": url, "verification": "official_link", "evidence": evidence, "source_url": source_url}


def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = clean(soup.get_text(" "))
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        target = urljoin(url, anchor.get("href", "").strip())
        if target.startswith(("mailto:", "tel:", "javascript:")) or target in seen:
            continue
        seen.add(target)
        label = clean(anchor.get_text(" "))
        social = social_link(target, url, label)
        if social:
            links.append(social)
    title = clean(soup.title.get_text(" ")) if soup.title else ""
    return {"url": url, "title": title, "text": text, "links": links, "content_hash": content_hash(text)}


def parse_directory(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    organizations: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        name = clean(anchor.get_text(" "))
        target = urljoin(base_url, href)
        if not name or not target.startswith(base_url.rstrip("/")):
            continue
        match = re.search(r"/(?:Home/)?Details/(\d+)", target, re.I)
        if not match or target in seen:
            continue
        seen.add(target)
        organizations.append({"id": match.group(1), "official_name": name, "directory_url": target})
    return organizations
