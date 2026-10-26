"""AWS Bedrock Business Data Enrichment Client.

Enriches business records with concise customer-facing brand names (short_name)
and commercial marketing objectives (business_goal) using AWS Bedrock foundation models
(such as Claude 3.5 Haiku) with fallback heuristics.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    import boto3
except ImportError:
    boto3 = None

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Fallback mapping of place primary types to representative business goals
DEFAULT_TYPE_GOALS: Dict[str, str] = {
    # Automotive
    "car_dealer": "more test drives",
    "car_rental": "more rental bookings",
    "car_repair": "more service bookings",
    "car_wash": "more service bookings",
    "electric_vehicle_charging_station": "higher charger awareness",
    "gas_station": "higher station footfall",
    "parking": "higher parking usage",
    "rest_stop": "higher visitor footfall",
    # Business
    "corporate_office": "greater brand visibility",
    "farm": "higher visitor numbers",
    "ranch": "higher visitor numbers",
    # Culture
    "art_gallery": "higher artwork sales",
    "art_studio": "more class enrolments",
    "auditorium": "more event bookings",
    "cultural_landmark": "higher visitor footfall",
    "historical_place": "higher visitor numbers",
    "monument": "higher visitor numbers",
    "museum": "higher visitor numbers",
    "performing_arts_theater": "higher ticket sales",
    "sculpture": "greater public awareness",
    # Education
    "library": "higher daily footfall",
    "preschool": "more admission enquiries",
    "primary_school": "more admission enquiries",
    "school": "more admission enquiries",
    "secondary_school": "more admission enquiries",
    "university": "more student applications",
    # Entertainment & Recreation
    "adventure_sports_center": "more event bookings",
    "amusement_center": "higher ticket sales",
    "amusement_park": "higher ticket sales",
    "aquarium": "higher ticket sales",
    "banquet_hall": "more event bookings",
    "bowling_alley": "higher visitor footfall",
    "casino": "higher visitor numbers",
    "comedy_club": "higher ticket sales",
    "concert_hall": "higher ticket sales",
    "event_venue": "more event bookings",
    "movie_theater": "higher ticket sales",
    "night_club": "higher ticket sales",
    "park": "higher visitor numbers",
    "tourist_attraction": "higher visitor numbers",
    "zoo": "higher visitor numbers",
    # Finance
    "accounting": "more client consultations",
    "bank": "more account openings",
    "atm": "higher walk-in usage",
    # Food & Drink
    "bakery": "more takeaway orders",
    "bar": "higher ticket sales",
    "bar_and_grill": "higher dine-in footfall",
    "cafe": "higher dine-in footfall",
    "coffee_shop": "higher daily footfall",
    "fast_food_restaurant": "more takeaway orders",
    "food_delivery": "more online orders",
    "ice_cream_shop": "more impulse purchases",
    "meal_delivery": "more online orders",
    "meal_takeaway": "more takeaway orders",
    "pub": "higher ticket sales",
    "restaurant": "higher dine-in footfall",
    "tea_house": "higher daily footfall",
    # Services
    "astrologer": "more consultation bookings",
    "barber_shop": "more appointment bookings",
    "beautician": "more appointment bookings",
    "beauty_salon": "more appointment bookings",
    "body_art_service": "more appointment bookings",
    "catering_service": "more catering enquiries",
    "cemetery": "greater public awareness",
    "child_care_agency": "more admission enquiries",
    "consultant": "more client enquiries",
    "courier_service": "more shipping accounts",
    "electrician": "more service leads",
    "florist": "more gifting orders",
    "foot_care": "more appointment bookings",
    "hair_care": "more appointment bookings",
    "hair_salon": "more appointment bookings",
    "insurance_agency": "more policy leads",
    "laundry": "more pickup orders",
    "lawyer": "more client consultations",
    "locksmith": "more service leads",
    "makeup_artist": "more appointment bookings",
    "moving_company": "more moving enquiries",
    "nail_salon": "more appointment bookings",
    "painter": "more service leads",
    "plumber": "more service leads",
    "psychic": "more consultation bookings",
    "real_estate_agency": "more property leads",
    "storage": "more moving enquiries",
    "tailor": "more pickup orders",
    "telecommunications_service_provider": "more new subscribers",
    "tour_agency": "more trip bookings",
    "tourist_information_center": "more visitor engagement",
    "travel_agency": "more trip bookings",
    "veterinary_care": "more appointment bookings",
    # Shopping
    "asian_grocery_store": "bigger basket sizes",
    "auto_parts_store": "more service bookings",
    "bicycle_store": "more showroom visits",
    "book_store": "more showroom visits",
    "butcher_shop": "bigger basket sizes",
    "cell_phone_store": "more store visits",
    "clothing_store": "higher store footfall",
    "convenience_store": "bigger basket sizes",
    "department_store": "higher store footfall",
    "discount_store": "more showroom visits",
    "electronics_store": "more store visits",
    "food_store": "bigger basket sizes",
    "furniture_store": "more showroom visits",
    "gift_shop": "more showroom visits",
    "grocery_store": "bigger basket sizes",
    "hardware_store": "more showroom visits",
    "home_goods_store": "more showroom visits",
    "home_improvement_store": "more showroom visits",
    "jewelry_store": "higher store footfall",
    "market": "bigger basket sizes",
    "pet_store": "stronger pet-owner loyalty",
    "shoe_store": "higher store footfall",
    "shopping_mall": "higher mall footfall",
    "sporting_goods_store": "higher equipment sales",
    "store": "more showroom visits",
    "supermarket": "bigger basket sizes",
    "warehouse_store": "more showroom visits",
    "wholesaler": "more bulk buyers",
    # Sports
    "arena": "more event bookings",
    "athletic_field": "more memberships",
    "fitness_center": "more membership sign-ups",
    "golf_course": "more memberships",
    "gym": "more membership sign-ups",
    "playground": "more memberships",
    "sports_activity_location": "more memberships",
    "sports_club": "more memberships",
    "sports_coaching": "more memberships",
    "sports_complex": "more memberships",
    "swimming_pool": "more memberships",
    # Transportation
    "bus_stop": "greater public awareness",
    "international_airport": "greater traveller visibility",
}

SYSTEM_PROMPT = """You are a business data enrichment engine.
For each business item provided, generate:
1. 'short_name': A clean, concise brand or business name suitable for display. Remove legal entities (Pvt Ltd, LLC, LLP, Inc, Co), branch/location details (e.g., '- Jasper, Lajpat Nagar', 'in Lajpat Nagar', parentheses with locations), and long secondary descriptors/taglines. Retain the core recognizable store or brand identity.
2. 'business_goal': A 3-4 word phrase representing the core commercial marketing objective for this business type (e.g., 'more test drives' for car dealers, 'more service bookings' for car repairs, 'more rental bookings' for car rentals, 'higher dine-in footfall' for restaurants, 'more trip bookings' for travel agencies, 'more appointment bookings' for salons/services, 'higher store footfall' for retail clothing, 'more store visits' for electronics/mobile stores, 'bigger basket sizes' for supermarkets/groceries).

Return ONLY a valid JSON array of objects with keys 'id', 'short_name', and 'business_goal'. No explanation or markdown."""


def heuristic_short_name(name: str) -> str:
    """Derive clean concise short name heuristically when LLM is unavailable."""
    if not name:
        return ""
    # Strip parenthetical annotations: "Store (Branch, City)" -> "Store"
    s = re.sub(r"\(.*?\)", "", name)
    # Strip after hyphen or em-dash or pipe if likely branch/tagline
    if " - " in s:
        s = s.split(" - ")[0]
    elif " | " in s:
        s = s.split(" | ")[0]
    # Remove common legal entity terms
    legal_pattern = r"(?i)\b(pvt\.?\s*ltd\.?|private\s+limited|limited|llc|llp|inc\.?|corp\.?|co\.?)(?:\.|\b)"
    s = re.sub(legal_pattern, "", s)
    # Clean up whitespace and trailing punctuation
    s = re.sub(r"[,;:\.\-\s]+$", "", s).strip()
    return s if s else name.strip()


def heuristic_business_goal(primary_type: str, source_group: str = "") -> str:
    """Lookup default marketing business goal from taxonomy."""
    pt = (primary_type or "").lower().strip()
    if pt in DEFAULT_TYPE_GOALS:
        return DEFAULT_TYPE_GOALS[pt]
    sg = (source_group or "").lower().strip()
    if "food" in sg or "drink" in sg:
        return "higher dine-in footfall"
    if "shop" in sg:
        return "more store visits"
    if "service" in sg:
        return "more client enquiries"
    if "auto" in sg:
        return "more service bookings"
    if "sport" in sg:
        return "more memberships"
    return "greater brand visibility"


class BedrockEnricher:
    """Enriches business records using AWS Bedrock runtime client."""

    def __init__(
        self,
        region_name: Optional[str] = None,
        bearer_token: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        """Initialize AWS Bedrock client.

        Args:
            region_name: AWS region string (defaults to AWS_REGION or 'ap-south-1').
            bearer_token: Bedrock API Key / Bearer token (defaults to AWS_BEARER_TOKEN_BEDROCK).
            model_id: Model ID string (defaults to LLM_MODEL_ID or Claude 3.5 Haiku).
        """
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self.bearer_token = bearer_token or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        self.model_id = model_id or os.getenv(
            "LLM_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
        self.client = None

        if self.bearer_token and "AWS_BEARER_TOKEN_BEDROCK" not in os.environ:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = self.bearer_token

        if boto3 is not None and (self.bearer_token or os.getenv("AWS_ACCESS_KEY_ID")):
            try:
                self.client = boto3.client("bedrock-runtime", region_name=self.region_name)
            except Exception as e:
                logger.warning(f"Could not initialize AWS Bedrock client: {e}")
                self.client = None

    def is_available(self) -> bool:
        """Return True if Bedrock client is configured and available."""
        return self.client is not None

    def _call_bedrock_batch(self, batch_items: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
        """Call Bedrock Converse API for a batch of items."""
        if not self.client:
            return {}

        prompt_payload = [
            {
                "id": item["id"],
                "name": item["name"],
                "primary_type": item.get("primary_type", ""),
                "source_group": item.get("source_group", ""),
            }
            for item in batch_items
        ]

        try:
            response = self.client.converse(
                modelId=self.model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": json.dumps(prompt_payload)}]}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
            )
            raw_text = response["output"]["message"]["content"][0]["text"].strip()
            # Strip markdown formatting if present
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text).strip()

            parsed = json.loads(raw_text)
            results: Dict[int, Dict[str, str]] = {}
            if isinstance(parsed, list):
                for obj in parsed:
                    if isinstance(obj, dict) and "id" in obj:
                        results[obj["id"]] = {
                            "short_name": str(obj.get("short_name", "")).strip(),
                            "business_goal": str(obj.get("business_goal", "")).strip(),
                        }
            return results
        except Exception as e:
            logger.warning(f"Bedrock converse call failed: {e}")
            return {}

    def enrich_records(
        self,
        records: List[Dict[str, Any]],
        batch_size: int = 25,
        log_callback: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Enrich a list of records with short_name and business_goal.

        Args:
            records: List of dictionaries containing at least 'name', 'primary_type', 'source_group'.
            batch_size: Number of records per Bedrock API call (default 25).
            log_callback: Optional logging function.

        Returns:
            List of updated records with 'short_name' and 'business_goal' populated.
        """
        if not records:
            return []

        enriched: List[Dict[str, Any]] = [dict(r) for r in records]

        # Process in batches
        for start_idx in range(0, len(enriched), batch_size):
            chunk = enriched[start_idx : start_idx + batch_size]
            batch_items = [
                {
                    "id": idx,
                    "name": r.get("business_name") or r.get("name", ""),
                    "primary_type": r.get("primary_type", ""),
                    "source_group": r.get("source_group", ""),
                }
                for idx, r in enumerate(chunk)
            ]

            results = {}
            if self.is_available():
                results = self._call_bedrock_batch(batch_items)

            for item in batch_items:
                i = item["id"]
                target_row = chunk[i]
                res = results.get(i)
                short_name = (res.get("short_name") if res else "") or heuristic_short_name(
                    item["name"]
                )
                business_goal = (res.get("business_goal") if res else "") or heuristic_business_goal(
                    item["primary_type"], item["source_group"]
                )

                target_row["short_name"] = short_name
                target_row["business_goal"] = business_goal

            if log_callback:
                processed = min(start_idx + batch_size, len(enriched))
                log_callback(f"Bedrock enrichment: {processed}/{len(enriched)} records processed")

        return enriched
