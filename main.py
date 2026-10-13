"""Main entry point for Google Places Business Scraper.

Usage:
    python main.py
    python main.py --workers 8
    python main.py --radius 5.0 --locations my_locations.csv --workers 10
"""

import argparse
import sys

from src.config import ScraperConfig, get_default_workers
from src.scraper import BusinessScraper


def parse_args() -> ScraperConfig:
    """Parse command line arguments and return ScraperConfig."""
    default_workers = get_default_workers()
    parser = argparse.ArgumentParser(
        description="Scrape Google Places businesses within a radius around coordinates using multi-threading."
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=3.0,
        help="Search radius in kilometers (default: 3.0)",
    )
    parser.add_argument(
        "--locations",
        type=str,
        default="locations.csv",
        help="Path to CSV file with locations (default: locations.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/google",
        help="Output directory for generated CSV files (default: ./data/google)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Number of concurrent worker threads (default: auto-detected from CPU cores/threads: {default_workers})",
    )
    args = parser.parse_args()

    return ScraperConfig(
        radius_km=args.radius,
        locations_file=args.locations,
        output_dir=args.output_dir,
        max_workers=args.workers,
    )


def main() -> None:
    """Run scraper with command-line or default configuration."""
    try:
        config = parse_args()
        scraper = BusinessScraper(config)
        scraper.run()
    except KeyboardInterrupt:
        print("\nScraper interrupted by user.", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
