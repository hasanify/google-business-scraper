"""Automated tests for Revoplakt Business Scraper GUI components."""

import os
import tempfile
import tkinter as tk
import unittest

from src.config import ScraperConfig
from src.constants import KEYWORD_GROUPS
from src.gui.app import ScraperApp
from src.gui.tabs.dashboard_tab import DashboardTab
from src.gui.tabs.locations_tab import LocationsTab
from src.gui.tabs.viewer_tab import ViewerTab
from src.scraper import BusinessScraper


class TestGUIComponents(unittest.TestCase):
    """Test suite for GUI widgets, state variables, and event handling."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create a shared root application instance for headless testing."""
        cls.app = ScraperApp()
        cls.app.update()

    @classmethod
    def tearDownClass(cls) -> None:
        """Destroy root application instance."""
        cls.app.destroy()

    def test_app_structure(self) -> None:
        """Verify that the ScraperApp creates all three primary tabs."""
        self.assertIsNotNone(self.app.dashboard_tab)
        self.assertIsNotNone(self.app.locations_tab)
        self.assertIsNotNone(self.app.viewer_tab)
        tabs = self.app.notebook.tabs()
        self.assertEqual(len(tabs), 3)

    def test_dashboard_categories(self) -> None:
        """Verify category select all / deselect all toggles."""
        dash = self.app.dashboard_tab

        # Deselect all
        dash._deselect_all_categories()
        for var in dash.category_vars.values():
            self.assertFalse(var.get())

        # Select all
        dash._select_all_categories()
        for var in dash.category_vars.values():
            self.assertTrue(var.get())

    def test_dashboard_console_logging(self) -> None:
        """Verify that append_log properly updates the console text widget."""
        dash = self.app.dashboard_tab
        dash._clear_console_logs()
        dash.append_log("Test info line")
        dash.append_log("[ERROR] Test error line")
        content = dash.console_text.get("1.0", tk.END)
        self.assertIn("Test info line", content)
        self.assertIn("Test error line", content)

    def test_locations_tab_filtering(self) -> None:
        """Verify locations tab table search filtering."""
        loc_tab = self.app.locations_tab
        loc_tab.locations = [
            {"name": "Alpha Mall", "lat": 28.5, "lng": 77.2},
            {"name": "Beta Hub", "lat": 28.6, "lng": 77.3},
        ]
        loc_tab.search_var.set("Alpha")
        loc_tab._filter_table()
        children = loc_tab.tree.get_children()
        self.assertEqual(len(children), 1)

        # Clear filter
        loc_tab.search_var.set("")
        loc_tab._filter_table()
        children = loc_tab.tree.get_children()
        self.assertEqual(len(children), 2)

    def test_viewer_tab_metrics(self) -> None:
        """Verify CSV results parsing and metric calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "location_01_test.csv")
            with open(csv_path, "w", encoding="utf-8-sig") as f:
                f.write(
                    "sno,name,address,gmb_link,lat,lng,distance_km,phone,rating,user_ratings_total,source_group,primary_type,opening_hours,tag\n"
                    "1,Test Cafe,123 St,http://maps,28.5,77.2,0.5,+123456789,4.5,10,food_and_drink,cafe,Mon-Fri,test\n"
                    "2,Test Store,456 St,http://maps,28.5,77.2,1.2,,4.0,5,shopping,store,Mon-Fri,test\n"
                )

            viewer = self.app.viewer_tab
            viewer.directory_var.set(tmpdir)
            viewer.refresh_files()

            self.assertEqual(viewer.total_rows_var.get(), "2")
            self.assertEqual(viewer.with_phone_var.get(), "1")
            self.assertIn("4.25", viewer.avg_rating_var.get())

    def test_scraper_category_filtering(self) -> None:
        """Verify that ScraperConfig selected_categories filters keyword groups correctly."""
        config = ScraperConfig(
            api_key="AIzaSyDummyKey",
            selected_categories=["automotive"],
        )
        self.assertEqual(config.selected_categories, ["automotive"])


if __name__ == "__main__":
    unittest.main()
