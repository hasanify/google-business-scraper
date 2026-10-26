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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .api.bedrock_enricher import (
    BedrockEnricher,
    heuristic_business_goal,
    heuristic_short_name,
)
from .api.google_places import GooglePlacesClient
from .api.rate_limiter import ThreadSafeRateLimiter
from .config import DEFAULT_CONFIG, ScraperConfig
from .constants import CSV_FIELDNAMES, DEDUP_CSV_FIELDNAMES, KEYWORD_GROUPS
from .geo.vincenty import vincenty_km
from .utils.formatters import clean_text, compress_opening_hours, sanitize_filename
from .utils.io import ensure_output_dir, load_locations


class BusinessScraper:
    """Orchestrator for scraping Google Places POIs around target coordinates."""

    def __init__(
        self,
        config: Optional[ScraperConfig] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """Initialize scraper with runtime configuration.

        Args:
            config: ScraperConfig instance, or None to use DEFAULT_CONFIG.
            log_callback: Optional function to receive streaming log text.
            progress_callback: Optional function to receive structured progress dictionaries.
        """
        self.config = config or DEFAULT_CONFIG
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.stop_event = threading.Event()
        self.rate_limiter = ThreadSafeRateLimiter(max_qps=self.config.max_qps)
        self.client = GooglePlacesClient(
            api_key=self.config.api_key or "",
            search_url=self.config.search_url,
            timeout=self.config.request_timeout,
            page_delay=self.config.pagination_delay,
            rate_limiter=self.rate_limiter,
            max_qps=self.config.max_qps,
            max_retries=self.config.max_retries,
            retry_backoff=self.config.retry_backoff,
        )
        self.enricher = (
            BedrockEnricher(
                region_name=self.config.aws_region,
                bearer_token=self.config.aws_bearer_token,
                model_id=self.config.bedrock_model_id,
            )
            if self.config.enable_enrichment
            else None
        )

    def log(self, message: str) -> None:
        """Output message to stdout and optional log_callback."""
        print(message, flush=True)
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception:
                pass

    def emit_progress(self, data: Dict[str, Any]) -> None:
        """Send progress dictionary to optional progress_callback."""
        if self.progress_callback:
            try:
                self.progress_callback(data)
            except Exception:
                pass

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
        filename = f"location_{index:02d}_{slug}.csv"
        output_file = os.path.join(self.config.output_dir, filename)

        dedup_output_file = None
        if self.config.dedup_output_dir:
            if os.path.abspath(self.config.dedup_output_dir) == os.path.abspath(self.config.output_dir):
                dedup_filename = f"location_{index:02d}_{slug}_deduped.csv"
            else:
                dedup_filename = filename
            dedup_output_file = os.path.join(
                self.config.dedup_output_dir, dedup_filename
            )
            os.makedirs(os.path.dirname(dedup_output_file), exist_ok=True)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        tag = f"[{index:02d}/{total_count:02d}] ({loc_name[:25]})"

        self.log(f"\n{tag} Starting scrape at ({lat}, {lng}) | Radius: {self.config.radius_km} km")
        self.log(f"{tag} Output (All): {output_file}")
        if dedup_output_file:
            self.log(f"{tag} Output (Dedup + Phone): {dedup_output_file}")

        self.emit_progress({
            "type": "location_start",
            "index": index,
            "total": total_count,
            "location": loc_name,
            "lat": lat,
            "lng": lng,
            "output_file": output_file,
            "dedup_output_file": dedup_output_file,
        })

        seen: Set[str] = set()
        dedup_seen: Set[str] = set()
        dedup_candidates: List[Dict[str, Any]] = []
        sno = 0
        dedup_sno = 0

        groups_to_query = {
            group: types
            for group, types in KEYWORD_GROUPS.items()
            if not self.config.selected_categories or group in self.config.selected_categories
        }

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            f.flush()

            try:
                for group, types in groups_to_query.items():
                    if self.stop_event.is_set():
                        break

                    self.log(f"{tag} Fetching category: {group}")
                    self.emit_progress({
                        "type": "category_start",
                        "index": index,
                        "total": total_count,
                        "location": loc_name,
                        "group": group,
                        "sno": sno,
                        "dedup_sno": dedup_sno,
                    })

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
                            phone = (
                                place.get("internationalPhoneNumber")
                                or place.get("nationalPhoneNumber")
                                or ""
                            )

                            sno += 1
                            row_data = {
                                "sno": sno,
                                "name": clean_text(
                                    place.get("displayName", {}).get("text", ""),
                                    is_name=True,
                                ),
                                "address": clean_text(
                                    place.get("formattedAddress", ""),
                                    is_name=False,
                                ),
                                "gmb_link": f"https://www.google.com/maps/place/?q=place_id:{pid}",
                                "lat": plat,
                                "lng": plng,
                                "distance_km": distance_km,
                                "phone": phone,
                                "rating": place.get("rating", ""),
                                "review_count": place.get("userRatingCount", ""),
                                "source_group": group,
                                "primary_type": place_type,
                                "opening_hours": compress_opening_hours(
                                    place.get("regularOpeningHours")
                                ),
                                "tag": slug.lower(),
                            }
                            writer.writerow(row_data)

                            # Candidate check for deduplicated export:
                            # Must have valid phone, valid review_count, and valid name
                            raw_reviews = place.get("userRatingCount")
                            has_phone = bool(
                                phone and phone.strip().lower() not in ("none", "null", "nan", "n/a", "-")
                            )
                            has_reviews = (
                                raw_reviews is not None
                                and str(raw_reviews).strip() != ""
                                and str(raw_reviews).strip().lower() not in ("none", "null", "nan")
                            )
                            has_biz_name = bool(
                                row_data["name"]
                                and row_data["name"].strip()
                                and row_data["name"].strip().lower() not in ("none", "null", "nan")
                            )
                            if has_phone and has_reviews and has_biz_name and pid not in dedup_seen:
                                dedup_seen.add(pid)
                                dedup_candidates.append(dict(row_data))
                                dedup_sno = len(dedup_candidates)

                            self.emit_progress({
                                "type": "place_found",
                                "index": index,
                                "total": total_count,
                                "location": loc_name,
                                "sno": sno,
                                "dedup_sno": dedup_sno,
                                "name": row_data["name"],
                            })

                        f.flush()

                        if self.stop_event.wait(self.config.inter_query_delay):
                            break
            finally:
                # Perform Bedrock enrichment & cleanup filtering on deduplicated candidates
                if dedup_output_file:
                    if dedup_candidates:
                        self.log(
                            f"{tag} Enriching {len(dedup_candidates)} places with Bedrock (short_name & business_goal)..."
                        )
                        if self.enricher and self.config.enable_enrichment:
                            enriched_records = self.enricher.enrich_records(
                                dedup_candidates,
                                batch_size=25,
                                log_callback=self.log,
                            )
                        else:
                            enriched_records = []
                            for r in dedup_candidates:
                                er = dict(r)
                                er["short_name"] = heuristic_short_name(er.get("name", ""))
                                er["business_goal"] = heuristic_business_goal(
                                    er.get("primary_type", ""), er.get("source_group", "")
                                )
                                enriched_records.append(er)

                        final_dedup_rows: List[Dict[str, Any]] = []
                        for r in enriched_records:
                            b_name = (r.get("name") or "").strip()
                            s_name = (r.get("short_name") or "").strip()
                            b_goal = (r.get("business_goal") or "").strip()
                            r_cnt = str(r.get("review_count", "")).strip()

                            def _is_present(val: str) -> bool:
                                return bool(val and val.lower() not in ("none", "null", "nan"))

                            if (
                                _is_present(b_name)
                                and _is_present(s_name)
                                and _is_present(b_goal)
                                and _is_present(r_cnt)
                            ):
                                final_row = {
                                    "sno": len(final_dedup_rows) + 1,
                                    "whatsapp_name": b_name,
                                    "business_name": b_name,
                                    "short_name": s_name,
                                    "address": r.get("address", ""),
                                    "gmb_link": r.get("gmb_link", ""),
                                    "lat": r.get("lat", ""),
                                    "lng": r.get("lng", ""),
                                    "distance_km": r.get("distance_km", ""),
                                    "phone": r.get("phone", ""),
                                    "rating": r.get("rating", ""),
                                    "review_count": r_cnt,
                                    "source_group": r.get("source_group", ""),
                                    "primary_type": r.get("primary_type", ""),
                                    "opening_hours": r.get("opening_hours", ""),
                                    "tag": r.get("tag", ""),
                                    "business_goal": b_goal,
                                }
                                final_dedup_rows.append(final_row)

                        with open(dedup_output_file, "w", newline="", encoding="utf-8-sig") as f_dedup:
                            dedup_writer = csv.DictWriter(f_dedup, fieldnames=DEDUP_CSV_FIELDNAMES)
                            dedup_writer.writeheader()
                            dedup_writer.writerows(final_dedup_rows)
                            f_dedup.flush()

                        dedup_sno = len(final_dedup_rows)
                        self.log(
                            f"{tag} Saved {dedup_sno} enriched & cleaned deduplicated places to {dedup_output_file}"
                        )
                    else:
                        with open(dedup_output_file, "w", newline="", encoding="utf-8-sig") as f_dedup:
                            dedup_writer = csv.DictWriter(f_dedup, fieldnames=DEDUP_CSV_FIELDNAMES)
                            dedup_writer.writeheader()
                            f_dedup.flush()
                        dedup_sno = 0

        if self.stop_event.is_set():
            msg = f"\n[!] {tag} Interrupted early. Flushed {sno} places to {output_file}"
            if dedup_output_file:
                msg += f" ({dedup_sno} with phone to {dedup_output_file})"
            self.log(msg)
        else:
            msg = f"\n>>> {tag} COMPLETED: Saved {sno} unique places to {output_file}"
            if dedup_output_file:
                msg += f" ({dedup_sno} with phone to {dedup_output_file})"
            self.log(msg)

        self.emit_progress({
            "type": "location_complete",
            "index": index,
            "total": total_count,
            "location": loc_name,
            "sno": sno,
            "dedup_sno": dedup_sno,
            "output_file": output_file,
            "dedup_output_file": dedup_output_file,
        })

        return sno, output_file

    def run(self) -> None:
        """Execute the scraping pipeline across all locations with graceful interrupt handling."""
        ensure_output_dir(self.config.output_dir)
        if self.config.dedup_output_dir:
            ensure_output_dir(self.config.dedup_output_dir)

        locations = load_locations(self.config.locations_file)
        if not locations:
            self.log(f"No locations found in {self.config.locations_file}!")
            self.emit_progress({
                "type": "error",
                "message": f"No locations found in {self.config.locations_file}!",
            })
            return

        total_locations = len(locations)
        cpu_threads = os.cpu_count() or 1
        num_workers = min(total_locations, max(1, self.config.max_workers or 1))

        self.log("=" * 65)
        self.log(f"Loaded {total_locations} locations from {self.config.locations_file}.")
        self.log(f"Configured Radius : {self.config.radius_km} km per location.")
        self.log(f"Concurrency       : {num_workers} parallel thread(s) (CPU: {cpu_threads} logical cores/threads).")
        self.log(f"Global Rate Limit : {self.config.max_qps:.1f} requests/sec across all threads (Google Cloud safe).")
        self.log("Interrupt Guide   : Press Ctrl+C at any time for graceful shutdown.")
        self.log("=" * 65)

        self.emit_progress({
            "type": "run_start",
            "total_locations": total_locations,
            "num_workers": num_workers,
            "radius_km": self.config.radius_km,
        })

        # Pre-flight check with the first location
        if not self.client.check_api_key(locations[0]["lat"], locations[0]["lng"]):
            self.log("Aborting run due to API authorization/billing error.")
            self.emit_progress({
                "type": "error",
                "message": "Aborting run due to Google Places API authorization or billing error.",
            })
            return

        self.log(f"Starting scrape across {num_workers} thread(s)...\n")

        summary: List[Tuple[int, str, int, str]] = []

        is_main_thread = threading.current_thread() is threading.main_thread()
        original_sigint = None
        original_sigterm = None
        has_sigterm = hasattr(signal, "SIGTERM")

        if is_main_thread:
            def _handle_interrupt(signum: int, frame: Any) -> None:
                if not self.stop_event.is_set():
                    self.log("\n\n[!] Interrupt signal received (Ctrl+C). Initiating graceful shutdown...")
                    self.stop_event.set()

            original_sigint = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, _handle_interrupt)
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
                            self.log(f"[ERROR] Location [{i}/{total_locations}] '{loc['name']}' failed: {exc}")
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
                                    self.log(f"[ERROR] Location [{idx}/{total_locations}] '{loc['name']}' failed: {exc}")

                            if self.stop_event.is_set():
                                executor.shutdown(wait=False, cancel_futures=True)
                                break
                    except KeyboardInterrupt:
                        self.log("\n[!] Ctrl+C detected. Cancelling remaining threads...")
                        self.stop_event.set()
                        executor.shutdown(wait=False, cancel_futures=True)
        except KeyboardInterrupt:
            self.log("\n[!] Ctrl+C caught during execution.")
            self.stop_event.set()
        finally:
            if is_main_thread and original_sigint is not None:
                signal.signal(signal.SIGINT, original_sigint)
                if has_sigterm and original_sigterm:
                    signal.signal(signal.SIGTERM, original_sigterm)

        # Sort summary by original location index
        summary.sort(key=lambda item: item[0])

        if self.stop_event.is_set():
            self.log("\n" + "=" * 70)
            self.log("SCRAPER STOPPED BY USER (GRACEFUL EXIT COMPLETE)")
            self.log("=" * 70)
            if summary:
                self.log(f"Fully completed {len(summary)} of {total_locations} locations before stop:")
                for idx, name, count, outfile in summary:
                    self.log(f"[{idx:02d}] {name[:38]:<38} -> {count:4d} places | {outfile}")
            else:
                self.log("Interrupted before any single location finished all selected categories.")
            self.log("All CSV files were cleanly flushed to disk. No corrupted data.")
            self.log("=" * 70 + "\n")
        else:
            self.log("\n" + "=" * 70)
            self.log("ALL LOCATIONS COMPLETED")
            self.log("=" * 70)
            for idx, name, count, outfile in summary:
                self.log(f"[{idx:02d}] {name[:38]:<38} -> {count:4d} places | {outfile}")

        self.emit_progress({
            "type": "run_finish",
            "total_locations": total_locations,
            "completed_locations": len(summary),
            "summary": summary,
            "interrupted": self.stop_event.is_set(),
        })
