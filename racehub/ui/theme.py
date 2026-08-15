"""深色主题与 ttk 样式。"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# 调色板
BG = "#0e141b"
PANEL = "#151d27"
PANEL2 = "#1b2531"
BORDER = "#283442"
INPUT = "#1f2937"
TEXT = "#e8eef5"
MUTED = "#93a6bb"
ACCENT = "#4c8bf5"
OK = "#3fb950"
WARN = "#d29922"
ERR = "#f85149"

SERIES_ACCENT = {"F1": "#e10600", "WEC": "#f5b301", "CS2": "#3b82f6"}
STATUS_COLOR = {"upcoming": "#4c8bf5", "ongoing": "#f5b301", "completed": "#57606a"}

FONT_FAMILY = "Microsoft YaHei UI"


def setup(root: tk.Tk) -> None:
    """初始化全局 ttk 样式。"""
    try:
        fam = tkfont.families(root)
        if "Microsoft YaHei UI" not in fam and "Microsoft YaHei" in fam:
            globals()["FONT_FAMILY"] = "Microsoft YaHei"
    except Exception:
        pass
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(".", background=BG, foreground=TEXT, font=(FONT_FAMILY, 10))
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Panel2.TFrame", background=PANEL2)
    style.configure("TLabel", background=BG, foreground=TEXT, font=(FONT_FAMILY, 10))
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Panel.Muted.TLabel", background=PANEL, foreground=MUTED)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=(FONT_FAMILY, 16, "bold"))
    style.configure("Section.TLabel", background=PANEL, foreground="#c9d7e8", font=(FONT_FAMILY, 11, "bold"))

    style.configure("TButton", background=INPUT, foreground=TEXT, bordercolor=BORDER,
                    focusthickness=0, padding=(10, 4))
    style.map("TButton", background=[("active", "#26303d"), ("pressed", "#1b2531")])
    style.configure("Accent.TButton", background=SERIES_ACCENT["F1"], foreground="#ffffff")
    style.configure("Small.TButton", padding=(6, 2), font=(FONT_FAMILY, 9))

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL2, foreground=MUTED, padding=(16, 7),
                    font=(FONT_FAMILY, 10))
    style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])
    style.configure("Sub.TNotebook", background=BG, borderwidth=0)
    style.configure("Sub.TNotebook.Tab", background=BG, foreground=MUTED, padding=(12, 5),
                    font=(FONT_FAMILY, 9))
    style.map("Sub.TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])

    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    bordercolor=BORDER, rowheight=26, font=(FONT_FAMILY, 9))
    style.configure("Treeview.Heading", background=PANEL2, foreground="#c9d7e8",
                    bordercolor=BORDER, font=(FONT_FAMILY, 9, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", "#26435f")], foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading", background=[("active", "#223042")])

    style.configure("TCombobox", fieldbackground=INPUT, background=INPUT, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=BORDER, padding=3)
    style.map("TCombobox", fieldbackground=[("readonly", INPUT)])
    style.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG, bordercolor=BG, arrowcolor=TEXT)
    style.configure("Horizontal.TScrollbar", background=PANEL2, troughcolor=BG, bordercolor=BG, arrowcolor=TEXT)

    style.configure("Status.TLabel", background=BG, foreground=MUTED, font=(FONT_FAMILY, 9))
    style.configure("Badge.TLabel", background=PANEL2, foreground="#ffd75e", font=(FONT_FAMILY, 9, "bold"),
                    padding=(6, 2))
    style.configure("OkBadge.TLabel", background="#12301c", foreground=OK, font=(FONT_FAMILY, 9, "bold"),
                    padding=(6, 2))
    style.configure("ErrBadge.TLabel", background="#35171a", foreground=ERR, font=(FONT_FAMILY, 9, "bold"),
                    padding=(6, 2))
    style.configure("Countdown.TLabel", background=PANEL, foreground=ACCENT, font=(FONT_FAMILY, 10, "bold"))
    style.configure("Card.TFrame", background=PANEL2, relief="flat")
