# Revoplakt Business Scraper

A modular, production-ready Python tool that discovers, aggregates, and exports Points of Interest (POIs) and businesses surrounding geographic coordinates using the **Google Places API (New)**.

---

## Features

- **High-Precision Geodesy:** Uses Vincenty's direct and inverse formulas on the **WGS-84 reference ellipsoid** for exact metric geodesic distance filtering and bounding-box restrictions.
- **Broad Industry Taxonomy:** Preconfigured across 10 major category groups and 150+ Google Place types (automotive, entertainment, food & drink, sports, shopping, services, culture, education, finance, facilities).
- **Intelligent Deduplication:** Enforces unique Google Place ID tracking across multiple keyword scans for each target location.
- **Operating Hours Compression:** Compresses raw daily scheduling periods into compact, readable range strings (e.g., `Mon-Fri 09:00-18:00 | Sat 10:00-16:00`).
- **Multi-Threaded Parallel Execution:** Scrapes multiple target locations concurrently using a worker thread pool (one location per thread) for high performance and minimal turnaround time.
- **Resilient Pagination & Rate Limiting:** Handles `pageToken` pagination, network timeouts, and inter-query delays to prevent API throttling.
- **Streaming CSV Export:** Flushes discovered records progressively to disk to avoid data loss during network hiccups.
- **100% Backward Compatible:** Keeps legacy `google_get_poi.py` importable and runnable while providing a modern modular architecture.

---

## Project Structure

```text
revoplakt-business-scraper/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── config.py             # ScraperConfig dataclass & environment loading (.env support)
│   ├── constants.py          # Category taxonomy, CSV field schemas, day maps
│   ├── scraper.py            # BusinessScraper pipeline orchestrator
│   ├── api/
│   │   ├── __init__.py
│   │   └── google_places.py  # Google Places API client, auth check, paginated queries
│   ├── geo/
│   │   ├── __init__.py
│   │   └── vincenty.py       # WGS-84 Vincenty geodesic distance & bounding box math
│   └── utils/
│       ├── __init__.py
│       ├── formatters.py     # Opening hours compression & filename sanitization
│       └── io.py             # CSV location parser & directory managers
├── tests/
│   └── test_scraper.py       # Automated unit tests for geo math, formatters, and I/O
├── .env.example              # Template for API credentials
├── .gitignore                # Git exclusions (credentials, data, venv, planning)
├── google_get_poi.py         # Backward-compatible script entry point
├── main.py                   # Modern CLI entry point with argument flags
├── locations.csv             # Target locations and coordinates (gitignored)
└── requirements.txt          # Python dependencies
```

---

## Getting Started

### 1. Prerequisites

- Python 3.10 or higher
- A Google Cloud Project with:
  - **Places API (New)** enabled (`places.googleapis.com`)
  - Valid billing account attached

### 2. Installation

Clone the repository and set up a Python virtual environment:

```bash
# Clone the repository
git clone <repo-url>
cd revoplakt-business-scraper

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Copy `.env.example` to `.env` and insert your Google Cloud API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_API_KEY="AIzaSyYourActualGooglePlacesApiKeyHere"
```

*(Alternatively, you can export `GOOGLE_API_KEY` in your terminal shell).*

---

## Input Data Format

The scraper expects a CSV file (default: `locations.csv`) containing location descriptions and coordinate points:

```csv
Location,Lat,Long
"Select City Walk Saket",28.529237,77.219177
"Ambience Mall, Vasant Kunj",28.541410,77.152561
"Cyber Hub - Next to Uniqlo",28.494601,77.087972
```

---

## Usage

### Run with Modern CLI (`main.py`)

Run with default settings (3 km radius, `locations.csv`):
```bash
python main.py
```

Run with custom parameters:
```bash
python main.py --radius 5.0 --locations my_custom_locations.csv --output-dir ./data/custom
```

#### CLI Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--radius` | `3.0` | Search radius in kilometers around each point |
| `--locations` | `locations.csv` | Path to CSV file containing target coordinates |
| `--output-dir` | `./data/google` | Directory where output CSV files will be saved |
| `--workers` | `5` | Number of concurrent worker threads (one location per thread) |

### Run with Legacy Entry Point (`google_get_poi.py`)

If you have existing automation or scripts expecting `google_get_poi.py`:
```bash
python google_get_poi.py
```

---

## Output CSV Schema

For each input location, a corresponding CSV file is created in `data/google/` named `location_{index:02d}_{sanitized_name}.csv`.

Each file contains the following fields:

| Column | Description | Example |
| :--- | :--- | :--- |
| `sno` | Sequential number per location | `1` |
| `name` | Place display name | `"Starbucks Coffee"` |
| `address` | Formatted street address | `"Ground Floor, DLF Promenade..."` |
| `gmb_link` | Direct Google Maps URL with Place ID | `https://www.google.com/maps/place/?q=place_id:ChIJ...` |
| `lat` | Place latitude | `28.5426` |
| `lng` | Place longitude | `77.1557` |
| `distance_km` | Precise ellipsoidal distance from target | `0.1425` |
| `phone` | Contact phone number | `"+91 11 4123 4567"` |
| `rating` | Average Google review rating | `4.4` |
| `user_ratings_total` | Total count of Google reviews | `1250` |
| `source_group` | Scraped category group | `food_and_drink` |
| `primary_type` | Specific Google Places type | `coffee_shop` |
| `opening_hours` | Compressed schedule summary | `Mon-Sun 08:00-23:00` |

---

## Running Tests

Automated tests verify geodesic math, opening hours formatting, and CSV parsing:

```bash
python -m unittest discover tests
```

---

## License

Internal proprietary tooling for Revoplakt.
