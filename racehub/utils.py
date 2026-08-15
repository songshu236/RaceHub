"""通用小工具：日期、倒计时、文本处理。"""
from __future__ import annotations

import datetime as _dt
import re

CN_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def today() -> _dt.date:
    return _dt.date.today()


def parse_date(s: str | None) -> _dt.date | None:
    """解析 'YYYY-MM-DD' / 'YYYY-MM-DDTHH:MM' / 'DD/MM/YYYY' 等。"""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return _dt.datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def event_status(start: str | None, end: str | None, now: _dt.date | None = None) -> str:
    """根据起止日期推断状态: upcoming / ongoing / completed"""
    now = now or today()
    d0 = parse_date(start)
    d1 = parse_date(end) or d0
    if d0 is None:
        return "upcoming"
    if d1 is None:
        d1 = d0
    if now < d0:
        return "upcoming"
    if now > d1:
        return "completed"
    return "ongoing"


def countdown_days(target: str | None, now: _dt.date | None = None) -> int | None:
    d = parse_date(target)
    if d is None:
        return None
    return (d - (now or today())).days


def fmt_countdown(days: int | None) -> str:
    if days is None:
        return "—"
    if days < 0:
        return f"已结束{-days}天"
    if days == 0:
        return "今天"
    if days == 1:
        return "明天"
    return f"{days}天后"


def fmt_date(s: str | None, with_weekday: bool = False) -> str:
    d = parse_date(s)
    if d is None:
        return s or "—"
    out = d.strftime("%Y-%m-%d")
    if with_weekday:
        out += f" {CN_WEEKDAYS[d.weekday()]}"
    return out


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def safe_int(v, default: int | None = None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default
