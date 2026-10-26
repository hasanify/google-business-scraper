"""Unified Data Explorer Tab: Seamless inspection of Scraped POIs and Target Locations."""

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

from ..theme import ThemeColors
from .locations_tab import LocationsTab
from .viewer_tab import ViewerTab


class DataExplorerTab(ttk.Frame):
    """Modern unified container integrating Scraped POI Results and Target Locations."""

    def __init__(
        self,
        parent: ttk.Notebook,
        default_results_dir: str = "./data/google",
        default_locations_csv: str = "locations.csv",
    ) -> None:
        super().__init__(parent, style="TFrame")

        self.current_mode = tk.StringVar(value="results")  # 'results' or 'locations'

        # Build top segmented switcher
        self._build_header_switcher()

        # Content container
        self.content_frame = ttk.Frame(self, style="TFrame")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 6))

        # Instantiate sub-views
        self.results_view = ViewerTab(self.content_frame, default_dir=default_results_dir)
        self.locations_view = LocationsTab(self.content_frame, default_csv=default_locations_csv)

        # Default display
        self._switch_mode("results")

    def _build_header_switcher(self) -> None:
        """Construct top Windows 11 style segmented view switcher."""
        switcher_bar = ttk.Frame(self, style="Card.TFrame", padding=(12, 8))
        switcher_bar.pack(fill=tk.X, padx=8, pady=(8, 4))

        title_box = ttk.Frame(switcher_bar, style="Card.TFrame")
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="Saved Data & Locations", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Browse found business leads or view and edit your search locations",
            style="Muted.TLabel",
        ).pack(anchor="w")

        # Segment buttons on right
        btn_box = ttk.Frame(switcher_bar, style="Card.TFrame")
        btn_box.pack(side=tk.RIGHT)

        self.btn_results = ttk.Button(
            btn_box,
            text="📊 Found Businesses",
            style="SegmentActive.TButton",
            command=lambda: self._switch_mode("results"),
        )
        self.btn_results.pack(side=tk.LEFT, padx=3)

        self.btn_locations = ttk.Button(
            btn_box,
            text="📍 Search Locations",
            style="SegmentInactive.TButton",
            command=lambda: self._switch_mode("locations"),
        )
        self.btn_locations.pack(side=tk.LEFT, padx=3)

    def _switch_mode(self, mode: str) -> None:
        """Switch active sub-view between Scraped Results and Target Locations."""
        self.current_mode.set(mode)
        if mode == "results":
            self.locations_view.pack_forget()
            self.results_view.pack(fill=tk.BOTH, expand=True)
            self.btn_results.configure(style="SegmentActive.TButton")
            self.btn_locations.configure(style="SegmentInactive.TButton")
            self.results_view.refresh_files()
        else:
            self.results_view.pack_forget()
            self.locations_view.pack(fill=tk.BOTH, expand=True)
            self.btn_results.configure(style="SegmentInactive.TButton")
            self.btn_locations.configure(style="SegmentActive.TButton")
            self.locations_view.reload_file(self.locations_view.current_filepath)
