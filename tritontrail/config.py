from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("TRITONRADAR_DB_PATH", "data/tritonradar.db"))
    directory_url: str = os.getenv("UCSD_DIRECTORY_URL", "https://studentorg.ucsd.edu/")
    user_agent: str = os.getenv("CRAWLER_USER_AGENT", "TritonRadar/0.1")
    crawl_delay_seconds: float = float(os.getenv("CRAWL_DELAY_SECONDS", "0.35"))
    crawl_timeout_seconds: float = float(os.getenv("CRAWL_TIMEOUT_SECONDS", "20"))
    gemma_base_url: str = os.getenv("GEMMA_BASE_URL", "").strip()
    gemma_api_key: str = os.getenv("GEMMA_API_KEY", "").strip()
    gemma_provider: str = os.getenv("GEMMA_PROVIDER", "google").strip().lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemma_model: str = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    gemma_timeout_seconds: float = float(os.getenv("GEMMA_TIMEOUT_SECONDS", "90"))
    brightdata_api_key: str = os.getenv("BRIGHTDATA_API_KEY", "").strip()
    brightdata_dataset_id: str = os.getenv("BRIGHTDATA_INSTAGRAM_DATASET_ID", "gd_lk5ns7kz21pck8jpis").strip()
    brightdata_timeout_seconds: float = float(os.getenv("BRIGHTDATA_TIMEOUT_SECONDS", "120"))
    instagram_posts_per_account: int = int(os.getenv("INSTAGRAM_POSTS_PER_ACCOUNT", "10"))
    image_max_bytes: int = int(os.getenv("IMAGE_MAX_BYTES", "8000000"))


settings = Settings()
