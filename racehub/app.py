"""RaceHub 主应用。"""
from __future__ import annotations

import logging
import sys
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import messagebox, ttk

from . import __app_name__, __version__
from .cache import clear_cache
from .config import ensure_dirs, load_config, save_config
from .store import SERIES_CN, DataStore
from .ui import theme
from .ui.cs2_panel import CS2Panel
from .ui.f1_panel import F1Panel
from .ui.mini_window import MiniWindow
from .ui.wec_panel import WECPanel


class RaceHubApp(tk.Tk):
    def __init__(self, offline: bool = False):
        super().__init__()
        self.config = load_config()
        if offline:
            self.config["offline_mode"] = True
        ensure_dirs()
        theme.setup(self)
        self.store = DataStore(self.config)
        self._mini = None
        self._setup_logging()
        sys.excepthook = self._log_exception
        logging.info("=== RaceHub 启动 ===")
        logging.info("python: %s", sys.version.split()[0])
        logging.info("config: %s", self.config)
        self._build_window()
        self._build_menubar()
        self._build_topbar()
        try:
            self._build_tabs()
        except Exception:
            logging.exception("构建标签页失败")
            traceback.print_exc()
        self._build_statusbar()
        self._check_startup_data()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # 迷你窗
        self.after(600, self._init_mini)
        # 自动刷新
        self.after(1500, self._initial_refresh)
        self._schedule_auto_refresh()
        # 强制重绘（部分 Windows/Tk 环境下 ttk 控件首次不绘制）
        try:
            self.update_idletasks()
        except Exception:
            pass
        self.after(300, self._force_repaint)
        self.after(1200, self._force_repaint)
        self.after(400, self._log_layout)
        self.after(3000, self._log_layout)

    # ------------------------------------------------------------------
    def _build_window(self):
        self.title(f"{__app_name__}  v{__version__}")
        self.configure(bg=theme.BG)
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except Exception:
            sw = sh = 0
        w = min(1340, max(1080, sw - 80)) if sw else 1340
        h = min(880, max(680, sh - 120)) if sh else 880
        self.geometry(f"{w}x{h}")
        self.minsize(1000, 620)

    def _build_menubar(self):
        bar = tk.Menu(self)
        m_file = tk.Menu(bar, tearoff=0)
        m_file.add_command(label="退出", command=self.on_close)
        bar.add_cascade(label="文件", menu=m_file)

        m_data = tk.Menu(bar, tearoff=0)
        m_data.add_command(label="全部刷新", command=self.refresh_all)
        m_data.add_command(label="清空本地缓存", command=self.clear_cache)
        m_data.add_separator()
        m_data.add_command(label="设置…", command=self.open_settings)
        bar.add_cascade(label="数据", menu=m_data)

        m_view = tk.Menu(bar, tearoff=0)
        m_view.add_command(label="显示/隐藏迷你窗", command=self.toggle_mini)
        bar.add_cascade(label="视图", menu=m_view)

        m_help = tk.Menu(bar, tearoff=0)
        m_help.add_command(label="🖼 下载全部 CS2 队标", command=self.download_all_cs2_logos)
        m_help.add_separator()
        m_help.add_command(label="生成界面截图", command=self.save_screenshot)
        m_help.add_command(label="修复显示（强制重绘）", command=self.repair_display)
        m_help.add_command(label="诊断信息", command=self.show_diagnostics)
        m_help.add_command(label="关于", command=self.show_about)
        bar.add_cascade(label="帮助", menu=m_help)
        self.configure(menu=bar)

    def _build_topbar(self):
        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(side="top", fill="x", padx=14, pady=(12, 6))
        bar.columnconfigure(2, weight=1)
        tk.Label(bar, text="🏁 RaceHub", bg=theme.BG, fg=theme.TEXT,
                 font=(theme.FONT_FAMILY, 20, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(bar, text="F1 · WEC · CS2  赛事日历 / 赛果 / 积分聚合", bg=theme.BG, fg=theme.MUTED,
                 font=(theme.FONT_FAMILY, 10)).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
        self.online_badge = tk.Label(bar, text="", bg=theme.BG, fg=theme.OK,
                                     font=(theme.FONT_FAMILY, 9))
        self.online_badge.grid(row=0, column=2, sticky="e")
        self.data_badge = tk.Label(bar, text="", bg=theme.BG, fg=theme.MUTED,
                                   font=(theme.FONT_FAMILY, 9))
        self.data_badge.grid(row=0, column=6, sticky="e", padx=8)
        self.mini_btn = ttk.Button(bar, text="🗔 迷你窗", command=self.toggle_mini)
        self.mini_btn.grid(row=0, column=3, padx=(6, 4))
        self.settings_btn = ttk.Button(bar, text="⚙ 设置", command=self.open_settings)
        self.settings_btn.grid(row=0, column=4, padx=(0, 4))
        self.refresh_all_btn = ttk.Button(bar, text="🔄 全部刷新", style="Accent.TButton",
                                          command=self.refresh_all)
        self.refresh_all_btn.grid(row=0, column=5, padx=(4, 0))
        self._update_online_badge()

    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(side="top", fill="both", expand=True, padx=10, pady=4)
        self.f1 = F1Panel(nb, self.store)
        self.wec = WECPanel(nb, self.store)
        self.cs2 = CS2Panel(nb, self.store)
        nb.add(self.f1, text="  F1 赛车  ")
        nb.add(self.wec, text="  WEC 耐力赛  ")
        nb.add(self.cs2, text="  CS2 电竞  ")
        self.notebook = nb

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=theme.PANEL2, height=26)
        bar.pack(side="bottom", fill="x")
        bar.columnconfigure(1, weight=1)
        self.status_lbl = tk.Label(bar, text="", bg=theme.PANEL2, fg=theme.MUTED,
                                   font=(theme.FONT_FAMILY, 9), anchor="w")
        self.status_lbl.grid(row=0, column=0, sticky="we", padx=10)
        self.clock_lbl = tk.Label(bar, text="", bg=theme.PANEL2, fg=theme.MUTED,
                                  font=(theme.FONT_FAMILY, 9), anchor="e")
        self.clock_lbl.grid(row=0, column=1, sticky="e", padx=10)
        self._update_status()
        self.after(1000, self._status_tick)

    # ------------------------------------------------------------------
    def _init_mini(self):
        self._mini = MiniWindow(self)
        if self.config.get("mini_window_show", True):
            self._mini.show()

    @property
    def mini(self):
        return self._mini

    def toggle_mini(self):
        if self._mini is None:
            self._init_mini()
        if self._mini:
            if self._mini.state() == "withdrawn":
                self._mini.show()
                self.config["mini_window_show"] = True
            else:
                self._mini.hide()
                self.config["mini_window_show"] = False

    # ------------------------------------------------------------------
    def refresh_all(self):
        if self.refresh_all_btn is not None:
            self.refresh_all_btn.config(state="disabled", text="刷新中…")
        self.store.refresh_all(callback=self._on_refresh_done)

    def _on_refresh_done(self, series, kind, ok, msg):
        try:
            self.after(0, lambda: self._apply_refresh_done(series, kind, ok, msg))
        except Exception:
            pass

    def _apply_refresh_done(self, series, kind, ok, msg):
        self._update_online_badge()
        self._update_status()
        self.refresh_all_btn.config(state="normal", text="🔄 全部刷新")
        if self._mini is not None and self._mini.winfo_exists():
            self._mini.refresh()

    def _initial_refresh(self):
        if not self.config.get("offline_mode"):
            self.refresh_all()

    def _schedule_auto_refresh(self):
        minutes = int(self.config.get("auto_refresh_minutes", 60) or 60)
        self.after(minutes * 60000, self._auto_tick)

    def _auto_tick(self):
        if not self.config.get("offline_mode"):
            self.refresh_all()
        self._schedule_auto_refresh()

    # ------------------------------------------------------------------
    def _update_online_badge(self):
        offline = self.config.get("offline_mode")
        using_demo = False
        for series in ("F1", "WEC", "CS2"):
            for m in self.store.all_meta(series).values():
                if m.get("using_demo"):
                    using_demo = True
        if offline:
            self.online_badge.config(text="● 离线模式（示例数据）", fg=theme.WARN)
        elif using_demo:
            self.online_badge.config(text="● 部分数据为示例", fg=theme.WARN)
        else:
            self.online_badge.config(text="● 在线", fg=theme.OK)

    def _update_status(self):
        self.status_lbl.config(text=self.store.status_summary())

    def _status_tick(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.clock_lbl.config(text=now)
        self.after(1000, self._status_tick)

    # ------------------------------------------------------------------
    def clear_cache(self):
        if messagebox.askyesno("清空缓存", "确定清空所有本地缓存数据吗？下次刷新会重新抓取。"):
            n = clear_cache()
            messagebox.showinfo("完成", f"已清空 {n} 个缓存文件。")

    def open_settings(self):
        SettingsDialog(self)

    def download_all_cs2_logos(self):
        """帮助菜单：批量下载 CS2 全部真实队标（白底、本地保存）。"""
        cs2 = getattr(self, "cs2", None)
        if cs2 is None or not hasattr(cs2, "download_all_logos"):
            messagebox.showinfo("下载队标", "CS2 面板尚未创建，请稍后重试。")
            return
        cs2.download_all_logos(notify=True)

    def show_about(self):
        messagebox.showinfo(
            "关于",
            f"{__app_name__} v{__version__}\n\n"
            "数据来源：\n"
            "· F1 — Ergast API (api.jolpi.ca)\n"
            "· WEC — FIA WEC 官网与官方计时系统\n"
            "· CS2 — HLTV (hltv.org)\n\n"
            "说明：HLTV 有 Cloudflare 防护，如抓取失败请在设置中配置代理。",
        )

    def _force_repaint(self):
        """通过 1px 缩放切换强制 Tk 重绘（修复部分系统 ttk 不绘制的问题）。"""
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            if w > 10 and h > 10:
                self.geometry(f"{w + 1}x{h}")
                self.update_idletasks()
                self.geometry(f"{w}x{h}")
        except Exception:
            pass

    def _log_layout(self):
        """记录屏幕/窗口/各表格的几何与映射状态，用于排查“空窗口”。"""
        try:
            logging.info(
                "屏幕=%sx%s 缩放=%.2f 窗口=%sx%s@(%s,%s) 状态=%s 主题=%s",
                self.winfo_screenwidth(), self.winfo_screenheight(),
                self.winfo_fpixels("1i"), self.winfo_width(), self.winfo_height(),
                self.winfo_x(), self.winfo_y(), self.state(),
                self.tk.call("ttk::style", "theme", "use"),
            )
            for name, panel in (("F1", getattr(self, "f1", None)),
                                ("WEC", getattr(self, "wec", None)),
                                ("CS2", getattr(self, "cs2", None))):
                if panel is None:
                    continue
                for attr in ("cal_tree", "res_tree", "stand_tree", "match_tree", "rank_tree"):
                    t = getattr(panel, attr, None)
                    if t is None:
                        continue
                    logging.info(
                        "  %s/%s rows=%d mapped=%s viewable=%s size=%sx%s",
                        name, attr, len(t.get_children()),
                        t.winfo_ismapped(), t.winfo_viewable(),
                        t.winfo_width(), t.winfo_height(),
                    )
        except Exception as e:
            logging.warning("布局日志失败: %s", e)

    def _check_startup_data(self):
        """启动时校验数据是否为空；为空则显示醒目提示并写日志，便于排查。"""
        total = 0
        for series in ("F1", "WEC", "CS2"):
            for kind in ("calendar", "results", "standings", "matches", "ranking", "vrs"):
                p = self.store.get(series, kind)
                if p is None:
                    continue
                total += len(p) if isinstance(p, list) else (len(p.get("rows", [])) or len(p.get("tables", [])))
        logging.info("启动时数据总条数: %d", total)
        self.data_badge.config(text=f"已加载 {total} 条数据")
        # 记录每个面板实际渲染行数（排查“空窗口”）
        for name, panel in (("F1", getattr(self, "f1", None)),
                            ("WEC", getattr(self, "wec", None)),
                            ("CS2", getattr(self, "cs2", None))):
            if panel is None:
                logging.warning("面板 %s 未创建", name)
                continue
            try:
                counts = []
                for attr in ("cal_tree", "res_tree", "stand_tree", "match_tree", "rank_tree"):
                    t = getattr(panel, attr, None)
                    if t is not None:
                        counts.append(f"{attr}={len(t.get_children())}")
                logging.info("面板 %s 渲染: %s", name, " ".join(counts))
            except Exception as e:
                logging.warning("面板 %s 行数统计失败: %s", name, e)
        if total == 0:
            logging.warning("启动时没有任何数据！请运行: python scripts\\gen_demo.py 重新生成示例数据")
            banner = tk.Label(self, text="⚠ 未加载到任何数据：请点击右上角「🔄 全部刷新」，"
                                          "或关闭后在项目目录运行  python scripts\\gen_demo.py",
                              bg="#3a1f1f", fg="#ffb3a7", font=(theme.FONT_FAMILY, 11, "bold"), pady=6)
            banner.pack(side="top", fill="x", padx=10)

    def _setup_logging(self):
        from .config import LOG_DIR
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                filename=LOG_DIR / "app.log",
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(message)s",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _log_exception(self, etype, value, tb):
        logging.error("未捕获异常: %s", "".join(traceback.format_exception(etype, value, tb)))
        try:
            messagebox.showerror("程序错误", f"发生未捕获异常：\n{etype.__name__}: {value}")
        except Exception:
            pass

    def show_diagnostics(self):
        DiagnosticsDialog(self)

    def repair_display(self):
        """手动强制重绘 + 窗口尺寸恢复。"""
        self._force_repaint()
        self._force_repaint()
        try:
            self.update()
        except Exception:
            pass
        messagebox.showinfo("修复显示", "已触发强制重绘。如果仍然空白，请用「生成界面截图」把画面发我。")

    def save_screenshot(self):
        """生成界面截图并打开所在文件夹。"""
        try:
            from .ui.screenshot import save_screenshot as _ss
            from .config import ROOT
            path = _ss(self, ROOT / "docs")
            logging.info("界面截图已保存: %s", path)
            messagebox.showinfo("截图已保存", f"界面截图已保存到：\n{path}\n\n请打开图片查看，或直接把它发给我。")
            try:
                import os
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception as e:
            logging.exception("生成界面截图失败")
            messagebox.showerror("截图失败", f"生成界面截图失败：{e}\n\n请用 Win+Shift+S 手动截图后发给我。")

    def on_close(self):
        logging.info("=== RaceHub 退出 ===")
        save_config(self.config)
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """代理 / 离线 / 刷新间隔设置。"""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("设置")
        self.geometry("460x300")
        self.resizable(False, False)
        self.configure(bg=theme.BG)
        self.transient(app)
        self.grab_set()
        self._build()

    def _build(self):
        cfg = self.app.config
        pad = {"padx": 14, "pady": 8}
        ttk.Label(self, text="数据设置", style="Section.TLabel").pack(anchor="w", **pad)

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="代理 (http/socks5):", width=20).pack(side="left")
        self.proxy_var = tk.StringVar(value=cfg.get("proxy", ""))
        ttk.Entry(row, textvariable=self.proxy_var, width=34).pack(side="left")

        self.offline_var = tk.BooleanVar(value=bool(cfg.get("offline_mode")))
        ttk.Checkbutton(self, text="离线模式（不联网，仅使用缓存/示例数据）",
                        variable=self.offline_var).pack(anchor="w", **pad)

        row2 = ttk.Frame(self)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="缓存有效期(小时):", width=20).pack(side="left")
        self.ttl_var = tk.StringVar(value=str(cfg.get("ttl_hours", 6)))
        ttk.Spinbox(row2, from_=1, to=72, textvariable=self.ttl_var, width=8).pack(side="left")

        row3 = ttk.Frame(self)
        row3.pack(fill="x", **pad)
        ttk.Label(row3, text="自动刷新间隔(分钟):", width=20).pack(side="left")
        self.auto_var = tk.StringVar(value=str(cfg.get("auto_refresh_minutes", 60)))
        ttk.Spinbox(row3, from_=5, to=1440, textvariable=self.auto_var, width=8).pack(side="left")

        ttk.Label(self, text="提示：HLTV 抓取失败时，可配置本地代理（如 Clash 的 http://127.0.0.1:7890）后点击“全部刷新”。",
                  style="Muted.TLabel", wraplength=420).pack(anchor="w", **pad)

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="保存", style="Accent.TButton", command=self._save).pack(side="right", padx=4)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right")

    def _save(self):
        cfg = self.app.config
        cfg["proxy"] = self.proxy_var.get().strip()
        cfg["offline_mode"] = self.offline_var.get()
        try:
            cfg["ttl_hours"] = int(self.ttl_var.get())
        except ValueError:
            pass
        try:
            cfg["auto_refresh_minutes"] = int(self.auto_var.get())
        except ValueError:
            pass
        save_config(cfg)
        self.app.store.config = cfg
        self.app._update_online_badge()
        self.destroy()



class DiagnosticsDialog(tk.Toplevel):
    """显示各项目数据条数 / 错误 / 运行环境，便于排查空窗口等问题。"""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("诊断信息")
        self.geometry("640x520")
        self.configure(bg=theme.BG)
        self.transient(app)
        self._build()

    def _build(self):
        lines = []
        lines.append(f"应用版本: {__version__}")
        lines.append(f"Python: {sys.version.split()[0]}")
        lines.append(f"Tk: {self.app.tk.call('info', 'patchlevel')}")
        lines.append(f"主题: {self.app.tk.call('ttk::style', 'theme', 'use')}")
        lines.append("")
        lines.append("数据加载情况:")
        for series in ("F1", "WEC", "CS2"):
            for kind, m in self.app.store.all_meta(series).items():
                p = self.app.store.get(series, kind)
                n = len(p) if isinstance(p, list) else (len(p.get("rows", [])) or len(p.get("tables", [])))
                src = m.get("source", "")
                err = m.get("error", "")
                lines.append(f"  {series}/{kind}: {n} 条  [{src}]" + (f"  错误:{err}" if err else ""))
        lines.append("")
        lines.append("面板渲染行数:")
        for name, panel in (("F1", getattr(self.app, "f1", None)),
                            ("WEC", getattr(self.app, "wec", None)),
                            ("CS2", getattr(self.app, "cs2", None))):
            if panel is None:
                lines.append(f"  {name}: 未创建")
                continue
            try:
                counts = []
                for attr in ("cal_tree", "res_tree", "stand_tree", "match_tree", "rank_tree"):
                    t = getattr(panel, attr, None)
                    if t is not None:
                        counts.append(f"{attr}={len(t.get_children())}")
                lines.append(f"  {name}: " + (" ".join(counts) if counts else "无表格"))
            except Exception as e:
                lines.append(f"  {name}: 读取失败 {e}")
        lines.append("")
        lines.append("日志文件: logs/app.log")
        lines.append("数据目录: data/")

        txt = tk.Text(self, bg=theme.PANEL, fg=theme.TEXT, font=("Consolas", 9),
                      relief="flat", padx=10, pady=10, wrap="none")
        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="打开数据目录", command=self._open_data).pack(side="left")
        ttk.Button(bar, text="关闭", command=self.destroy).pack(side="right")

    def _open_data(self):
        import os
        from .config import DATA_DIR
        os.startfile(DATA_DIR)  # type: ignore[attr-defined]
