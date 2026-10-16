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
from src.utils.io import clean_all_csv_files


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
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
        "--dedup-output-dir",
        type=str,
        default=None,
        help="Output directory for deduplicated CSV files with phone numbers (default: <output_dir>_deduplicated)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Number of concurrent worker threads (default: auto-detected from CPU cores/threads: {default_workers})",
    )
    parser.add_argument(
        "--max-qps",
        type=float,
        default=10.0,
        help="Maximum requests/sec across all worker threads combined (default: 10.0 for Google Cloud quotas)",
    )
    parser.add_argument(
        "--clean-existing",
        action="store_true",
        help="Clean text fields (names, addresses) and re-encode existing CSV files with UTF-8 BOM",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the desktop graphical user interface (GUI)",
    )
    return parser.parse_args()


def main() -> None:
    """Run scraper with command-line or default configuration."""
    try:
        args = parse_args()
        if args.gui:
            from src.gui import launch_gui
            launch_gui()
            return

        if args.clean_existing:
            out_dir = args.output_dir
            dedup_dir = args.dedup_output_dir or f"{args.output_dir}_deduplicated"
            print(f"Cleaning existing CSV files in '{out_dir}' and '{dedup_dir}'...", flush=True)
            summary = clean_all_csv_files([out_dir, dedup_dir])
            print(
                f"\nCleanup finished: Processed {summary['files_processed']} files, "
                f"{summary['total_rows']} total rows, "
                f"{summary['modified_rows']} modified rows.",
                flush=True,
            )
            return

        config = ScraperConfig(
            radius_km=args.radius,
            locations_file=args.locations,
            output_dir=args.output_dir,
            dedup_output_dir=args.dedup_output_dir,
            max_workers=args.workers,
            max_qps=args.max_qps,
        )
        scraper = BusinessScraper(config)
        scraper.run()
    except KeyboardInterrupt:
        print("\nScraper interrupted by user.", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()

