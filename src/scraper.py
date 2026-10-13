"""Business Scraper Orchestration Engine.

Coordinates the loading of target locations, spatial querying of Google Places,
result deduplication, geodesic distance verification, multi-threaded parallel execution,
graceful interruption (Ctrl+C / SIGINT) handling, and streaming CSV export.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import os
from pathlib import Path
import signal
import threading
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
        self.stop_event = threading.Event()

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
                if self.stop_event.is_set():
                    break

                print(f"{tag} Fetching category: {group}", flush=True)
                for place_type in types:
                    if self.stop_event.is_set():
                        break

                    places = self.client.search_text_paginated(
                        place_type,
                        lat,
                        lng,
                        self.config.radius_km,
                        seen,
                        stop_event=self.stop_event,
                    )

                    for place in places:
                        if self.stop_event.is_set():
                            break

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

                    if self.stop_event.wait(self.config.inter_query_delay):
                        break

        if self.stop_event.is_set():
            print(f"\n[!] {tag} Interrupted early. Flushed {sno} places to {output_file}", flush=True)
        else:
            print(f"\n>>> {tag} COMPLETED: Saved {sno} unique places to {output_file}", flush=True)

        return sno, output_file

    def run(self) -> None:
        """Execute the scraping pipeline across all locations with graceful interrupt handling."""
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
        print("Interrupt Guide   : Press Ctrl+C at any time for graceful shutdown.", flush=True)
        print("=" * 65, flush=True)

        # Pre-flight check with the first location
        if not self.client.check_api_key(locations[0]["lat"], locations[0]["lng"]):
            print("Aborting run due to API authorization/billing error.", flush=True)
            return

        print(f"Starting scrape across {num_workers} thread(s)...\n", flush=True)

        summary: List[Tuple[int, str, int, str]] = []

        # Graceful signal handler setup
        def _handle_interrupt(signum: int, frame: Any) -> None:
            if not self.stop_event.is_set():
                print("\n\n[!] Interrupt signal received (Ctrl+C). Initiating graceful shutdown...", flush=True)
                self.stop_event.set()

        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _handle_interrupt)
        has_sigterm = hasattr(signal, "SIGTERM")
        original_sigterm = signal.getsignal(signal.SIGTERM) if has_sigterm else None
        if has_sigterm:
            signal.signal(signal.SIGTERM, _handle_interrupt)

        try:
            if num_workers == 1:
                for i, loc in enumerate(locations, start=1):
                    if self.stop_event.is_set():
                        break
                    try:
                        count, outfile = self.process_single_location(i, loc, total_locations)
                        if not self.stop_event.is_set():
                            summary.append((i, loc["name"], count, outfile))
                    except Exception as exc:
                        if not self.stop_event.is_set():
                            print(f"[ERROR] Location [{i}/{total_locations}] '{loc['name']}' failed: {exc}", flush=True)
            else:
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    future_to_loc = {
                        executor.submit(
                            self.process_single_location, i, loc, total_locations
                        ): (i, loc)
                        for i, loc in enumerate(locations, start=1)
                    }

                    try:
                        for future in as_completed(future_to_loc):
                            idx, loc = future_to_loc[future]
                            try:
                                count, outfile = future.result()
                                if not self.stop_event.is_set():
                                    summary.append((idx, loc["name"], count, outfile))
                            except Exception as exc:
                                if not self.stop_event.is_set():
                                    print(f"[ERROR] Location [{idx}/{total_locations}] '{loc['name']}' failed: {exc}", flush=True)

                            if self.stop_event.is_set():
                                executor.shutdown(wait=False, cancel_futures=True)
                                break
                    except KeyboardInterrupt:
                        print("\n[!] Ctrl+C detected. Cancelling remaining threads...", flush=True)
                        self.stop_event.set()
                        executor.shutdown(wait=False, cancel_futures=True)
        except KeyboardInterrupt:
            print("\n[!] Ctrl+C caught during execution.", flush=True)
            self.stop_event.set()
        finally:
            # Restore initial signal handlers
            signal.signal(signal.SIGINT, original_sigint)
            if has_sigterm and original_sigterm:
                signal.signal(signal.SIGTERM, original_sigterm)

        # Sort summary by original location index
        summary.sort(key=lambda item: item[0])

        if self.stop_event.is_set():
            print("\n" + "=" * 70, flush=True)
            print("SCRAPER STOPPED BY USER (GRACEFUL EXIT COMPLETE)", flush=True)
            print("=" * 70, flush=True)
            if summary:
                print(f"Fully completed {len(summary)} of {total_locations} locations before stop:", flush=True)
                for idx, name, count, outfile in summary:
                    print(f"[{idx:02d}] {name[:38]:<38} -> {count:4d} places | {outfile}", flush=True)
            else:
                print("Interrupted before any single location finished all 150 categories.", flush=True)
            print("All CSV files were cleanly flushed to disk. No corrupted data.", flush=True)
            print("=" * 70 + "\n", flush=True)
        else:
            print("\n" + "=" * 70, flush=True)
            print("ALL LOCATIONS COMPLETED", flush=True)
            print("=" * 70, flush=True)
            for idx, name, count, outfile in summary:
                print(f"[{idx:02d}] {name[:38]:<38} -> {count:4d} places | {outfile}", flush=True)
