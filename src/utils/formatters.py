"""Formatting utilities for Google Places API data.

Provides functions to compress opening hour periods into human-readable ranges
and sanitize location names for safe filesystem naming.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from ..constants import DAY_MAP

# Map common non-ASCII punctuation and typographic symbols to clean ASCII equivalents
PUNCTUATION_TRANSLATION: Dict[int, str] = {
    0x2019: "'",  # Right single quotation mark
    0x2018: "'",  # Left single quotation mark
    0x201C: '"',  # Left double quotation mark
    0x201D: '"',  # Right double quotation mark
    0x2013: "-",  # En dash
    0x2014: "-",  # Em dash
    0x2022: "-",  # Bullet
    0x00B7: "-",  # Middle dot
    0x2026: "...",  # Horizontal ellipsis
    0x00D7: "x",  # Multiplication sign
    0x00A0: " ",  # Non-breaking space
    0x200B: "",  # Zero-width space
    0xFEFF: "",  # Zero-width no-break space / BOM
}


def clean_text(text: Optional[str], is_name: bool = False) -> str:
    """Sanitize and normalize text strings (names, addresses) for clean CSV export.

    - Normalizes Unicode compatibility (NFKD) to convert stylized characters
      (e.g., mathematical bold/italic to standard Latin) and decompose accents.
    - Converts common smart quotes, dashes, and typographic symbols to ASCII.
    - Strips combining diacritical marks (e.g. Cafe -> Cafe, Skoda -> Skoda).
    - Removes non-ASCII scripts (such as Hindi/Devanagari, Arabic, CJK).
    - Tidies redundant punctuation, orphan commas, empty brackets, and repeated spaces.
    - Fallback: If stripping leaves no alphanumeric characters but the original text
      had non-empty content (e.g. business names written purely in local script),
      returns the trimmed original text so names are never left blank.

    Args:
        text: Raw input string or None.
        is_name: Whether this field represents a business name (enables fallback).

    Returns:
        Cleaned, normalized string.
    """
    if not text:
        return ""

    original = str(text).strip()
    if not original:
        return ""

    # Translate known non-ASCII punctuation/typography to ASCII
    s = original.translate(PUNCTUATION_TRANSLATION)

    # Normalize compatibility forms (e.g. mathematical bold/italic fonts to standard Latin,
    # and decompose accented characters like e + acute accent)
    s = unicodedata.normalize("NFKD", s)

    # Remove combining diacritical marks (leaving base Latin letters: e -> e, s -> s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # Remove remaining non-ASCII characters (Devanagari, Arabic, CJK, etc.)
    ascii_s = "".join(c for c in s if ord(c) < 128)

    # Tidy whitespace and punctuation
    cleaned = re.sub(r"[\t\r\n]+", " ", ascii_s)
    # Remove empty parentheses/brackets left behind by stripped text
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)
    cleaned = re.sub(r"\{\s*\}", "", cleaned)
    # Normalize comma spacing
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    # Collapse consecutive commas separated by spaces
    cleaned = re.sub(r"(,\s*)+,", ",", cleaned)
    cleaned = re.sub(r",+", ",", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r" +", " ", cleaned)
    # Strip leading/trailing punctuation and whitespace
    cleaned = re.sub(r"^[\s,;:\-]+|[\s,;:\-]+$", "", cleaned).strip()

    # If all alphanumeric characters were stripped:
    if not any(c.isalnum() for c in cleaned):
        # Fallback: keep original text for names so fields are not left blank
        if is_name and original:
            return original
        return ""

    return cleaned



def compress_opening_hours(roh: Optional[Dict[str, Any]]) -> str:
    """Convert Google Places regularOpeningHours object into a concise schedule string.

    Converts periods into format like 'Mon-Fri 09:00-18:00 | Sat 10:00-16:00'.

    Args:
        roh: The raw regularOpeningHours dictionary from Google Places API response.

    Returns:
        Pipe-separated compressed string of opening hours, or empty string if unavailable.
    """
    if not roh or "periods" not in roh or not isinstance(roh["periods"], list):
        return ""

    day_times: Dict[int, List[str]] = {i: [] for i in range(7)}

    for p in roh["periods"]:
        o = p.get("open")
        c = p.get("close")
        if not o or not c:
            continue

        day = o.get("day")
        if day is None or not (0 <= day <= 6):
            continue

        open_hour = o.get("hour", 0)
        open_minute = o.get("minute", 0)
        close_hour = c.get("hour", 0)
        close_minute = c.get("minute", 0)

        ot = f"{open_hour:02d}:{open_minute:02d}"
        ct = f"{close_hour:02d}:{close_minute:02d}"
        day_times[day].append(f"{ot}-{ct}")

    # Combine and sort times for each day
    formatted_days: Dict[int, str] = {
        d: ",".join(sorted(times)) for d, times in day_times.items()
    }

    parts: List[str] = []
    start = 0

    while start < 7:
        if not formatted_days[start]:
            start += 1
            continue

        end = start
        while end + 1 < 7 and formatted_days[end + 1] == formatted_days[start]:
            end += 1

        day_range = (
            DAY_MAP[start]
            if start == end
            else f"{DAY_MAP[start]}-{DAY_MAP[end]}"
        )

        parts.append(f"{day_range} {formatted_days[start]}")
        start = end + 1

    return " | ".join(parts)


def sanitize_filename(name: str, max_length: int = 45) -> str:
    """Sanitize a location name string to be filesystem and URL path safe.

    Replaces non-alphanumeric characters with underscores, condenses multiple
    underscores, and truncates to max_length characters.

    Args:
        name: Raw location or place name.
        max_length: Maximum allowed length for the sanitized name (default 45).

    Returns:
        Cleaned and safe string suitable for file naming.
    """
    clean = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    clean = re.sub(r"[-\s]+", "_", clean).strip("-_")
    return clean[:max_length] if clean else "location"
