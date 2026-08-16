"""CS2 面板（数据源 HLTV）。"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from ..utils import countdown_days, fmt_countdown, fmt_date
from . import theme
from .base_panel import SeriesPanel
from .widgets import SectionHeader, add_badge_column, fill_tree, make_tree, set_odd_even, status_tag
from .badges import get_badge
from .team_logos import collect_event_logos, collect_team_logos, logo_manager
import threading


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
    ex = match.get("extra", {}) or {}
    score = ex.get("score_text", "")
    winner = ex.get("winner", "")
    if score and winner:
        return f"{score}  {winner} 胜"
    return score or ""


def _match_display(match: dict) -> str:
    """对阵列文案：两队都未定（TBD）时显示「待定 · 阶段」，避免 TBD vs TBD。"""
    t1 = (match.get("team1") or {}).get("name", "")
    t2 = (match.get("team2") or {}).get("name", "")
    both_tbd = (not t1 or t1 == "TBD") and (not t2 or t2 == "TBD")
    if not both_tbd:
        return f"{t1 or '?'} vs {t2 or '?'}"
    label = (match.get("extra") or {}).get("label", "")
    ev = match.get("event", "")
    if label:
        rest = label
        if ev and label.startswith(ev):
            rest = label[len(ev):].lstrip(" -\u2013\u2014:.")
        rest = rest.strip() or "待定"
        return f"待定 · {rest}"
    return "待定"


_STATUS_CN = {"upcoming": "未开始", "ongoing": "进行中", "finished": "已结束"}


def _status_cn(status: str) -> str:
    return _STATUS_CN.get(status, status)


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
        ], widths={"start": 100, "end": 100, "status": 80, "name": 280, "venue": 180,
                   "prize": 120, "countdown": 90})
        self.cal_tree_frame.grid(row=1, column=0, sticky="nsew")
        add_badge_column(self.cal_tree)

    def _build_results_page(self):
        p = self.res_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "对阵表与赛果", subtitle="点击比赛查看各局详情", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        self.match_tree, self.match_tree_frame = make_tree(p, [
            ("date", "日期"), ("status", "状态"), ("event", "赛事"), ("match", "对阵"),
            ("score", "比分"),
        ], widths={"date": 120, "status": 100, "event": 460, "match": 330, "score": 230},
            stretch=("event",))
        self.match_tree_frame.grid(row=1, column=0, sticky="nsew")
        add_badge_column(self.match_tree)
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
        lines = [f"{_match_display(match)}   ·   {ev}   ·   {_score_text(match) or '未开始'}"]
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
                self.match_tree.item(iid, values=(
                    fmt_date(m.get("date")), _status_cn(m.get("status", "")), m.get("event", ""),
                    _match_display(m), _score_text(m)))
                break
        # 重新显示详情
        self._on_match_select()

    def _open_selected_match(self):
        m = getattr(self, "_selected_match", None)
        url = (m or {}).get("url", "")
        if url:
            webbrowser.open(url)

    def _on_logos_ready(self):
        """队标/赛事图标下载完成后刷新当前列表。"""
        try:
            self._render_calendar()
            self._render_matches()
            self._render_ranking()
        except Exception:
            pass

    _ICON_SIZE = 40

    def _match_image(self, m):
        t1 = m.get("team1") or {}
        name = t1.get("name", "")
        img = logo_manager.get(name, t1.get("logo", ""), size=self._ICON_SIZE)
        return img or get_badge(name, size=self._ICON_SIZE)

    def _rank_image(self, r):
        name = r.get("name", "")
        url = (r.get("extra") or {}).get("logo", "")
        img = logo_manager.get(name, url, size=self._ICON_SIZE)
        return img or get_badge(name, size=self._ICON_SIZE)

    def _event_image(self, e):
        name = e.get("name", "")
        url = (e.get("extra") or {}).get("logo", "")
        img = logo_manager.get(name, url, size=self._ICON_SIZE, kind="event")
        return img or get_badge(name, size=self._ICON_SIZE)

    def download_all_logos(self, notify: bool = False):
        """批量下载所有缺失 CS2 队标（后台线程 + 进度），供帮助菜单调用。"""
        if getattr(self, "_dl_all", False):
            return
        self._dl_all = True
        self._dl_notify = notify
        try:
            self.logo_progress.config(text="正在下载缺失队标…")
        except Exception:
            pass
        teams = collect_team_logos(self.store)
        events = collect_event_logos(self.store)

        def worker():
            def progress(name, ok, done, total, label):
                try:
                    self.after(0, lambda: self.logo_progress.config(
                        text=f"{label} {done}/{total}" + (" ✓" if done >= total else "")))
                except Exception:
                    pass
            logo_manager.reset_retry()
            logo_manager.download_all_sync(teams, progress=lambda n, ok, d, t: progress(n, ok, d, t, "队标"),
                                           kind="team")
            logo_manager.download_all_sync(events, progress=lambda n, ok, d, t: progress(n, ok, d, t, "赛事图标"),
                                           kind="event")
            self.after(0, self._finish_logo_download)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_logo_download(self):
        self._dl_all = False
        try:
            self.logo_progress.config(text="队标下载完成 ✓")
        except Exception:
            pass
        notify = getattr(self, "_dl_notify", False)
        self._dl_notify = False
        if notify:
            try:
                from tkinter import messagebox
                messagebox.showinfo("下载完成", "CS2 全部队标与赛事图标已下载完成 ✓")
            except Exception:
                pass
        self._render_calendar()
        self._render_matches()
        self._render_ranking()

    def _build_standings_page(self):
        p = self.sta_page
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        SectionHeader(p, "CS2 队伍积分排名", subtitle="HLTV 世界排名 / V社 VRS 积分", accent=self.accent).grid(
            row=0, column=0, sticky="ew")
        bar = ttk.Frame(p, style="TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=(4, 2))
        bar.columnconfigure(3, weight=1)
        ttk.Label(bar, text="榜单:", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.rank_choice = ttk.Combobox(bar, state="readonly", width=22,
                                        values=["HLTV 世界排名", "V社 VRS 积分排行"])
        self.rank_choice.current(0)
        self.rank_choice.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.rank_choice.bind("<<ComboboxSelected>>", lambda _e: self._render_ranking())
        self.logo_progress = tk.Label(bar, text="", bg=theme.BG, fg=theme.MUTED,
                                      font=(theme.FONT_FAMILY, 9))
        self.logo_progress.grid(row=0, column=3, sticky="e", padx=8)
        self.rank_tree, self.rank_tree_frame = make_tree(p, [
            ("pos", "排名"), ("name", "队伍"), ("points", "积分"), ("change", "变化"),
        ], widths={"pos": 60, "name": 300, "points": 90, "change": 80})
        self.rank_tree_frame.grid(row=2, column=0, sticky="nsew")
        add_badge_column(self.rank_tree)

    def _rank_columns_for(self, mode: str):
        """返回 (columns, widths, value_fn)。mode: ranking / vrs。

        排名与队伍名统一右移 2 个字符（加 2 个空格前缀，仅影响显示）。
        """
        if mode == "vrs":
            cols = [("pos", "排名"), ("name", "队伍"), ("points", "积分"), ("region", "地区")]
            widths = {"pos": 60, "name": 300, "points": 90, "region": 90}
            def val(r):
                return ("  " + r.get("pos", "")), ("  " + r.get("name", "")), r.get("points", ""), r.get("region", "")
        else:
            cols = [("pos", "排名"), ("name", "队伍"), ("points", "积分"), ("change", "变化")]
            widths = {"pos": 60, "name": 300, "points": 90, "change": 80}
            def val(r):
                return ("  " + r.get("pos", "")), ("  " + r.get("name", "")), r.get("points", ""), r.get("change", "")
        return cols, widths, val

    def _set_rank_columns(self, cols, widths):
        keys = [k for k, _ in cols]
        self.rank_tree.configure(columns=keys, show="tree headings")
        for key, title in cols:
            self.rank_tree.heading(key, text=title)
            self.rank_tree.column(key, width=widths.get(key, 100), minwidth=40, anchor="w",
                                  stretch=(key == "name"))
        self.rank_tree.heading("#0", text="队标")
        self.rank_tree.column("#0", width=44, minwidth=40, anchor="center", stretch=False)

    def _current_rank_mode(self) -> str:
        try:
            return "vrs" if self.rank_choice.get() == "V社 VRS 积分排行" else "ranking"
        except Exception:
            return "ranking"

    def _on_kind_updated(self, kind):
        if kind == "calendar":
            self._render_calendar()
        elif kind == "matches":
            self._render_matches()
        elif kind in ("ranking", "vrs"):
            self._render_ranking()

    def _render_calendar(self):
        cal = self.store.get("CS2", "calendar") or []
        fill_tree(self.cal_tree, cal,
                  lambda e: (str(id(e)), (
                      fmt_date(e.get("start")), fmt_date(e.get("end")), e.get("status", ""),
                      e.get("name", ""), e.get("venue", ""),
                      (e.get("extra") or {}).get("prize_pool", ""),
                      fmt_countdown(countdown_days(e.get("start"))))),
                  tags=lambda e: status_tag(e.get("status")),
                  image_fn=self._event_image)
        set_odd_even(self.cal_tree)

    def _render_matches(self):
        payload = self.store.get("CS2", "matches") or {"rows": []}
        rows = payload.get("rows", [])
        self._match_by_iid = {}
        def fn(m):
            iid = str(id(m))
            self._match_by_iid[iid] = m
            return iid, (fmt_date(m.get("date")), _status_cn(m.get("status", "")), m.get("event", ""),
                         _match_display(m), _score_text(m))
        fill_tree(self.match_tree, rows, fn,
                  tags=lambda m: status_tag(m.get("status")),
                  image_fn=self._match_image)
        set_odd_even(self.match_tree)

    def _render_ranking(self):
        mode = self._current_rank_mode()
        payload = self.store.get("CS2", mode) or {"rows": []}
        rows = payload.get("rows", [])
        cols, widths, val = self._rank_columns_for(mode)
        self._set_rank_columns(cols, widths)
        fill_tree(self.rank_tree, rows,
                  lambda r: (str(id(r)), val(r)),
                  tags=lambda r: ("leader",) if str(r.get("pos")) == "1" else (),
                  image_fn=self._rank_image)
        set_odd_even(self.rank_tree)

    def _apply_initial(self):
        logo_manager.set_ui_callback(lambda: self.after(0, self._on_logos_ready))
        self._render_calendar()
        self._render_matches()
        self._render_ranking()
        self._apply_meta()
