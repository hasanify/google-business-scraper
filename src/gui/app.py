"""Main GUI Application Window and background worker orchestration."""

import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from ..config import ScraperConfig
from ..scraper import BusinessScraper
from .tabs.dashboard_tab import DashboardTab
from .tabs.locations_tab import LocationsTab
from .tabs.viewer_tab import ViewerTab
from .theme import ThemeColors, setup_theme


class ScraperApp(tk.Tk):
    """Main window for the Revoplakt Business Scraper desktop application."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Revoplakt Business Scraper - Desktop GUI")
        self.geometry("1100x720")
        self.minsize(980, 640)

        # Apply high DPI awareness and dark slate theme
        setup_theme(self)

        # Threading state & message queue
        self.worker_thread: Optional[threading.Thread] = None
        self.active_scraper: Optional[BusinessScraper] = None
        self.ui_queue: queue.Queue[Dict[str, Any]] = queue.Queue()

        self._build_header()
        self._build_notebook()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start periodic queue polling
        self.after(50, self._poll_queue)

    def _build_header(self) -> None:
        """Top banner with app branding and quick stats."""
        header = ttk.Frame(self, style="TFrame", padding=(16, 12, 16, 8))
        header.pack(fill=tk.X)

        title_box = ttk.Frame(header, style="TFrame")
        title_box.pack(side=tk.LEFT)

        ttk.Label(
            title_box,
            text="Revoplakt Business Scraper",
            style="AppTitle.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            title_box,
            text="Google Places (New) POI Aggregation & WGS-84 Geodesic Verification Engine",
            font=("Segoe UI", 9),
            foreground=ThemeColors.TEXT_MUTED,
            background=ThemeColors.BG_DARK,
        ).pack(anchor="w", pady=(2, 0))

        # Right version tag
        ver_box = ttk.Frame(header, style="TFrame")
        ver_box.pack(side=tk.RIGHT)
        ttk.Label(
            ver_box,
            text="v1.2.0 • Production Ready",
            font=("Segoe UI", 9, "bold"),
            foreground=ThemeColors.PRIMARY,
            background=ThemeColors.BG_DARK,
        ).pack(anchor="e")

    def _build_notebook(self) -> None:
        """Tabbed notebook container."""
        self.notebook = ttk.Notebook(self, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))

        # Tab 1: Dashboard
        self.dashboard_tab = DashboardTab(
            self.notebook,
            on_start_scrape=self.start_scraping,
            on_stop_scrape=self.stop_scraping,
        )
        self.notebook.add(self.dashboard_tab, text="  Scraper Dashboard  ")

        # Tab 2: Locations Manager
        self.locations_tab = LocationsTab(self.notebook, default_csv="locations.csv")
        self.notebook.add(self.locations_tab, text="  Locations Manager  ")

        # Tab 3: CSV Data Viewer & Tools
        self.viewer_tab = ViewerTab(self.notebook, default_dir="./data/google")
        self.notebook.add(self.viewer_tab, text="  Results Viewer & Tools  ")

    # --- Background Worker Management ---

    def start_scraping(self, config: ScraperConfig) -> None:
        """Launch scraper execution in a detached worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Active Job", "A scrape job is already currently running.")
            return

        def log_sink(msg: str) -> None:
            self.ui_queue.put({"event": "log", "text": msg})

        def progress_sink(data: Dict[str, Any]) -> None:
            self.ui_queue.put({"event": "progress", "data": data})

        self.active_scraper = BusinessScraper(
            config=config,
            log_callback=log_sink,
            progress_callback=progress_sink,
        )

        def worker_target() -> None:
            try:
                if self.active_scraper:
                    self.active_scraper.run()
            except Exception as exc:
                self.ui_queue.put({
                    "event": "error",
                    "text": f"Unhandled error in scraper thread: {exc}",
                })

        self.worker_thread = threading.Thread(
            target=worker_target,
            name="ScraperWorkerThread",
            daemon=True,
        )
        self.worker_thread.start()

    def stop_scraping(self) -> None:
        """Signal the active scraper to gracefully halt execution."""
        if self.active_scraper:
            self.active_scraper.stop_event.set()

    # --- Queue Polling for UI Thread Safety ---

    def _poll_queue(self) -> None:
        """Process messages pushed by the background thread."""
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                event_type = msg.get("event")

                if event_type == "log":
                    self.dashboard_tab.append_log(msg.get("text", ""))

                elif event_type == "progress":
                    self._handle_progress(msg.get("data", {}))

                elif event_type == "error":
                    err_text = msg.get("text", "Unknown error")
                    self.dashboard_tab.append_log(f"[ERROR] {err_text}")
                    self.dashboard_tab.set_scraping_active(False)
                    messagebox.showerror("Scraper Error", err_text)

                self.ui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(40, self._poll_queue)

    def _handle_progress(self, data: Dict[str, Any]) -> None:
        """Handle structured progress events from the scraper."""
        p_type = data.get("type")

        if p_type == "run_start":
            total = data.get("total_locations", 1)
            self.dashboard_tab.progress_bar.config(maximum=total, value=0)
            self.dashboard_tab.metric_locations_var.set(f"0 / {total}")
            self.dashboard_tab.metric_places_var.set("0")
            self.dashboard_tab.metric_phone_var.set("0")

        elif p_type == "location_start":
            loc_name = data.get("location", "")
            idx = data.get("index", 1)
            total = data.get("total", 1)
            self.dashboard_tab.metric_current_var.set(f"[{idx}/{total}] {loc_name}")

        elif p_type == "category_start":
            loc_name = data.get("location", "")
            group = data.get("group", "")
            idx = data.get("index", 1)
            total = data.get("total", 1)
            self.dashboard_tab.metric_current_var.set(f"[{idx}/{total}] {loc_name} ({group})")

        elif p_type == "place_found":
            sno = data.get("sno", 0)
            dedup_sno = data.get("dedup_sno", 0)
            self.dashboard_tab.metric_places_var.set(str(sno))
            self.dashboard_tab.metric_phone_var.set(str(dedup_sno))

        elif p_type == "location_complete":
            idx = data.get("index", 1)
            total = data.get("total", 1)
            self.dashboard_tab.progress_bar.config(value=idx)
            self.dashboard_tab.metric_locations_var.set(f"{idx} / {total}")

        elif p_type == "run_finish":
            interrupted = data.get("interrupted", False)
            total = data.get("total_locations", 0)
            completed = data.get("completed_locations", 0)

            self.dashboard_tab.set_scraping_active(False)
            if interrupted:
                self.dashboard_tab.status_var.set("Stopped")
                self.dashboard_tab.status_badge.config(background="#b45309", foreground="#fef3c7")
            else:
                self.dashboard_tab.status_var.set("Completed")
                self.dashboard_tab.status_badge.config(background="#065f46", foreground="#a7f3d0")
                self.dashboard_tab.progress_bar.config(value=total)

            self.dashboard_tab.metric_current_var.set("Finished")
            # Automatically refresh Results Viewer
            self.viewer_tab.refresh_files()

        elif p_type == "error":
            msg = data.get("message", "Error encountered")
            self.dashboard_tab.set_scraping_active(False)
            self.dashboard_tab.status_var.set("Error")
            self.dashboard_tab.status_badge.config(background="#991b1b", foreground="#fecaca")
            messagebox.showerror("Scraper Notice", msg)

    def _on_close(self) -> None:
        """Handle window close event with graceful thread termination."""
        if self.worker_thread and self.worker_thread.is_alive():
            confirm = messagebox.askyesno(
                "Exit Confirmation",
                "A scrape operation is currently running. Would you like to stop it and exit?",
            )
            if not confirm:
                return
            if self.active_scraper:
                self.active_scraper.stop_event.set()
        self.destroy()


def launch_gui() -> None:
    """Entry point to start the Tkinter application main loop."""
    app = ScraperApp()
    app.mainloop()
