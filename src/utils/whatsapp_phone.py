"""WhatsApp phone number detection, scoring, and normalization utilities.

Accurately distinguishes mobile/WhatsApp-capable numbers from fixed-line landlines,
toll-free, and invalid numbers using Google's libphonenumber (phonenumbers package)
with heuristic fallbacks.
"""

import re
from typing import List, Optional, Set, Tuple

try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat, PhoneNumberType, number_type
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

# Major Indian STD area codes for landline fallback detection
KNOWN_INDIAN_STD_CODES: Set[str] = {
    "11",   # New Delhi
    "22",   # Mumbai
    "33",   # Kolkata
    "44",   # Chennai
    "80",   # Bengaluru / Cloud IVR (e.g. 080 6251...)
    "40",   # Hyderabad
    "79",   # Ahmedabad
    "20",   # Pune
    "120",  # Noida / Ghaziabad
    "124",  # Gurgaon
    "129",  # Faridabad
    "141",  # Jaipur
    "522",  # Lucknow
    "755",  # Bhopal
    "731",  # Indore
    "612",  # Patna
    "172",  # Chandigarh
    "265",  # Vadodara
    "261",  # Surat
}

PHONE_DELIMITERS_REGEX = re.compile(r"[\s]*[/,;|\n]+[\s]*|\s+(?:or|and)\s+", re.IGNORECASE)


def extract_phone_candidates(raw_text: Optional[str]) -> List[str]:
    """Split and extract individual candidate phone numbers from raw string.

    Handles multiple numbers separated by slashes, commas, pipes, or semicolons.
    Example: '+91 11 4767 4000 / +91 95608 50044' -> ['+91 11 4767 4000', '+91 95608 50044']
    """
    if not raw_text:
        return []

    s = str(raw_text).strip()
    if not s or s.lower() in ("none", "null", "nan", "n/a", "-", "0"):
        return []

    parts = PHONE_DELIMITERS_REGEX.split(s)
    candidates = []
    for part in parts:
        cleaned = part.strip()
        # Keep if it contains at least 5 digits
        digits = "".join(c for c in cleaned if c.isdigit())
        if len(digits) >= 5:
            candidates.append(cleaned)

    return candidates if candidates else [s]


def clean_digits_only(raw_phone: str) -> str:
    """Return only digits from phone string."""
    return "".join(c for c in str(raw_phone) if c.isdigit())


def get_phone_priority(phone: str, default_region: str = "IN") -> int:
    """Score a phone number based on WhatsApp suitability.

    Returns:
        100: Confirmed Mobile Number (High Priority for WhatsApp)
        50:  Fixed-line or mobile ambiguous
        0:   Fixed-line landline, toll-free, or premium rate (Not WhatsApp)
        -1:  Invalid or unparseable
    """
    if not phone:
        return -1

    raw = str(phone).strip()
    digits = clean_digits_only(raw)
    if len(digits) < 7:
        return -1

    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if not phonenumbers.is_valid_number(parsed):
                return -1

            ntype = number_type(parsed)
            if ntype == PhoneNumberType.MOBILE:
                return 100
            if ntype == PhoneNumberType.FIXED_LINE_OR_MOBILE:
                return 50
            if ntype in (
                PhoneNumberType.FIXED_LINE,
                PhoneNumberType.TOLL_FREE,
                PhoneNumberType.PREMIUM_RATE,
                PhoneNumberType.SHARED_COST,
                PhoneNumberType.VOIP,
                PhoneNumberType.UAN,
            ):
                return 0
        except Exception:
            pass

    # Heuristic fallback (primarily targeting India +91)
    local = digits
    if digits.startswith("91") and len(digits) > 10:
        local = digits[2:]
    elif digits.startswith("0") and len(digits) > 10:
        local = digits[1:]

    # Toll-free check
    if local.startswith("1800") or local.startswith("1860"):
        return 0

    # Landline STD area code check
    for std in sorted(KNOWN_INDIAN_STD_CODES, key=len, reverse=True):
        if local.startswith(std) and len(local) in (len(std) + 8, len(std) + 7):
            return 0

    # Mobile check: 10 digits starting with 6, 7, 8, or 9
    if len(local) == 10 and local[0] in "6789":
        return 100

    return 0


def is_whatsapp_number(phone: str, default_region: str = "IN") -> bool:
    """Check if the phone number is a valid WhatsApp (mobile) candidate."""
    return get_phone_priority(phone, default_region) >= 50


def format_e164(phone: str, default_region: str = "IN") -> str:
    """Format phone number to international E.164 representation.

    Example: '09871864545' -> '+919871864545'
    """
    if not phone:
        return ""

    raw = str(phone).strip()
    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
        except Exception:
            pass

    digits = clean_digits_only(raw)
    if digits.startswith("91") and len(digits) == 12:
        return f"+91 {digits[2:7]} {digits[7:]}"
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91 {digits[:5]} {digits[5:]}"

    return raw


def get_wa_link(phone: str, default_region: str = "IN") -> str:
    """Generate official wa.me link for WhatsApp Web/App outreach.

    Example: '+91 98718 64545' -> 'https://wa.me/919871864545'
    """
    if not phone:
        return ""

    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(phone, default_region)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
                return f"https://wa.me/{e164.lstrip('+')}"
        except Exception:
            pass

    digits = clean_digits_only(phone)
    if digits.startswith("0") and len(digits) == 11:
        digits = "91" + digits[1:]
    elif len(digits) == 10 and digits[0] in "6789":
        digits = "91" + digits

    return f"https://wa.me/{digits}" if digits else ""


def select_best_whatsapp_number(
    candidates: List[str], default_region: str = "IN"
) -> Optional[str]:
    """Evaluate candidate numbers and select the best WhatsApp (mobile) number.

    Prioritizes Mobile numbers (Score 100) over landlines/toll-free (Score 0).
    Returns None if no candidate qualifies as a valid WhatsApp number.

    Args:
        candidates: List of phone number strings.
        default_region: Default country code for parsing (default 'IN').

    Returns:
        Best formatted WhatsApp number or None if none qualify.
    """
    valid_scored: List[Tuple[int, str]] = []

    for cand in candidates:
        for single in extract_phone_candidates(cand):
            score = get_phone_priority(single, default_region)
            if score >= 50:
                formatted = format_e164(single, default_region)
                valid_scored.append((score, formatted))

    if not valid_scored:
        return None

    # Sort descending by score
    valid_scored.sort(key=lambda item: item[0], reverse=True)
    return valid_scored[0][1]
