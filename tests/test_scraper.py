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
from src.utils.formatters import compress_opening_hours, sanitize_filename
from src.utils.io import load_locations


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
        """Scraper should output all entries to output_dir and only valid phone entries to dedup_output_dir."""
        import csv
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmp_all, tempfile.TemporaryDirectory() as tmp_dedup:
            cfg = ScraperConfig(
                output_dir=tmp_all,
                dedup_output_dir=tmp_dedup,
                inter_query_delay=0.0,
            )
            scraper = BusinessScraper(cfg)

            # Mock search_text_paginated to return 2 places: 1 with phone, 1 without phone
            mock_places = [
                {
                    "id": "place_1",
                    "displayName": {"text": "Store With Phone"},
                    "formattedAddress": "123 Main St",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": "+91 98765 43210",
                    "businessStatus": "OPERATIONAL",
                },
                {
                    "id": "place_2",
                    "displayName": {"text": "Store Without Phone"},
                    "formattedAddress": "456 Side St",
                    "location": {"latitude": 28.5, "longitude": 77.2},
                    "internationalPhoneNumber": None,
                    "businessStatus": "OPERATIONAL",
                },
            ]
            scraper.client.search_text_paginated = MagicMock(return_value=mock_places)

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

            with open(all_outfile, "r", encoding="utf-8") as f:
                all_rows = list(csv.DictReader(f))
            with open(dedup_outfile, "r", encoding="utf-8") as f:
                dedup_rows = list(csv.DictReader(f))

            self.assertEqual(len(all_rows), 2)
            self.assertEqual(len(dedup_rows), 1)
            self.assertEqual(dedup_rows[0]["phone"], "+91 98765 43210")
            self.assertEqual(dedup_rows[0]["tag"], "test_hub")


if __name__ == "__main__":
    unittest.main()
