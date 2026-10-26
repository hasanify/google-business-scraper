"""Locations Manager Tab: Inspect, add, edit, import, and save target coordinates."""

import csv
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional

from ...utils.io import load_locations
from ..theme import ThemeColors


class LocationsTab(ttk.Frame):
    """Tab for managing target coordinates and exporting updated locations.csv files."""

    def __init__(self, parent: ttk.Notebook, default_csv: str = "locations.csv") -> None:
        super().__init__(parent, style="TFrame")
        self.current_filepath = default_csv
        self.filepath_var = tk.StringVar(value=default_csv)
        self.search_var = tk.StringVar()
        self.stats_var = tk.StringVar(value="0 locations loaded")

        self.locations: List[Dict[str, Any]] = []

        self._build_ui()
        self.reload_file(default_csv)

    def _build_ui(self) -> None:
        """Construct the Locations Manager layout."""
        top_bar = ttk.Frame(self, style="Card.TFrame", padding=12)
        top_bar.pack(fill=tk.X, padx=8, pady=(8, 4))

        # File selector row
        ttk.Label(top_bar, text="Locations File:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(top_bar, textvariable=self.filepath_var, style="TEntry", width=36).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top_bar, text="Open...", command=self._browse_and_open).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_bar, text="Reload", command=self._reload_current).pack(side=tk.LEFT, padx=(0, 12))

        # Search filter
        ttk.Label(top_bar, text="Search locations:", style="Card.TLabel").pack(side=tk.LEFT, padx=(10, 6))
        search_entry = ttk.Entry(top_bar, textvariable=self.search_var, style="TEntry", width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 6))
        search_entry.bind("<KeyRelease>", lambda e: self._filter_table())

        # Table frame
        table_card = ttk.Frame(self, style="Card.TFrame", padding=10)
        table_card.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        table_scroll_y = ttk.Scrollbar(table_card, orient=tk.VERTICAL)
        table_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        table_scroll_x = ttk.Scrollbar(table_card, orient=tk.HORIZONTAL)
        table_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(
            table_card,
            columns=("sno", "name", "lat", "lng"),
            show="headings",
            style="Treeview",
            yscrollcommand=table_scroll_y.set,
            xscrollcommand=table_scroll_x.set,
        )
        self.tree.pack(fill=tk.BOTH, expand=True)

        table_scroll_y.config(command=self.tree.yview)
        table_scroll_x.config(command=self.tree.xview)

        # Setup columns
        self.tree.heading("sno", text="#", anchor="center")
        self.tree.heading("name", text="Location Name", anchor="w")
        self.tree.heading("lat", text="Latitude", anchor="center")
        self.tree.heading("lng", text="Longitude", anchor="center")

        self.tree.column("sno", width=50, anchor="center")
        self.tree.column("name", width=380, anchor="w")
        self.tree.column("lat", width=120, anchor="center")
        self.tree.column("lng", width=120, anchor="center")

        self.tree.bind("<Double-1>", lambda e: self._edit_selected_location())

        # Action Toolbar at bottom
        toolbar = ttk.Frame(self, style="Card.TFrame", padding=10)
        toolbar.pack(fill=tk.X, padx=8, pady=(4, 8))

        ttk.Button(toolbar, text="+ Add Location", style="Primary.TButton", command=self._add_location_dialog).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_selected_location).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Delete Selected", command=self._delete_selected_location).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Save Changes", style="Success.TButton", command=self._save_locations_to_disk).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Save As...", command=self._save_locations_as).pack(
            side=tk.LEFT, padx=(0, 6)
        )

        ttk.Label(toolbar, textvariable=self.stats_var, style="Muted.TLabel").pack(side=tk.RIGHT, padx=8)

    def reload_file(self, filepath: str) -> None:
        """Load coordinates from the specified CSV file into the treeview."""
        if not os.path.exists(filepath):
            self.locations = []
            self._refresh_tree([])
            self.stats_var.set(f"File not found: {filepath}")
            return

        self.current_filepath = filepath
        self.filepath_var.set(filepath)
        self.locations = load_locations(filepath)
        self._filter_table()

    def _browse_and_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Locations CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=os.getcwd(),
        )
        if path:
            self.reload_file(path)

    def _reload_current(self) -> None:
        path = self.filepath_var.get().strip()
        self.reload_file(path)

    def _filter_table(self) -> None:
        query = self.search_var.get().strip().lower()
        if not query:
            filtered = self.locations
        else:
            filtered = [
                loc for loc in self.locations
                if query in loc["name"].lower() or query in str(loc["lat"]) or query in str(loc["lng"])
            ]
        self._refresh_tree(filtered)

    def _refresh_tree(self, data: List[Dict[str, Any]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, loc in enumerate(data, start=1):
            self.tree.insert(
                "",
                tk.END,
                values=(idx, loc["name"], f"{loc['lat']:.6f}", f"{loc['lng']:.6f}"),
            )

        self.stats_var.set(f"{len(self.locations)} total location(s) ({len(data)} showing)")

    def _add_location_dialog(self) -> None:
        self._open_location_editor("Add New Location", None)

    def _edit_selected_location(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Row", "Please select a location row to edit.")
            return

        item = self.tree.item(selected[0])
        values = item["values"]
        index = int(values[0]) - 1
        if 0 <= index < len(self.locations):
            self._open_location_editor("Edit Location", index)

    def _delete_selected_location(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Row", "Please select a location row to delete.")
            return

        item = self.tree.item(selected[0])
        values = item["values"]
        index = int(values[0]) - 1

        loc_name = values[1]
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{loc_name}'?",
        )
        if confirm and 0 <= index < len(self.locations):
            del self.locations[index]
            self._filter_table()

    def _open_location_editor(self, title: str, index: Optional[int]) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("440x260")
        dialog.configure(bg=ThemeColors.BG_CARD)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        initial_name = self.locations[index]["name"] if index is not None else ""
        initial_lat = str(self.locations[index]["lat"]) if index is not None else ""
        initial_lng = str(self.locations[index]["lng"]) if index is not None else ""

        name_var = tk.StringVar(value=initial_name)
        lat_var = tk.StringVar(value=initial_lat)
        lng_var = tk.StringVar(value=initial_lng)

        content = ttk.Frame(dialog, style="Card.TFrame", padding=16)
        content.pack(fill=tk.BOTH, expand=True)

        ttk.Label(content, text="Location Name:", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(content, textvariable=name_var, style="TEntry").pack(fill=tk.X, pady=(2, 8))

        ttk.Label(content, text="Latitude (-90 to 90):", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(content, textvariable=lat_var, style="TEntry").pack(fill=tk.X, pady=(2, 8))

        ttk.Label(content, text="Longitude (-180 to 180):", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(content, textvariable=lng_var, style="TEntry").pack(fill=tk.X, pady=(2, 12))

        btn_box = ttk.Frame(content, style="Card.TFrame")
        btn_box.pack(fill=tk.X)

        def save() -> None:
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Location name cannot be empty.", parent=dialog)
                return

            try:
                lat = float(lat_var.get().strip())
                if not (-90.0 <= lat <= 90.0):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Latitude must be a valid number between -90 and 90.", parent=dialog)
                return

            try:
                lng = float(lng_var.get().strip())
                if not (-180.0 <= lng <= 180.0):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Longitude must be a valid number between -180 and 180.", parent=dialog)
                return

            entry = {"name": name, "lat": lat, "lng": lng}
            if index is None:
                self.locations.append(entry)
            else:
                self.locations[index] = entry

            self._filter_table()
            dialog.destroy()

        ttk.Button(btn_box, text="Save Location", style="Success.TButton", command=save).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    def _save_locations_to_disk(self) -> None:
        target = self.filepath_var.get().strip()
        if not target:
            target = "locations.csv"
        self._write_csv(target)

    def _save_locations_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Locations CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=os.getcwd(),
        )
        if path:
            self._write_csv(path)
            self.filepath_var.set(path)
            self.current_filepath = path

    def _write_csv(self, filepath: str) -> None:
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Location", "Lat", "Long"])
                for loc in self.locations:
                    writer.writerow([loc["name"], loc["lat"], loc["lng"]])
            messagebox.showinfo(
                "Saved",
                f"Successfully saved {len(self.locations)} locations to '{filepath}'.",
            )
        except Exception as exc:
            messagebox.showerror("Save Error", f"Failed to save locations: {exc}")
