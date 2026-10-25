from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from .config import Settings

PROMPT_VERSION = "v1"
TAGS = ["academic", "career", "cultural", "faith", "hobby", "performance", "service", "social", "sport", "technology", "health", "political", "identity-community", "graduate", "undergraduate"]


def input_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fallback_payload(name: str, description: str) -> dict[str, Any]:
    lowered = f"{name} {description}".lower()
    tags = []
    keyword_tags = {"computer": "technology", "engineering": "academic", "career": "career", "cultural": "cultural", "dance": "performance", "volunteer": "service", "health": "health", "sport": "sport", "faith": "faith", "church": "faith", "social": "social"}
    for key, tag in keyword_tags.items():
        if key in lowered and tag not in tags:
            tags.append(tag)
    return {"normalized_name": name, "aliases": [], "summary": description[:360], "features": [{"tag": tag, "confidence": "low", "evidence": "Keyword-based fallback; verify from source."} for tag in tags], "evidence": [], "unknowns": ["Gemma enrichment was not configured or unavailable."]}


class GemmaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.gemma_base_url)

    def enrich(self, official_name: str, description: str, source_text: str, source_url: str) -> tuple[dict[str, Any], str, str | None]:
        prompt = f"""You are enriching a UC San Diego student-organization record. Return JSON only.
Never invent facts, social handles, URLs, audience eligibility, or meeting details. Use unknown when unsupported.
Allowed feature tags: {', '.join(TAGS)}.
Every feature and evidence item must include a short exact or near-exact supporting quote from the supplied source.
Schema: {{\"normalized_name\": string, \"aliases\": string[], \"summary\": string, \"features\": [{{\"tag\": string, \"confidence\": \"high|medium|low|unknown\", \"evidence\": string}}], \"evidence\": [{{\"field\": string, \"quote\": string, \"confidence\": \"high|medium|low|unknown\"}}], \"unknowns\": string[]}}

Official name: {official_name}
Directory description: {description}
Source URL: {source_url}
Source text:\n{source_text[:12000]}"""
        raw = ""
        if not self.configured:
            return fallback_payload(official_name, description), raw, "Gemma endpoint is not configured"
        try:
            headers = {"Authorization": f"Bearer {self.settings.gemma_api_key}"} if self.settings.gemma_api_key else {}
            response = httpx.post(f"{self.settings.gemma_base_url.rstrip('/')}/chat/completions", headers=headers, json={"model": self.settings.gemma_model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "You are a careful information extraction system."}, {"role": "user", "content": prompt}]}, timeout=self.settings.gemma_timeout_seconds)
            response.raise_for_status()
            raw = response.text
            data = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(data)
            payload["features"] = [x for x in payload.get("features", []) if isinstance(x, dict) and x.get("tag") in TAGS]
            return payload, raw, None
        except Exception as exc:  # keep crawl usable when the model is unavailable
            return fallback_payload(official_name, description), raw, str(exc)
