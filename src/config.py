"""Configuration management for the Google Places Business Scraper.

Handles environment variable loading (with built-in fallback for .env files),
CPU core/thread detection for concurrency, API quota rate limits, and runtime configuration.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


def load_dotenv(env_path: Optional[Path] = None) -> None:
    """Lightweight .env file parser to populate os.environ if not already set.

    Avoids hard dependency on python-dotenv while seamlessly reading local .env files.
    """
    if env_path is None:
        env_path = Path(".env")

    if not env_path.exists() or not env_path.is_file():
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


# Automatically attempt to load local .env if present
load_dotenv()


def get_default_workers() -> int:
    """Calculate default worker thread count based on CPU cores/threads and API safety limits.

    Uses os.cpu_count() while applying an upper default bound of 8 threads so concurrent
    workers do not overwhelm Google's standard rate limits (10 QPS / 600 QPM).
    Can be overridden via the --workers CLI argument.
    """
    cpu_threads = os.cpu_count() or 4
    return max(2, min(8, cpu_threads))


@dataclass
class ScraperConfig:
    """Runtime configuration container for POI scraping."""

    api_key: Optional[str] = None
    radius_km: float = 3.0
    locations_file: str = "locations.csv"
    output_dir: str = "./data/google"
    search_url: str = "https://places.googleapis.com/v1/places:searchText"
    page_size: int = 20
    request_timeout: float = 15.0
    inter_query_delay: float = 0.2
    pagination_delay: float = 1.0
    max_workers: Optional[int] = None
    max_qps: float = 10.0
    max_retries: int = 4
    retry_backoff: float = 1.5

    def __post_init__(self) -> None:
        """Resolve API key and dynamic CPU-based worker count if not explicitly set."""
        if not self.api_key:
            self.api_key = os.environ.get("GOOGLE_API_KEY", "")

        if self.max_workers is None or self.max_workers <= 0:
            self.max_workers = get_default_workers()


# Global default configuration instance
DEFAULT_CONFIG = ScraperConfig()
