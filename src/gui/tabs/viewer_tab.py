"""Data Viewer & Tools Tab: Inspect generated CSV results and run cleanup utilities."""

import csv
import os
from pathlib import Path
import platform
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from ...utils.io import clean_all_csv_files
from ..theme import ThemeColors


class ViewerTab(ttk.Frame):
    """Tab for browsing scraped CSV datasets, searching records, and running cleanup tools."""

    def __init__(self, parent: ttk.Notebook, default_dir: str = "./data/google") -> None:
        super().__init__(parent, style="TFrame")
        self.directory_var = tk.StringVar(value=default_dir)
        self.selected_file_var = tk.StringVar()
        self.search_var = tk.StringVar()

        # Stats
        self.total_rows_var = tk.StringVar(value="0")
        self.with_phone_var = tk.StringVar(value="0")
        self.avg_rating_var = tk.StringVar(value="-")

        self.available_files: List[str] = []
        self.current_rows: List[Dict[str, str]] = []

        self._build_ui()
        self.refresh_files()

    def _build_ui(self) -> None:
        """Construct the Viewer & Tools layout."""
        top_bar = ttk.Frame(self, style="Card.TFrame", padding=12)
        top_bar.pack(fill=tk.X, padx=8, pady=(8, 4))

        # Output folder picker
        ttk.Label(top_bar, text="Results Directory:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(top_bar, textvariable=self.directory_var, style="TEntry", width=28).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top_bar, text="Browse...", command=self._browse_dir).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_bar, text="Refresh", command=self.refresh_files).pack(side=tk.LEFT, padx=(0, 12))

        # CSV File dropdown
        ttk.Label(top_bar, text="Select CSV:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.file_combo = ttk.Combobox(
            top_bar,
            textvariable=self.selected_file_var,
            state="readonly",
            width=36,
        )
        self.file_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.file_combo.bind("<<ComboboxSelected>>", lambda e: self._load_selected_file())

        # Cleanup Tool Button
        ttk.Button(
            top_bar,
            text="🧹 Clean Text & UTF-8 BOM",
            style="Primary.TButton",
            command=self._run_cleanup_tool,
        ).pack(side=tk.RIGHT)

        # Metrics bar
        stats_card = ttk.Frame(self, style="Card.TFrame", padding=10)
        stats_card.pack(fill=tk.X, padx=8, pady=4)

        self._create_metric_widget(stats_card, "Total Businesses", self.total_rows_var, "#3b82f6")
        self._create_metric_widget(stats_card, "With Phone Numbers", self.with_phone_var, "#10b981")
        self._create_metric_widget(stats_card, "Average Rating", self.avg_rating_var, "#f59e0b")

        # Search row
        search_box = ttk.Frame(stats_card, style="Card.TFrame")
        search_box.pack(side=tk.RIGHT, fill=tk.Y, padx=4)
        ttk.Label(search_box, text="Filter Table:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        s_entry = ttk.Entry(search_box, textvariable=self.search_var, style="TEntry", width=24)
        s_entry.pack(side=tk.LEFT)
        s_entry.bind("<KeyRelease>", lambda e: self._filter_table())

        # Table
        table_card = ttk.Frame(self, style="Card.TFrame", padding=10)
        table_card.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        table_scroll_y = ttk.Scrollbar(table_card, orient=tk.VERTICAL)
        table_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        table_scroll_x = ttk.Scrollbar(table_card, orient=tk.HORIZONTAL)
        table_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.columns = ("sno", "name", "phone", "rating", "primary_type", "distance_km", "address")
        self.tree = ttk.Treeview(
            table_card,
            columns=self.columns,
            show="headings",
            style="Treeview",
            yscrollcommand=table_scroll_y.set,
            xscrollcommand=table_scroll_x.set,
        )
        self.tree.pack(fill=tk.BOTH, expand=True)

        table_scroll_y.config(command=self.tree.yview)
        table_scroll_x.config(command=self.tree.xview)

        # Setup column headers & widths
        headers = {
            "sno": ("#", 45, "center"),
            "name": ("Business Name", 260, "w"),
            "phone": ("Phone Number", 150, "center"),
            "rating": ("Rating", 70, "center"),
            "primary_type": ("Place Type", 140, "w"),
            "distance_km": ("Dist (km)", 80, "center"),
            "address": ("Formatted Address", 340, "w"),
        }
        for col, (title, width, anchor) in headers.items():
            self.tree.heading(col, text=title, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor)

        # Bottom Actions toolbar
        toolbar = ttk.Frame(self, style="Card.TFrame", padding=10)
        toolbar.pack(fill=tk.X, padx=8, pady=(4, 8))

        ttk.Button(toolbar, text="📂 Open in Excel / Default App", command=self._open_file_in_system).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="📁 Open Folder in Explorer", command=self._open_folder_in_system).pack(
            side=tk.LEFT, padx=(0, 6)
        )

    def _create_metric_widget(
        self, parent: ttk.Frame, label: str, var: tk.StringVar, color: str
    ) -> None:
        cell = ttk.Frame(parent, style="BorderCard.TFrame", padding=(12, 6))
        cell.pack(side=tk.LEFT, padx=6)
        ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
        tk.Label(
            cell,
            textvariable=var,
            font=("Segoe UI", 14, "bold"),
            fg=color,
            bg=ThemeColors.BG_CARD,
        ).pack(anchor="w")

    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="Select Results Directory",
            initialdir=os.getcwd(),
        )
        if chosen:
            self.directory_var.set(chosen)
            self.refresh_files()

    def refresh_files(self) -> None:
        """Scan directory and dedup directory for CSV files."""
        dirpath = self.directory_var.get().strip()
        files: List[str] = []

        dirs_to_check = [dirpath]
        clean_dir = dirpath.rstrip("/\\")
        dedup_dir = f"{clean_dir}_deduplicated"
        if os.path.exists(dedup_dir) and dedup_dir not in dirs_to_check:
            dirs_to_check.append(dedup_dir)

        for d in dirs_to_check:
            if os.path.exists(d):
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith(".csv"):
                        files.append(os.path.join(d, f))

        self.available_files = files
        display_names = [os.path.basename(f) + (" (Dedup)" if "_deduplicated" in f else "") for f in files]
        self.file_combo["values"] = display_names

        if files:
            current = self.selected_file_var.get()
            if not current or current not in display_names:
                self.file_combo.current(0)
            self._load_selected_file()
        else:
            self.selected_file_var.set("")
            self.current_rows = []
            self._refresh_tree([])
            self.total_rows_var.set("0")
            self.with_phone_var.set("0")
            self.avg_rating_var.set("-")

    def _load_selected_file(self) -> None:
        idx = self.file_combo.current()
        if idx < 0 or idx >= len(self.available_files):
            return

        file_path = self.available_files[idx]
        rows: List[Dict[str, str]] = []
        total_rating = 0.0
        rating_count = 0
        phone_count = 0

        try:
            with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
                    phone = (row.get("phone") or "").strip()
                    if phone and phone.lower() not in ("none", "null", "nan", "n/a", "-"):
                        phone_count += 1
                    try:
                        r = float(row.get("rating", ""))
                        total_rating += r
                        rating_count += 1
                    except (ValueError, TypeError):
                        pass

            self.current_rows = rows
            self.total_rows_var.set(str(len(rows)))
            self.with_phone_var.set(str(phone_count))
            avg_str = f"{(total_rating / rating_count):.2f} ★" if rating_count > 0 else "N/A"
            self.avg_rating_var.set(avg_str)
            self._filter_table()
        except Exception as exc:
            messagebox.showerror("Read Error", f"Failed to read CSV: {exc}")

    def _filter_table(self) -> None:
        query = self.search_var.get().strip().lower()
        if not query:
            filtered = self.current_rows
        else:
            filtered = [
                row for row in self.current_rows
                if any(query in str(val).lower() for val in row.values())
            ]
        self._refresh_tree(filtered)

    def _refresh_tree(self, data: List[Dict[str, str]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in data:
            dist = row.get("distance_km", "")
            try:
                dist = f"{float(dist):.2f}"
            except Exception:
                pass

            self.tree.insert(
                "",
                tk.END,
                values=(
                    row.get("sno", ""),
                    row.get("name", ""),
                    row.get("phone", ""),
                    row.get("rating", ""),
                    row.get("primary_type", ""),
                    dist,
                    row.get("address", ""),
                ),
            )

    def _open_file_in_system(self) -> None:
        idx = self.file_combo.current()
        if idx < 0 or idx >= len(self.available_files):
            messagebox.showinfo("No Selection", "Please select a CSV file first.")
            return

        file_path = os.path.abspath(self.available_files[idx])
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File does not exist.")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as exc:
            messagebox.showerror("Open Error", f"Could not launch file: {exc}")

    def _open_folder_in_system(self) -> None:
        dirpath = os.path.abspath(self.directory_var.get().strip())
        if not os.path.exists(dirpath):
            messagebox.showerror("Error", "Directory does not exist.")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(dirpath)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", dirpath])
            else:
                subprocess.Popen(["xdg-open", dirpath])
        except Exception as exc:
            messagebox.showerror("Open Error", f"Could not launch folder: {exc}")

    def _run_cleanup_tool(self) -> None:
        dirpath = self.directory_var.get().strip()
        clean_dir = dirpath.rstrip("/\\")
        dedup_dir = f"{clean_dir}_deduplicated"
        dirs = [d for d in [clean_dir, dedup_dir] if os.path.exists(d)]

        if not dirs:
            messagebox.showinfo("No Folders", "No existing output directories found to clean.")
            return

        confirm = messagebox.askyesno(
            "Confirm Cleanup",
            f"Run text sanitization (remove non-Latin scripts, normalize accents) "
            f"and re-encode CSV files with UTF-8 BOM in:\n"
            + "\n".join(f"- {d}" for d in dirs)
            + "\n\nProceed?",
        )
        if not confirm:
            return

        summary = clean_all_csv_files(dirs)
        self.refresh_files()
        messagebox.showinfo(
            "Cleanup Complete",
            f"Cleanup finished successfully:\n\n"
            f"• Files processed: {summary['files_processed']}\n"
            f"• Total rows examined: {summary['total_rows']}\n"
            f"• Rows sanitized & updated: {summary['modified_rows']}",
        )
