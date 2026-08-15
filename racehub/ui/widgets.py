"""共享 UI 组件。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme


def make_tree(parent, columns, widths=None, stretch=None, height=10, style=None) -> ttk.Treeview:
    """创建带滚动条与表头的 Treeview。"""
    frame = ttk.Frame(parent, style=style or "TFrame")
    tree = ttk.Treeview(frame, columns=[k for k, _ in columns], show="headings", height=height)
    headings = {k: v for k, v in columns}
    for idx, (key, title) in enumerate(columns):
        tree.heading(key, text=title)
        w = (widths or {}).get(key, 100)
        tree.column(key, width=w, minwidth=40, anchor="w",
                    stretch=bool(stretch is None or key in stretch))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    apply_tree_tags(tree)
    return tree, frame


def fill_tree(tree: ttk.Treeview, rows: list, fn, tags=None):
    """清空并填充 tree。fn(row) -> (iid, values)。tags(row) 可选。"""
    tree.delete(*tree.get_children())
    for row in rows:
        iid, values = fn(row)
        tag = tags(row) if tags else ()
        if isinstance(tag, str):
            tag = (tag,)
        tree.insert("", "end", iid=iid, values=values, tags=tag)


def status_tag(status: str) -> str:
    return {"upcoming": "st_upcoming", "ongoing": "st_ongoing", "completed": "st_done"}.get(status, "")


def apply_tree_tags(tree: ttk.Treeview):
    tree.tag_configure("st_upcoming", foreground=theme.SERIES_ACCENT["CS2"])
    tree.tag_configure("st_ongoing", foreground=theme.WARN)
    tree.tag_configure("st_done", foreground=theme.MUTED)
    tree.tag_configure("row_odd", background=theme.PANEL)
    tree.tag_configure("row_even", background=theme.PANEL2)
    tree.tag_configure("leader", foreground=theme.OK, font=(theme.FONT_FAMILY, 9, "bold"))


def set_odd_even(tree: ttk.Treeview):
    for i, iid in enumerate(tree.get_children()):
        tags = tree.item(iid, "tags")
        base = [t for t in tags if not t.startswith("row_")]
        base.append("row_odd" if i % 2 == 0 else "row_even")
        tree.item(iid, tags=tuple(base))


class SectionHeader(ttk.Frame):
    def __init__(self, master, text, subtitle="", accent="#4c8bf5", **kw):
        super().__init__(master, style="Panel.TFrame", **kw)
        self.columnconfigure(1, weight=1)
        bar = tk.Frame(self, bg=accent, width=4, height=22)
        bar.grid(row=0, column=0, padx=(0, 8), pady=6, sticky="ns")
        tk.Label(self, text=text, bg=theme.PANEL, fg=theme.TEXT,
                 font=(theme.FONT_FAMILY, 12, "bold")).grid(row=0, column=1, sticky="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=theme.PANEL, fg=theme.MUTED,
                     font=(theme.FONT_FAMILY, 9)).grid(row=0, column=2, sticky="e")


class StatusBadge(ttk.Label):
    def __init__(self, master, text="", kind="demo", **kw):
        style = {"demo": "Badge.TLabel", "ok": "OkBadge.TLabel", "err": "ErrBadge.TLabel"}.get(kind, "Badge.TLabel")
        super().__init__(master, text=text, style=style, **kw)


class KeyValueRow(ttk.Frame):
    """键值对信息行。"""

    def __init__(self, master, key, value, key_width=14, **kw):
        super().__init__(master, style="Panel.TFrame", **kw)
        self.columnconfigure(1, weight=1)
        tk.Label(self, text=key, bg=theme.PANEL, fg=theme.MUTED,
                 font=(theme.FONT_FAMILY, 9), width=key_width, anchor="w").grid(row=0, column=0, sticky="w")
        self.value_lbl = tk.Label(self, text=value, bg=theme.PANEL, fg=theme.TEXT,
                                  font=(theme.FONT_FAMILY, 10), anchor="w", justify="left")
        self.value_lbl.grid(row=0, column=1, sticky="we")

    def set(self, value):
        self.value_lbl.config(text=value)
