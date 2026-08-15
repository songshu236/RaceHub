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
    COOLDOWN_SECONDS = 600   # CDN 不可用时的冷却时间（避免请求风暴）

    def __init__(self):
        self._mem: dict[tuple, tk.PhotoImage] = {}
        self._queued: set[str] = set()
        self._ui_cb = None
        self._blocked_until: float = 0
        self._q: queue.Queue = queue.Queue()
        for _ in range(self.MAX_WORKERS):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
        try:
            _logos_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def set_ui_callback(self, cb):
        self._ui_cb = cb

    def _worker(self):
        while True:
            try:
                name, url, size = self._q.get(timeout=5)
            except queue.Empty:
                continue
            try:
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
            if self._ui_cb is not None:
                try:
                    self._ui_cb()
                except Exception:
                    pass
        except Exception:
            # 网络/CDN 不可用：进入冷却，避免请求风暴
            self._blocked_until = time.time() + self.COOLDOWN_SECONDS

    @staticmethod
    def _load_image(path: Path, size: int):
        # 优先 PIL：缩放 + 透明背景
        try:
            from PIL import Image, ImageTk  # type: ignore
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
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
