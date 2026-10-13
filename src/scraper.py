"""Business Scraper Orchestration Engine.

Coordinates the loading of target locations, spatial querying of Google Places,
result deduplication, geodesic distance verification, multi-threaded parallel execution,
and streaming CSV export.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
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
        tag = f"[{index:02d}/{total_count:02d}] ({loc_name[:25]})"

        print(f"\n{tag} Starting scrape at ({lat}, {lng}) | Radius: {self.config.radius_km} km", flush=True)
        print(f"{tag} Output: {output_file}", flush=True)

        seen: Set[str] = set()
        sno = 0

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            f.flush()

            for group, types in KEYWORD_GROUPS.items():
                print(f"{tag} Fetching category: {group}", flush=True)
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

        print(f"\n>>> {tag} COMPLETED: Saved {sno} unique places to {output_file}", flush=True)
        return sno, output_file

    def run(self) -> None:
        """Execute the scraping pipeline across all locations with multi-threaded concurrency."""
        ensure_output_dir(self.config.output_dir)

        locations = load_locations(self.config.locations_file)
        if not locations:
            print(f"No locations found in {self.config.locations_file}!", flush=True)
            return

        total_locations = len(locations)
        cpu_threads = os.cpu_count() or 1
        num_workers = min(total_locations, max(1, self.config.max_workers or 1))

        print("=" * 65, flush=True)
        print(f"Loaded {total_locations} locations from {self.config.locations_file}.", flush=True)
        print(f"Configured Radius : {self.config.radius_km} km per location.", flush=True)
        print(f"Concurrency       : {num_workers} parallel thread(s) (CPU: {cpu_threads} logical cores/threads).", flush=True)
        print("=" * 65, flush=True)

        # Pre-flight check with the first location
        if not self.client.check_api_key(locations[0]["lat"], locations[0]["lng"]):
            print("Aborting run due to API authorization/billing error.", flush=True)
            return

        print(f"Starting parallel scrape across {num_workers} thread(s)...\n", flush=True)

        summary: List[Tuple[int, str, int, str]] = []

        if num_workers == 1:
            for i, loc in enumerate(locations, start=1):
                try:
                    count, outfile = self.process_single_location(i, loc, total_locations)
                    summary.append((i, loc["name"], count, outfile))
                except Exception as exc:
                    print(f"[ERROR] Location [{i}/{total_locations}] '{loc['name']}' failed: {exc}", flush=True)
        else:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_loc = {
                    executor.submit(
                        self.process_single_location, i, loc, total_locations
                    ): (i, loc)
                    for i, loc in enumerate(locations, start=1)
                }

                for future in as_completed(future_to_loc):
                    idx, loc = future_to_loc[future]
                    try:
                        count, outfile = future.result()
                        summary.append((idx, loc["name"], count, outfile))
                    except Exception as exc:
                        print(f"[ERROR] Location [{idx}/{total_locations}] '{loc['name']}' failed: {exc}", flush=True)

        # Sort summary by original location index
        summary.sort(key=lambda item: item[0])

        print("\n" + "=" * 70, flush=True)
        print("ALL LOCATIONS COMPLETED", flush=True)
        print("=" * 70, flush=True)
        for idx, name, count, outfile in summary:
            print(f"[{idx:02d}] {name[:38]:<38} -> {count:4d} places | {outfile}", flush=True)
