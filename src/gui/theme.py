"""Theme, typography, and styling configuration for Tkinter GUI (Windows Light Mode)."""

import ctypes
import os
import platform
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


class ThemeColors:
    """Windows 11 Light Theme palette - Clean, high contrast, and accessible."""

    BG_DARK = "#f3f3f3"        # Windows 11 light desktop canvas
    BG_CARD = "#ffffff"        # Elevated clean white card surface
    BG_INPUT = "#ffffff"       # Clean text input surface
    BG_HOVER = "#e5e5e5"       # Element hover light gray
    BG_CONSOLE = "#f8fafc"     # Crisp light slate console surface

    BORDER = "#e0e0e0"         # Subtle card border (1px stroke)
    BORDER_LIGHT = "#cccccc"   # Input field border

    TEXT_MAIN = "#18181b"      # Crisp dark slate text
    TEXT_MUTED = "#52525b"     # Secondary descriptive text
    TEXT_DIM = "#94a3b8"       # Disabled / hint text

    PRIMARY = "#0067b8"        # Windows 11 Blue
    PRIMARY_HOVER = "#005da6"
    SUCCESS = "#0e703c"        # Windows 11 Green
    SUCCESS_HOVER = "#0a562e"
    DANGER = "#c42b1c"         # Windows 11 Red
    DANGER_HOVER = "#a80000"
    WARNING = "#9d5d00"        # Warm amber
    ACCENT = "#0067b8"         # Blue accent


def enable_high_dpi_awareness() -> None:
    """Enable Windows per-monitor High-DPI awareness to avoid fuzzy text."""
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass


def setup_theme(root: tk.Tk) -> None:
    """Configure modern light ttk styles and custom widget fonts on root window."""
    enable_high_dpi_awareness()

    root.configure(bg=ThemeColors.BG_DARK)

    # Base typography (Segoe UI Variable if available, fallback to Segoe UI)
    font_family = "Segoe UI Variable Text"
    try:
        available_fonts = tkfont.families(root)
        if font_family not in available_fonts:
            font_family = "Segoe UI"
    except Exception:
        font_family = "Segoe UI"

    default_font = (font_family, 10)
    bold_font = (font_family, 10, "bold")
    heading_font = (font_family, 12, "bold")
    title_font = (font_family, 15, "bold")
    mono_font = ("Consolas", 9)

    style = ttk.Style(root)
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
        font=(font_family, 9),
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

    # Status Badges (Windows 11 Light Pill Style)
    style.configure(
        "StatusBadge.TLabel",
        background="#e0f2fe",
        foreground="#0369a1",
        font=(font_family, 9, "bold"),
        padding=(8, 4),
    )
    style.configure(
        "BadgeSuccess.TLabel",
        background="#dcfce7",
        foreground="#15803d",
        font=(font_family, 9, "bold"),
        padding=(8, 3),
    )
    style.configure(
        "BadgeWarning.TLabel",
        background="#fef3c7",
        foreground="#b45309",
        font=(font_family, 9, "bold"),
        padding=(8, 3),
    )
    style.configure(
        "BadgeMuted.TLabel",
        background="#f1f5f9",
        foreground="#64748b",
        font=(font_family, 9, "bold"),
        padding=(8, 3),
    )
    style.configure(
        "Drawer.TButton",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.PRIMARY,
        font=(font_family, 9, "bold"),
        padding=(8, 6),
    )

    # Segmented navigation buttons
    style.configure(
        "SegmentActive.TButton",
        background=ThemeColors.PRIMARY,
        foreground="#ffffff",
        font=(font_family, 10, "bold"),
        padding=(14, 6),
    )
    style.map(
        "SegmentActive.TButton",
        background=[("active", ThemeColors.PRIMARY_HOVER)],
        foreground=[("active", "#ffffff")],
    )

    style.configure(
        "SegmentInactive.TButton",
        background="#f1f5f9",
        foreground=ThemeColors.TEXT_MUTED,
        font=(font_family, 10),
        padding=(14, 6),
    )
    style.map(
        "SegmentInactive.TButton",
        background=[("active", ThemeColors.BG_HOVER)],
        foreground=[("active", ThemeColors.TEXT_MAIN)],
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
        background=[("active", ThemeColors.BG_HOVER), ("disabled", "#f3f3f3")],
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
        background=[("active", ThemeColors.PRIMARY_HOVER), ("disabled", "#cccccc")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Success Start Button
    style.configure(
        "Success.TButton",
        background=ThemeColors.SUCCESS,
        foreground="#ffffff",
        font=(font_family, 11, "bold"),
        padding=(16, 8),
    )
    style.map(
        "Success.TButton",
        background=[("active", ThemeColors.SUCCESS_HOVER), ("disabled", "#cccccc")],
        foreground=[("disabled", ThemeColors.TEXT_DIM)],
    )

    # Danger Stop Button
    style.configure(
        "Danger.TButton",
        background=ThemeColors.DANGER,
        foreground="#ffffff",
        font=(font_family, 11, "bold"),
        padding=(16, 8),
    )
    style.map(
        "Danger.TButton",
        background=[("active", ThemeColors.DANGER_HOVER), ("disabled", "#cccccc")],
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

    # Notebook Tabs (Windows 11 Light Tabs)
    style.configure(
        "TNotebook",
        background=ThemeColors.BG_DARK,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=ThemeColors.BG_DARK,
        foreground=ThemeColors.TEXT_MUTED,
        padding=(20, 9),
        font=(font_family, 10, "bold"),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", ThemeColors.BG_CARD), ("active", ThemeColors.BG_HOVER)],
        foreground=[("selected", ThemeColors.PRIMARY), ("active", ThemeColors.TEXT_MAIN)],
    )

    # Progressbar
    style.configure(
        "Horizontal.TProgressbar",
        background=ThemeColors.PRIMARY,
        troughcolor="#e2e8f0",
        borderwidth=0,
        thickness=6,
    )

    # Treeview (Data tables)
    style.configure(
        "Treeview",
        background=ThemeColors.BG_CARD,
        foreground=ThemeColors.TEXT_MAIN,
        fieldbackground=ThemeColors.BG_CARD,
        font=default_font,
        rowheight=28,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", ThemeColors.PRIMARY)],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background="#f1f5f9",
        foreground=ThemeColors.TEXT_MAIN,
        font=bold_font,
        padding=7,
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", "#e2e8f0")],
    )

    # Scrollbars
    style.configure(
        "Vertical.TScrollbar",
        background="#d1d5db",
        troughcolor=ThemeColors.BG_DARK,
        arrowcolor=ThemeColors.TEXT_MUTED,
        borderwidth=0,
    )
    style.configure(
        "Horizontal.TScrollbar",
        background="#d1d5db",
        troughcolor=ThemeColors.BG_DARK,
        arrowcolor=ThemeColors.TEXT_MUTED,
        borderwidth=0,
    )
