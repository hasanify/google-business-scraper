"""Input and output file handling utilities.

Provides functions to read input locations CSV files and ensure directory structures.
"""

import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Union


def load_locations(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse a CSV file containing target locations and geographic coordinates.

    Expected CSV columns:
        - Location: Name or description of the location
        - Lat: Latitude as float string
        - Long: Longitude as float string

    Args:
        filepath: Path to the locations CSV file.

    Returns:
        A list of dictionaries with keys 'name', 'lat', and 'lng'.
    """
    path = Path(filepath)
    if not path.exists():
        return []

    locations: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_name = row.get("Location", "").strip()
            lat_str = row.get("Lat", "").strip()
            lng_str = row.get("Long", "").strip()

            if not lat_str or not lng_str:
                continue

            try:
                lat = float(lat_str)
                lng = float(lng_str)
                locations.append({
                    "name": loc_name,
                    "lat": lat,
                    "lng": lng,
                })
            except ValueError:
                continue

    return locations


def ensure_output_dir(dirpath: Union[str, Path]) -> Path:
    """Ensure that the target output directory exists.

    Args:
        dirpath: Path to the target directory.

    Returns:
        Path object pointing to the ensured directory.
    """
    path = Path(dirpath)
    path.mkdir(parents=True, exist_ok=True)
    return path
