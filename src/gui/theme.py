"""Theme, typography, and styling configuration for Tkinter GUI."""

import ctypes
import os
import platform
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


class ThemeColors:
    """Design color palette for modern dark-slate interface."""

    BG_DARK = "#0f172a"        # Deep slate background
    BG_CARD = "#1e293b"        # Card / panel surface
    BG_INPUT = "#0b1220"       # Text input & table row background
    BG_HOVER = "#334155"       # Hover highlight
    BG_CONSOLE = "#080c14"     # Terminal console black

    BORDER = "#334155"         # Subtle card border
    BORDER_LIGHT = "#475569"   # Input field border

    TEXT_MAIN = "#f8fafc"      # Primary text (nearly white)
    TEXT_MUTED = "#94a3b8"     # Secondary text (slate 400)
    TEXT_DIM = "#64748b"       # Dim placeholder / metadata text

    PRIMARY = "#3b82f6"        # Vibrant blue
    PRIMARY_HOVER = "#2563eb"
    SUCCESS = "#10b981"        # Emerald green for Start/Done
    SUCCESS_HOVER = "#059669"
    DANGER = "#ef4444"         # Red for Stop/Delete
    DANGER_HOVER = "#dc2626"
    WARNING = "#f59e0b"        # Amber for Warnings/Paused
    ACCENT = "#8b5cf6"         # Purple for tags/dedup


def enable_high_dpi_awareness() -> None:
    """Enable Windows per-monitor High-DPI awareness to avoid fuzzy text."""
    if platform.system() == "Windows":
        try:
            # Per-monitor DPI awareness V2
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # Per-monitor DPI awareness V1 fallback
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass


def setup_theme(root: tk.Tk) -> None:
    """Configure modern ttk styles and custom widget fonts on root window."""
    enable_high_dpi_awareness()

    root.configure(bg=ThemeColors.BG_DARK)

    # Base typography
    default_font = ("Segoe UI", 10)
    bold_font = ("Segoe UI", 10, "bold")
    heading_font = ("Segoe UI", 13, "bold")
    title_font = ("Segoe UI", 16, "bold")
    mono_font = ("Consolas", 10)

    style = ttk.Style(root)
    # Use 'clam' as cross-platform baseline for reliable color customization
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Frame backgrounds
    style.configure("TFrame", background=ThemeColors.BG_DARK)
    style.configure("Card.TFrame", background=ThemeColors.BG_CARD, relief="flat")
    style.configure("BorderCard.TFrame", background=ThemeColors.BG_CARD)

    # Label styles
    style.configure(
        "TLabel",
        background=ThemeColors.BG_DARK,
        foreground=ThemeColors.TEXT_MAIN,
        font=default_font,
    )
    style.configure(
        "Card.TLabel",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        font=default_font,
    )
    style.configure(
        "Muted.TLabel",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MUTED,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Heading.TLabel",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        font=heading_font,
    )
    style.configure(
        "AppTitle.TLabel",
        background=ThemeColors.BG_DARK,
        foreground=ThemeColors.TEXT_MAIN,
        font=title_font,
    )
    style.configure(
        "StatusBadge.TLabel",
        background="#1e3a8a",
        foreground="#93c5fd",
        font=("Segoe UI", 9, "bold"),
        padding=(8, 4),
    )

    # Entry styles
    style.configure(
        "TEntry",
        fieldbackground=ThemeColors.BG_INPUT,
        foreground=ThemeColors.TEXT_MAIN,
        insertcolor=ThemeColors.TEXT_MAIN,
        bordercolor=ThemeColors.BORDER_LIGHT,
        lightcolor=ThemeColors.BORDER_LIGHT,
        darkcolor=ThemeColors.BORDER_LIGHT,
        padding=6,
    )

    # Button styles
    style.configure(
        "TButton",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        bordercolor=ThemeColors.BORDER_LIGHT,
        focuscolor=ThemeColors.PRIMARY,
        font=default_font,
        padding=(12, 6),
    )
    style.map(
        "TButton",
        background=[("active", ThemeColors.BG_HOVER), ("disabled", "#1e293b")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Primary Action Button
    style.configure(
        "Primary.TButton",
        background=ThemeColors.PRIMARY,
        foreground="#ffffff",
        font=bold_font,
        padding=(14, 7),
    )
    style.map(
        "Primary.TButton",
        background=[("active", ThemeColors.PRIMARY_HOVER), ("disabled", "#334155")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Success Start Button
    style.configure(
        "Success.TButton",
        background=ThemeColors.SUCCESS,
        foreground="#ffffff",
        font=("Segoe UI", 11, "bold"),
        padding=(16, 8),
    )
    style.map(
        "Success.TButton",
        background=[("active", ThemeColors.SUCCESS_HOVER), ("disabled", "#334155")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Danger Stop Button
    style.configure(
        "Danger.TButton",
        background=ThemeColors.DANGER,
        foreground="#ffffff",
        font=("Segoe UI", 11, "bold"),
        padding=(16, 8),
    )
    style.map(
        "Danger.TButton",
        background=[("active", ThemeColors.DANGER_HOVER), ("disabled", "#334155")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Checkbutton styles
    style.configure(
        "TCheckbutton",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        font=default_font,
    )
    style.map(
        "TCheckbutton",
        background=[("active", ThemeColors.BG_CARD)],
        foreground=[("active", ThemeColors.PRIMARY)],
    )

    # Notebook Tabs
    style.configure(
        "TNotebook",
        background=ThemeColors.BG_DARK,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MUTED,
        padding=(18, 8),
        font=bold_font,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", ThemeColors.PRIMARY), ("active", ThemeColors.BG_HOVER)],
        foreground=[("selected", "#ffffff"), ("active", ThemeColors.TEXT_MAIN)],
    )

    # Progressbar
    style.configure(
        "Horizontal.TProgressbar",
        background=ThemeColors.PRIMARY,
        troughcolor=ThemeColors.BG_INPUT,
        borderwidth=0,
        thickness=8,
    )

    # Treeview (Data tables)
    style.configure(
        "Treeview",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        fieldbackground=ThemeColors.BG_CARD,
        font=default_font,
        rowheight=26,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", "#2563eb")],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background=ThemeColors.BG_INPUT,
        foreground=ThemeColors.TEXT_MAIN,
        font=bold_font,
        padding=6,
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", ThemeColors.BG_HOVER)],
    )

    # Scrollbars
    style.configure(
        "Vertical.TScrollbar",
        background=ThemeColors.BG_CARD,
        troughcolor=ThemeColors.BG_DARK,
        arrowcolor=ThemeColors.TEXT_MUTED,
        borderwidth=0,
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=ThemeColors.BG_CARD,
        troughcolor=ThemeColors.BG_DARK,
        arrowcolor=ThemeColors.TEXT_MUTED,
        borderwidth=0,
    )
