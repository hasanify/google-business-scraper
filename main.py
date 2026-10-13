"""Main entry point for Google Places Business Scraper.

Usage:
    python main.py
    python main.py --radius 5.0 --locations my_locations.csv
"""

import argparse
import sys

from src.config import ScraperConfig
from src.scraper import BusinessScraper


def parse_args() -> ScraperConfig:
    """Parse command line arguments and return ScraperConfig."""
    parser = argparse.ArgumentParser(
        description="Scrape Google Places businesses within a radius around coordinates."
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
    args = parser.parse_args()

    return ScraperConfig(
        radius_km=args.radius,
        locations_file=args.locations,
        output_dir=args.output_dir,
    )


def main() -> None:
    """Run scraper with command-line or default configuration."""
    config = parse_args()
    scraper = BusinessScraper(config)
    scraper.run()


if __name__ == "__main__":
    main()
