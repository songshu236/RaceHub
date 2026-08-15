"""CS2 面板（数据源 HLTV）。"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from ..utils import countdown_days, fmt_countdown, fmt_date
from . import theme
from .base_panel import SeriesPanel
from .widgets import SectionHeader, KeyValueRow, add_badge_column, fill_tree, make_tree, set_odd_even, status_tag
from .badges import get_badge


def _map_summary(match: dict) -> str:
    ms = match.get("map_scores") or []
    if not ms:
        return ""
    parts = []
    for m in ms:
        if "t1" in m and "t2" in m:
            parts.append(f"{m.get('map') or '?'} {m['t1']}:{m['t2']}")
        elif m.get("text"):
            parts.append(m["text"])
    return "  ".join(parts)


def _score_text(match: dict) -> str:
    if match.get("status") != "finished":
        return "—"
    return match.get("extra", {}).get("score_text") or ""


class CS2Panel(SeriesPanel):
    series = "CS2"
    title = "CS2 反恐精英 2"
    accent = theme.SERIES_ACCENT["CS2"]
    source = "HLTV (hltv.org)"

    def _build_calendar_page(self):
        p = self.cal_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        SectionHeader(p, "赛事日历", subtitle="大型线下赛 / 联赛 / Major", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.cal_tree, self.cal_tree_frame = make_tree(p, [
            ("start", "开始"), ("end", "结束"), ("status", "状态"), ("name", "赛事"),
            ("venue", "地点"), ("prize", "奖金"), ("countdown", "倒计时"),
        ], widths={"start": 90, "end": 90, "status": 70, "name": 230, "venue": 150,
                   "prize": 110, "countdown": 80})
        self.cal_tree_frame.grid(row=1, column=0, sticky="nsew")

    def _build_results_page(self):
        p = self.res_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "对阵表与赛果", subtitle="包含各局比分；点击比赛查看详情", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.match_tree, self.match_tree_frame = make_tree(p, [
            ("date", "日期"), ("status", "状态"), ("event", "赛事"), ("match", "对阵"),
            ("score", "比分"), ("maps", "各局比分"),
        ], widths={"date": 90, "status": 65, "event": 210, "match": 210, "score": 60, "maps": 300},
            stretch=("maps",))
        self.match_tree_frame.grid(row=1, column=0, sticky="nsew")
        self.match_tree.bind("<<TreeviewSelect>>", self._on_match_select)

        detail = ttk.Frame(p, style="Panel.TFrame")
        detail.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        detail.columnconfigure(1, weight=1)
        tk.Label(detail, text="各局详情:", bg=theme.PANEL, fg=theme.MUTED,
                 font=(theme.FONT_FAMILY, 9)).grid(row=0, column=0, sticky="nw", padx=6, pady=4)
        self.match_detail = tk.Text(detail, height=4, wrap="none", bg=theme.PANEL, fg=theme.TEXT,
                                    font=(theme.FONT_FAMILY, 9), relief="flat", padx=6, pady=4)
        self.match_detail.grid(row=0, column=1, sticky="nsew")
        self.match_detail.config(state="disabled")
        self.open_btn = ttk.Button(detail, text="🌐 打开 HLTV 比赛页", style="Small.TButton",
                                   command=self._open_selected_match)
        self.open_btn.grid(row=1, column=1, sticky="e", padx=6, pady=4)

    def _on_match_select(self, _evt=None):
        sel = self.match_tree.selection()
        if not sel:
            return
        iid = sel[0]
        match = self._match_by_iid.get(iid)
        if not match:
            return
        t1 = (match.get("team1") or {}).get("name", "?")
        t2 = (match.get("team2") or {}).get("name", "?")
        ev = match.get("event", "")
        lines = [f"{t1}  vs  {t2}   ·   {ev}   ·   {_score_text(match) or '未开始'}"]
        ms = match.get("map_scores") or []
        if ms:
            for m in ms:
                if "t1" in m and "t2" in m:
                    lines.append(f"  {m.get('map') or '地图'}:  {t1} {m['t1']}  :  {m['t2']} {t2}")
                elif m.get("text"):
                    lines.append(f"  {m['text']}")
        else:
            lines.append("  （暂无各局比分）")
        self.match_detail.config(state="normal")
        self.match_detail.delete("1.0", "end")
        self.match_detail.insert("1.0", "\n".join(lines))
        self.match_detail.config(state="disabled")
        self._selected_match = match
        # 已结束但尚未抓取各局比分 -> 按需后台抓取
        mid = (match.get("extra") or {}).get("match_id", "")
        if match.get("status") == "finished" and not (match.get("map_scores") or []) and mid:
            self.match_detail.config(state="normal")
            self.match_detail.insert("end", "\n⏳ 正在从 HLTV 抓取各局比分…")
            self.match_detail.config(state="disabled")
            self.store.refresh_match_detail(mid, callback=lambda d: self.after(0, lambda: self._apply_match_detail(match, d)))

    def _apply_match_detail(self, match, detail):
        """把按需抓取的各局比分应用到详情与列表。"""
        if not match or not detail:
            return
        if detail.get("error"):
            self.match_detail.config(state="normal")
            self.match_detail.insert("end", "\n⚠ 抓取失败：" + detail["error"][:100])
            self.match_detail.config(state="disabled")
            return
        match["map_scores"] = detail.get("map_scores") or []
        if detail.get("team1"):
            match["team1"] = {"name": detail["team1"]}
        if detail.get("team2"):
            match["team2"] = {"name": detail["team2"]}
        if detail.get("event"):
            match["event"] = detail["event"]
        # 刷新列表该行
        for iid, m in (getattr(self, "_match_by_iid", {}) or {}).items():
            if m is match:
                t1 = (m.get("team1") or {}).get("name", "?")
                t2 = (m.get("team2") or {}).get("name", "?")
                self.match_tree.item(iid, values=(
                    fmt_date(m.get("date")), m.get("status", ""), m.get("event", ""),
                    f"{t1} vs {t2}", _score_text(m), _map_summary(m)))
                break
        # 重新显示详情
        self._on_match_select()

    def _open_selected_match(self):
        m = getattr(self, "_selected_match", None)
        url = (m or {}).get("url", "")
        if url:
            webbrowser.open(url)

    def _build_standings_page(self):
        p = self.sta_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "HLTV 世界排名", subtitle="队伍积分排名（示例/实抓）", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.sta_info = KeyValueRow(p, "说明", "排名基于 HLTV 世界排名页", key_width=10)
        self.sta_info.grid(row=1, column=0, sticky="ew")
        self.rank_tree, self.rank_tree_frame = make_tree(p, [
            ("pos", "排名"), ("name", "队伍"), ("points", "积分"), ("change", "变化"),
        ], widths={"pos": 55, "name": 240, "points": 80, "change": 70})
        self.rank_tree_frame.grid(row=2, column=0, sticky="nsew")

    def _on_kind_updated(self, kind):
        if kind == "calendar":
            self._render_calendar()
        elif kind == "matches":
            self._render_matches()
        elif kind == "ranking":
            self._render_ranking()

    def _render_calendar(self):
        cal = self.store.get("CS2", "calendar") or []
        fill_tree(self.cal_tree, cal,
                  lambda e: (str(id(e)), (
                      fmt_date(e.get("start")), fmt_date(e.get("end")), e.get("status", ""),
                      e.get("name", ""), e.get("venue", ""),
                      (e.get("extra") or {}).get("prize_pool", ""),
                      fmt_countdown(countdown_days(e.get("start"))))),
                  tags=lambda e: status_tag(e.get("status")))
        set_odd_even(self.cal_tree)

    def _render_matches(self):
        payload = self.store.get("CS2", "matches") or {"rows": []}
        rows = payload.get("rows", [])
        self._match_by_iid = {}
        def fn(m):
            iid = str(id(m))
            self._match_by_iid[iid] = m
            t1 = (m.get("team1") or {}).get("name", "?")
            t2 = (m.get("team2") or {}).get("name", "?")
            return iid, (fmt_date(m.get("date")), m.get("status", ""), m.get("event", ""),
                         f"{t1} vs {t2}", _score_text(m), _map_summary(m))
        fill_tree(self.match_tree, rows, fn,
                  tags=lambda m: status_tag(m.get("status")),
                  image_fn=lambda m: get_badge((m.get("team1") or {}).get("name", "")))
        set_odd_even(self.match_tree)

    def _render_ranking(self):
        payload = self.store.get("CS2", "ranking") or {"rows": []}
        fill_tree(self.rank_tree, payload.get("rows", []),
                  lambda r: (str(id(r)), (r.get("pos", ""), r.get("name", ""),
                                           r.get("points", ""), r.get("change", ""))),
                  tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                  image_fn=lambda r: get_badge(r.get("name", "")))
        set_odd_even(self.rank_tree)

    def _apply_initial(self):
        self._render_calendar()
        self._render_matches()
        self._render_ranking()
        self._apply_meta()
