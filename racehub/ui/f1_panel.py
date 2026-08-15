"""F1 面板。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..utils import countdown_days, fmt_countdown, fmt_date
from . import theme
from .base_panel import SeriesPanel
from .widgets import SectionHeader, KeyValueRow, add_badge_column, fill_tree, make_tree, set_odd_even, status_tag
from .badges import get_badge


class F1Panel(SeriesPanel):
    series = "F1"
    title = "F1 一级方程式"
    accent = theme.SERIES_ACCENT["F1"]
    source = "Ergast API (api.jolpi.ca)"

    # ---------------- 赛程 ----------------
    def _build_calendar_page(self):
        p = self.cal_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        SectionHeader(p, "2026 赛季赛程", subtitle="点击某站查看该站比赛结果", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.cal_tree, self.cal_tree_frame = make_tree(p, [
            ("round", "轮次"), ("date", "日期"), ("status", "状态"),
            ("name", "大奖赛"), ("venue", "赛道"), ("countdown", "倒计时"),
        ], widths={"round": 55, "date": 100, "status": 80, "name": 220, "venue": 230, "countdown": 90})
        self.cal_tree_frame.grid(row=1, column=0, sticky="nsew")
        self.cal_tree.bind("<<TreeviewSelect>>", self._on_cal_select)

    def _on_cal_select(self, _evt=None):
        sel = self.cal_tree.selection()
        if not sel:
            return
        item = self.cal_tree.item(sel[0], "values")
        if not item:
            return
        # 跳到赛果页并选中对应分站
        rnd = item[0]
        self.notebook.select(self.res_page)
        combo = getattr(self, "round_combo", None)
        if combo is not None:
            values = list(combo["values"])
            if rnd in values:
                combo.set(rnd)
                self._render_results_for_round(rnd)

    # ---------------- 赛果 ----------------
    def _build_results_page(self):
        p = self.res_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "分站比赛结果", accent=self.accent).grid(row=0, column=0, sticky="ew")
        bar = ttk.Frame(p, style="TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=6)
        tk.Label(bar, text="选择分站:", bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=(0, 6))
        self.round_combo = ttk.Combobox(bar, state="readonly", width=34)
        self.round_combo.pack(side="left")
        self.round_combo.bind("<<ComboboxSelected>>", lambda e: self._render_results_for_round(self.round_combo.get()))
        self.res_info = KeyValueRow(p, "比赛", "", key_width=10)
        self.res_info.grid(row=3, column=0, sticky="ew")
        self.res_tree, self.res_tree_frame = make_tree(p, [
            ("pos", "名次"), ("driver", "车手"), ("team", "车队"), ("laps", "圈数"),
            ("time", "用时"), ("points", "积分"), ("fl", "最快圈"),
        ], widths={"pos": 50, "driver": 210, "team": 170, "laps": 55, "time": 125, "points": 60, "fl": 100})
        self.res_tree_frame.grid(row=2, column=0, sticky="nsew")
        add_badge_column(self.res_tree)

    def _render_results_for_round(self, rnd):
        payload = self.store.get("F1", "results") or {"rows": []}
        for race in payload.get("rows", []):
            if str(race.get("round")) == str(rnd):
                self.res_info.set(f"{race.get('event_name','')}  ·  {fmt_date(race.get('date'))}")
                fill_tree(self.res_tree, race.get("rows", []),
                          lambda r: (str(id(r)), (
                              r.get("pos", ""), r.get("driver", ""), r.get("team", ""),
                              r.get("laps", ""), r.get("time", ""), r.get("points", ""),
                              r.get("fastest_lap", ""))),
                          tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                          image_fn=lambda r: get_badge(r.get("team", "")))
                set_odd_even(self.res_tree)
                return
        self.res_info.set("该分站暂无比赛结果")
        fill_tree(self.res_tree, [], lambda r: (str(id(r)), ()))

    # ---------------- 积分 ----------------
    def _build_standings_page(self):
        p = self.sta_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "赛季积分榜", accent=self.accent).grid(row=0, column=0, sticky="ew")
        bar = ttk.Frame(p, style="TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=6)
        tk.Label(bar, text="榜单:", bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=(0, 6))
        self.stand_combo = ttk.Combobox(bar, state="readonly", width=28)
        self.stand_combo.pack(side="left")
        self.stand_combo.bind("<<ComboboxSelected>>", lambda e: self._render_standings(self.stand_combo.get()))
        self.sta_info = KeyValueRow(p, "赛季", "", key_width=10)
        self.sta_info.grid(row=3, column=0, sticky="ew")
        self.stand_tree, self.stand_tree_frame = make_tree(p, [
            ("pos", "名次"), ("name", "车手 / 车队"), ("team", "车队"),
            ("points", "积分"), ("wins", "胜场"),
        ], widths={"pos": 55, "name": 250, "team": 180, "points": 80, "wins": 60})
        self.stand_tree_frame.grid(row=2, column=0, sticky="nsew")
        add_badge_column(self.stand_tree)

    def _render_standings(self, title):
        payload = self.store.get("F1", "standings") or {"tables": []}
        for t in payload.get("tables", []):
            if t.get("title") == title:
                self.sta_info.set(f"{t.get('season','')} 赛季 · 第 {t.get('round','')} 轮后")
                if t.get("kind") == "constructor":
                    fill_tree(self.stand_tree, t.get("rows", []),
                              lambda r: (str(id(r)), (r.get("pos", ""), r.get("name", ""), "",
                                                       r.get("points", ""), r.get("wins", ""))),
                              tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                              image_fn=lambda r: get_badge(r.get("name", "")))
                else:
                    fill_tree(self.stand_tree, t.get("rows", []),
                              lambda r: (str(id(r)), (r.get("pos", ""), r.get("name", ""),
                                                       r.get("team", ""), r.get("points", ""), r.get("wins", ""))),
                              tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                              image_fn=lambda r: get_badge(r.get("team", "")))
                set_odd_even(self.stand_tree)
                return

    # ---------------- 数据更新 ----------------
    def _on_kind_updated(self, kind):
        if kind == "calendar":
            self._render_calendar()
        elif kind == "results":
            self._refresh_round_combo()
            if self.round_combo.get():
                self._render_results_for_round(self.round_combo.get())
        elif kind == "standings":
            self._refresh_stand_combo()
            if self.stand_combo.get():
                self._render_standings(self.stand_combo.get())

    def _render_calendar(self):
        cal = self.store.get("F1", "calendar") or []
        fill_tree(self.cal_tree, cal,
                  lambda e: (str(id(e)), (
                      e.get("round", ""), fmt_date(e.get("start")), e.get("status", ""),
                      e.get("name", ""), e.get("venue", ""),
                      fmt_countdown(countdown_days(e.get("start"))))),
                  tags=lambda e: status_tag(e.get("status")))
        set_odd_even(self.cal_tree)

    def _refresh_round_combo(self):
        payload = self.store.get("F1", "results") or {"rows": []}
        rounds = [str(r.get("round")) for r in payload.get("rows", [])]
        self.round_combo["values"] = rounds
        if rounds and not self.round_combo.get():
            self.round_combo.set(rounds[-1])
            self._render_results_for_round(rounds[-1])

    def _refresh_stand_combo(self):
        payload = self.store.get("F1", "standings") or {"tables": []}
        titles = [t.get("title") for t in payload.get("tables", [])]
        self.stand_combo["values"] = titles
        if titles and not self.stand_combo.get():
            self.stand_combo.set(titles[0])
            self._render_standings(titles[0])

    def _apply_initial(self):
        self._render_calendar()
        self._refresh_round_combo()
        self._refresh_stand_combo()
        self._apply_meta()
