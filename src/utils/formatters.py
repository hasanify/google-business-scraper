"""Formatting utilities for Google Places API data.

Provides functions to compress opening hour periods into human-readable ranges
and sanitize location names for safe filesystem naming.
"""

import re
from typing import Any, Dict, List, Optional

from ..constants import DAY_MAP


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
