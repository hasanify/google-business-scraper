"""Input and output file handling utilities.

Provides functions to read input locations CSV files and ensure directory structures.
"""

import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


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
    with open(path, "r", encoding="utf-8-sig") as f:
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


def clean_csv_file(filepath: Union[str, Path]) -> Tuple[int, int]:
    """Clean and re-encode an existing CSV file in place using clean_text and utf-8-sig.

    Args:
        filepath: Path to the target CSV file.

    Returns:
        Tuple of (total_rows, modified_rows).
    """
    from .formatters import clean_text

    path = Path(filepath)
    if not path.exists():
        return (0, 0)

    rows: List[Dict[str, Any]] = []
    fieldnames: List[str] = []
    total_rows = 0
    modified_rows = 0

    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            total_rows += 1
            orig_name = row.get("business_name") or row.get("name", "")
            orig_addr = row.get("address", "")
            new_name = clean_text(orig_name, is_name=True)
            new_addr = clean_text(orig_addr, is_name=False)

            if new_name != orig_name or new_addr != orig_addr:
                modified_rows += 1
                if "business_name" in row:
                    row["business_name"] = new_name
                if "whatsapp_name" in row:
                    row["whatsapp_name"] = new_name
                if "name" in row:
                    row["name"] = new_name
                row["address"] = new_addr
            rows.append(row)

    # Write back with utf-8-sig encoding
    tmp_path = path.with_suffix(".csv.tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    os.replace(tmp_path, path)
    return (total_rows, modified_rows)


def clean_all_csv_files(directories: List[Union[str, Path]]) -> Dict[str, Any]:
    """Scan and sanitize all CSV files across given directories.

    Args:
        directories: List of directory paths containing CSV files.

    Returns:
        Summary dict containing processed files count, total rows, and modified rows.
    """
    summary = {
        "files_processed": 0,
        "total_rows": 0,
        "modified_rows": 0,
        "details": [],
    }

    for dir_path in directories:
        d = Path(dir_path)
        if not d.exists():
            continue

        for csv_file in sorted(d.glob("*.csv")):
            total, modified = clean_csv_file(csv_file)
            summary["files_processed"] += 1
            summary["total_rows"] += total
            summary["modified_rows"] += modified
            summary["details"].append({
                "file": str(csv_file),
                "total": total,
                "modified": modified,
            })

    return summary

