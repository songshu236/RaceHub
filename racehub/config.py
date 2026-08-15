"""全局配置：路径、代理、缓存 TTL、离线模式。"""
from __future__ import annotations

import json
from pathlib import Path

APP_NAME = "RaceHub 赛事日历"
APP_VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
DEMO_DIR = DATA_DIR / "demo"
LOG_DIR = ROOT / "logs"
CONFIG_FILE = ROOT / "config.json"

# 各类数据的默认缓存时长（秒）
DEFAULT_TTL_SECONDS = {
    "calendar": 6 * 3600,
    "results": 6 * 3600,
    "standings": 6 * 3600,
    "matches": 6 * 3600,
    "ranking": 12 * 3600,
}

DEFAULT_CONFIG = {
    "offline_mode": False,          # 强制使用内置示例数据
    "proxy": "",                    # 例如 http://127.0.0.1:7890
    "ttl_hours": 6,                 # 缓存有效期（小时）
    "use_demo_if_fetch_fails": True,
    "auto_refresh_minutes": 60,
    "mini_window_topmost": True,
    "mini_window_show": True,
}

_config: dict | None = None


def ensure_dirs() -> None:
    for d in (CACHE_DIR, DEMO_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    _config = cfg
    return _config


def save_config(cfg: dict | None = None) -> None:
    global _config
    if cfg is not None:
        _config = cfg
    if _config is not None:
        CONFIG_FILE.write_text(
            json.dumps(_config, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def ttl_seconds(kind: str) -> int:
    cfg = load_config()
    hours = float(cfg.get("ttl_hours", 6) or 6)
    return int(hours * 3600)
