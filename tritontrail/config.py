from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("TRITONTRAIL_DB_PATH", "data/tritontrail.db"))
    directory_url: str = os.getenv("UCSD_DIRECTORY_URL", "https://studentorg.ucsd.edu/")
    user_agent: str = os.getenv("CRAWLER_USER_AGENT", "TritonTrail/0.1")
    crawl_delay_seconds: float = float(os.getenv("CRAWL_DELAY_SECONDS", "0.35"))
    crawl_timeout_seconds: float = float(os.getenv("CRAWL_TIMEOUT_SECONDS", "20"))
    gemma_base_url: str = os.getenv("GEMMA_BASE_URL", "").strip()
    gemma_api_key: str = os.getenv("GEMMA_API_KEY", "").strip()
    gemma_provider: str = os.getenv("GEMMA_PROVIDER", "google").strip().lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemma_model: str = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    gemma_timeout_seconds: float = float(os.getenv("GEMMA_TIMEOUT_SECONDS", "90"))


settings = Settings()
