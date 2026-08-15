"""系列面板基类：统一的头部 + 三个子页（赛程/赛果/积分）。"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from . import theme
from .widgets import SectionHeader, StatusBadge, apply_tree_tags


class SeriesPanel(ttk.Frame):
    series = ""
    title = ""
    accent = "#4c8bf5"
    source = ""

    def __init__(self, master, store, **kw):
        super().__init__(master, style="TFrame", **kw)
        self.store = store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_header()
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.cal_page = ttk.Frame(self.notebook, style="TFrame")
        self.res_page = ttk.Frame(self.notebook, style="TFrame")
        self.sta_page = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.cal_page, text="  赛程  ")
        self.notebook.add(self.res_page, text="  赛果  ")
        self.notebook.add(self.sta_page, text="  积分  ")
        try:
            self._build_pages()
        except Exception:
            import logging
            import traceback
            logging.exception("面板 %s 构建失败", self.series)
            traceback.print_exc()
        try:
            self._apply_initial()
        except Exception:
            import logging
            import traceback
            logging.exception("面板 %s 首次渲染失败", self.series)
            traceback.print_exc()

    # ------------------------------------------------------------------
    def _build_header(self):
        bar = ttk.Frame(self, style="TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        bar.columnconfigure(3, weight=1)
        dot = tk.Frame(bar, bg=self.accent, width=10, height=10)
        dot.grid(row=0, column=0, padx=(2, 8))
        tk.Label(bar, text=self.title, bg=theme.BG, fg=theme.TEXT,
                 font=(theme.FONT_FAMILY, 15, "bold")).grid(row=0, column=1, sticky="w")
        self.badge = StatusBadge(bar, text="加载中", kind="demo")
        self.badge.grid(row=0, column=2, padx=(10, 4))
        self.src_lbl = tk.Label(bar, text=self.source, bg=theme.BG, fg=theme.MUTED,
                                font=(theme.FONT_FAMILY, 9))
        self.src_lbl.grid(row=0, column=3, sticky="w", padx=(4, 0))
        self.updated_lbl = tk.Label(bar, text="", bg=theme.BG, fg=theme.MUTED,
                                    font=(theme.FONT_FAMILY, 9))
        self.updated_lbl.grid(row=0, column=4, sticky="e", padx=8)
        self.refresh_btn = ttk.Button(bar, text="🔄 刷新", style="Small.TButton", command=self.refresh)
        self.refresh_btn.grid(row=0, column=5, padx=(4, 0))
        self._apply_meta("calendar")

    # ------------------------------------------------------------------
    def _build_pages(self):
        self._build_calendar_page()
        self._build_results_page()
        self._build_standings_page()

    def _build_calendar_page(self): raise NotImplementedError
    def _build_results_page(self): raise NotImplementedError
    def _build_standings_page(self): raise NotImplementedError

    def _apply_initial(self):
        """子类可重载：首次渲染数据。"""
        pass

    # ------------------------------------------------------------------
    def _apply_meta(self, kind=None):
        """根据元信息刷新 badge / 来源 / 更新时间。"""
        metas = self.store.all_meta(self.series) if hasattr(self.store, "all_meta") else {}
        metas = metas or {}
        using_demo = any(m.get("using_demo") for m in metas.values())
        errors = [m.get("error") for m in metas.values() if m.get("error")]
        if using_demo:
            self.badge.config(text="示例数据 · 离线", style="Badge.TLabel")
        elif errors:
            self.badge.config(text="部分更新失败", style="ErrBadge.TLabel")
        else:
            self.badge.config(text="实时数据", style="OkBadge.TLabel")
        src = self.source
        if metas:
            first_src = next((m.get("source") for m in metas.values() if m.get("source")), "")
            if first_src:
                src = first_src
        self.src_lbl.config(text=src)
        times = [m.get("fetched_at", 0) for m in metas.values() if m.get("fetched_at")]
        if times:
            ts = datetime.fromtimestamp(max(times)).strftime("%m-%d %H:%M")
            self.updated_lbl.config(text=f"更新于 {ts}")

    def refresh(self):
        if self.refresh_btn is not None:
            self.refresh_btn.config(state="disabled", text="刷新中…")
        self.store.refresh(self.series, callback=self._on_refresh_done)

    def _on_refresh_done(self, series, kind, ok, msg):
        try:
            self.after(0, lambda: self._handle_refresh_done(series, kind, ok, msg))
        except Exception:
            pass

    def _handle_refresh_done(self, series, kind, ok, msg):
        if series != self.series:
            return
        self._apply_meta(kind)
        self._on_kind_updated(kind)
        self.refresh_btn.config(state="normal", text="🔄 刷新")

    def _on_kind_updated(self, kind):
        """子类可重载：某类数据更新后刷新对应视图。"""
        pass
