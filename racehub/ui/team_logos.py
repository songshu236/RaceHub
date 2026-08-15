"""CS2 真实队标与赛事图标：后台下载 HLTV 素材、本地缓存、失败回退彩色徽章。

kind="team"  -> data/logos/{队名}.png
kind="event" -> data/logos/events/{赛事名}.png
两者均：白底显示（不用透明底）、本地保存（免重复爬）、24h 失败重试冷却。
"""
from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path

from ..config import DATA_DIR
from ..fetcher import fetch_bytes
from ..scrapers.cs2 import BLACK_BG_TEAMS
from .badges import get_badge

_logos_dir = DATA_DIR / "logos"

KINDS = ("team", "event")


def _safe(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name or "").strip("_") or "item"


def _kind_dir(kind: str) -> Path:
    return _logos_dir / "events" if kind == "event" else _logos_dir


def _file_for(kind: str, name: str) -> Path:
    return _kind_dir(kind) / f"{_safe(name)}.png"


# 黑底队标（其余默认白底）：MIBR / BIG 及以后更新都保持黑底
def _is_black_bg(name: str) -> bool:
    return (name or "").strip().lower() in BLACK_BG_TEAMS


def _looks_like_image(data: bytes) -> bool:
    """PNG 签名，或可尝试转换的 SVG。"""
    if not data:
        return False
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    head = data.lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<svg")


class TeamLogoManager:
    """管理 HLTV 队标/赛事图标：内存缓存 + 磁盘缓存 + 后台下载。"""

    MAX_WORKERS = 3          # 并发下载上限
    COOLDOWN_SECONDS = 300   # 连续失败 N 次后的冷却
    MAX_CONSEC_FAIL = 3      # 连续失败多少次进入冷却
    RETRY_INTERVAL = 24 * 3600  # 单条下载失败后 24 小时内不再重试

    def __init__(self):
        self._mem: dict[tuple, tk.PhotoImage] = {}
        self._queued: set[tuple] = set()
        self._ui_cb = None
        self._blocked_until: float = 0
        self._consec_fail: int = 0
        self._status_lock = threading.Lock()
        self._status: dict[str, dict] = {k: self._load_status(k) for k in KINDS}
        self._q: queue.Queue = queue.Queue()
        for _ in range(self.MAX_WORKERS):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
        try:
            _logos_dir.mkdir(parents=True, exist_ok=True)
            (_logos_dir / "events").mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # ---- 持久化下载状态：避免每次启动都重新爬 ----
    @staticmethod
    def _status_path(kind: str) -> Path:
        return _logos_dir / ("_status.json" if kind == "team" else f"_status_{kind}.json")

    def _load_status(self, kind: str) -> dict:
        try:
            import json
            p = self._status_path(kind)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_status(self, kind: str):
        try:
            import json
            with self._status_lock:
                self._status_path(kind).write_text(
                    json.dumps(self._status.get(kind, {})), encoding="utf-8")
        except Exception:
            pass

    def _mark_attempt(self, name: str, kind: str = "team"):
        with self._status_lock:
            self._status.setdefault(kind, {})[name] = time.time()
        self._save_status(kind)

    def _clear_status(self, name: str, kind: str = "team"):
        with self._status_lock:
            self._status.get(kind, {}).pop(name, None)
        self._save_status(kind)

    def _should_skip(self, name: str, kind: str = "team") -> bool:
        with self._status_lock:
            t = self._status.get(kind, {}).get(name, 0)
        return bool(t) and (time.time() - t) < self.RETRY_INTERVAL

    def set_ui_callback(self, cb):
        self._ui_cb = cb

    def _worker(self):
        while True:
            try:
                kind, name, url, size = self._q.get(timeout=5)
            except queue.Empty:
                continue
            try:
                # 整批冷却期间：等待冷却结束再继续，不丢弃任务
                while time.time() < self._blocked_until:
                    time.sleep(1)
                self._download(name, url, size, kind)
            finally:
                self._queued.discard((kind, name))

    def get(self, name: str, url: str = "", size: int = 30, kind: str = "team"):
        """返回图标 PhotoImage；无缓存时触发后台下载并返回 None（调用方回退徽章）。"""
        if not name:
            return None
        key = (kind, name.strip(), size)
        if key in self._mem:
            return self._mem[key]
        f = _file_for(kind, name)
        if f.exists():
            img = self._load_image(f, size, name)
            if img is not None:
                self._mem[key] = img
                return img
            # 文件存在但无法加载（如 SVG 未能转换）-> 记录尝试，避免反复下载
            self._mark_attempt(name, kind)
            return None
        if url:
            self._schedule_download(name, url, size, kind)
        return None

    def _schedule_download(self, name: str, url: str, size: int, kind: str = "team"):
        qk = (kind, name)
        if qk in self._queued:
            return
        if time.time() < self._blocked_until:
            return  # CDN 冷却中，跳过
        if self._should_skip(name, kind):
            return  # 24 小时内尝试过且失败，跳过，避免每次启动都爬
        self._queued.add(qk)
        self._q.put((kind, name, url, size))

    def _download(self, name: str, url: str, size: int, kind: str = "team"):
        data = None
        for attempt in range(2):
            try:
                data = fetch_bytes(url, timeout=20, use_cloudscraper=True)
                if data and len(data) >= 100 and _looks_like_image(data):
                    break
                data = None
            except Exception:
                data = None
            time.sleep(2)
        if not data:
            self._mark_attempt(name, kind)
            self._consec_fail += 1
            if self._consec_fail >= self.MAX_CONSEC_FAIL:
                self._blocked_until = time.time() + self.COOLDOWN_SECONDS
                self._consec_fail = 0
            return
        try:
            f = _file_for(kind, name)
            f.parent.mkdir(parents=True, exist_ok=True)
            # HLTV 部分素材实际是 SVG：尝试转成 PNG
            if data.lstrip().startswith((b"<?xml", b"<svg")):
                png = self._svg_to_png(data)
                if png:
                    data = png
            try:
                f.write_bytes(data)
            except Exception:
                return
            # 转换失败则删除无效文件，避免残留
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
                self._mark_attempt(name, kind)
                return
            img = self._load_image(f, size, name)
            if img is not None:
                self._mem[(kind, name.strip(), size)] = img
                self._clear_status(name, kind)
                self._consec_fail = 0
            if self._ui_cb is not None:
                try:
                    self._ui_cb()
                except Exception:
                    pass
        except Exception:
            # 记录失败时间，24 小时内不再重试该条
            self._mark_attempt(name, kind)
            # 连续失败达阈值则整批冷却
            self._consec_fail += 1
            if self._consec_fail >= self.MAX_CONSEC_FAIL:
                self._blocked_until = time.time() + self.COOLDOWN_SECONDS
                self._consec_fail = 0

    @staticmethod
    def _svg_to_png(raw: bytes):
        """SVG -> PNG 字节。

        尝试顺序：cairosvg（需系统 cairo）-> svglib+reportlab+PyMuPDF（纯 wheel）。
        全部失败返回 None。
        """
        try:
            import cairosvg  # type: ignore
            return cairosvg.svg2png(bytestring=raw)
        except Exception:
            pass
        try:
            import io as _io
            from svglib.svglib import svg2rlg  # type: ignore
            from reportlab.graphics import renderPDF  # type: ignore
            drawing = svg2rlg(_io.BytesIO(raw))
            if drawing is None:
                return None
            pdf = renderPDF.drawToString(drawing)
            try:
                import pymupdf  # type: ignore
            except Exception:
                import fitz as pymupdf  # type: ignore
            doc = pymupdf.open(stream=pdf, filetype="pdf")
            page = doc[0]
            # alpha=True：透明背景，避免浅色/白色队标被白色页面吞掉
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=True)
            out = pix.tobytes("png")
            doc.close()
            return out
        except Exception:
            return None

    @staticmethod
    def _load_image(path: Path, size: int, name: str = ""):
        # 优先 PIL：缩放 + 底（默认白底；MIBR/BIG 用黑底，其余不变）
        try:
            from PIL import Image, ImageDraw, ImageTk  # type: ignore
            raw = path.read_bytes()
            if raw.lstrip().startswith((b"<?xml", b"<svg")):
                png = TeamLogoManager._svg_to_png(raw)
                if not png:
                    return None
                raw = png
            import io as _io
            img = Image.open(_io.BytesIO(raw)).convert("RGBA")
            img.thumbnail((size - 4, size - 4), Image.LANCZOS)
            # 不用透明底：黑底队标（MIBR/BIG）或白底（其他），加细边框便于深色背景下区分
            dark = _is_black_bg(name)
            canvas = Image.new("RGBA", (size, size),
                               (18, 18, 18, 255) if dark else (255, 255, 255, 255))
            canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
            d = ImageDraw.Draw(canvas)
            d.rectangle((0, 0, size - 1, size - 1),
                        outline=("#3a4657" if dark else "#c9d2dc"), width=1)
            return ImageTk.PhotoImage(canvas)
        except Exception:
            pass
        # 回退：tk 直接读取并整数倍缩小（用 data= 避免中文路径/编码问题）
        try:
            import base64
            ph = tk.PhotoImage(data=base64.b64encode(path.read_bytes()).decode("ascii"))
            w, h = ph.width(), ph.height()
            factor = max(1, w // size, h // size)
            if factor > 1:
                ph = ph.subsample(factor, factor)
            return ph
        except Exception:
            return None

    def download_all_sync(self, teams: dict, size: int = 30, progress=None, workers: int = 4, kind: str = "team"):
        """批量下载图标（并行）。teams: {名称: 图标URL}；progress(name, ok, done, total) 可选。"""
        from concurrent.futures import ThreadPoolExecutor
        items = [(n, u) for n, u in teams.items() if u]
        total = len(items)
        done = 0
        _lock = threading.Lock()

        def _one(item):
            nonlocal done
            name, url = item
            f = _file_for(kind, name)
            if f.exists() and self.get(name, url, size, kind) is not None:
                with _lock:
                    done += 1
                    if progress:
                        progress(name, True, done, total)
                return True
            ok = False
            data = None
            for attempt in range(2):
                try:
                    data = fetch_bytes(url, timeout=15, use_cloudscraper=True)
                    if data and len(data) >= 100 and _looks_like_image(data):
                        ok = True
                        break
                    data = None
                except Exception:
                    data = None
                time.sleep(1.5)
            if ok and data:
                try:
                    if data.lstrip().startswith((b"<?xml", b"<svg")):
                        png = self._svg_to_png(data)
                        if png:
                            data = png
                    if data[:8] != b"\x89PNG\r\n\x1a\n":
                        ok = False
                        data = None
                    else:
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_bytes(data)
                        img = self._load_image(f, size, name)
                    with _lock:
                        if img is not None:
                            self._mem[(kind, name.strip(), size)] = img
                            self._clear_status(name, kind)
                except Exception:
                    ok = False
            if not ok:
                self._mark_attempt(name, kind)
            with _lock:
                done += 1
                if progress:
                    progress(name, ok, done, total)
            return ok

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_one, items))

    def reset_retry(self):
        """清除 24 小时重试记录（用于“下载全部”强制重试）。"""
        with self._status_lock:
            for k in self._status:
                self._status[k].clear()
        for kind in KINDS:
            self._save_status(kind)
        self._blocked_until = 0
        self._consec_fail = 0


def collect_team_logos(store=None) -> dict:
    """从 store/示例数据汇总 {队名: logo_url}。"""
    teams: dict = {}
    payloads = []
    if store is not None:
        payloads = [store.get("CS2", "ranking"), store.get("CS2", "matches"),
                    store.get("CS2", "vrs")]
    if not any(payloads):
        import json
        for f in (DATA_DIR / "demo").glob("CS2_*.json"):
            try:
                payloads.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    for p in payloads:
        if not isinstance(p, dict):
            continue
        for r in p.get("rows", []):
            if isinstance(r, dict) and "name" in r:
                n = r.get("name", "")
                u = (r.get("extra") or {}).get("logo", "")
                if n and u:
                    teams.setdefault(n, u)
            elif isinstance(r, dict) and ("team1" in r or "team2" in r):
                for side in ("team1", "team2"):
                    t = r.get(side) or {}
                    n = t.get("name", "")
                    u = t.get("logo", "")
                    if n and u:
                        teams.setdefault(n, u)
    return teams


def collect_event_logos(store=None) -> dict:
    """从 CS2 赛事日历汇总 {赛事名: 图标URL}。"""
    events: dict = {}
    payloads = []
    if store is not None:
        p = store.get("CS2", "calendar")
        if p:
            payloads.append(p)
    if not payloads:
        import json
        f = DATA_DIR / "demo" / "CS2_calendar.json"
        try:
            payloads.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    for p in payloads:
        if not isinstance(p, list):
            continue
        for e in p:
            if not isinstance(e, dict):
                continue
            n = e.get("name", "")
            u = (e.get("extra") or {}).get("logo", "")
            if n and u:
                events.setdefault(n, u)
    return events


# 全局单例
logo_manager = TeamLogoManager()
