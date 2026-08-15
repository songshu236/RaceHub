"""WEC 数据爬虫 - 数据来自 FIA WEC 官网与官方计时系统。

- 赛程/积分:  https://www.fiawec.com  （赛季页 + 首页日历滑块）
- 比赛结果:   https://fiawec.alkamelsystems.com （官方计时结果，CSV）
"""
from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup

from ..fetcher import fetch_bytes, fetch_text
from ..utils import event_status, parse_date
from .base import Scraper, SourceError

WEC_HOME = "https://www.fiawec.com/"
WEC_SEASON_URL = "https://www.fiawec.com/en/season/{year}"
TIMING_URL = "https://fiawec.alkamelsystems.com/"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CN_COUNTRIES = {
    "ITA": "意大利", "BEL": "比利时", "FRA": "法国", "BRA": "巴西", "USA": "美国",
    "JPN": "日本", "ESP": "西班牙", "QAT": "卡塔尔", "GBR": "英国", "SAU": "沙特阿拉伯",
    "CHN": "中国", "UAE": "阿联酋", "PRT": "葡萄牙", "CZE": "捷克", "BHR": "巴林",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


class WECScraper(Scraper):
    series = "WEC"
    source_label = "FIA WEC 官网 / 官方计时"

    def __init__(self, year: int | None = None):
        super().__init__()
        self.year = year

    # ------------------------------------------------------------------
    # 赛程（首页日历滑块）
    # ------------------------------------------------------------------
    def fetch_calendar(self) -> list:
        try:
            html, _ = fetch_text(WEC_HOME, timeout=25)
        except Exception as e:
            raise SourceError(f"WEC 官网请求失败: {e}") from e
        soup = BeautifulSoup(html, "html.parser")
        events = []
        for item in soup.select(".calendar-item"):
            cls = item.get("class") or []
            status = "completed" if "completed" in cls else "upcoming"
            a = item.find("a", href=True)
            url = a["href"] if a else ""
            text = item.get_text("|", strip=True)
            parts = [p.strip() for p in text.split("|") if p.strip()]
            if not parts:
                continue
            country = parts[0][:3].upper() if parts else ""
            full = item.get_text(" ", strip=True)

            # 周末范围: From 17 to 19 April 2026
            m = re.search(r"From\s+(\d{1,2})\s+(?:to|au)\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", full)
            start_s = end_s = ""
            year_hint = None
            if m:
                day1, day2, mon, year = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
                y = int(year)
                start_s = f"{y:04d}-{MONTHS.get(mon[:3].lower(), 1):02d}-{day1:02d}"
                end_s = f"{y:04d}-{MONTHS.get(mon[:3].lower(), 1):02d}-{day2:02d}"
                year_hint = y
            else:
                # 单日: 19 Apr
                m2 = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})", full)
                m3 = re.search(r"-(\d{4})", url)
                if m2 and m3:
                    day, mon = int(m2.group(1)), m2.group(2)
                    y = int(m3.group(1))
                    start_s = end_s = f"{y:04d}-{MONTHS.get(mon[:3].lower(), 1):02d}-{day:02d}"
                    year_hint = y

            # 赛事名：日期 token 之后、'From'/'Race info'/'Tickets' 之前的 token 拼接
            name_parts = []
            for p in parts[1:]:
                if p.lower() in ("race info", "tickets", "hospitality", "replay", "race recap"):
                    break
                if p.lower().startswith("from"):
                    break
                if re.fullmatch(r"\d{1,2}", p):
                    continue
                if p[:3].lower() in MONTHS:
                    continue
                name_parts.append(p)
            name = " ".join(name_parts).strip()
            if not name:
                name = full.split("From")[0].strip()

            events.append({
                "series": "WEC",
                "round": None,
                "name": name,
                "short_name": name,
                "venue": name,
                "country": CN_COUNTRIES.get(country, country),
                "flag": _flag(country),
                "start": start_s,
                "end": end_s,
                "status": status,
                "url": "https://www.fiawec.com" + url if url.startswith("/") else url,
                "extra": {"country_code": country, "year": year_hint},
            })
        events.sort(key=lambda e: (e["start"] or "9999", e["name"]))
        return events

    # ------------------------------------------------------------------
    # 积分榜（赛季页 4 张表）
    # ------------------------------------------------------------------
    def fetch_standings(self, year: int | None = None) -> dict:
        y = year or self.year
        if y is None:
            cal = self.fetch_calendar()
            years = [e["extra"].get("year") for e in cal if e["extra"].get("year")]
            y = max(years) if years else None
        if y is None:
            raise SourceError("无法确定 WEC 赛季年份")
        try:
            html, _ = fetch_text(WEC_SEASON_URL.format(year=y), timeout=25)
        except Exception as e:
            raise SourceError(f"WEC 赛季页请求失败: {e}") from e
        soup = BeautifulSoup(html, "html.parser")
        out = {"series": "WEC", "title": f"{y} 赛季积分榜", "season": str(y), "tables": []}
        for tb in soup.find_all("table", class_=re.compile("table-standing")):
            heading = tb.find_previous(["h2", "h3", "h4", "strong", "button"])
            title = heading.get_text(" ", strip=True) if heading else "积分榜"
            title = re.sub(r"\s+", " ", title)
            trs = tb.find_all("tr")
            if not trs:
                continue
            header = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]
            rows = []
            for tr in trs[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                pos = cells[0]
                # 名称列：Manufacturer->1；Team/Drivers->3；否则取前几列中最长的
                name = ""
                if "Manufacturer" in header:
                    name = cells[1] if len(cells) > 1 else ""
                elif any(k in header for k in ("Team", "Drivers")):
                    name = cells[3] if len(cells) > 3 else ""
                if not name:
                    candidates = [c for c in cells[1:4] if c and not re.fullmatch(r"#?\d+", c)]
                    name = max(candidates, key=len) if candidates else ""
                # 每站积分 = 名称之后、最后一列(总分)之前的列
                race_pts = []
                total = ""
                try:
                    name_idx = cells.index(name) if name in cells else 1
                except ValueError:
                    name_idx = 1
                rest = cells[name_idx + 1:]
                if rest:
                    total = rest[-1]
                    race_pts = rest[:-1]
                rows.append({
                    "pos": pos,
                    "name": name,
                    "points": total,
                    "race_pts": race_pts,
                    "extra": {"no": _find_no(cells), "team": name},
                })
            out["tables"].append({"title": title, "rows": rows})
        return out

    # ------------------------------------------------------------------
    # 官方计时：赛季 / 分站 / 结果
    # ------------------------------------------------------------------
    def list_timing_seasons(self) -> list:
        html, _ = fetch_text(TIMING_URL, timeout=25)
        soup = BeautifulSoup(html, "html.parser")
        sel = soup.find("select", {"name": "season"})
        out = []
        if sel:
            for opt in sel.find_all("option"):
                val = opt.get("value", "")
                out.append({"code": val, "label": opt.get_text(strip=True)})
        return out

    def list_timing_events(self, season_code: str) -> list:
        url = f"{TIMING_URL}?season={urllib.parse.quote(season_code)}"
        html, _ = fetch_text(url, timeout=25)
        soup = BeautifulSoup(html, "html.parser")
        sel = soup.find("select", {"name": "evvent"})
        out = []
        if sel:
            for opt in sel.find_all("option"):
                out.append({"code": opt.get("value", ""), "label": opt.get_text(strip=True)})
        return out

    def _race_csv_url(self, season_code: str, event_code: str):
        url = f"{TIMING_URL}?season={urllib.parse.quote(season_code)}&evvent={urllib.parse.quote(event_code)}"
        html, _ = fetch_text(url, timeout=25)
        links = re.findall(r'["\'](Results/[^"\']+\.CSV)["\']', html, re.I)
        candidates = []
        for l in links:
            m = re.search(r"_Race/(?:[^\"' ]*?/)?03_Classification_Race(?:_Hour(?:%20|\s)*(\d+))?\.CSV", l, re.I)
            if m:
                hour = int(m.group(1)) if m.group(1) else 0
                candidates.append((hour, l))
        if not candidates:
            return None
        # 取最大小时数（即最终成绩），无小时则直接分类
        candidates.sort(key=lambda x: x[0], reverse=True)
        return urllib.parse.urljoin(TIMING_URL, candidates[0][1])

    @staticmethod
    def _fetch_csv_text(url: str) -> str:
        """官方计时 CSV 为 UTF-8 但响应头无 charset，必须按字节解码。"""
        raw = fetch_bytes(url, timeout=25)
        for enc in ("utf-8-sig", "utf-8"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("latin-1", errors="replace")

    @staticmethod
    def _parse_wec_csv(text: str) -> list:
        # 兼容 UTF-8 BOM（可能是 ﻿ 或 latin-1 解码的 ï»¿）
        if text.startswith("\ufeff"):
            text = text[1:]
        elif text.startswith("\xef\xbb\xbf"):
            text = text[3:]
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return []
        header = [h.strip().upper() for h in lines[0].split(";")]
        rows = []
        for ln in lines[1:]:
            cells = [c.strip() for c in ln.split(";")]
            row = dict(zip(header, cells))
            drivers = " / ".join(
                d for d in [row.get("DRIVER_1", ""), row.get("DRIVER_2", ""),
                            row.get("DRIVER_3", ""), row.get("DRIVER_4", ""),
                            row.get("DRIVER_5", "")] if d
            )
            rows.append({
                "pos": row.get("POSITION", ""),
                "no": row.get("NUMBER", ""),
                "team": row.get("TEAM", ""),
                "drivers": drivers,
                "car": row.get("VEHICLE", ""),
                "cls": row.get("CLASS", ""),
                "status": row.get("STATUS", ""),
                "laps": row.get("LAPS", ""),
                "total_time": row.get("TOTAL_TIME", ""),
                "gap": row.get("GAP_FIRST", ""),
                "fl_lap": row.get("FL_LAPNUM", ""),
                "fl_time": row.get("FL_TIME", ""),
            })
        return rows

    def fetch_results(self, year: int | None = None) -> dict:
        """抓取该赛季所有已进行分站的最终成绩。"""
        seasons = self.list_timing_seasons()
        if not seasons:
            raise SourceError("无法获取 WEC 官方计时赛季列表")
        # 选当前年份对应的赛季
        y = year or self.year
        if y is None:
            cal = self.fetch_calendar()
            ys = [e["extra"].get("year") for e in cal if e["extra"].get("year")]
            y = max(ys) if ys else None
        season = None
        for s in seasons:
            if y is not None and str(y) in s["label"]:
                season = s
                break
        if season is None:
            season = seasons[-1]
        events = self.list_timing_events(season["code"])
        # 用日历做展示名匹配
        cal = self.fetch_calendar()
        cal_by_norm = {_norm(c["name"]): c for c in cal}

        out = {"series": "WEC", "title": f"{season['label']} 比赛结果", "season": season["label"], "rows": []}
        for ev in events:
            code = ev["code"]
            try:
                csv_url = self._race_csv_url(season["code"], code)
            except Exception:
                continue
            if not csv_url:
                continue
            try:
                text = self._fetch_csv_text(csv_url)
            except Exception:
                continue
            rows = self._parse_wec_csv(text)
            if not rows:
                continue
            ev_name = ev["label"]
            cal_match = cal_by_norm.get(_norm(ev_name))
            out["rows"].append({
                "round": None,
                "event_name": (cal_match or {}).get("name", ev_name.title()),
                "short_name": ev_name.title(),
                "date": (cal_match or {}).get("start", ""),
                "title": "正赛最终成绩",
                "rows": rows,
            })
        return out


def _flag(code: str) -> str:
    flags = {
        "ITA": "🇮🇹", "BEL": "🇧🇪", "FRA": "🇫🇷", "BRA": "🇧🇷", "USA": "🇺🇸",
        "JPN": "🇯🇵", "ESP": "🇪🇸", "QAT": "🇶🇦", "GBR": "🇬🇧", "SAU": "🇸🇦",
        "CHN": "🇨🇳", "UAE": "🇦🇪", "PRT": "🇵🇹", "CZE": "🇨🇿", "BHR": "🇧🇭",
    }
    return flags.get(code.upper(), "")


def _find_no(cells: list) -> str:
    for c in cells:
        if re.fullmatch(r"#\d+", c):
            return c
    return ""
