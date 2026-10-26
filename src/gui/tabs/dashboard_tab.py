"""Dashboard Tab: Primary business search execution and live activity interface."""

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
    """Main tab for configuring parameters, launching search, and viewing live activity."""

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

        # AI Enrichment state variables
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

        # Drawer toggle state
        self.advanced_expanded_var = tk.BooleanVar(value=False)

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
        """Construct the simplified dashboard layout."""
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

        # Right panel (Live Metrics & Activity Console)
        right_frame = ttk.Frame(paned, style="TFrame")
        paned.add(right_frame, minsize=500)

        # Assemble Left Column Cards
        self._build_status_badges_card(left_frame)
        self._build_essential_config_card(left_frame)
        self._build_categories_card(left_frame)
        self._build_action_card(left_frame)
        self._build_advanced_drawer_section(left_frame)

        # Assemble Right Column Panels
        self._build_metrics_panel(right_frame)
        self._build_console_panel(right_frame)

        # Initialize dynamic badges & indicators
        self._update_credential_badges()
        self._update_locations_count()

        # Wire reactive variable traces
        self.api_key_var.trace_add("write", lambda *a: self._update_credential_badges())
        self.aws_bearer_token_var.trace_add("write", lambda *a: self._update_credential_badges())
        self.enable_enrichment_var.trace_add("write", lambda *a: self._update_credential_badges())
        self.locations_file_var.trace_add("write", lambda *a: self._update_locations_count())

    def _build_status_badges_card(self, parent: ttk.Frame) -> None:
        """Card displaying real-time connection and service readiness."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        card.pack(fill=tk.X, padx=4, pady=(4, 2))

        header_row = ttk.Frame(card, style="Card.TFrame")
        header_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header_row, text="System Status", style="Heading.TLabel").pack(side=tk.LEFT)

        badges_row = ttk.Frame(card, style="Card.TFrame")
        badges_row.pack(fill=tk.X)

        self.places_badge = ttk.Label(badges_row, text="Checking...", style="BadgeMuted.TLabel")
        self.places_badge.pack(side=tk.LEFT, padx=(0, 6))

        self.bedrock_badge = ttk.Label(badges_row, text="Checking...", style="BadgeMuted.TLabel")
        self.bedrock_badge.pack(side=tk.LEFT)

    def _build_essential_config_card(self, parent: ttk.Frame) -> None:
        """Streamlined primary inputs: Locations file and Search Distance."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, padx=4, pady=4)

        title_row = ttk.Frame(card, style="Card.TFrame")
        title_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(title_row, text="Search Locations & Distance", style="Heading.TLabel").pack(side=tk.LEFT)

        # Locations CSV
        loc_label_row = ttk.Frame(card, style="Card.TFrame")
        loc_label_row.pack(fill=tk.X)
        ttk.Label(loc_label_row, text="Locations Spreadsheet:", style="Card.TLabel").pack(side=tk.LEFT)
        self.locations_count_label = ttk.Label(
            loc_label_row, text="", style="Muted.TLabel"
        )
        self.locations_count_label.pack(side=tk.RIGHT)

        loc_box = ttk.Frame(card, style="Card.TFrame")
        loc_box.pack(fill=tk.X, pady=(2, 8))
        self.locations_entry = ttk.Entry(
            loc_box, textvariable=self.locations_file_var, style="TEntry"
        )
        self.locations_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(loc_box, text="Browse...", command=self._browse_locations).pack(side=tk.LEFT)

        # Distance row
        rad_row = ttk.Frame(card, style="Card.TFrame")
        rad_row.pack(fill=tk.X)
        ttk.Label(rad_row, text="Search Distance (km):", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Label(rad_row, text=" (Distance around each location)", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            rad_row,
            from_=0.5,
            to=50.0,
            increment=0.5,
            textvariable=self.radius_var,
            width=8,
        ).pack(side=tk.RIGHT)

    def _build_categories_card(self, parent: ttk.Frame) -> None:
        """Card for selecting business types to find."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, padx=4, pady=4)

        header_box = ttk.Frame(card, style="Card.TFrame")
        header_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header_box, text="Types of Businesses to Find", style="Heading.TLabel").pack(side=tk.LEFT)

        btn_box = ttk.Frame(header_box, style="Card.TFrame")
        btn_box.pack(side=tk.RIGHT)
        ttk.Button(btn_box, text="Select All", width=9, command=self._select_all_categories).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_box, text="Clear All", width=8, command=self._deselect_all_categories).pack(
            side=tk.LEFT, padx=2
        )

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
        """Card containing the Start and Stop buttons and progress indicator."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, padx=4, pady=4)

        btn_box = ttk.Frame(card, style="Card.TFrame")
        btn_box.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(
            btn_box,
            text="▶ Start Search",
            style="Success.TButton",
            command=self._handle_start_click,
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.stop_btn = ttk.Button(
            btn_box,
            text="■ Stop Search",
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

    def _build_advanced_drawer_section(self, parent: ttk.Frame) -> None:
        """Collapsible drawer containing technical settings, API keys, and save folders."""
        self.drawer_toggle_btn = ttk.Button(
            parent,
            text="⚙ Advanced Settings & Keys  ▶ Expand",
            command=self._toggle_advanced_drawer,
            style="Drawer.TButton",
        )
        self.drawer_toggle_btn.pack(fill=tk.X, padx=4, pady=(4, 6))

        self.drawer_frame = ttk.Frame(parent, style="TFrame")
        # Collapsed by default

        # Card 1: Google API Key
        api_card = ttk.Frame(self.drawer_frame, style="Card.TFrame", padding=12)
        api_card.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Label(api_card, text="Google API Key", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        ttk.Label(api_card, text="Your Google Places Key:", style="Card.TLabel").pack(anchor="w")
        api_box = ttk.Frame(api_card, style="Card.TFrame")
        api_box.pack(fill=tk.X, pady=(2, 2))

        self.api_entry = ttk.Entry(
            api_box,
            textvariable=self.api_key_var,
            show="*",
            style="TEntry",
        )
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.toggle_api_btn = ttk.Button(
            api_box,
            text="Show",
            width=6,
            command=self._toggle_api_visibility,
        )
        self.toggle_api_btn.pack(side=tk.LEFT, padx=(0, 6))

        save_env_btn = ttk.Button(
            api_box,
            text="Save .env",
            command=self._save_api_to_env,
        )
        save_env_btn.pack(side=tk.LEFT)

        # Card 2: Smart AI Business Descriptions
        bedrock_card = ttk.Frame(self.drawer_frame, style="Card.TFrame", padding=12)
        bedrock_card.pack(fill=tk.X, padx=4, pady=(0, 4))

        b_head = ttk.Frame(bedrock_card, style="Card.TFrame")
        b_head.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(b_head, text="Smart AI Business Descriptions", style="Heading.TLabel").pack(side=tk.LEFT)
        ttk.Checkbutton(
            b_head,
            text="Turn on AI",
            variable=self.enable_enrichment_var,
            style="TCheckbutton",
            command=self._on_toggle_enrichment,
        ).pack(side=tk.RIGHT)

        self.bedrock_inputs_frame = ttk.Frame(bedrock_card, style="Card.TFrame")
        self.bedrock_inputs_frame.pack(fill=tk.X)

        ttk.Label(
            self.bedrock_inputs_frame,
            text="Amazon Bedrock API Key:",
            style="Card.TLabel",
        ).pack(anchor="w")

        b_token_box = ttk.Frame(self.bedrock_inputs_frame, style="Card.TFrame")
        b_token_box.pack(fill=tk.X, pady=(2, 6))

        self.bedrock_token_entry = ttk.Entry(
            b_token_box,
            textvariable=self.aws_bearer_token_var,
            show="*",
            style="TEntry",
        )
        self.bedrock_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.toggle_bedrock_btn = ttk.Button(
            b_token_box,
            text="Show",
            width=6,
            command=self._toggle_bedrock_visibility,
        )
        self.toggle_bedrock_btn.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            b_token_box,
            text="Save .env",
            command=self._save_bedrock_to_env,
        ).pack(side=tk.LEFT)

        b_row = ttk.Frame(self.bedrock_inputs_frame, style="Card.TFrame")
        b_row.pack(fill=tk.X)

        reg_col = ttk.Frame(b_row, style="Card.TFrame")
        reg_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Label(reg_col, text="Cloud Region:", style="Card.TLabel").pack(anchor="w")
        ttk.Combobox(
            reg_col,
            textvariable=self.aws_region_var,
            values=["ap-south-1", "us-east-1", "us-west-2", "eu-central-1", "ap-southeast-1"],
            style="TCombobox",
        ).pack(fill=tk.X, pady=2)

        model_col = ttk.Frame(b_row, style="Card.TFrame")
        model_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(model_col, text="AI Model:", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(
            model_col,
            textvariable=self.bedrock_model_id_var,
            style="TEntry",
        ).pack(fill=tk.X, pady=2)

        # Card 3: Speed & Save Folders
        perf_card = ttk.Frame(self.drawer_frame, style="Card.TFrame", padding=12)
        perf_card.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Label(perf_card, text="Speed & Save Folders", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6)
        )

        tune_row = ttk.Frame(perf_card, style="Card.TFrame")
        tune_row.pack(fill=tk.X, pady=(0, 6))

        cpu_count = os.cpu_count() or 4
        work_col = ttk.Frame(tune_row, style="Card.TFrame")
        work_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Label(work_col, text=f"Parallel Searches (max {cpu_count}):", style="Card.TLabel").pack(
            anchor="w"
        )
        ttk.Spinbox(
            work_col,
            from_=1,
            to=32,
            textvariable=self.workers_var,
            width=6,
        ).pack(fill=tk.X, pady=2)

        qps_col = ttk.Frame(tune_row, style="Card.TFrame")
        qps_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(qps_col, text="Searches Per Second:", style="Card.TLabel").pack(anchor="w")
        ttk.Spinbox(
            qps_col,
            from_=1.0,
            to=50.0,
            increment=1.0,
            textvariable=self.max_qps_var,
            width=6,
        ).pack(fill=tk.X, pady=2)

        ttk.Label(perf_card, text="Save All Results To:", style="Card.TLabel").pack(anchor="w")
        out_box = ttk.Frame(perf_card, style="Card.TFrame")
        out_box.pack(fill=tk.X, pady=(2, 6))
        out_entry = ttk.Entry(out_box, textvariable=self.output_dir_var, style="TEntry")
        out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(out_box, text="Browse...", command=self._browse_output_dir).pack(side=tk.LEFT)
        out_entry.bind("<KeyRelease>", self._on_output_dir_change)

        ttk.Label(perf_card, text="Save Clean Results (With Phone) To:", style="Card.TLabel").pack(
            anchor="w"
        )
        dedup_box = ttk.Frame(perf_card, style="Card.TFrame")
        dedup_box.pack(fill=tk.X, pady=(2, 2))
        ttk.Entry(dedup_box, textvariable=self.dedup_dir_var, style="TEntry").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(dedup_box, text="Browse...", command=self._browse_dedup_dir).pack(side=tk.LEFT)

    def _toggle_advanced_drawer(self) -> None:
        """Expand or collapse the advanced settings drawer."""
        is_expanded = self.advanced_expanded_var.get()
        if is_expanded:
            self.drawer_frame.pack_forget()
            self.advanced_expanded_var.set(False)
            self.drawer_toggle_btn.config(text="⚙ Advanced Settings & Keys  ▶ Expand")
        else:
            self.drawer_frame.pack(fill=tk.X, padx=0, pady=(0, 4), after=self.drawer_toggle_btn)
            self.advanced_expanded_var.set(True)
            self.drawer_toggle_btn.config(text="⚙ Advanced Settings & Keys  ▼ Collapse")

    def _update_credential_badges(self) -> None:
        """Update top status pills based on active keys."""
        key = self.api_key_var.get().strip()
        if key:
            self.places_badge.config(text="✓ Google Search Connected", style="BadgeSuccess.TLabel")
        else:
            self.places_badge.config(text="⚠ Google API Key Needed", style="BadgeWarning.TLabel")

        if not self.enable_enrichment_var.get():
            self.bedrock_badge.config(text="○ AI Assistant Off", style="BadgeMuted.TLabel")
        else:
            token = self.aws_bearer_token_var.get().strip()
            if token:
                self.bedrock_badge.config(text="✓ AI Assistant Active", style="BadgeSuccess.TLabel")
            else:
                self.bedrock_badge.config(text="⚠ AI Key Needed", style="BadgeWarning.TLabel")

    def _update_locations_count(self) -> None:
        """Check target locations file and update row count badge."""
        filepath = self.locations_file_var.get().strip()
        if not filepath or not os.path.exists(filepath):
            self.locations_count_label.config(text="⚠ File not found", foreground=ThemeColors.WARNING)
            return
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                lines = [line.strip() for line in f if line.strip()]
            count = max(0, len(lines) - 1)
            self.locations_count_label.config(
                text=f"✓ {count} locations loaded", foreground=ThemeColors.SUCCESS
            )
        except Exception:
            self.locations_count_label.config(text="⚠ Cannot read file", foreground=ThemeColors.DANGER)

    def _build_metrics_panel(self, parent: ttk.Frame) -> None:
        """Metrics display panel showing locations, total places, and status."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.pack(fill=tk.X, padx=4, pady=4)

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
        ttk.Label(curr_box, text="Current target: ", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Label(curr_box, textvariable=self.metric_current_var, style="Card.TLabel").pack(side=tk.LEFT)

        stats_row = ttk.Frame(panel, style="Card.TFrame")
        stats_row.pack(fill=tk.X)

        self._create_stat_cell(stats_row, "Locations Finished", self.metric_locations_var, "#0067b8")
        self._create_stat_cell(stats_row, "Businesses Found", self.metric_places_var, "#0e703c")
        self._create_stat_cell(stats_row, "Verified Phone Numbers", self.metric_phone_var, "#7c3aed")

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
        """Real-time live activity log viewer in crisp light mode."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=10)
        panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        header = ttk.Frame(panel, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="Activity Log", style="Heading.TLabel").pack(side=tk.LEFT)

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
            bd=1,
            relief="solid",
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.console_text.yview)

        # High-contrast light mode log tags
        self.console_text.tag_config("info", foreground="#475569")
        self.console_text.tag_config("success", foreground="#15803d", font=("Consolas", 9, "bold"))
        self.console_text.tag_config("warn", foreground="#b45309", font=("Consolas", 9, "bold"))
        self.console_text.tag_config("error", foreground="#b91c1c", font=("Consolas", 9, "bold"))
        self.console_text.tag_config("accent", foreground="#0369a1")

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
            messagebox.showwarning("Key Missing", "Please enter an API key before saving.")
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
        self._update_credential_badges()
        messagebox.showinfo("Saved", "API key successfully saved to your .env file.")

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
                "Key Missing",
                "Please enter an Amazon Bedrock API Key before saving.",
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
        self._update_credential_badges()
        messagebox.showinfo(
            "Saved", "Amazon Bedrock configuration successfully saved to your .env file."
        )

    def _on_toggle_enrichment(self) -> None:
        enabled = self.enable_enrichment_var.get()
        state = "normal" if enabled else "disabled"
        for child in self.bedrock_inputs_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass
        self._update_credential_badges()

    def _browse_locations(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Locations Spreadsheet",
            filetypes=[("Spreadsheet (CSV)", "*.csv"), ("All Files", "*.*")],
            initialdir=os.getcwd(),
        )
        if file_path:
            self.locations_file_var.set(file_path)
            self._update_locations_count()

    def _browse_output_dir(self) -> None:
        dir_path = filedialog.askdirectory(
            title="Select Folder to Save All Results",
            initialdir=os.getcwd(),
        )
        if dir_path:
            self.output_dir_var.set(dir_path)
            clean = dir_path.rstrip("/\\")
            self.dedup_dir_var.set(f"{clean}_deduplicated")

    def _browse_dedup_dir(self) -> None:
        dir_path = filedialog.askdirectory(
            title="Select Folder to Save Clean Results",
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
            messagebox.showinfo("Copied", "Activity log copied to clipboard.")

    def _clear_console_logs(self) -> None:
        self.console_text.delete("1.0", tk.END)

    def append_log(self, text: str) -> None:
        """Thread-safe append text with styling to the activity text widget."""
        tag = "info"
        if "[ERROR]" in text or "error" in text.lower():
            tag = "error"
        elif "COMPLETED" in text or "Saved" in text:
            tag = "success"
        elif "[!]" in text or "Interrupted" in text or "warn" in text.lower():
            tag = "warn"
        elif "Starting" in text or "Fetching" in text or "Searching" in text:
            tag = "accent"

        self.console_text.insert(tk.END, text + "\n", tag)
        self.console_text.see(tk.END)

    def _handle_start_click(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(
                "API Key Needed",
                "Please provide a Google API key before starting. You can enter it under Advanced Settings.",
            )
            return

        locations_file = self.locations_file_var.get().strip()
        if not locations_file or not os.path.exists(locations_file):
            messagebox.showerror(
                "Locations File Missing",
                f"The locations spreadsheet '{locations_file}' was not found. Please check the path.",
            )
            return

        selected_cats = [
            cat for cat, var in self.category_vars.items() if var.get()
        ]
        if not selected_cats:
            messagebox.showerror(
                "No Types Selected",
                "Please choose at least one business type to find.",
            )
            return

        try:
            radius = float(self.radius_var.get())
            if radius <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Distance", "Search distance must be a positive number.")
            return

        try:
            workers = int(self.workers_var.get())
            if workers <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Setting", "Parallel searches must be a positive whole number.")
            return

        try:
            max_qps = float(self.max_qps_var.get())
            if max_qps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Speed", "Speed must be a positive number.")
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
        self.status_badge.config(style="StatusBadge.TLabel", background="#fef3c7", foreground="#b45309")
        self.stop_btn.config(state="disabled")
        self.append_log("[!] Stopping current search...")
        self.on_stop_scrape()

    def set_scraping_active(self, active: bool) -> None:
        """Update widget enablement state when searching begins or finishes."""
        if active:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_var.set("Searching...")
            self.status_badge.config(background="#dcfce7", foreground="#15803d")
            self.progress_bar.config(value=0)
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_var.set("Ready")
            self.status_badge.config(background="#e0f2fe", foreground="#0369a1")
