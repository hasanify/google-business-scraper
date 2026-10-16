"""Desktop GUI launcher for Google Business Scraper.

Usage:
    python gui.py
"""

import sys

from src.gui import launch_gui


def main() -> None:
    """Launch the Google Business Scraper GUI."""
    try:
        launch_gui()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
