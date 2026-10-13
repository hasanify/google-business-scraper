"""Google Places API (New) Client.

Provides an interface to the Google Places API v1 searchText endpoint, handling
authentication headers, field masks, spatial restriction bounding boxes, pagination,
distance filtering, and pre-flight connectivity verification.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set

import requests

from ..constants import PLACES_FIELD_MASK
from ..geo.vincenty import bounding_box_vincenty, vincenty_km


class GooglePlacesClient:
    """Client for interacting with the Google Places API (New) endpoint."""

    def __init__(
        self,
        api_key: str,
        search_url: str = "https://places.googleapis.com/v1/places:searchText",
        field_mask: str = PLACES_FIELD_MASK,
        timeout: float = 15.0,
        page_delay: float = 1.0,
    ) -> None:
        """Initialize Google Places API client.

        Args:
            api_key: Google Cloud API Key with Places API (New) enabled.
            search_url: Endpoint URL for searchText queries.
            field_mask: Comma-separated list of place fields to request.
            timeout: HTTP request timeout in seconds.
            page_delay: Sleep delay between paginated requests in seconds.
        """
        self.api_key = api_key
        self.search_url = search_url
        self.field_mask = field_mask
        self.timeout = timeout
        self.page_delay = page_delay

    def _get_headers(self) -> Dict[str, str]:
        """Generate common request headers including API key and field mask."""
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key or "",
            "X-Goog-FieldMask": self.field_mask,
        }

    def check_api_key(self, test_lat: float, test_lng: float) -> bool:
        """Verify API key validity, quota, and project billing status via a light pre-flight query.

        Args:
            test_lat: Sample latitude for restriction bounding box.
            test_lng: Sample longitude for restriction bounding box.

        Returns:
            True if API key is authorized and active; False otherwise.
        """
        print("Checking Google Places API key...", flush=True)

        if not self.api_key:
            print("\n" + "=" * 70, flush=True)
            print("[ERROR] GOOGLE_API_KEY is not set or empty.", flush=True)
            print("Set it in your .env file or export it as an environment variable.", flush=True)
            print("=" * 70 + "\n", flush=True)
            return False

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName",
        }
        payload = {
            "textQuery": "restaurant",
            "pageSize": 1,
            "locationRestriction": {
                "rectangle": bounding_box_vincenty(test_lat, test_lng, 1.0)
            },
        }

        try:
            response = requests.post(
                self.search_url,
                headers=headers,
                json=payload,
                timeout=10.0,
            )
            if response.status_code == 200:
                print("API Key verification successful!\n", flush=True)
                return True

            print("\n" + "=" * 70, flush=True)
            print(f"[ERROR] Google Places API returned status code {response.status_code}:", flush=True)
            print(response.text, flush=True)
            print("=" * 70, flush=True)
            print("Troubleshooting:", flush=True)
            print("1. Enable billing on your Google Cloud Project: https://console.cloud.google.com/billing", flush=True)
            print("2. Enable 'Places API (New)': https://console.cloud.google.com/apis/library/places.googleapis.com", flush=True)
            print("3. Check API key restrictions or set environment variable GOOGLE_API_KEY.", flush=True)
            print("=" * 70 + "\n", flush=True)
            return False
        except Exception as exc:
            print(f"Network error during API verification: {exc}", flush=True)
            return False

    def search_text_paginated(
        self,
        place_type: str,
        lat: float,
        lng: float,
        radius_km: float,
        seen: Set[str],
        stop_event: Optional[threading.Event] = None,
    ) -> List[Dict[str, Any]]:
        """Search Google Places for a specific type within a radius, handling pagination and distance filter.

        Args:
            place_type: Google Places type string (e.g. 'car_repair', 'restaurant').
            lat: Center latitude.
            lng: Center longitude.
            radius_km: Maximum radial distance in kilometers.
            seen: Set of already observed place IDs for deduplication.
            stop_event: Optional threading.Event to signal immediate cancellation.

        Returns:
            List of matching operational Place dictionaries within radius_km.
        """
        headers = self._get_headers()
        payload: Dict[str, Any] = {
            "textQuery": place_type.replace("_", " "),
            "includedType": place_type,
            "pageSize": 20,
            "locationRestriction": {
                "rectangle": bounding_box_vincenty(lat, lng, radius_km)
            },
        }

        all_places: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            if stop_event and stop_event.is_set():
                break

            if page_token:
                payload["pageToken"] = page_token
                if stop_event:
                    if stop_event.wait(self.page_delay):
                        break
                else:
                    time.sleep(self.page_delay)

            try:
                response = requests.post(
                    self.search_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except Exception as exc:
                print(f"Request exception: {exc}")
                break

            if response.status_code != 200:
                print(f"Error {response.status_code}: {response.text}")
                break

            data = response.json()
            all_places.extend(data.get("places", []))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        # Filter places by operational status, validity, and precise ellipsoidal distance
        places: List[Dict[str, Any]] = []
        for place in all_places:
            if stop_event and stop_event.is_set():
                break
            pid = place.get("id")
            if not pid or pid in seen:
                continue
            if place.get("businessStatus") != "OPERATIONAL":
                continue

            loc = place.get("location", {})
            plat = loc.get("latitude")
            plng = loc.get("longitude")
            if plat is None or plng is None:
                continue

            distance_km = vincenty_km(lat, lng, plat, plng)
            if distance_km > radius_km:
                continue

            places.append(place)
            seen.add(pid)

        return places
