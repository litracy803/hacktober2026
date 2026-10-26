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

GENERIC_SOCIAL_HANDLES = {"ucsandiego", "ucsd", "uc_san_diego", "company", "channel"}


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
    parts = [part for part in path.split("/") if part]
    if platform == "linkedin" and len(parts) >= 2 and parts[0] in {"company", "in"}:
        handle = parts[1]
    else:
        handle = parts[0] if parts and platform not in {"linktree", "discord"} else None
    return {"platform": platform, "handle": handle or "", "url": url, "verification": "official_link", "evidence": evidence, "source_url": source_url}


def social_handles_from_text(text: str, source_url: str) -> list[dict[str, str]]:
    """Convert explicit directory social fields into conservative candidates.

    The UCSD directory uses both ``@handle`` and bare values such as
    ``acm.at.ucsd`` after the ``Social Media`` label.  The latter was being
    missed by the original extractor, which made the apparent discovery rate
    much lower than the source actually supports.
    """
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    # Prefer the bounded field so words from the following directory sections
    # (for example, a fund manager's name) cannot become handles.
    field_pattern = re.compile(
        r"(?:social\s+media|instagram|ig)\s*[:：-]?\s*"
        r"(https?://[^\s]+|@[A-Za-z0-9_.-]+|[A-Za-z][A-Za-z0-9_.-]{2,})"
        r"(?=\s+(?:fund\s+manager|principal\s+members|organization\s+constitution|student\s+organization\s+advisor)\b|$)",
        re.I,
    )
    for match in field_pattern.finditer(text):
        value = match.group(1).strip().rstrip(".,;)")
        context = text[max(0, match.start() - 40):min(len(text), match.end() + 80)]
        if value.lower().startswith(("http://", "https://")):
            parsed = social_link(value, source_url, context)
            if parsed and parsed["url"] not in seen:
                parsed["verification"] = "directory_link"
                results.append(parsed)
                seen.add(parsed["url"])
            continue
        handle = value.lstrip("@").lower()
        if handle in GENERIC_SOCIAL_HANDLES or "@" in handle or handle in {"fund", "manager", "principal", "members"}:
            continue
        url = f"https://www.instagram.com/{handle}"
        if url in seen:
            continue
        results.append({"platform": "instagram", "handle": handle, "url": url, "verification": "directory_handle_candidate", "evidence": context, "source_url": source_url})
        seen.add(url)

    # Also support a handle explicitly attached to a sentence that does not
    # have a bounded field value (for example, older directory templates).
    pattern = re.compile(r"(?:social\s+media|instagram|ig)\s*[:：-]?\s*@([A-Za-z0-9_.-]+)", re.I)
    for match in pattern.finditer(text):
        handle = match.group(1).lower().rstrip(".,")
        url = f"https://www.instagram.com/{handle}"
        if handle in GENERIC_SOCIAL_HANDLES or url in seen:
            continue
        context = text[max(0, match.start() - 40):min(len(text), match.end() + 40)]
        results.append({"platform": "instagram", "handle": handle, "url": url, "verification": "directory_handle_candidate", "evidence": context, "source_url": source_url})
        seen.add(url)
    return results


def parse_page(html: str, url: str, include_chrome_links: bool = False) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    if not include_chrome_links:
        for node in soup(["nav", "header", "footer", "aside"]):
            node.decompose()
    content = soup.select_one("main, #main-content, .main-content, article") or soup.body or soup
    text = clean(content.get_text(" "))
    links: list[dict[str, str]] = []
    external_links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href, label = anchor.get("href", ""), clean(anchor.get_text(" "))
        target = urljoin(url, href.strip())
        if target.startswith(("mailto:", "tel:", "javascript:")) or target in seen:
            continue
        seen.add(target)
        social = social_link(target, url, label)
        if social:
            links.append(social)
        elif urlparse(target).netloc and urlparse(target).netloc != urlparse(url).netloc:
            external_links.append(target)
    title = clean(soup.title.get_text(" ")) if soup.title else ""
    links.extend(social_handles_from_text(text, url))
    return {"url": url, "title": title, "text": text, "links": links, "external_links": external_links[:10], "content_hash": content_hash(text)}


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
