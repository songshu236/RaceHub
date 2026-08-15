"""DataStore：统一管理各项目数据的加载 / 缓存 / 后台刷新 / 示例回退。"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .cache import read_cache, write_cache
from .config import DEMO_DIR, load_config, ttl_seconds
from .scrapers import CS2Scraper, F1Scraper, WECScraper
from .scrapers.base import SourceError

SERIES_LIST = ["F1", "WEC", "CS2"]

# 每个项目需要抓取的数据种类
KINDS_BY_SERIES = {
    "F1": ["calendar", "results", "standings"],
    "WEC": ["calendar", "results", "standings"],
    "CS2": ["calendar", "matches", "ranking", "vrs"],
}

SERIES_CN = {"F1": "F1 赛车", "WEC": "WEC 耐力赛", "CS2": "CS2 电竞"}
SERIES_COLOR = {"F1": "#e10600", "WEC": "#f5b301", "CS2": "#1f6feb"}


def _scraper_for(series: str):
    if series == "F1":
        return F1Scraper()
    if series == "WEC":
        return WECScraper()
    if series == "CS2":
        return CS2Scraper()
    raise ValueError(series)


class DataStore:
    """持有内存数据，提供后台刷新。线程安全。"""

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        self.data: dict[str, dict] = {}
        self.lock = threading.RLock()
        self._load_initial()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _load_initial(self):
        for series, kinds in KINDS_BY_SERIES.items():
            self.data[series] = {}
            for kind in kinds:
                payload, meta = self._load_kind(series, kind)
                self.data[series][kind] = {"payload": payload, **meta}

    def _load_kind(self, series: str, kind: str):
        cached = read_cache(series, kind, max_age=ttl_seconds(kind))
        if cached is not None:
            payload = cached.get("payload", cached)
            return payload, {
                "source": cached.get("source", ""),
                "fetched_at": cached.get("_fetched_at", 0),
                "using_demo": False,
                "error": "",
            }
        demo = self._load_demo(series, kind)
        if demo is not None:
            return demo, {
                "source": "内置示例数据",
                "fetched_at": 0,
                "using_demo": True,
                "error": "",
            }
        empty = [] if kind == "calendar" else {"series": series, "rows": []}
        return empty, {"source": "暂无数据", "fetched_at": 0, "using_demo": False, "error": ""}

    def _load_demo(self, series: str, kind: str):
        p = DEMO_DIR / f"{series}_{kind}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    def get(self, series: str, kind: str):
        with self.lock:
            return self.data.get(series, {}).get(kind, {}).get("payload")

    def meta(self, series: str, kind: str) -> dict:
        with self.lock:
            return self.data.get(series, {}).get(kind, {})

    def all_meta(self, series: str) -> dict:
        with self.lock:
            return {k: dict(v) for k, v in self.data.get(series, {}).items()}

    def set_payload(self, series: str, kind: str, payload, source: str, fetched_at: float | None = None):
        with self.lock:
            self.data.setdefault(series, {})[kind] = {
                "payload": payload,
                "source": source,
                "fetched_at": fetched_at if fetched_at is not None else time.time(),
                "using_demo": False,
                "error": "",
            }

    def mark_error(self, series: str, kind: str, error: str):
        with self.lock:
            entry = self.data.get(series, {}).get(kind, {})
            if entry:
                entry["error"] = error
            else:
                self.data.setdefault(series, {})[kind] = {
                    "payload": [] if kind == "calendar" else {"rows": []},
                    "source": "暂无数据", "fetched_at": 0, "using_demo": False, "error": error,
                }

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------
    def refresh(self, series: str, kinds=None, force: bool = False, callback=None):
        """在后台线程刷新指定项目的数据。callback(series, kind, ok, message)。"""
        if kinds is None:
            kinds = KINDS_BY_SERIES.get(series, [])
        t = threading.Thread(
            target=self._refresh_worker, args=(series, list(kinds), force, callback), daemon=True
        )
        t.start()
        return t

    def refresh_all(self, callback=None, kinds=None):
        threads = []
        for series in SERIES_LIST:
            threads.append(self.refresh(series, kinds=kinds, force=True, callback=callback))
        return threads

    def _refresh_worker(self, series, kinds, force, callback):
        scraper = _scraper_for(series)
        # 同项目内各数据种类并行抓取（WEC 尤其受益：日历/赛果/积分同时跑）
        with ThreadPoolExecutor(max_workers=min(4, len(kinds))) as pool:
            futures = [pool.submit(self._refresh_one_kind, scraper, series, kind, callback)
                       for kind in kinds]
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass

    def _refresh_one_kind(self, scraper, series, kind, callback):
        if self.config.get("offline_mode"):
            self._notify(callback, series, kind, False, "离线模式，未联网")
            return
        try:
            payload, source = self._fetch_kind(scraper, kind)
            if payload is None:
                raise SourceError("数据源无返回")
            existing = self.get(series, kind)
            if _payload_empty(payload) and not _payload_empty(existing):
                self.mark_error(series, kind, "本次抓取返回空数据，已保留原有数据")
                self._notify(callback, series, kind, False, "返回空数据，保留原数据")
                return
            if not _payload_plausible(payload, existing):
                self.mark_error(series, kind, "本次抓取结果偏少，疑似页面不完整，已保留原数据")
                self._notify(callback, series, kind, False, "结果偏少，保留原数据")
                return
            self.set_payload(series, kind, payload, source)
            try:
                write_cache(series, kind, "", {"payload": payload, "source": source})
            except Exception:
                pass
            self._notify(callback, series, kind, True, "")
        except Exception as e:
            msg = str(e)[:300]
            self.mark_error(series, kind, msg)
            self._notify(callback, series, kind, False, msg)

    @staticmethod
    def _fetch_kind(scraper, kind):
        if kind == "calendar":
            if getattr(scraper, "series", "") == "CS2":
                return scraper.fetch_events(), scraper.source_label
            return scraper.fetch_calendar(), scraper.source_label
        if kind == "results":
            return scraper.fetch_results(), scraper.source_label
        if kind == "standings":
            return scraper.fetch_standings(), scraper.source_label
        if kind == "matches":
            return scraper.fetch_matches(), scraper.source_label
        if kind == "ranking":
            return scraper.fetch_ranking(), scraper.source_label
        if kind == "vrs":
            return scraper.fetch_valve_ranking(), scraper.source_label
        raise ValueError(f"unknown kind {kind}")

    @staticmethod
    def _notify(callback, series, kind, ok, msg):
        if callback:
            try:
                callback(series, kind, ok, msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 迷你窗 / 概览
    # ------------------------------------------------------------------
    def next_events(self, n: int = 6) -> list:
        """跨项目最近的 upcoming/ongoing 事件，用于迷你窗置顶显示。"""
        out = []
        with self.lock:
            for series in SERIES_LIST:
                cal = self.data.get(series, {}).get("calendar", {}).get("payload", []) or []
                for ev in cal:
                    out.append({"series": series, **ev})
        out = [e for e in out if e.get("status") in ("upcoming", "ongoing")]
        out.sort(key=lambda e: (e.get("start") or "9999-12-31", e.get("name") or ""))
        return out[:n]

    def status_summary(self) -> str:
        """底部状态栏文本。"""
        parts = []
        with self.lock:
            for series in SERIES_LIST:
                metas = self.data.get(series, {})
                using_demo = any(m.get("using_demo") for m in metas.values())
                errors = [m.get("error") for m in metas.values() if m.get("error")]
                if using_demo:
                    tag = "示例数据"
                elif errors:
                    tag = "部分失败"
                else:
                    tag = "已更新"
                parts.append(f"{SERIES_CN[series]}: {tag}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # 按需抓取单场比赛各局比分
    # ------------------------------------------------------------------
    def refresh_match_detail(self, match_id: str, callback=None):
        """后台抓取单场比赛详情（各局比分），结果写入缓存。callback(detail dict)。"""
        from .cache import read_cache
        cached = read_cache("CS2", "matchdetail", _match_detail_cache_key(match_id), max_age=6 * 3600)
        if cached is not None and cached.get("payload"):
            if callback:
                try:
                    callback(cached["payload"])
                except Exception:
                    pass
            return None

        def worker():
            try:
                detail = CS2Scraper().fetch_match_detail(match_id)
                try:
                    write_cache("CS2", "matchdetail", _match_detail_cache_key(match_id),
                                {"payload": detail, "source": "HLTV"})
                except Exception:
                    pass
            except Exception as e:
                detail = {"match_id": match_id, "error": str(e)[:200]}
            if callback:
                try:
                    callback(detail)
                except Exception:
                    pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    def newest_fetched_at(self) -> float:
        with self.lock:
            times = [m.get("fetched_at", 0) for s in self.data.values() for m in s.values()]
        return max(times) if times else 0


def _payload_empty(payload) -> bool:
    """判断抓取结果是否为空（无任何行/条目）。"""
    if payload is None:
        return True
    if isinstance(payload, (list, tuple)):
        return len(payload) == 0
    if isinstance(payload, dict):
        if payload.get("rows"):
            return False
        if payload.get("tables"):
            return False
        if payload.get("Races"):
            return False
        # 没有 rows/tables 的 dict 视为空
        return True
    return not payload


def _match_detail_cache_key(match_id: str) -> str:
    return f"detail_{match_id}"



def _payload_count(payload) -> int:
    if isinstance(payload, (list, tuple)):
        return len(payload)
    if isinstance(payload, dict):
        if payload.get("rows"):
            return len(payload["rows"])
        if payload.get("tables"):
            return len(payload["tables"])
    return 0


def _payload_plausible(new_payload, old_payload) -> bool:
    """防覆盖保护：新结果过少而原有数据很多时视为抓取不完整。"""
    n_new = _payload_count(new_payload)
    n_old = _payload_count(old_payload)
    if n_old <= 0:
        return True
    if n_new >= 15:
        return True
    if n_new * 3 >= n_old:
        return True
    return False
