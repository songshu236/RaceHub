"""F1 数据爬虫 - 使用 Ergast 镜像 (https://api.jolpi.ca/ergast)。

提供：赛季赛程、每站比赛结果、车手/车队积分榜。
"""
from __future__ import annotations

import json
import re

import requests

from ..fetcher import fetch_text
from ..utils import event_status
from .base import Scraper, SourceError

API_BASE = "https://api.jolpi.ca/ergast/f1"

# 常用赛道/大奖赛中文名（仅供展示，找不到时保留英文）
CN_NAMES = {
    "Australian Grand Prix": "澳大利亚大奖赛",
    "Chinese Grand Prix": "中国大奖赛",
    "Japanese Grand Prix": "日本大奖赛",
    "Bahrain Grand Prix": "巴林大奖赛",
    "Saudi Arabian Grand Prix": "沙特阿拉伯大奖赛",
    "Miami Grand Prix": "迈阿密大奖赛",
    "Emilia Romagna Grand Prix": "艾米利亚-罗马涅大奖赛",
    "Monaco Grand Prix": "摩纳哥大奖赛",
    "Spanish Grand Prix": "西班牙大奖赛",
    "Canadian Grand Prix": "加拿大大奖赛",
    "Austrian Grand Prix": "奥地利大奖赛",
    "British Grand Prix": "英国大奖赛",
    "Belgian Grand Prix": "比利时大奖赛",
    "Hungarian Grand Prix": "匈牙利大奖赛",
    "Dutch Grand Prix": "荷兰大奖赛",
    "Italian Grand Prix": "意大利大奖赛",
    "Azerbaijan Grand Prix": "阿塞拜疆大奖赛",
    "Singapore Grand Prix": "新加坡大奖赛",
    "United States Grand Prix": "美国大奖赛",
    "Mexico City Grand Prix": "墨西哥城大奖赛",
    "Brazilian Grand Prix": "巴西大奖赛",
    "Las Vegas Grand Prix": "拉斯维加斯大奖赛",
    "Qatar Grand Prix": "卡塔尔大奖赛",
    "Abu Dhabi Grand Prix": "阿布扎比大奖赛",
}


def _cn_race_name(name: str) -> str:
    return CN_NAMES.get(name, name)


class F1Scraper(Scraper):
    series = "F1"
    source_label = "Ergast API (api.jolpi.ca)"

    def __init__(self, season: str = "current"):
        super().__init__()
        self.season = season

    # ---------- helpers ----------
    def _get_json(self, path: str):
        url = f"{API_BASE}/{path}"
        try:
            text, code = fetch_text(url, timeout=20, headers={"Accept": "application/json"})
            return json.loads(text)
        except Exception as e:
            raise SourceError(f"F1 请求失败 ({url}): {e}") from e

    def _get_all_results(self, path: str) -> list:
        """分页拉取全部比赛结果（镜像接口 limit 上限 100）。"""
        limit = 100
        offset = 0
        races_by_round = {}
        while True:
            url = f"{API_BASE}/{path}?limit={limit}&offset={offset}"
            try:
                text, _ = fetch_text(url, timeout=20, headers={"Accept": "application/json"})
                data = json.loads(text)
            except Exception as e:
                raise SourceError(f"F1 请求失败 ({url}): {e}") from e
            md = data.get("MRData", {})
            rt = md.get("RaceTable", {})
            total = int(md.get("total", 0) or 0)
            for race in rt.get("Races", []):
                rnd = race.get("round")
                races_by_round.setdefault(rnd, {"race": race, "results": []})
                races_by_round[rnd]["results"].extend(race.get("Results", []))
            have = sum(len(v["results"]) for v in races_by_round.values())
            if have >= total or offset >= total:
                break
            offset += limit
        # 组装每个分站的完整数据
        out = []
        for rnd in sorted(races_by_round, key=lambda r: int(r or 0)):
            item = dict(races_by_round[rnd]["race"])
            item["Results"] = races_by_round[rnd]["results"]
            out.append(item)
        return out

    @staticmethod
    def _race_to_event(r: dict) -> dict:
        c = r.get("Circuit", {})
        name = r.get("raceName", "")
        date = r.get("date", "")
        time = r.get("time", "") or ""
        start = f"{date}T{time[:5]}" if time else date
        return {
            "series": "F1",
            "round": r.get("round"),
            "name": _cn_race_name(name),
            "short_name": name,
            "venue": c.get("circuitName", ""),
            "country": c.get("Location", {}).get("country", ""),
            "flag": "",
            "start": date,
            "end": date,
            "status": event_status(date, date),
            "url": r.get("url", ""),
            "extra": {"locality": c.get("Location", {}).get("locality", ""), "time": time},
        }

    # ---------- calendar ----------
    def fetch_calendar(self) -> list:
        data = self._get_json(f"{self.season}.json")
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        events = [self._race_to_event(r) for r in races]
        # 按轮次排序
        events.sort(key=lambda e: (e["start"] or "", int(e["round"] or 0)))
        return events

    # ---------- results ----------
    def fetch_results(self, round_num: int | None = None) -> dict:
        path = f"{self.season}/results.json" if round_num is None else f"{self.season}/{round_num}/results.json"
        if round_num is None:
            races = self._get_all_results(path)
        else:
            data = self._get_json(path)
            races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        out = {"series": "F1", "title": "比赛结果", "rows": [], "extra": {}}
        for race in races:
            ev = self._race_to_event(race)
            rows = []
            for res in race.get("Results", []):
                d = res.get("Driver", {})
                cons = res.get("Constructor", {})
                fl = res.get("FastestLap", {})
                rows.append({
                    "pos": res.get("position"),
                    "no": res.get("number"),
                    "driver": f"{d.get('givenName', '')} {d.get('familyName', '')}".strip(),
                    "code": d.get("code", ""),
                    "team": cons.get("name", ""),
                    "laps": res.get("laps"),
                    "time": (res.get("Time") or {}).get("time", ""),
                    "gap": "",
                    "points": res.get("points"),
                    "status": res.get("status", ""),
                    "fastest_lap": fl.get("Time", {}).get("time", "") if fl else "",
                    "fl_rank": fl.get("rank", "") if fl else "",
                })
            out["rows"].append({
                "round": race.get("round"),
                "event_name": ev["name"],
                "short_name": ev["short_name"],
                "date": race.get("date", ""),
                "title": "正赛结果",
                "rows": rows,
            })
        if races:
            out["extra"]["season"] = races[0].get("season", self.season)
        else:
            out["extra"]["season"] = self.season
        return out

    # ---------- standings ----------
    def fetch_standings(self) -> dict:
        out = {"series": "F1", "title": "积分榜", "tables": []}
        for kind, path, title in (
            ("driver", f"{self.season}/driverstandings.json", "车手积分榜"),
            ("constructor", f"{self.season}/constructorstandings.json", "车队积分榜"),
        ):
            data = self._get_json(path)
            lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            rows = []
            season = data.get("MRData", {}).get("StandingsTable", {}).get("season", "")
            round_no = data.get("MRData", {}).get("StandingsTable", {}).get("round", "")
            for sl in lists:
                if kind == "driver":
                    for s in sl.get("DriverStandings", []):
                        d = s.get("Driver", {})
                        rows.append({
                            "pos": s.get("position"),
                            "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                            "code": d.get("code", ""),
                            "points": s.get("points"),
                            "wins": s.get("wins"),
                            "team": (s.get("Constructors") or [{}])[0].get("name", ""),
                        })
                else:
                    for s in sl.get("ConstructorStandings", []):
                        c = s.get("Constructor", {})
                        rows.append({
                            "pos": s.get("position"),
                            "name": c.get("name", ""),
                            "points": s.get("points"),
                            "wins": s.get("wins"),
                        })
            out["tables"].append({
                "title": title,
                "season": season,
                "round": round_no,
                "rows": rows,
                "kind": kind,
            })
        return out
