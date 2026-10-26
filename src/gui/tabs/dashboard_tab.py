"""Dashboard Tab: Primary scraper execution and monitoring interface."""

import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from ...config import DEFAULT_CONFIG, ScraperConfig, get_default_workers
from ...constants import KEYWORD_GROUPS
from ..theme import ThemeColors


class DashboardTab(ttk.Frame):
    """Main tab for configuring parameters, launching scraper, and viewing live logs."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_start_scrape: Callable[[ScraperConfig], None],
        on_stop_scrape: Callable[[], None],
    ) -> None:
        super().__init__(parent, style="TFrame")
        self.on_start_scrape = on_start_scrape
        self.on_stop_scrape = on_stop_scrape

        # Reactive State variables
        self.api_key_var = tk.StringVar(value=os.environ.get("GOOGLE_API_KEY", ""))
        self.show_api_key_var = tk.BooleanVar(value=False)
        self.locations_file_var = tk.StringVar(value="locations.csv")
        self.output_dir_var = tk.StringVar(value="./data/google")
        self.dedup_dir_var = tk.StringVar(value="./data/google_deduplicated")
        self.radius_var = tk.DoubleVar(value=3.0)
        self.workers_var = tk.IntVar(value=get_default_workers())
        self.max_qps_var = tk.DoubleVar(value=10.0)

        # Bedrock AI Enrichment state variables
        self.enable_enrichment_var = tk.BooleanVar(value=True)
        self.aws_bearer_token_var = tk.StringVar(
            value=os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        )
        self.show_bedrock_token_var = tk.BooleanVar(value=False)
        self.aws_region_var = tk.StringVar(value=os.environ.get("AWS_REGION", "ap-south-1"))
        self.bedrock_model_id_var = tk.StringVar(
            value=os.environ.get(
                "LLM_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
            )
        )

        # Category selections
        self.category_vars: Dict[str, tk.BooleanVar] = {
            group: tk.BooleanVar(value=True) for group in KEYWORD_GROUPS.keys()
        }

        # Status & Metrics
        self.status_var = tk.StringVar(value="Ready")
        self.metric_locations_var = tk.StringVar(value="0 / 0")
        self.metric_places_var = tk.StringVar(value="0")
        self.metric_phone_var = tk.StringVar(value="0")
        self.metric_current_var = tk.StringVar(value="-")

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dashboard layout."""
        # Main two-column or paned layout: Left (Configs) and Right (Logs & Status)
        paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=ThemeColors.BORDER,
            sashwidth=4,
            bd=0,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left panel (scrollable configuration & controls)
        left_canvas = tk.Canvas(paned, bg=ThemeColors.BG_DARK, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(paned, orient=tk.VERTICAL, command=left_canvas.yview)
        left_frame = ttk.Frame(left_canvas, style="TFrame")

        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        paned.add(left_canvas, minsize=420, width=460)

        # Right panel (Live Metrics & Streaming Log Console)
        right_frame = ttk.Frame(paned, style="TFrame")
        paned.add(right_frame, minsize=500)

        self._build_config_card(left_frame)
        self._build_bedrock_card(left_frame)
        self._build_categories_card(left_frame)
        self._build_action_card(left_frame)
        self._build_metrics_panel(right_frame)
        self._build_console_panel(right_frame)

    def _build_config_card(self, parent: ttk.Frame) -> None:
        """Card for scraper parameters and credentials."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X, padx=4, pady=4)

        title = ttk.Label(card, text="Scraper Configuration", style="Heading.TLabel")
        title.pack(anchor="w", pady=(0, 10))

        # API Key
        ttk.Label(card, text="Google Places API Key:", style="Card.TLabel").pack(anchor="w")
        api_box = ttk.Frame(card, style="Card.TFrame")
        api_box.pack(fill=tk.X, pady=(2, 8))

        self.api_entry = ttk.Entry(
            api_box,
            textvariable=self.api_key_var,
            show="*",
            style="TEntry",
        )
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        toggle_btn = ttk.Button(
            api_box,
            text="Show",
            width=6,
            command=self._toggle_api_visibility,
        )
        toggle_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.toggle_api_btn = toggle_btn

        save_env_btn = ttk.Button(
            api_box,
            text="Save .env",
            command=self._save_api_to_env,
        )
        save_env_btn.pack(side=tk.LEFT)

        # Locations File
        ttk.Label(card, text="Locations CSV File:", style="Card.TLabel").pack(anchor="w")
        loc_box = ttk.Frame(card, style="Card.TFrame")
        loc_box.pack(fill=tk.X, pady=(2, 8))
        ttk.Entry(loc_box, textvariable=self.locations_file_var, style="TEntry").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(loc_box, text="Browse...", command=self._browse_locations).pack(side=tk.LEFT)

        # Output Directory
        ttk.Label(card, text="Output Directory (All POIs):", style="Card.TLabel").pack(anchor="w")
        out_box = ttk.Frame(card, style="Card.TFrame")
        out_box.pack(fill=tk.X, pady=(2, 8))
        out_entry = ttk.Entry(out_box, textvariable=self.output_dir_var, style="TEntry")
        out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(out_box, text="Browse...", command=self._browse_output_dir).pack(side=tk.LEFT)
        out_entry.bind("<KeyRelease>", self._on_output_dir_change)

        # Deduplicated Output Directory
        ttk.Label(card, text="Deduplicated Output Directory (With Phone):", style="Card.TLabel").pack(anchor="w")
        dedup_box = ttk.Frame(card, style="Card.TFrame")
        dedup_box.pack(fill=tk.X, pady=(2, 8))
        ttk.Entry(dedup_box, textvariable=self.dedup_dir_var, style="TEntry").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(dedup_box, text="Browse...", command=self._browse_dedup_dir).pack(side=tk.LEFT)

        # Tuning row: Radius, Workers, QPS
        tune_row = ttk.Frame(card, style="Card.TFrame")
        tune_row.pack(fill=tk.X, pady=(4, 2))

        # Radius
        rad_col = ttk.Frame(tune_row, style="Card.TFrame")
        rad_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Label(rad_col, text="Radius (km):", style="Card.TLabel").pack(anchor="w")
        ttk.Spinbox(
            rad_col,
            from_=0.5,
            to=50.0,
            increment=0.5,
            textvariable=self.radius_var,
            width=8,
        ).pack(fill=tk.X, pady=2)

        # Workers
        cpu_count = os.cpu_count() or 4
        work_col = ttk.Frame(tune_row, style="Card.TFrame")
        work_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Label(work_col, text=f"Workers (max {cpu_count}):", style="Card.TLabel").pack(anchor="w")
        ttk.Spinbox(
            work_col,
            from_=1,
            to=32,
            textvariable=self.workers_var,
            width=6,
        ).pack(fill=tk.X, pady=2)

        # Max QPS
        qps_col = ttk.Frame(tune_row, style="Card.TFrame")
        qps_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(qps_col, text="Max QPS:", style="Card.TLabel").pack(anchor="w")
        ttk.Spinbox(
            qps_col,
            from_=1.0,
            to=50.0,
            increment=1.0,
            textvariable=self.max_qps_var,
            width=6,
        ).pack(fill=tk.X, pady=2)

    def _build_bedrock_card(self, parent: ttk.Frame) -> None:
        """Card for configuring AWS Bedrock AI enrichment parameters."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X, padx=4, pady=4)

        header_box = ttk.Frame(card, style="Card.TFrame")
        header_box.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_box, text="AWS Bedrock AI Enrichment", style="Heading.TLabel").pack(
            side=tk.LEFT
        )

        enable_cb = ttk.Checkbutton(
            header_box,
            text="Enable AI",
            variable=self.enable_enrichment_var,
            style="TCheckbutton",
            command=self._on_toggle_enrichment,
        )
        enable_cb.pack(side=tk.RIGHT)

        self.bedrock_inputs_frame = ttk.Frame(card, style="Card.TFrame")
        self.bedrock_inputs_frame.pack(fill=tk.X)

        # Bearer Token / API Key
        ttk.Label(
            self.bedrock_inputs_frame,
            text="Bedrock Bearer Token / API Key:",
            style="Card.TLabel",
        ).pack(anchor="w")
        token_box = ttk.Frame(self.bedrock_inputs_frame, style="Card.TFrame")
        token_box.pack(fill=tk.X, pady=(2, 8))

        self.bedrock_token_entry = ttk.Entry(
            token_box,
            textvariable=self.aws_bearer_token_var,
            show="*",
            style="TEntry",
        )
        self.bedrock_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.toggle_bedrock_btn = ttk.Button(
            token_box,
            text="Show",
            width=6,
            command=self._toggle_bedrock_visibility,
        )
        self.toggle_bedrock_btn.pack(side=tk.LEFT, padx=(0, 6))

        save_bedrock_btn = ttk.Button(
            token_box,
            text="Save .env",
            command=self._save_bedrock_to_env,
        )
        save_bedrock_btn.pack(side=tk.LEFT)

        # Region & Model ID in 2 columns
        model_row = ttk.Frame(self.bedrock_inputs_frame, style="Card.TFrame")
        model_row.pack(fill=tk.X, pady=(2, 2))

        # Region column
        reg_col = ttk.Frame(model_row, style="Card.TFrame")
        reg_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Label(reg_col, text="AWS Region:", style="Card.TLabel").pack(anchor="w")
        reg_combo = ttk.Combobox(
            reg_col,
            textvariable=self.aws_region_var,
            values=["ap-south-1", "us-east-1", "us-west-2", "eu-central-1", "ap-southeast-1"],
            style="TCombobox",
        )
        reg_combo.pack(fill=tk.X, pady=2)

        # Model ID column
        model_col = ttk.Frame(model_row, style="Card.TFrame")
        model_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(model_col, text="Model ID:", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(
            model_col,
            textvariable=self.bedrock_model_id_var,
            style="TEntry",
        ).pack(fill=tk.X, pady=2)

    def _build_categories_card(self, parent: ttk.Frame) -> None:
        """Card for toggling category taxonomy groups."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X, padx=4, pady=4)

        header_box = ttk.Frame(card, style="Card.TFrame")
        header_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header_box, text="Categories to Scrape", style="Heading.TLabel").pack(side=tk.LEFT)

        btn_box = ttk.Frame(header_box, style="Card.TFrame")
        btn_box.pack(side=tk.RIGHT)
        ttk.Button(btn_box, text="All", width=5, command=self._select_all_categories).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="None", width=5, command=self._deselect_all_categories).pack(side=tk.LEFT, padx=2)

        grid_frame = ttk.Frame(card, style="Card.TFrame")
        grid_frame.pack(fill=tk.X)

        groups = sorted(KEYWORD_GROUPS.keys())
        for idx, group in enumerate(groups):
            row = idx // 2
            col = idx % 2
            display_name = group.replace("_", " ").title()
            cb = ttk.Checkbutton(
                grid_frame,
                text=display_name,
                variable=self.category_vars[group],
                style="TCheckbutton",
            )
            cb.grid(row=row, column=col, sticky="w", padx=6, pady=3)

    def _build_action_card(self, parent: ttk.Frame) -> None:
        """Card containing the Start and Stop controls and progress indicator."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X, padx=4, pady=4)

        btn_box = ttk.Frame(card, style="Card.TFrame")
        btn_box.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(
            btn_box,
            text="▶ Start Scraper",
            style="Success.TButton",
            command=self._handle_start_click,
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.stop_btn = ttk.Button(
            btn_box,
            text="■ Stop Scraper",
            style="Danger.TButton",
            command=self._handle_stop_click,
            state="disabled",
        )
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(
            card,
            orient="horizontal",
            mode="determinate",
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X, pady=(4, 2))

    def _build_metrics_panel(self, parent: ttk.Frame) -> None:
        """Metrics display panel showing locations, total places, and status."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.pack(fill=tk.X, padx=4, pady=4)

        # Top row: Status Badge & Current Activity
        top_row = ttk.Frame(panel, style="Card.TFrame")
        top_row.pack(fill=tk.X, pady=(0, 8))

        self.status_badge = ttk.Label(
            top_row,
            textvariable=self.status_var,
            style="StatusBadge.TLabel",
        )
        self.status_badge.pack(side=tk.LEFT, padx=(0, 10))

        curr_box = ttk.Frame(top_row, style="Card.TFrame")
        curr_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(curr_box, text="Current Target: ", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Label(curr_box, textvariable=self.metric_current_var, style="Card.TLabel").pack(side=tk.LEFT)

        # Metrics 3-column stats
        stats_row = ttk.Frame(panel, style="Card.TFrame")
        stats_row.pack(fill=tk.X)

        self._create_stat_cell(stats_row, "Locations Done", self.metric_locations_var, "#3b82f6")
        self._create_stat_cell(stats_row, "Places Discovered", self.metric_places_var, "#10b981")
        self._create_stat_cell(stats_row, "Valid Phone Numbers", self.metric_phone_var, "#8b5cf6")

    def _create_stat_cell(
        self, parent: ttk.Frame, title: str, var: tk.StringVar, color: str
    ) -> None:
        cell = ttk.Frame(parent, style="BorderCard.TFrame", padding=(10, 6))
        cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Label(cell, text=title, style="Muted.TLabel").pack(anchor="w")
        val_lbl = tk.Label(
            cell,
            textvariable=var,
            font=("Segoe UI", 16, "bold"),
            fg=color,
            bg=ThemeColors.BG_CARD,
        )
        val_lbl.pack(anchor="w")

    def _build_console_panel(self, parent: ttk.Frame) -> None:
        """Real-time console log viewer."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=10)
        panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        header = ttk.Frame(panel, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="Live Scraper Output", style="Heading.TLabel").pack(side=tk.LEFT)

        btn_box = ttk.Frame(header, style="Card.TFrame")
        btn_box.pack(side=tk.RIGHT)
        ttk.Button(btn_box, text="Copy", command=self._copy_console_logs).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_box, text="Clear", command=self._clear_console_logs).pack(side=tk.LEFT)

        text_frame = ttk.Frame(panel, style="Card.TFrame")
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.console_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg=ThemeColors.BG_CONSOLE,
            fg=ThemeColors.TEXT_MAIN,
            insertbackground=ThemeColors.TEXT_MAIN,
            font=("Consolas", 9),
            padx=8,
            pady=8,
            bd=0,
            yscrollcommand=scrollbar.set,
        )
        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.console_text.yview)

        # Highlight tags
        self.console_text.tag_config("info", foreground="#94a3b8")
        self.console_text.tag_config("success", foreground="#34d399", font=("Consolas", 9, "bold"))
        self.console_text.tag_config("warn", foreground="#fbbf24")
        self.console_text.tag_config("error", foreground="#f87171", font=("Consolas", 9, "bold"))
        self.console_text.tag_config("accent", foreground="#60a5fa")

    # --- UI Helpers & Event Handlers ---

    def _toggle_api_visibility(self) -> None:
        is_shown = self.show_api_key_var.get()
        if is_shown:
            self.api_entry.config(show="*")
            self.toggle_api_btn.config(text="Show")
            self.show_api_key_var.set(False)
        else:
            self.api_entry.config(show="")
            self.toggle_api_btn.config(text="Hide")
            self.show_api_key_var.set(True)

    def _save_api_to_env(self) -> None:
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("API Key Missing", "Please enter an API key before saving.")
            return

        env_path = Path(".env")
        lines: List[str] = []
        replaced = False

        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GOOGLE_API_KEY="):
                        lines.append(f'GOOGLE_API_KEY="{key}"\n')
                        replaced = True
                    else:
                        lines.append(line)

        if not replaced:
            lines.append(f'GOOGLE_API_KEY="{key}"\n')

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        os.environ["GOOGLE_API_KEY"] = key
        messagebox.showinfo("Saved", "API key successfully saved to .env file.")

    def _toggle_bedrock_visibility(self) -> None:
        is_shown = self.show_bedrock_token_var.get()
        if is_shown:
            self.bedrock_token_entry.config(show="*")
            self.toggle_bedrock_btn.config(text="Show")
            self.show_bedrock_token_var.set(False)
        else:
            self.bedrock_token_entry.config(show="")
            self.toggle_bedrock_btn.config(text="Hide")
            self.show_bedrock_token_var.set(True)

    def _save_bedrock_to_env(self) -> None:
        token = self.aws_bearer_token_var.get().strip()
        region = self.aws_region_var.get().strip() or "ap-south-1"
        model_id = (
            self.bedrock_model_id_var.get().strip()
            or "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        )

        if not token:
            messagebox.showwarning(
                "Bearer Token Missing",
                "Please enter a Bedrock Bearer Token before saving.",
            )
            return

        env_path = Path(".env")
        lines: List[str] = []
        keys_set = {
            "AWS_BEARER_TOKEN_BEDROCK": False,
            "AWS_REGION": False,
            "LLM_MODEL_ID": False,
        }

        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("AWS_BEARER_TOKEN_BEDROCK="):
                        lines.append(f'AWS_BEARER_TOKEN_BEDROCK="{token}"\n')
                        keys_set["AWS_BEARER_TOKEN_BEDROCK"] = True
                    elif stripped.startswith("AWS_REGION="):
                        lines.append(f'AWS_REGION="{region}"\n')
                        keys_set["AWS_REGION"] = True
                    elif stripped.startswith("LLM_MODEL_ID="):
                        lines.append(f'LLM_MODEL_ID="{model_id}"\n')
                        keys_set["LLM_MODEL_ID"] = True
                    else:
                        lines.append(line)

        if not keys_set["AWS_BEARER_TOKEN_BEDROCK"]:
            lines.append(f'AWS_BEARER_TOKEN_BEDROCK="{token}"\n')
        if not keys_set["AWS_REGION"]:
            lines.append(f'AWS_REGION="{region}"\n')
        if not keys_set["LLM_MODEL_ID"]:
            lines.append(f'LLM_MODEL_ID="{model_id}"\n')

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = token
        os.environ["AWS_REGION"] = region
        os.environ["LLM_MODEL_ID"] = model_id
        messagebox.showinfo(
            "Saved", "AWS Bedrock configuration successfully saved to .env file."
        )

    def _on_toggle_enrichment(self) -> None:
        enabled = self.enable_enrichment_var.get()
        state = "normal" if enabled else "disabled"
        for child in self.bedrock_inputs_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass

    def _browse_locations(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Locations CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=os.getcwd(),
        )
        if file_path:
            self.locations_file_var.set(file_path)

    def _browse_output_dir(self) -> None:
        dir_path = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=os.getcwd(),
        )
        if dir_path:
            self.output_dir_var.set(dir_path)
            clean = dir_path.rstrip("/\\")
            self.dedup_dir_var.set(f"{clean}_deduplicated")

    def _browse_dedup_dir(self) -> None:
        dir_path = filedialog.askdirectory(
            title="Select Deduplicated Output Directory",
            initialdir=os.getcwd(),
        )
        if dir_path:
            self.dedup_dir_var.set(dir_path)

    def _on_output_dir_change(self, event: Any) -> None:
        out = self.output_dir_var.get().strip()
        if out:
            clean = out.rstrip("/\\")
            self.dedup_dir_var.set(f"{clean}_deduplicated")

    def _select_all_categories(self) -> None:
        for var in self.category_vars.values():
            var.set(True)

    def _deselect_all_categories(self) -> None:
        for var in self.category_vars.values():
            var.set(False)

    def _copy_console_logs(self) -> None:
        text = self.console_text.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Console logs copied to clipboard.")

    def _clear_console_logs(self) -> None:
        self.console_text.delete("1.0", tk.END)

    def append_log(self, text: str) -> None:
        """Thread-safe append text with styling to the console text widget."""
        tag = "info"
        if "[ERROR]" in text or "error" in text.lower():
            tag = "error"
        elif "COMPLETED" in text or "Saved" in text:
            tag = "success"
        elif "[!]" in text or "Interrupted" in text or "warn" in text.lower():
            tag = "warn"
        elif "Starting" in text or "Fetching" in text:
            tag = "accent"

        self.console_text.insert(tk.END, text + "\n", tag)
        self.console_text.see(tk.END)

    def _handle_start_click(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(
                "API Key Missing",
                "Please provide a Google Places API key in the configuration panel.",
            )
            return

        locations_file = self.locations_file_var.get().strip()
        if not locations_file or not os.path.exists(locations_file):
            messagebox.showerror(
                "Locations File Missing",
                f"The locations file '{locations_file}' was not found. Please verify the path.",
            )
            return

        selected_cats = [
            cat for cat, var in self.category_vars.items() if var.get()
        ]
        if not selected_cats:
            messagebox.showerror(
                "No Categories Selected",
                "Please select at least one category to scrape.",
            )
            return

        try:
            radius = float(self.radius_var.get())
            if radius <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Radius", "Search radius must be a positive number.")
            return

        try:
            workers = int(self.workers_var.get())
            if workers <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Workers", "Workers count must be a positive integer.")
            return

        try:
            max_qps = float(self.max_qps_var.get())
            if max_qps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid QPS", "Max QPS must be a positive number.")
            return

        config = ScraperConfig(
            api_key=api_key,
            radius_km=radius,
            locations_file=locations_file,
            output_dir=self.output_dir_var.get().strip() or "./data/google",
            dedup_output_dir=self.dedup_dir_var.get().strip() or None,
            max_workers=workers,
            max_qps=max_qps,
            selected_categories=selected_cats,
            enable_enrichment=self.enable_enrichment_var.get(),
            aws_region=self.aws_region_var.get().strip() or "ap-south-1",
            aws_bearer_token=self.aws_bearer_token_var.get().strip() or None,
            bedrock_model_id=self.bedrock_model_id_var.get().strip()
            or "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        )

        self.set_scraping_active(True)
        self.on_start_scrape(config)

    def _handle_stop_click(self) -> None:
        self.status_var.set("Stopping...")
        self.status_badge.config(style="StatusBadge.TLabel", background="#b45309", foreground="#fef3c7")
        self.stop_btn.config(state="disabled")
        self.append_log("[!] Stop signal requested by user...")
        self.on_stop_scrape()

    def set_scraping_active(self, active: bool) -> None:
        """Update widget enablement state when scraping begins or terminates."""
        if active:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_var.set("Scraping...")
            self.status_badge.config(background="#065f46", foreground="#a7f3d0")
            self.progress_bar.config(value=0)
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_var.set("Ready")
            self.status_badge.config(background="#1e3a8a", foreground="#93c5fd")
