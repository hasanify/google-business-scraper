# Google Business Scraper

A modular, production-ready Python tool that discovers, aggregates, and exports Points of Interest (POIs) and businesses surrounding geographic coordinates using the **Google Places API (New)**.

---

## Features

- **High-Precision Geodesy:** Uses Vincenty's direct and inverse formulas on the **WGS-84 reference ellipsoid** for exact metric geodesic distance filtering and bounding-box restrictions.
- **Broad Industry Taxonomy:** Preconfigured across 10 major category groups and 150+ Google Place types (automotive, entertainment, food & drink, sports, shopping, services, culture, education, finance, facilities).
- **Intelligent Deduplication:** Enforces unique Google Place ID tracking across multiple keyword scans for each target location.
- **Operating Hours Compression:** Compresses raw daily scheduling periods into compact, readable range strings (e.g., `Mon-Fri 09:00-18:00 | Sat 10:00-16:00`).
- **Text Sanitization & Excel Compatibility:** Automatically strips non-Latin scripts (e.g., Devanagari/Hindi, Arabic), normalizes accents (`Café` -> `Cafe`, `Škoda` -> `Skoda`) and stylized typography to clean ASCII, and exports files with UTF-8 BOM (`utf-8-sig`) to eliminate spreadsheet mojibake.
- **Multi-Threaded Parallel Execution:** Scrapes multiple target locations concurrently using a worker thread pool (one location per thread) for high performance and minimal turnaround time.
- **Resilient Pagination & Rate Limiting:** Handles `pageToken` pagination, network timeouts, and inter-query delays to prevent API throttling.
- **Streaming CSV Export:** Flushes discovered records progressively to disk to avoid data loss during network hiccups.

---

## Project Structure

```text
google-business-scraper/
├── .github/
│   └── workflows/
│       └── release.yml       # Automated GitHub Actions workflow to build and release exe
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
│   ├── gui/
│   │   ├── __init__.py       # GUI package initialization
│   │   ├── app.py            # ScraperApp main window & worker thread queue
│   │   ├── theme.py          # Dark-slate theme, typography & DPI scaling
│   │   └── tabs/             # Dashboard, Locations Manager & Results Viewer tabs
│   └── utils/
│       ├── __init__.py
│       ├── formatters.py     # Opening hours compression, text sanitization & filename sanitization
│       └── io.py             # CSV location parser, directory managers & CSV cleanup utilities
├── tests/
│   ├── test_gui.py           # Automated unit tests for GUI components and tabs
│   └── test_scraper.py       # Automated unit tests for geo math, formatters, and I/O
├── .env.example              # Template for API credentials
├── .gitignore                # Git exclusions (credentials, data, venv, planning)
├── gui.py                    # Standalone Desktop GUI launcher
├── main.py                   # CLI entry point with argument flags
├── locations.example.csv     # Sample template for target locations and coordinates
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
cd google-business-scraper

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
cp locations.example.csv locations.csv
```

Edit `.env`:

```env
GOOGLE_API_KEY="AIzaSyYourActualGooglePlacesApiKeyHere"
```

*(Alternatively, you can export `GOOGLE_API_KEY` in your terminal shell).*

---

## Input Data Format

The scraper expects a CSV file (default: `locations.csv`) containing location descriptions and coordinate points (a starter template is available in `locations.example.csv`):

```csv
Location,Lat,Long
"Select City Walk Saket",28.529237,77.219177
"Ambience Mall, Vasant Kunj",28.541410,77.152561
"Cyber Hub - Next to Uniqlo",28.494601,77.087972
```

---

## Usage

### 1. Launch with Standalone Executable (`GoogleBusinessScraper.exe`)

Simply double-click `GoogleBusinessScraper.exe` in the project folder (or in `dist/`). No terminal commands or Python virtual environment activations are required.

To rebuild the executable at any time:
```bash
pyinstaller --noconsole --onefile --name GoogleBusinessScraper gui.py
```

---

### 2. Run with Python Desktop GUI (`gui.py`)

Launch the native graphical user interface via Python:
```bash
python gui.py
# or via CLI flag:
python main.py --gui
```

**Desktop GUI Features:**
- **Scraper Dashboard:** Configure API key (show/hide toggle, save to `.env`), target CSV file, output directories, search radius, concurrency worker count, max QPS, and category checklists with a real-time progress bar, live metrics cards, streaming console log, and start/stop controls.
- **Locations Manager:** View, filter, add, edit, delete, and save target coordinates directly within an interactive table with latitude/longitude bounds validation.
- **Results Viewer & Tools:** Browse and search scraped business records, view key metrics (total places, valid phone count, average rating), open CSVs directly in Excel or folder in Explorer, and run one-click text sanitization with UTF-8 BOM encoding.

---

### 3. Run with Modern CLI (`main.py`)

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
| `--gui` | `False` | Launch the desktop graphical user interface (GUI) |
| `--radius` | `3.0` | Search radius in kilometers around each point |
| `--locations` | `locations.csv` | Path to CSV file containing target coordinates |
| `--output-dir` | `./data/google` | Directory where output CSV files will be saved |
| `--dedup-output-dir` | `<output-dir>_deduplicated` | Directory where deduplicated records with valid phones will be saved |
| `--workers` | Auto (CPU threads) | Number of concurrent worker threads (quota-safe default up to 8 threads, overrides allowed) |
| `--max-qps` | `10.0` | Maximum queries-per-second across all threads combined (Google Cloud quota compliant) |
| `--clean-existing` | `False` | Clean text fields (names, addresses) and re-encode existing CSV files with UTF-8 BOM |

---

## Output CSV Schema

For each input location, a corresponding CSV file is created in `data/google/` named `location_{index:02d}_{sanitized_name}.csv`. Files are written with **UTF-8 with BOM (`utf-8-sig`)** encoding to ensure native readability in Microsoft Excel without character corruption or mojibake. Non-Latin scripts (e.g., Devanagari/Hindi, Arabic) are sanitized, while accented Latin characters and stylized fonts are normalized to clean ASCII.

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

Internal proprietary tooling for Google Business Scraper.
