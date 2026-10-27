"""Business Scraper Orchestration Engine.

Coordinates the loading of target locations, spatial querying of Google Places,
result deduplication, geodesic distance verification, multi-threaded parallel execution,
graceful interruption (Ctrl+C / SIGINT) handling, and streaming CSV export.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import os
from pathlib import Path
import re
import signal
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

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
from .utils.formatters import (
    clean_text,
    compress_opening_hours,
    format_distance,
    sanitize_filename,
)
from .utils.io import ensure_output_dir, load_locations
from .utils.whatsapp_phone import (
    extract_phone_candidates,
    select_best_whatsapp_number,
)


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
        dedup_candidates_map: Dict[str, Dict[str, Any]] = {}
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

                            # Candidate collection for deduplicated export:
                            # Must have candidate phone(s), valid review_count, and valid name
                            raw_int_phone = place.get("internationalPhoneNumber") or ""
                            raw_nat_phone = place.get("nationalPhoneNumber") or ""
                            extracted_cands: Set[str] = set()
                            for p_str in (raw_int_phone, raw_nat_phone, phone):
                                if p_str:
                                    extracted_cands.update(extract_phone_candidates(p_str))

                            raw_reviews = place.get("userRatingCount")
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

                            if extracted_cands and has_reviews and has_biz_name:
                                dedup_key = pid or (
                                    row_data["name"].strip().lower(),
                                    row_data["address"].strip().lower(),
                                )
                                if dedup_key not in dedup_candidates_map:
                                    rec = dict(row_data)
                                    rec["_phone_candidates"] = set(extracted_cands)
                                    dedup_candidates_map[dedup_key] = rec
                                else:
                                    dedup_candidates_map[dedup_key]["_phone_candidates"].update(
                                        extracted_cands
                                    )

                                dedup_sno = len(dedup_candidates_map)

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
                # Perform WhatsApp validation, priority selection, Bedrock enrichment & cleanup
                if dedup_output_file:
                    # Select WhatsApp number (prioritize mobile over landline), filter out non-WhatsApp
                    valid_dedup_candidates: List[Dict[str, Any]] = []
                    for rec in dedup_candidates_map.values():
                        cands = list(rec.get("_phone_candidates", set()))
                        best_wa_phone = select_best_whatsapp_number(cands)
                        if not best_wa_phone:
                            # Not a WhatsApp-capable number (landline/toll-free/invalid) -> remove entry
                            continue
                        rec_copy = dict(rec)
                        rec_copy["phone"] = best_wa_phone
                        rec_copy.pop("_phone_candidates", None)
                        valid_dedup_candidates.append(rec_copy)

                    if valid_dedup_candidates:
                        self.log(
                            f"{tag} Enriching {len(valid_dedup_candidates)} WhatsApp-verified places with Bedrock..."
                        )
                        if self.enricher and self.config.enable_enrichment:
                            enriched_records = self.enricher.enrich_records(
                                valid_dedup_candidates,
                                batch_size=50,
                                log_callback=self.log,
                            )
                        else:
                            enriched_records = []
                            for r in valid_dedup_candidates:
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
                                    "formatted_distance": format_distance(r.get("distance_km", "")),
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

        if self.config.locations_list:
            locations = [dict(loc) for loc in self.config.locations_list]
            source_desc = f"{len(locations)} selected locations"
        else:
            locations = load_locations(self.config.locations_file)
            source_desc = self.config.locations_file

        if not locations:
            self.log(f"No locations found to search ({source_desc})!")
            self.emit_progress({
                "type": "error",
                "message": f"No locations found to search ({source_desc})!",
            })
            return

        total_locations = len(locations)
        cpu_threads = os.cpu_count() or 1
        num_workers = min(total_locations, max(1, self.config.max_workers or 1))

        self.log("=" * 65)
        self.log(f"Loaded {total_locations} locations from {source_desc}.")
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

    def dedup_and_enrich_existing(
        self,
        input_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deduplicate, filter WhatsApp mobile numbers, and AI-enrich existing raw CSV files.

        Args:
            input_dir: Source folder with raw CSV files (defaults to config.output_dir).
            output_dir: Destination folder (defaults to config.dedup_output_dir).

        Returns:
            Summary dict containing execution metrics and processed file paths.
        """
        in_dir = input_dir or self.config.output_dir
        out_dir = (
            output_dir
            or self.config.dedup_output_dir
            or f"{in_dir.rstrip('/\\\\')}_deduplicated"
        )
        return dedup_and_enrich_directory(
            input_dir=in_dir,
            output_dir=out_dir,
            enricher=self.enricher,
            log_callback=self.log,
        )


def dedup_and_enrich_csv_file(
    input_file: Union[str, Path],
    output_file: Union[str, Path],
    enricher: Optional[BedrockEnricher] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """Deduplicate, filter WhatsApp mobile numbers, and AI-enrich a single CSV file.

    Args:
        input_file: Path to source raw CSV file.
        output_file: Path where deduplicated and enriched CSV will be saved.
        enricher: Optional BedrockEnricher instance.
        log_callback: Optional function for logging messages.

    Returns:
        Number of valid deduplicated places written to output_file.
    """
    in_path = Path(input_file)
    out_path = Path(output_file)

    if not in_path.exists():
        if log_callback:
            log_callback(f"[!] Input file '{input_file}' does not exist.")
        return 0

    stem = in_path.stem
    clean_stem = re.sub(r"^location_\d+_", "", stem)
    derived_tag = clean_stem.lower()

    dedup_candidates_map: Dict[Any, Dict[str, Any]] = {}

    with open(in_path, "r", encoding="utf-8-sig", errors="replace") as f_in:
        reader = csv.DictReader(f_in)
        for row in reader:
            raw_name = clean_text(row.get("name") or row.get("business_name") or "", is_name=True)
            raw_addr = clean_text(row.get("address") or "", is_name=False)
            raw_reviews = row.get("review_count") or row.get("user_ratings_total")

            has_reviews = bool(
                raw_reviews is not None
                and str(raw_reviews).strip() != ""
                and str(raw_reviews).strip().lower() not in ("none", "null", "nan")
            )
            has_biz_name = bool(
                raw_name
                and raw_name.strip()
                and raw_name.strip().lower() not in ("none", "null", "nan")
            )

            raw_phone = row.get("phone") or ""
            extracted_cands = extract_phone_candidates(raw_phone)

            if not (extracted_cands and has_reviews and has_biz_name):
                continue

            gmb = row.get("gmb_link") or ""
            pid = ""
            if "place_id:" in gmb:
                pid = gmb.split("place_id:")[1].split("&")[0].strip()

            dedup_key = pid or (raw_name.strip().lower(), raw_addr.strip().lower())

            if dedup_key not in dedup_candidates_map:
                rec = dict(row)
                rec["name"] = raw_name
                rec["address"] = raw_addr
                rec["review_count"] = str(raw_reviews).strip()
                rec["_phone_candidates"] = set(extracted_cands)
                dedup_candidates_map[dedup_key] = rec
            else:
                dedup_candidates_map[dedup_key]["_phone_candidates"].update(extracted_cands)

    valid_dedup_candidates: List[Dict[str, Any]] = []
    for rec in dedup_candidates_map.values():
        cands = list(rec.get("_phone_candidates", set()))
        best_wa_phone = select_best_whatsapp_number(cands)
        if not best_wa_phone:
            continue
        rec_copy = dict(rec)
        rec_copy["phone"] = best_wa_phone
        rec_copy.pop("_phone_candidates", None)
        valid_dedup_candidates.append(rec_copy)

    final_dedup_rows: List[Dict[str, Any]] = []
    if valid_dedup_candidates:
        if enricher and hasattr(enricher, "enrich_records"):
            enriched_records = enricher.enrich_records(
                valid_dedup_candidates,
                batch_size=50,
                log_callback=log_callback,
            )
        else:
            enriched_records = []
            for r in valid_dedup_candidates:
                er = dict(r)
                er["short_name"] = heuristic_short_name(er.get("name", ""))
                er["business_goal"] = heuristic_business_goal(
                    er.get("primary_type", ""), er.get("source_group", "")
                )
                enriched_records.append(er)

        for r in enriched_records:
            b_name = (r.get("name") or r.get("business_name") or "").strip()
            s_name = (r.get("short_name") or "").strip()
            b_goal = (r.get("business_goal") or "").strip()
            r_cnt = str(r.get("review_count") or "").strip()

            def _is_present(val: str) -> bool:
                return bool(val and val.lower() not in ("none", "null", "nan"))

            if (
                _is_present(b_name)
                and _is_present(s_name)
                and _is_present(b_goal)
                and _is_present(r_cnt)
            ):
                dist_km = r.get("distance_km", "")
                row_tag = r.get("tag") or derived_tag
                final_row = {
                    "sno": len(final_dedup_rows) + 1,
                    "whatsapp_name": b_name,
                    "business_name": b_name,
                    "short_name": s_name,
                    "address": r.get("address", ""),
                    "gmb_link": r.get("gmb_link", ""),
                    "lat": r.get("lat", ""),
                    "lng": r.get("lng", ""),
                    "distance_km": dist_km,
                    "formatted_distance": format_distance(dist_km),
                    "phone": r.get("phone", ""),
                    "rating": r.get("rating", ""),
                    "review_count": r_cnt,
                    "source_group": r.get("source_group", ""),
                    "primary_type": r.get("primary_type", ""),
                    "opening_hours": r.get("opening_hours", ""),
                    "tag": row_tag,
                    "business_goal": b_goal,
                }
                final_dedup_rows.append(final_row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=DEDUP_CSV_FIELDNAMES)
        writer.writeheader()
        if final_dedup_rows:
            writer.writerows(final_dedup_rows)
        f_out.flush()

    if log_callback:
        log_callback(f"Saved {len(final_dedup_rows)} deduplicated & enriched places to '{out_path}'")

    return len(final_dedup_rows)


def dedup_and_enrich_directory(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    enricher: Optional[BedrockEnricher] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Process all CSV files in input_dir, saving deduplicated and AI enriched CSVs to output_dir.

    Args:
        input_dir: Path to directory containing raw CSV files.
        output_dir: Path to destination directory for deduplicated files.
        enricher: Optional BedrockEnricher instance.
        log_callback: Optional logging callback.

    Returns:
        Summary dict containing counts and file paths.
    """
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(in_dir.glob("*.csv"))
    csv_files = [f for f in csv_files if not f.name.endswith("_deduped.csv")]

    total_records = 0
    details = []

    for i, csv_file in enumerate(csv_files, start=1):
        if log_callback:
            log_callback(f"\n[{i:02d}/{len(csv_files):02d}] Processing '{csv_file.name}'...")
        out_file = out_dir / csv_file.name
        count = dedup_and_enrich_csv_file(
            input_file=csv_file,
            output_file=out_file,
            enricher=enricher,
            log_callback=log_callback,
        )
        total_records += count
        details.append({
            "input_file": str(csv_file),
            "output_file": str(out_file),
            "record_count": count,
        })

    return {
        "files_processed": len(csv_files),
        "total_dedup_records": total_records,
        "details": details,
    }

