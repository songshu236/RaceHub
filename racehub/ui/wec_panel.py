"""WEC 面板。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..utils import countdown_days, fmt_countdown, fmt_date
from . import theme
from .base_panel import SeriesPanel
from .widgets import SectionHeader, KeyValueRow, add_badge_column, fill_tree, make_tree, set_odd_even, status_tag
from .badges import get_badge


class WECPanel(SeriesPanel):
    series = "WEC"
    title = "WEC 世界耐力锦标赛"
    accent = theme.SERIES_ACCENT["WEC"]
    source = "FIA WEC 官网 / 官方计时"

    def _build_calendar_page(self):
        p = self.cal_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        SectionHeader(p, "2026 赛季赛程", subtitle="点击某站查看该站最终成绩", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.cal_tree, self.cal_tree_frame = make_tree(p, [
            ("date", "日期"), ("status", "状态"), ("name", "赛事"),
            ("country", "国家"), ("countdown", "倒计时"),
        ], widths={"date": 115, "status": 80, "name": 300, "country": 100, "countdown": 90})
        self.cal_tree_frame.grid(row=1, column=0, sticky="nsew")
        self.cal_tree.bind("<<TreeviewSelect>>", self._on_cal_select)

    def _on_cal_select(self, _evt=None):
        sel = self.cal_tree.selection()
        if not sel:
            return
        item = self.cal_tree.item(sel[0], "values")
        if not item:
            return
        name = item[2]
        self.notebook.select(self.res_page)
        combo = getattr(self, "event_combo", None)
        if combo is not None:
            for ev in combo["values"]:
                if ev and (ev in name or name in ev):
                    combo.set(ev)
                    self._render_results_for_event(ev)
                    return

    def _build_results_page(self):
        p = self.res_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "分站最终成绩（官方计时）", accent=self.accent).grid(row=0, column=0, sticky="ew")
        bar = ttk.Frame(p, style="TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=6)
        tk.Label(bar, text="选择分站:", bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=(0, 6))
        self.event_combo = ttk.Combobox(bar, state="readonly", width=36)
        self.event_combo.pack(side="left")
        self.event_combo.bind("<<ComboboxSelected>>",
                              lambda e: self._render_results_for_event(self.event_combo.get()))
        self.res_info = KeyValueRow(p, "比赛", "", key_width=10)
        self.res_info.grid(row=3, column=0, sticky="ew")
        self.res_tree, self.res_tree_frame = make_tree(p, [
            ("pos", "名次"), ("no", "车号"), ("team", "车队"), ("drivers", "车手"),
            ("car", "赛车"), ("cls", "组别"), ("laps", "圈数"), ("time", "用时"),
            ("gap", "差距"), ("fl", "最快圈"),
        ], widths={"pos": 48, "no": 50, "team": 210, "drivers": 280, "car": 180,
                   "cls": 80, "laps": 50, "time": 115, "gap": 95, "fl": 100})
        self.res_tree_frame.grid(row=2, column=0, sticky="nsew")
        add_badge_column(self.res_tree)

    def _render_results_for_event(self, ev):
        payload = self.store.get("WEC", "results") or {"rows": []}
        for race in payload.get("rows", []):
            if race.get("event_name") == ev or race.get("short_name") == ev:
                self.res_info.set(f"{race.get('event_name','')}  ·  {fmt_date(race.get('date'))}")
                fill_tree(self.res_tree, race.get("rows", []),
                          lambda r: (str(id(r)), (
                              r.get("pos", ""), r.get("no", ""), r.get("team", ""),
                              r.get("drivers", ""), r.get("car", ""), r.get("cls", ""),
                              r.get("laps", ""), r.get("total_time", ""), r.get("gap", ""),
                              r.get("fl_time", ""))),
                          tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                          image_fn=lambda r: get_badge(r.get("team", "")))
                set_odd_even(self.res_tree)
                return
        self.res_info.set("该分站暂无最终成绩")
        fill_tree(self.res_tree, [], lambda r: (str(id(r)), ()))

    def _build_standings_page(self):
        p = self.sta_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "赛季积分榜", accent=self.accent).grid(row=0, column=0, sticky="ew")
        bar = ttk.Frame(p, style="TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=6)
        tk.Label(bar, text="榜单:", bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=(0, 6))
        self.stand_combo = ttk.Combobox(bar, state="readonly", width=40)
        self.stand_combo.pack(side="left")
        self.stand_combo.bind("<<ComboboxSelected>>",
                              lambda e: self._render_standings(self.stand_combo.get()))
        self.sta_info = KeyValueRow(p, "赛季", "", key_width=10)
        self.sta_info.grid(row=3, column=0, sticky="ew")
        self.stand_tree, self.stand_tree_frame = make_tree(p, [
            ("pos", "名次"), ("name", "车队 / 车手"), ("race_pts", "各站积分"), ("points", "总分"),
        ], widths={"pos": 55, "name": 300, "race_pts": 300, "points": 75})
        self.stand_tree_frame.grid(row=2, column=0, sticky="nsew")
        add_badge_column(self.stand_tree)

    def _render_standings(self, title):
        payload = self.store.get("WEC", "standings") or {"tables": []}
        for t in payload.get("tables", []):
            if t.get("title") == title:
                self.sta_info.set(f"{payload.get('season','')} 赛季")
                fill_tree(self.stand_tree, t.get("rows", []),
                          lambda r: (str(id(r)), (
                              r.get("pos", ""), r.get("name", ""),
                              ", ".join(str(x) for x in r.get("race_pts", [])),
                              r.get("points", ""))),
                          tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                          image_fn=lambda r: get_badge(r.get("name", "")))
                set_odd_even(self.stand_tree)
                return

    def _on_kind_updated(self, kind):
        if kind == "calendar":
            self._render_calendar()
        elif kind == "results":
            self._refresh_event_combo()
            if self.event_combo.get():
                self._render_results_for_event(self.event_combo.get())
        elif kind == "standings":
            self._refresh_stand_combo()
            if self.stand_combo.get():
                self._render_standings(self.stand_combo.get())

    def _render_calendar(self):
        cal = self.store.get("WEC", "calendar") or []
        fill_tree(self.cal_tree, cal,
                  lambda e: (str(id(e)), (
                      fmt_date(e.get("start")), e.get("status", ""), e.get("name", ""),
                      f"{e.get('flag','')} {e.get('country','')}".strip(),
                      fmt_countdown(countdown_days(e.get("start"))))),
                  tags=lambda e: status_tag(e.get("status")))
        set_odd_even(self.cal_tree)

    def _refresh_event_combo(self):
        payload = self.store.get("WEC", "results") or {"rows": []}
        names = [r.get("event_name") or r.get("short_name") for r in payload.get("rows", [])]
        self.event_combo["values"] = names
        if names and not self.event_combo.get():
            self.event_combo.set(names[0])
            self._render_results_for_event(names[0])

    def _refresh_stand_combo(self):
        payload = self.store.get("WEC", "standings") or {"tables": []}
        titles = [t.get("title") for t in payload.get("tables", [])]
        self.stand_combo["values"] = titles
        if titles and not self.stand_combo.get():
            self.stand_combo.set(titles[0])
            self._render_standings(titles[0])

    def _apply_initial(self):
        self._render_calendar()
        self._refresh_event_combo()
        self._refresh_stand_combo()
        self._apply_meta()
