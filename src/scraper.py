"""Business Scraper Orchestration Engine.

Coordinates the loading of target locations, spatial querying of Google Places,
result deduplication, geodesic distance verification, and streaming CSV export.
"""

import csv
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .api.google_places import GooglePlacesClient
from .config import DEFAULT_CONFIG, ScraperConfig
from .constants import CSV_FIELDNAMES, KEYWORD_GROUPS
from .geo.vincenty import vincenty_km
from .utils.formatters import compress_opening_hours, sanitize_filename
from .utils.io import ensure_output_dir, load_locations


class BusinessScraper:
    """Orchestrator for scraping Google Places POIs around target coordinates."""

    def __init__(self, config: Optional[ScraperConfig] = None) -> None:
        """Initialize scraper with runtime configuration.

        Args:
            config: ScraperConfig instance, or None to use DEFAULT_CONFIG.
        """
        self.config = config or DEFAULT_CONFIG
        self.client = GooglePlacesClient(
            api_key=self.config.api_key or "",
            search_url=self.config.search_url,
            timeout=self.config.request_timeout,
            page_delay=self.config.pagination_delay,
        )

    def process_single_location(
        self,
        index: int,
        loc_info: Dict[str, Any],
        total_count: int,
    ) -> Tuple[int, str]:
        """Scrape all POI categories within configured radius for a single location.

        Args:
            index: Current 1-based location index.
            loc_info: Dictionary containing 'name', 'lat', and 'lng'.
            total_count: Total number of locations being processed.

        Returns:
            A tuple of (total_places_saved, output_file_path).
        """
        loc_name = loc_info["name"]
        lat = loc_info["lat"]
        lng = loc_info["lng"]
        slug = sanitize_filename(loc_name)
        output_file = os.path.join(
            self.config.output_dir, f"location_{index:02d}_{slug}.csv"
        )

        print("\n" + "=" * 65)
        print(f"[{index}/{total_count}] Processing: {loc_name}")
        print(f"Coordinates: ({lat}, {lng}) | Radius: {self.config.radius_km} km")
        print(f"Output File: {output_file}")
        print("=" * 65)

        seen: Set[str] = set()
        sno = 0

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            f.flush()

            for group, types in KEYWORD_GROUPS.items():
                print(f"--- Fetching group: {group} ---")
                for place_type in types:
                    places = self.client.search_text_paginated(
                        place_type, lat, lng, self.config.radius_km, seen
                    )
                    for place in places:
                        pid = place.get("id")
                        plat = place["location"]["latitude"]
                        plng = place["location"]["longitude"]
                        distance_km = vincenty_km(lat, lng, plat, plng)

                        sno += 1
                        writer.writerow({
                            "sno": sno,
                            "name": place.get("displayName", {}).get("text", ""),
                            "address": place.get("formattedAddress", ""),
                            "gmb_link": f"https://www.google.com/maps/place/?q=place_id:{pid}",
                            "lat": plat,
                            "lng": plng,
                            "distance_km": distance_km,
                            "phone": (
                                place.get("internationalPhoneNumber")
                                or place.get("nationalPhoneNumber")
                                or ""
                            ),
                            "rating": place.get("rating", ""),
                            "user_ratings_total": place.get("userRatingCount", ""),
                            "source_group": group,
                            "primary_type": place_type,
                            "opening_hours": compress_opening_hours(
                                place.get("regularOpeningHours")
                            ),
                        })
                    f.flush()
                    time.sleep(self.config.inter_query_delay)

        print(f"Finished location [{index}/{total_count}]: {loc_name}")
        print(f"Saved {sno} unique businesses to {output_file}")
        return sno, output_file

    def run(self) -> None:
        """Execute the full scraping pipeline across all locations defined in locations_file."""
        ensure_output_dir(self.config.output_dir)

        locations = load_locations(self.config.locations_file)
        if not locations:
            print(f"No locations found in {self.config.locations_file}!", flush=True)
            return

        print(f"Loaded {len(locations)} locations from {self.config.locations_file}.", flush=True)
        print(f"Configured Radius: {self.config.radius_km} km per location.", flush=True)

        # Pre-flight check with the first location
        if not self.client.check_api_key(locations[0]["lat"], locations[0]["lng"]):
            print("Aborting run due to API authorization/billing error.", flush=True)
            return

        print(f"Scraping businesses within {self.config.radius_km} km for each location...", flush=True)

        summary: List[Tuple[int, str, int, str]] = []
        total_locations = len(locations)
        for i, loc in enumerate(locations, start=1):
            count, outfile = self.process_single_location(i, loc, total_locations)
            summary.append((i, loc["name"], count, outfile))

        print("\n" + "=" * 60, flush=True)
        print("ALL LOCATIONS COMPLETED", flush=True)
        print("=" * 60, flush=True)
        for idx, name, count, outfile in summary:
            print(f"[{idx:02d}] {name[:35]:<35} -> {count:4d} places | {outfile}", flush=True)
