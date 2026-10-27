"""Unit tests for geo calculations, formatters, I/O utilities, and concurrency config."""

import os
from pathlib import Path
import tempfile
import unittest

from src.config import ScraperConfig
from src.constants import CSV_FIELDNAMES, DAY_MAP, KEYWORD_GROUPS
from src.geo.vincenty import (
    bounding_box_vincenty,
    vincenty_direct,
    vincenty_km,
)
from src.scraper import BusinessScraper
from src.utils.formatters import clean_text, compress_opening_hours, sanitize_filename
from src.utils.io import (
    clean_all_csv_files,
    clean_csv_file,
    load_locations,
)


class TestGeodesicCalculations(unittest.TestCase):
    """Test Vincenty WGS-84 geodesic algorithms."""

    def test_vincenty_km_same_point(self):
        """Distance from a point to itself should be 0.0."""
        dist = vincenty_km(28.5686, 77.2213, 28.5686, 77.2213)
        self.assertEqual(dist, 0.0)

    def test_vincenty_km_known_distance(self):
        """Distance between South Extension and Priya Highstreet (~7.0km)."""
        dist = vincenty_km(28.568611, 77.221363, 28.557728, 77.164405)
        self.assertGreater(dist, 5.0)
        self.assertLess(dist, 6.0)

    def test_bounding_box_structure(self):
        """Bounding box should contain valid low and high coordinate boundaries."""
        bbox = bounding_box_vincenty(28.5686, 77.2213, 3.0)
        self.assertIn("low", bbox)
        self.assertIn("high", bbox)
        self.assertLess(bbox["low"]["latitude"], bbox["high"]["latitude"])
        self.assertLess(bbox["low"]["longitude"], bbox["high"]["longitude"])


class TestFormatters(unittest.TestCase):
    """Test string formatters and opening hours compression."""

    def test_sanitize_filename(self):
        """Special characters should be replaced with underscores and length truncated."""
        raw = 'Ambience Mall , Vasant Kunj - Set of 2 (3 Units - Lajpat Nagar towards AIIMS)'
        cleaned = sanitize_filename(raw, max_length=45)
        self.assertTrue(len(cleaned) <= 45)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("(", cleaned)
        self.assertNotIn(")", cleaned)

    def test_compress_opening_hours_empty(self):
        """Empty or invalid regularOpeningHours should return empty string."""
        self.assertEqual(compress_opening_hours(None), "")
        self.assertEqual(compress_opening_hours({}), "")
        self.assertEqual(compress_opening_hours({"periods": []}), "")

    def test_compress_opening_hours_consecutive_days(self):
        """Same opening hours across consecutive days should be grouped as range."""
        sample_hours = {
            "periods": [
                {"open": {"day": 0, "hour": 9, "minute": 0}, "close": {"day": 0, "hour": 18, "minute": 0}},
                {"open": {"day": 1, "hour": 9, "minute": 0}, "close": {"day": 1, "hour": 18, "minute": 0}},
                {"open": {"day": 2, "hour": 9, "minute": 0}, "close": {"day": 2, "hour": 18, "minute": 0}},
                {"open": {"day": 3, "hour": 9, "minute": 0}, "close": {"day": 3, "hour": 18, "minute": 0}},
                {"open": {"day": 4, "hour": 9, "minute": 0}, "close": {"day": 4, "hour": 18, "minute": 0}},
            ]
        }
        compressed = compress_opening_hours(sample_hours)
        self.assertEqual(compressed, "Mon-Fri 09:00-18:00")

    def test_clean_text_user_example(self):
        """User address example with Devanagari script should be cleanly stripped to ASCII."""
        raw_address = (
            "IndianOil e-Charge Station, Intimate Filling Station, "
            "\u092a\u0902\u091a\u0936\u0940\u0932 \u092e\u093e\u0930\u094d\u0917, "
            "\u0938\u094b\u0905\u092e\u0940 \u0928\u0917\u0930 \u0928\u0949\u0930\u094d\u0925, "
            "\u0938\u094b\u0905\u092e\u0940 \u0928\u0917\u0930, "
            "\u0928\u0908 \u0926\u093f\u0932\u094d\u0932\u0940, "
            "\u0926\u093f\u0932\u094d\u0932\u0940 110017, India"
        )
        cleaned = clean_text(raw_address, is_name=False)
        self.assertEqual(
            cleaned,
            "IndianOil e-Charge Station, Intimate Filling Station, 110017, India",
        )

    def test_clean_text_accents_and_typography(self):
        """Accented letters and typographic symbols should normalize to clean ASCII."""
        self.assertEqual(clean_text("Caf\xe9 27", is_name=True), "Cafe 27")
        self.assertEqual(
            clean_text("Buglee \u0160koda Showroom", is_name=True),
            "Buglee Skoda Showroom",
        )
        self.assertEqual(clean_text("Malik\u2019s Crib", is_name=True), "Malik's Crib")
        self.assertEqual(
            clean_text("Service 24\xd77", is_name=True), "Service 24x7"
        )

    def test_clean_text_mathematical_alphanumeric(self):
        """Mathematical stylized bold/italic fonts should normalize to standard ASCII."""
        math_str = (
            "\U0001d40f\U0001d414\U0001d40d\U0001d408\U0001d400 "
            "\U0001d413\U0001d411\U0001d415\U0001d40b\U0001d404\U0001d419 "
            "\U0001d408\U0001d40d\U0001d403\U0001d408\U0001d400 - Luxury rentals"
        )
        cleaned = clean_text(math_str, is_name=True)
        self.assertEqual(cleaned, "PUNIA TRVLEZ INDIA - Luxury rentals")

    def test_clean_text_arabic_and_empty_brackets(self):
        """Arabic words and empty brackets from stripped text should be removed cleanly."""
        arabic_addr = (
            "\u0634\u0627\u06be\u06cc 4/46, Double story, behind Shahi Masjid "
            "\u0645\u0633\u062c\u062f, Jungpura Extension, New Delhi, Delhi 110014, India"
        )
        cleaned = clean_text(arabic_addr, is_name=False)
        self.assertEqual(
            cleaned,
            "4/46, Double story, behind Shahi Masjid, Jungpura Extension, New Delhi, Delhi 110014, India",
        )
        self.assertEqual(
            clean_text("IndianOil (\u092a\u0902\u091a\u0936\u0940\u0932) Station"),
            "IndianOil Station",
        )

    def test_clean_text_fallback_for_pure_non_latin(self):
        """Pure non-Latin names should fallback to original text so names are not blank."""
        hindi_name = "\u0905\u0932\u0940\u0917\u0902\u091c \u0917\u093e\u0902\u0935 \u0917\u0941\u0930\u094d\u091c\u0930"
        self.assertEqual(clean_text(hindi_name, is_name=True), hindi_name)
        # For non-names (e.g. address), empty is returned if no ASCII content remains
        self.assertEqual(clean_text(hindi_name, is_name=False), "")

    def test_clean_text_empty_and_whitespace(self):
        """Empty, None, and pure punctuation should return empty string."""
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text("   "), "")
        self.assertEqual(clean_text(",,, , -"), "")

    def test_format_distance(self):
        """Should format distance up to 1 decimal place with proper singular/plural units."""
        from src.utils.formatters import format_distance

        self.assertEqual(format_distance(0.1425), "0.1 km")
        self.assertEqual(format_distance(0.1), "0.1 km")
        self.assertEqual(format_distance(0.0), "0 km")
        self.assertEqual(format_distance(1.0), "1 km")
        self.assertEqual(format_distance(1.04), "1 km")
        self.assertEqual(format_distance(1.52), "1.5 kms")
        self.assertEqual(format_distance(2.9123), "2.9 kms")
        self.assertEqual(format_distance(2.0), "2 kms")
        self.assertEqual(format_distance("3.45"), "3.5 kms")
        self.assertEqual(format_distance(None), "")
        self.assertEqual(format_distance(""), "")



class TestIO(unittest.TestCase):
    """Test file loading and parsing."""

    def test_load_locations_csv(self):
        """Valid CSV should parse location names and float coordinates."""
        csv_content = "Location,Lat,Long\nTest Center,28.500,77.200\nInvalid Row,,\n"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            locations = load_locations(temp_path)
            self.assertEqual(len(locations), 1)
            self.assertEqual(locations[0]["name"], "Test Center")
            self.assertEqual(locations[0]["lat"], 28.5)
            self.assertEqual(locations[0]["lng"], 77.2)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_clean_csv_file(self):
        """clean_csv_file should sanitize fields, write UTF-8 BOM, and report modified rows."""
        import csv
        header = "sno,name,address\n"
        row1 = (
            '1,Tata Power Charging Station,"IndianOil e-Charge Station, Intimate Filling Station, '
            '\u092a\u0902\u091a\u0936\u0940\u0932 \u092e\u093e\u0930\u094d\u0917, 110017, India"\n'
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(header + row1)
            temp_path = f.name

        try:
            total, modified = clean_csv_file(temp_path)
            self.assertEqual(total, 1)
            self.assertEqual(modified, 1)

            # Check UTF-8 BOM
            with open(temp_path, "rb") as f:
                self.assertEqual(f.read(3), b"\xef\xbb\xbf")

            # Check cleaned content
            with open(temp_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(
                    rows[0]["address"],
                    "IndianOil e-Charge Station, Intimate Filling Station, 110017, India",
                )

            # Idempotence: running again modifies 0 rows
            total2, modified2 = clean_csv_file(temp_path)
            self.assertEqual(total2, 1)
            self.assertEqual(modified2, 0)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestConcurrencyAndConfig(unittest.TestCase):
    """Test multi-threaded configuration and CPU-based worker sizing."""

    def test_default_workers_calculated_from_cpu(self):
        """Default workers should scale with system CPU cores/threads within quota-safe bound [2, 8]."""
        from src.config import get_default_workers
        expected = max(2, min(8, os.cpu_count() or 4))
        self.assertEqual(get_default_workers(), expected)

    def test_scraper_config_uses_cpu_default(self):
        """ScraperConfig should default max_workers to get_default_workers()."""
        from src.config import get_default_workers
        cfg = ScraperConfig()
        self.assertEqual(cfg.max_workers, get_default_workers())

    def test_custom_workers_config(self):
        """Custom workers parameter should override CPU defaults in ScraperConfig."""
        cfg = ScraperConfig(max_workers=10)
        self.assertEqual(cfg.max_workers, 10)

    def test_scraper_initializes_with_workers(self):
        """BusinessScraper should accept custom worker configuration."""
        cfg = ScraperConfig(max_workers=8)
        scraper = BusinessScraper(cfg)
        self.assertEqual(scraper.config.max_workers, 8)

    def test_stop_event_initialized(self):
        """BusinessScraper should have a threading.Event stop_event initialized."""
        import threading
        scraper = BusinessScraper()
        self.assertIsInstance(scraper.stop_event, threading.Event)
        self.assertFalse(scraper.stop_event.is_set())

    def test_process_location_aborts_immediately_if_stopped(self):
        """process_single_location should abort immediately if stop_event is already set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = ScraperConfig(output_dir=tmpdir)
            scraper = BusinessScraper(cfg)
            scraper.stop_event.set()
            loc_info = {"name": "Test Site", "lat": 28.5, "lng": 77.2}
            count, outfile = scraper.process_single_location(1, loc_info, 1)
            self.assertEqual(count, 0)
            self.assertTrue(os.path.exists(outfile))


class TestRateLimiterAndQuotas(unittest.TestCase):
    """Test global rate limiting and Google Places quota protections."""

    def test_rate_limiter_acquires_immediately_first_call(self):
        """First call to rate limiter should succeed immediately."""
        from src.api.rate_limiter import ThreadSafeRateLimiter
        limiter = ThreadSafeRateLimiter(max_qps=20.0)
        self.assertTrue(limiter.acquire())

    def test_rate_limiter_aborts_on_stop_event(self):
        """Rate limiter should abort and return False if stop_event is signaled."""
        import threading
        from src.api.rate_limiter import ThreadSafeRateLimiter
        limiter = ThreadSafeRateLimiter(max_qps=1.0)
        stop_event = threading.Event()
        stop_event.set()
        self.assertFalse(limiter.acquire(stop_event=stop_event))

    def test_client_initializes_with_rate_limiter(self):
        """GooglePlacesClient should be equipped with a ThreadSafeRateLimiter."""
        from src.api.google_places import GooglePlacesClient
        from src.api.rate_limiter import ThreadSafeRateLimiter
        client = GooglePlacesClient(api_key="test_key", max_qps=15.0)
        self.assertIsInstance(client.rate_limiter, ThreadSafeRateLimiter)
        self.assertEqual(client.rate_limiter.max_qps, 15.0)


class TestDualVariantGeneration(unittest.TestCase):
    """Test generating both all-entries and deduplicated-with-phone variants."""

    def test_dual_variant_files_created_and_filtered(self):
        """Scraper should output all entries to output_dir and only valid phone & review entries to dedup_output_dir."""
        import csv
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmp_all, tempfile.TemporaryDirectory() as tmp_dedup:
            cfg = ScraperConfig(
                output_dir=tmp_all,
                dedup_output_dir=tmp_dedup,
                inter_query_delay=0.0,
                enable_enrichment=False,  # Test heuristic enrichment path deterministically
            )
            scraper = BusinessScraper(cfg)

            # Mock search_text_paginated to return 4 places:
            # 1: multiple numbers (landline + mobile) -> should pick mobile WhatsApp number
            # 2: valid phone but NO review count -> filtered out from dedup
            # 3: no phone -> filtered out from dedup
            # 4: landline only -> filtered out from dedup (not on WhatsApp)
            mock_places = [
                {
                    "id": "place_1",
                    "displayName": {"text": "Store With Phone - Lajpat Nagar Branch"},
                    "formattedAddress": "123 Main St",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": "+91 11 4767 4000 / +91 98765 43210",
                    "userRatingCount": 25,
                    "rating": 4.5,
                    "businessStatus": "OPERATIONAL",
                },
                {
                    "id": "place_2",
                    "displayName": {"text": "Store With Phone But No Reviews"},
                    "formattedAddress": "456 Side St",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": "+91 91234 56789",
                    "userRatingCount": None,
                    "businessStatus": "OPERATIONAL",
                },
                {
                    "id": "place_3",
                    "displayName": {"text": "Store Without Phone"},
                    "formattedAddress": "789 Other St",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": None,
                    "userRatingCount": 10,
                    "businessStatus": "OPERATIONAL",
                },
                {
                    "id": "place_4",
                    "displayName": {"text": "Store With Landline Only"},
                    "formattedAddress": "101 Ring Rd",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": "+91 11 4614 6666",
                    "userRatingCount": 18,
                    "businessStatus": "OPERATIONAL",
                },
            ]
            loc_info = {"name": "Test Hub", "lat": 28.5, "lng": 77.2}
            call_count = [0]

            def fake_search(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_places
                scraper.stop_event.set()
                return []

            scraper.client.search_text_paginated = fake_search

            count, all_outfile = scraper.process_single_location(1, loc_info, 1)

            dedup_outfile = os.path.join(tmp_dedup, os.path.basename(all_outfile))
            self.assertTrue(os.path.exists(all_outfile))
            self.assertTrue(os.path.exists(dedup_outfile))

            with open(all_outfile, "r", encoding="utf-8-sig") as f:
                all_rows = list(csv.DictReader(f))
            with open(dedup_outfile, "r", encoding="utf-8-sig") as f:
                dedup_rows = list(csv.DictReader(f))

            # All 4 places in raw CSV
            self.assertEqual(len(all_rows), 4)
            self.assertIn("review_count", all_rows[0])

            # Only place_1 (valid review count + mobile WhatsApp number prioritized over landline)
            # place_4 (landline only) is automatically filtered out from WhatsApp deduplicated export
            self.assertEqual(len(dedup_rows), 1)
            self.assertEqual(dedup_rows[0]["sno"], "1")
            self.assertEqual(dedup_rows[0]["business_name"], "Store With Phone - Lajpat Nagar Branch")
            self.assertEqual(dedup_rows[0]["whatsapp_name"], "Store With Phone - Lajpat Nagar Branch")
            self.assertEqual(dedup_rows[0]["short_name"], "Store With Phone")
            self.assertEqual(dedup_rows[0]["review_count"], "25")
            self.assertTrue(bool(dedup_rows[0]["business_goal"]))
            # Prioritized WhatsApp mobile number (+91 98765 43210) over landline (+91 11 4767 4000)
            self.assertIn("98765", dedup_rows[0]["phone"])
            self.assertEqual(dedup_rows[0]["tag"], "test_hub")
            self.assertIn("formatted_distance", dedup_rows[0])
            self.assertIn("km", dedup_rows[0]["formatted_distance"])


class TestBedrockEnricher(unittest.TestCase):
    """Test Bedrock enrichment client and heuristic fallbacks."""

    def test_heuristic_short_name(self):
        """Should strip corporate suffixes and location/tagline text."""
        from src.api.bedrock_enricher import heuristic_short_name

        self.assertEqual(
            heuristic_short_name("TATA.CARS Showroom - Jasper, Lajpat Nagar"),
            "TATA.CARS Showroom",
        )
        self.assertEqual(
            heuristic_short_name("Maruti Suzuki ARENA (Competent Automobiles)"),
            "Maruti Suzuki ARENA",
        )
        self.assertEqual(
            heuristic_short_name("Punia Traveleaze Pvt. Ltd."),
            "Punia Traveleaze",
        )

    def test_heuristic_business_goal(self):
        """Should map primary types to concise marketing business goals."""
        from src.api.bedrock_enricher import heuristic_business_goal

        self.assertEqual(heuristic_business_goal("car_dealer"), "more test drives")
        self.assertEqual(heuristic_business_goal("car_repair"), "more service bookings")
        self.assertEqual(heuristic_business_goal("restaurant"), "higher dine-in footfall")
        self.assertEqual(heuristic_business_goal("supermarket"), "bigger basket sizes")

    def test_is_already_clean_short_name(self):
        """Should detect already-clean atomic store/brand names."""
        from src.api.bedrock_enricher import is_already_clean_short_name

        self.assertTrue(is_already_clean_short_name("Auto Elite"))
        self.assertTrue(is_already_clean_short_name("ZARA"))
        self.assertTrue(is_already_clean_short_name("Starbucks"))
        self.assertTrue(is_already_clean_short_name("KFC"))
        self.assertTrue(is_already_clean_short_name("Haldiram's"))

        # Complex names requiring extraction should return False
        self.assertFalse(is_already_clean_short_name("TATA.CARS Showroom - Jasper, Lajpat Nagar"))
        self.assertFalse(is_already_clean_short_name("Maruti Suzuki ARENA (Competent Automobiles)"))
        self.assertFalse(is_already_clean_short_name("Punia Traveleaze Pvt. Ltd."))
        self.assertFalse(is_already_clean_short_name("HDFC Bank Connaught Place Branch"))

    def test_brand_cache(self):
        """Should cache and recall resolved short names."""
        import tempfile
        from pathlib import Path
        from src.api.bedrock_enricher import BrandCache

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = Path(tmp_dir) / "test_cache.json"
            cache = BrandCache(cache_file=cache_file)
            cache.set("Tata Motors - Jasper Branch", "Tata Motors")
            cache.save()

            # Reload into new instance
            reloaded = BrandCache(cache_file=cache_file)
            self.assertEqual(reloaded.get("Tata Motors - Jasper Branch"), "Tata Motors")
            self.assertIsNone(reloaded.get("Unknown Business"))

    def test_enricher_batch_processing_mock(self):
        """Should process batch of records with compact pipe format and populate short_name and business_goal."""
        from unittest.mock import MagicMock
        from src.api.bedrock_enricher import BedrockEnricher

        enricher = BedrockEnricher(region_name="ap-south-1")
        mock_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": "0|TATA Showroom"
                        }
                    ]
                }
            }
        }
        enricher.client = MagicMock()
        enricher.client.converse.return_value = mock_response

        records = [
            {"name": "TATA Showroom Pvt Ltd", "primary_type": "car_dealer", "source_group": "automotive"}
        ]
        result = enricher.enrich_records(records)
        self.assertEqual(result[0]["short_name"], "TATA Showroom")
        self.assertEqual(result[0]["business_goal"], "more test drives")

    def test_enricher_bypasses_clean_names_without_llm(self):
        """Clean names should bypass Bedrock LLM calls entirely."""
        from unittest.mock import MagicMock
        from src.api.bedrock_enricher import BedrockEnricher

        enricher = BedrockEnricher(region_name="ap-south-1")
        enricher.client = MagicMock()

        records = [
            {"name": "Auto Elite", "primary_type": "car_dealer", "source_group": "automotive"},
            {"name": "Starbucks", "primary_type": "coffee_shop", "source_group": "food_and_drink"},
        ]
        result = enricher.enrich_records(records)
        self.assertEqual(result[0]["short_name"], "Auto Elite")
        self.assertEqual(result[0]["business_goal"], "more test drives")
        self.assertEqual(result[1]["short_name"], "Starbucks")
        self.assertEqual(result[1]["business_goal"], "higher daily footfall")

        # LLM client should NOT be called at all
        enricher.client.converse.assert_not_called()


class TestWhatsAppPhone(unittest.TestCase):
    """Test WhatsApp phone number validation, extraction, and priority selection."""

    def test_extract_phone_candidates_single_and_multiple(self):
        """Should split multiple numbers separated by slash, comma, or pipe."""
        from src.utils.whatsapp_phone import extract_phone_candidates

        single = extract_phone_candidates("+91 98718 64545")
        self.assertEqual(len(single), 1)

        multi = extract_phone_candidates("+91 11 4767 4000 / +91 95608 50044")
        self.assertEqual(len(multi), 2)
        self.assertIn("+91 11 4767 4000", multi)
        self.assertIn("+91 95608 50044", multi)

    def test_is_whatsapp_number(self):
        """Should recognize valid mobiles as WhatsApp capable and reject landlines/toll-free."""
        from src.utils.whatsapp_phone import is_whatsapp_number

        self.assertTrue(is_whatsapp_number("+91 98718 64545"))
        self.assertTrue(is_whatsapp_number("+91 95608 50044"))
        self.assertTrue(is_whatsapp_number("09871864545"))

        # Landlines & toll-free should be rejected
        self.assertFalse(is_whatsapp_number("+91 11 4614 6666"))
        self.assertFalse(is_whatsapp_number("+91 80 6251 4723"))
        self.assertFalse(is_whatsapp_number("+91 120 458 1260"))
        self.assertFalse(is_whatsapp_number("+91 1800 203 4044"))

    def test_select_best_whatsapp_number_priority(self):
        """Should prioritize mobile over landline when multiple numbers are present."""
        from src.utils.whatsapp_phone import select_best_whatsapp_number

        # Multiple candidates: 1 landline, 1 mobile
        best = select_best_whatsapp_number(["+91 11 4767 4000", "+91 95608 50044"])
        self.assertIsNotNone(best)
        self.assertIn("95608", best)

        # Candidates with only landlines should return None
        only_landline = select_best_whatsapp_number(["+91 11 4614 6666", "+91 80 6251 4723"])
        self.assertIsNone(only_landline)

    def test_get_wa_link(self):
        """Should generate canonical wa.me link for international outreach."""
        from src.utils.whatsapp_phone import get_wa_link

        link = get_wa_link("+91 98718 64545")
        self.assertEqual(link, "https://wa.me/919871864545")


class TestDedupAndEnrichExisting(unittest.TestCase):
    """Test standalone deduplication and AI enrichment of existing CSV files."""

    def test_dedup_and_enrich_csv_file(self):
        """Should filter out non-WhatsApp, deduplicate by place_id, and enrich records."""
        from src.constants import DEDUP_CSV_FIELDNAMES
        from src.scraper import dedup_and_enrich_csv_file

        with tempfile.TemporaryDirectory() as tmpdir:
            in_file = os.path.join(tmpdir, "location_01_Test_Location.csv")
            out_file = os.path.join(tmpdir, "location_01_Test_Location_deduped.csv")

            # Write raw test CSV
            rows = [
                {
                    "sno": "1",
                    "name": "Tata Motors Showroom - Jasper, South Ext",
                    "address": "Ring Road, South Extension",
                    "gmb_link": "https://www.google.com/maps/place/?q=place_id:ChIJ1111",
                    "lat": "28.56",
                    "lng": "77.22",
                    "distance_km": "1.52",
                    "phone": "+91 98718 64545",
                    "rating": "4.8",
                    "user_ratings_total": "120",
                    "source_group": "automotive",
                    "primary_type": "car_dealer",
                    "opening_hours": "Mon-Sun 10:00-19:00",
                },
                # Duplicate of first place with landline added
                {
                    "sno": "2",
                    "name": "Tata Motors Showroom - Jasper",
                    "address": "Ring Road, South Extension",
                    "gmb_link": "https://www.google.com/maps/place/?q=place_id:ChIJ1111",
                    "lat": "28.56",
                    "lng": "77.22",
                    "distance_km": "1.52",
                    "phone": "+91 11 4123 4567",
                    "rating": "4.8",
                    "user_ratings_total": "120",
                    "source_group": "automotive",
                    "primary_type": "car_dealer",
                    "opening_hours": "Mon-Sun 10:00-19:00",
                },
                # Landline-only business (should be filtered out)
                {
                    "sno": "3",
                    "name": "Only Landline Store",
                    "address": "Connaught Place",
                    "gmb_link": "https://www.google.com/maps/place/?q=place_id:ChIJ2222",
                    "lat": "28.63",
                    "lng": "77.21",
                    "distance_km": "2.1",
                    "phone": "+91 11 2345 6789",
                    "rating": "4.0",
                    "user_ratings_total": "50",
                    "source_group": "shopping",
                    "primary_type": "store",
                    "opening_hours": "Mon-Sat 10:00-20:00",
                },
                # Missing review count (should be filtered out)
                {
                    "sno": "4",
                    "name": "No Reviews Business",
                    "address": "Nehru Place",
                    "gmb_link": "https://www.google.com/maps/place/?q=place_id:ChIJ3333",
                    "lat": "28.55",
                    "lng": "77.25",
                    "distance_km": "3.0",
                    "phone": "+91 99999 12345",
                    "rating": "",
                    "user_ratings_total": "",
                    "source_group": "services",
                    "primary_type": "hair_salon",
                    "opening_hours": "",
                },
            ]

            import csv
            fieldnames = [
                "sno", "name", "address", "gmb_link", "lat", "lng", "distance_km",
                "phone", "rating", "user_ratings_total", "source_group",
                "primary_type", "opening_hours",
            ]
            with open(in_file, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(rows)

            saved_count = dedup_and_enrich_csv_file(in_file, out_file)
            self.assertEqual(saved_count, 1)

            with open(out_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, DEDUP_CSV_FIELDNAMES)
                out_rows = list(reader)
                self.assertEqual(len(out_rows), 1)
                row = out_rows[0]
                self.assertEqual(row["sno"], "1")
                self.assertIn("Tata Motors Showroom", row["business_name"])
                self.assertEqual(row["short_name"], "Tata Motors Showroom")
                self.assertEqual(row["business_goal"], "more test drives")
                self.assertEqual(row["formatted_distance"], "1.5 kms")
                self.assertIn("98718", row["phone"])
                self.assertEqual(row["tag"], "test_location")

    def test_dedup_and_enrich_existing_method(self):
        """Scraper.dedup_and_enrich_existing should process folder and default to _deduplicated suffix."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_dir = os.path.join(tmp_dir, "raw_data")
            os.makedirs(raw_dir, exist_ok=True)
            in_file = os.path.join(raw_dir, "location_01.csv")

            import csv
            fieldnames = [
                "sno", "name", "address", "gmb_link", "lat", "lng", "distance_km",
                "phone", "rating", "user_ratings_total", "source_group",
                "primary_type", "opening_hours",
            ]
            with open(in_file, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerow({
                    "sno": "1",
                    "name": "Test Motors",
                    "address": "Delhi",
                    "gmb_link": "https://maps.google.com/?q=place_id:ChIJ11",
                    "lat": "28.5",
                    "lng": "77.2",
                    "distance_km": "1.0",
                    "phone": "+91 98765 43210",
                    "rating": "4.5",
                    "user_ratings_total": "10",
                    "source_group": "automotive",
                    "primary_type": "car_dealer",
                    "opening_hours": "",
                })

            cfg = ScraperConfig(output_dir=raw_dir)
            scraper = BusinessScraper(cfg)
            summary = scraper.dedup_and_enrich_existing()

            self.assertEqual(summary["files_processed"], 1)
            self.assertEqual(summary["total_dedup_records"], 1)
            expected_dedup_dir = f"{raw_dir}_deduplicated"
            self.assertTrue(os.path.isdir(expected_dedup_dir))

    def test_no_fstring_backslash_for_python311_compatibility(self):
        """Ensure no f-string expression parts contain backslashes, maintaining Python <= 3.11 compatibility."""
        import ast
        repo_root = Path(__file__).resolve().parent.parent
        py_files = list(repo_root.glob("src/**/*.py")) + list(repo_root.glob("tests/**/*.py"))
        violations = []
        for py_file in py_files:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.FormattedValue):
                    segment = ast.get_source_segment(content, node.value)
                    if segment and "\\" in segment:
                        violations.append((str(py_file), node.lineno, segment))
        self.assertEqual(violations, [], f"F-string backslashes break Python <= 3.11: {violations}")


if __name__ == "__main__":
    unittest.main()

