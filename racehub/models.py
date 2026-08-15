"""数据结构约定（JSON 友好，直接可缓存/序列化）。

所有爬虫返回普通 dict / list，结构如下：
- 赛程:  {series, round, name, short_name, venue, country, flag,
          start, end, status, url, extra}
- 赛果:  {series, round, event_name, title, date, columns, rows, extra}
         rows 每行为 dict（pos/driver/team/laps/time/gap/points/status/car 等）
- 积分:  {series, title, season, rows, extra}
         rows 每行为 {pos, name, points, extra}
- CS2 比赛: {series, event, date, team1, team2, map_scores, best_of,
             status, url, extra}
- 队伍排名: {series, title, date, rows, extra}
         rows 每行为 {pos, name, points, change, extra}
"""
from __future__ import annotations


def event_sort_key(ev: dict):
    """赛程排序键：日期 -> 轮次。"""
    start = ev.get("start") or ev.get("date") or "9999-12-31"
    rnd = ev.get("round") or 0
    try:
        rnd = int(rnd)
    except (TypeError, ValueError):
        rnd = 0
    return (start, rnd)


def match_sort_key(m: dict):
    return m.get("date") or "9999-12-31"
