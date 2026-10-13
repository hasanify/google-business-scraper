"""Google Places POI Scraper - Backward-Compatible Entry Point.

This module preserves backwards compatibility with existing workflows while
delegating functionality to the modular `src` package.

All original constants, functions, and symbols remain available for import.
"""

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from src.api.google_places import GooglePlacesClient
from src.config import DEFAULT_CONFIG, ScraperConfig
from src.constants import CSV_FIELDNAMES, DAY_MAP, KEYWORD_GROUPS
from src.geo.vincenty import (
    bounding_box_vincenty,
    vincenty_direct,
    vincenty_km,
)
from src.scraper import BusinessScraper
from src.utils.formatters import compress_opening_hours, sanitize_filename
from src.utils.io import ensure_output_dir, load_locations

# ================= LEGACY CONFIG CONSTANTS =================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", DEFAULT_CONFIG.api_key or "")
RADIUS_KM = DEFAULT_CONFIG.radius_km
LOCATIONS_FILE = DEFAULT_CONFIG.locations_file
OUTPUT_DIR = DEFAULT_CONFIG.output_dir
SEARCH_URL = DEFAULT_CONFIG.search_url
MAX_WORKERS = DEFAULT_CONFIG.max_workers

# Default module-level client
_client = GooglePlacesClient(
    api_key=GOOGLE_API_KEY,
    search_url=SEARCH_URL,
)


def search_text_paginated(
    place_type: str,
    lat: float,
    lng: float,
    radius_km: float,
    seen: Set[str],
) -> List[Dict[str, Any]]:
    """Legacy wrapper for searching Google Places with pagination."""
    return _client.search_text_paginated(place_type, lat, lng, radius_km, seen)


def check_api_key(lat: float, lng: float) -> bool:
    """Legacy wrapper for pre-flight API key check."""
    return _client.check_api_key(lat, lng)


def process_single_location(
    index: int,
    loc_info: Dict[str, Any],
    total_count: int,
) -> Tuple[int, str]:
    """Legacy wrapper for processing a single location."""
    scraper = BusinessScraper(
        ScraperConfig(
            api_key=GOOGLE_API_KEY,
            radius_km=RADIUS_KM,
            locations_file=LOCATIONS_FILE,
            output_dir=OUTPUT_DIR,
            search_url=SEARCH_URL,
            max_workers=MAX_WORKERS,
        )
    )
    return scraper.process_single_location(index, loc_info, total_count)


def main() -> None:
    """Execute scraping pipeline using configured defaults."""
    scraper = BusinessScraper(
        ScraperConfig(
            api_key=GOOGLE_API_KEY,
            radius_km=RADIUS_KM,
            locations_file=LOCATIONS_FILE,
            output_dir=OUTPUT_DIR,
            search_url=SEARCH_URL,
            max_workers=MAX_WORKERS,
        )
    )
    scraper.run()


if __name__ == "__main__":
    main()
