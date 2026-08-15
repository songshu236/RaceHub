"""CS2 真实队标：后台下载 HLTV 队标、本地缓存、失败回退彩色徽章。"""
from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path

from ..config import DATA_DIR
from ..fetcher import fetch_bytes
from .badges import get_badge

_logos_dir = DATA_DIR / "logos"


def _safe(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name or "").strip("_") or "team"


class TeamLogoManager:
    """管理 HLTV 队标：内存缓存 + data/logos 磁盘缓存 + 后台下载。"""

    MAX_WORKERS = 3          # 并发下载上限
    COOLDOWN_SECONDS = 300   # 连续失败 N 次后的冷却
    MAX_CONSEC_FAIL = 3      # 连续失败多少次进入冷却
    RETRY_INTERVAL = 24 * 3600  # 单队下载失败后 24 小时内不再重试

    def __init__(self):
        self._mem: dict[tuple, tk.PhotoImage] = {}
        self._queued: set[str] = set()
        self._ui_cb = None
        self._blocked_until: float = 0
        self._consec_fail: int = 0
        self._status_lock = threading.Lock()
        self._status: dict = self._load_status()
        self._q: queue.Queue = queue.Queue()
        for _ in range(self.MAX_WORKERS):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
        try:
            _logos_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # ---- 持久化下载状态：避免每次启动都重新爬 ----
    @staticmethod
    def _status_path() -> Path:
        return _logos_dir / "_status.json"

    def _load_status(self) -> dict:
        try:
            import json
            p = self._status_path()
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_status(self):
        try:
            import json
            with self._status_lock:
                self._status_path().write_text(
                    json.dumps(self._status), encoding="utf-8")
        except Exception:
            pass

    def _mark_attempt(self, name: str):
        with self._status_lock:
            self._status[name] = time.time()
        self._save_status()

    def _clear_status(self, name: str):
        with self._status_lock:
            self._status.pop(name, None)
        self._save_status()

    def _should_skip(self, name: str) -> bool:
        with self._status_lock:
            t = self._status.get(name, 0)
        return bool(t) and (time.time() - t) < self.RETRY_INTERVAL

    def set_ui_callback(self, cb):
        self._ui_cb = cb

    def _worker(self):
        while True:
            try:
                name, url, size = self._q.get(timeout=5)
            except queue.Empty:
                continue
            try:
                # 整批冷却期间：跳过已排队项（下次启动再按状态决定是否重试）
                if time.time() < self._blocked_until:
                    continue
                self._download(name, url, size)
            finally:
                self._queued.discard(name)

    def get(self, name: str, url: str = "", size: int = 30):
        """返回队标 PhotoImage；无缓存时触发后台下载并返回 None（调用方回退徽章）。"""
        if not name:
            return None
        key = (name.strip(), size)
        if key in self._mem:
            return self._mem[key]
        f = _logos_dir / f"{_safe(name)}.png"
        if f.exists():
            img = self._load_image(f, size)
            if img is not None:
                self._mem[key] = img
                return img
        if url:
            self._schedule_download(name, url, size)
        return None

    def _schedule_download(self, name: str, url: str, size: int):
        if name in self._queued:
            return
        if time.time() < self._blocked_until:
            return  # CDN 冷却中，跳过
        if self._should_skip(name):
            return  # 24 小时内尝试过且失败，跳过，避免每次启动都爬
        self._queued.add(name)
        self._q.put((name, url, size))

    def _download(self, name: str, url: str, size: int):
        try:
            data = fetch_bytes(url, timeout=20, use_cloudscraper=True)
            if not data or len(data) < 100:
                return
            f = _logos_dir / f"{_safe(name)}.png"
            try:
                f.write_bytes(data)
            except Exception:
                return
            img = self._load_image(f, size)
            if img is not None:
                self._mem[(name.strip(), size)] = img
                self._clear_status(name)
                self._consec_fail = 0
            if self._ui_cb is not None:
                try:
                    self._ui_cb()
                except Exception:
                    pass
        except Exception:
            # 记录失败时间，24 小时内不再重试该队
            self._mark_attempt(name)
            # 连续失败达阈值则整批冷却
            self._consec_fail += 1
            if self._consec_fail >= self.MAX_CONSEC_FAIL:
                self._blocked_until = time.time() + self.COOLDOWN_SECONDS
                self._consec_fail = 0

    @staticmethod
    def _load_image(path: Path, size: int):
        # 优先 PIL：缩放 + 透明背景
        try:
            from PIL import Image, ImageDraw, ImageTk  # type: ignore
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size - 4, size - 4), Image.LANCZOS)
            # 白底（不用透明底），加细边框便于深色背景下区分
            canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
            canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
            d = ImageDraw.Draw(canvas)
            d.rectangle((0, 0, size - 1, size - 1), outline="#c9d2dc", width=1)
            return ImageTk.PhotoImage(canvas)
        except Exception:
            pass
        # 回退：tk 直接读取并整数倍缩小
        try:
            ph = tk.PhotoImage(file=str(path))
            w, h = ph.width(), ph.height()
            factor = max(1, w // size, h // size)
            if factor > 1:
                ph = ph.subsample(factor, factor)
            return ph
        except Exception:
            return None


# 全局单例
logo_manager = TeamLogoManager()
