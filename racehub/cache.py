"""本地 JSON 缓存：带时间戳与 TTL。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .config import CACHE_DIR

_lock = threading.Lock()


def _safe_name(series: str, kind: str, key: str = "") -> str:
    name = f"{series.lower()}_{kind}"
    if key:
        name += "_" + str(key).replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name) + ".json"


def read_cache(series: str, kind: str, key: str = "", max_age: int | None = None):
    """读取缓存。max_age 为秒，None 表示不校验年龄。返回 dict 或 None。"""
    path = CACHE_DIR / _safe_name(series, kind, key)
    if not path.exists():
        return None
    try:
        with _lock:
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if max_age is not None:
        fetched = data.get("_fetched_at", 0)
        if time.time() - fetched > max_age:
            return None
    return data


def write_cache(series: str, kind: str, key: str, payload) -> Path:
    path = CACHE_DIR / _safe_name(series, kind, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data["_fetched_at"] = time.time()
    with _lock:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def clear_cache(series: str | None = None) -> int:
    n = 0
    with _lock:
        for p in CACHE_DIR.glob("*.json"):
            if series is None or p.name.startswith(series.lower() + "_"):
                p.unlink(missing_ok=True)
                n += 1
    return n
