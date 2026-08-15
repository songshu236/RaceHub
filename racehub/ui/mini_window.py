"""置顶迷你窗口：显示跨项目最近的关键赛程。"""
from __future__ import annotations

import tkinter as tk

from ..store import SERIES_CN, SERIES_COLOR
from ..utils import countdown_days, fmt_countdown, fmt_date
from . import theme


class MiniWindow(tk.Toplevel):
    def __init__(self, app, **kw):
        super().__init__(app, **kw)
        self.app = app
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", bool(app.config.get("mini_window_topmost", True)))
        self.configure(bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.BORDER)
        self.geometry("+80+80")
        self._drag = None
        self._build()
        self.refresh()
        self.after(1000, self._tick)
        self.after(30000, self._periodic_refresh)

    # ------------------------------------------------------------------
    def _build(self):
        self.columnconfigure(0, weight=1)
        # 标题栏（可拖动）
        title = tk.Frame(self, bg=theme.PANEL2, height=30)
        title.grid(row=0, column=0, sticky="ew")
        title.columnconfigure(1, weight=1)
        tk.Label(title, text="🏁 关键赛程", bg=theme.PANEL2, fg=theme.TEXT,
                 font=(theme.FONT_FAMILY, 10, "bold")).grid(row=0, column=0, padx=8)
        self.pin_btn = tk.Button(title, text="📌 置顶:开", bg=theme.PANEL2, fg=theme.TEXT, relief="flat",
                                 font=(theme.FONT_FAMILY, 9), cursor="hand2", command=self.toggle_pin)
        self.pin_btn.grid(row=0, column=1, sticky="e")
        self.min_btn = tk.Button(title, text="🗕", bg=theme.PANEL2, fg=theme.TEXT, relief="flat",
                                 font=(theme.FONT_FAMILY, 9), cursor="hand2", command=self.hide)
        self.min_btn.grid(row=0, column=2, padx=(0, 2))
        self.close_btn = tk.Button(title, text="✕", bg=theme.PANEL2, fg=theme.TEXT, relief="flat",
                                   font=(theme.FONT_FAMILY, 9), cursor="hand2", command=self.close_mini)
        self.close_btn.grid(row=0, column=3, padx=(0, 6))
        for w in (title, self.pin_btn, self.min_btn, self.close_btn):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._stop_drag)

        # 事件列表
        body = tk.Frame(self, bg=theme.PANEL)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        self.rows_frame = body
        self.placeholder = tk.Label(body, text="暂无即将进行的赛事", bg=theme.PANEL, fg=theme.MUTED,
                                    font=(theme.FONT_FAMILY, 9))
        self.placeholder.grid(row=0, column=0, padx=8, pady=12, sticky="w")

        # 底部按钮
        foot = tk.Frame(self, bg=theme.PANEL2)
        foot.grid(row=2, column=0, sticky="ew")
        foot.columnconfigure(0, weight=1)
        tk.Button(foot, text="🔄 刷新", bg=theme.PANEL2, fg=theme.TEXT, relief="flat",
                  font=(theme.FONT_FAMILY, 9), cursor="hand2", command=self.refresh).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        tk.Button(foot, text="🗔 打开主窗口", bg=theme.PANEL2, fg=theme.TEXT, relief="flat",
                  font=(theme.FONT_FAMILY, 9), cursor="hand2",
                  command=self.open_main).grid(row=0, column=1, sticky="e", padx=8, pady=4)

    # ------------------------------------------------------------------
    def _start_drag(self, evt):
        self._drag = (evt.x_root - self.winfo_x(), evt.y_root - self.winfo_y())

    def _on_drag(self, evt):
        if self._drag:
            x = evt.x_root - self._drag[0]
            y = evt.y_root - self._drag[1]
            self.geometry(f"+{x}+{y}")

    def _stop_drag(self, _evt):
        self._drag = None

    # ------------------------------------------------------------------
    def refresh(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        events = self.app.store.next_events(n=5)
        if not events:
            self.placeholder = tk.Label(self.rows_frame, text="暂无即将进行的赛事", bg=theme.PANEL,
                                        fg=theme.MUTED, font=(theme.FONT_FAMILY, 9))
            self.placeholder.grid(row=0, column=0, padx=8, pady=10, sticky="w")
            return
        for i, ev in enumerate(events):
            self._add_event_row(i, ev)

    def _add_event_row(self, i, ev):
        series = ev.get("series", "")
        color = SERIES_COLOR.get(series, theme.MUTED)
        frame = tk.Frame(self.rows_frame, bg=theme.PANEL)
        frame.grid(row=i, column=0, sticky="ew", padx=8, pady=(4, 0))
        frame.columnconfigure(1, weight=1)
        tk.Frame(frame, bg=color, width=5, height=26).grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 6))
        name = ev.get("name", "")
        date = fmt_date(ev.get("start"), with_weekday=True)
        cd = fmt_countdown(countdown_days(ev.get("start")))
        tk.Label(frame, text=f"{SERIES_CN.get(series, series)} · {name}", bg=theme.PANEL,
                 fg=theme.TEXT, font=(theme.FONT_FAMILY, 9, "bold"), anchor="w").grid(
            row=0, column=1, sticky="we")
        tk.Label(frame, text=f"{date}  ({cd})", bg=theme.PANEL, fg=theme.MUTED,
                 font=(theme.FONT_FAMILY, 8), anchor="w").grid(row=1, column=1, sticky="we")

    def _tick(self):
        if self.winfo_exists():
            self.after(1000, self._tick)

    def _periodic_refresh(self):
        if self.winfo_exists():
            self.refresh()
            self.after(30000, self._periodic_refresh)

    # ------------------------------------------------------------------
    def toggle_pin(self):
        top = not bool(self.attributes("-topmost"))
        self.attributes("-topmost", top)
        self.pin_btn.config(text="📌 置顶:开" if top else "📌 置顶:关")
        self.app.config["mini_window_topmost"] = top

    def show(self):
        self.deiconify()

    def hide(self):
        self.withdraw()

    def close_mini(self):
        """关闭迷你窗（仅隐藏，不退出应用）。"""
        self.hide()
        self.app.config["mini_window_show"] = False

    def open_main(self):
        self.app.deiconify()
        self.app.lift()
        self.app.focus_force()
