"""CS2 数据爬虫 - 数据源 HLTV (https://www.hltv.org)。

HLTV 有 Cloudflare 防护且间歇性放行（部分请求 403）。本模块：
  - 多次重试（cloudscraper + 普通 requests 交替）
  - /results 与 /ranking 结构按 2026 实际页面解析
  - /matches(即将进行)、/events(赛事) 若被拦截则从 /results 推导，或留给
    上层回退到内置示例数据并明确标注
  - 各局比分在用户点击比赛时按需抓取比赛详情页

提供：赛事日历(/events)、对阵与赛果(/matches /results)、各局比分(比赛详情页)、
队伍世界排名(/ranking/teams)。
"""
from __future__ import annotations

import datetime as _dt
import re
import time

from bs4 import BeautifulSoup

from ..fetcher import fetch_text
from ..utils import event_status, parse_date
from .base import Scraper, SourceError

HLTV = "https://www.hltv.org"

_MONTH_FULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTHS = {}
for _i, _name in enumerate(_MONTH_FULL, 1):
    MONTHS[_name.lower()] = _i
    MONTHS[_name[:3].lower()] = _i
MONTHS["sept"] = 9


def _month_num(name: str) -> int:
    return MONTHS.get((name or "").strip().lower()[:3], 1)


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _best_logo_url(img) -> str:
    """从 <img> 标签提取最大尺寸的 teamlogo URL（优先 srcset 2x）。"""
    import html as _h
    srcset = img.get("srcset") or ""
    if srcset:
        parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
        def _w(u):
            m = re.search(r"[?&]w=(\d+)", u)
            return int(m.group(1)) if m else 50
        parts.sort(key=_w, reverse=True)
        if parts:
            return _h.unescape(parts[0])
    src = img.get("src") or ""
    return _h.unescape(src) if src else ""


def _team_logo_url(con, selector: str) -> str:
    cell = con.select_one(selector)
    if cell is None:
        return ""
    img = (cell.select_one("img.team-logo.night-only")
           or cell.select_one("img.match-team-logo.night-only")
           or cell.select_one("img.team-logo")
           or cell.select_one("img.match-team-logo")
           or cell.select_one("img[alt]"))
    if img is None:
        return ""
    return _best_logo_url(img)


def _unix_to_date(ms_or_s: str) -> str:
    """把 HLTV 的 data-unix 毫秒时间戳转成 YYYY-MM-DD。"""
    try:
        v = int(float(ms_or_s))
        if v > 10_000_000_000:
            v = v // 1000
        return _dt.datetime.fromtimestamp(v).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _clean_rank_pos(s: str) -> str:
    return re.sub(r"[^0-9]", "", s or "")


def _clean_points(s: str) -> str:
    m = re.search(r"(\d[\d,]*)", s or "")
    return m.group(1).replace(",", "") if m else ""


# 黑底队标（展示用夜间版/白底队标）：MIBR / BIG 抓取 night-only 图标
BLACK_BG_TEAMS = {"mibr", "big"}


def _is_black_bg_team(name: str) -> bool:
    return (name or "").strip().lower() in BLACK_BG_TEAMS


class CS2Scraper(Scraper):
    series = "CS2"
    source_label = "HLTV (hltv.org)"

    def __init__(self, max_attempts: int = 4):
        super().__init__()
        self.max_attempts = max_attempts

    # ------------------------------------------------------------------
    def _get(self, path: str, timeout: int = 20) -> str:
        url = path if path.startswith("http") else HLTV + path
        last_err = None
        for i in range(self.max_attempts):
            # 交替尝试 cloudscraper 与普通 requests
            use_cs = (i % 2 == 0)
            try:
                text, code = fetch_text(url, timeout=timeout, use_cloudscraper=use_cs)
                if code == 200 and len(text) > 20000:
                    return text
                last_err = f"HTTP {code} (len={len(text)})"
            except Exception as e:
                last_err = str(e)[:180]
            if i < self.max_attempts - 1:
                time.sleep(1.5 + i * 1.2)
        raise SourceError(f"HLTV 请求失败（{self.max_attempts} 次尝试）: {last_err}")

    @staticmethod
    def _soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------
    # 赛事日历 (/events)，失败时从 /results 推导
    # ------------------------------------------------------------------
    def fetch_events(self) -> list:
        events = []
        try:
            html = self._get("/events")
            events = self._parse_events_page(html)
        except Exception:
            events = []
        if not events:
            # 兜底：从赛果页的事件名+日期推导
            try:
                html = self._get("/results")
                events = self._derive_events_from_results(html)
            except Exception:
                raise SourceError("HLTV 赛事页与赛果页均不可用")
        events.sort(key=lambda e: (e["start"] or "9999", e["name"]))
        return events

    def _parse_events_page(self, html: str) -> list:
        soup = self._soup(html)
        out = []
        seen = set()
        anchors = (soup.select("a.standard-box.big-event")
                   + soup.select("a.standard-box.small-event")
                   + soup.select("a.ongoing-event"))
        for a in anchors:
            href = a.get("href", "")
            mid = re.search(r"/events/(\d+)", href)
            eid = mid.group(1) if mid else href
            if not eid or eid in seen:
                continue
            seen.add(eid)
            name = _norm_name(a.select_one(".big-event-name").get_text(" ", strip=True)) if a.select_one(".big-event-name") else ""
            if not name:
                name_el = (a.select_one(".event-name-small .text-ellipsis")
                           or a.select_one("td.col-value.event-col .text-ellipsis")
                           or a.select_one("td.event-col .text-ellipsis"))
                if name_el is not None:
                    name = _norm_name(name_el.get_text(" ", strip=True))
            if not name:
                name = _norm_name(a.get_text(" ", strip=True))
            if not name:
                continue
            # 去掉 HLTV 追加的 LAN/ONLINE 标记
            name = re.sub(r"\s+(LAN|ONLINE)\s*$", "", name, flags=re.I)
            loc = a.select_one(".big-event-location, .event-location")
            location = _norm_name(loc.get_text(" ", strip=True)) if loc else ""
            # 日期：data-unix 毫秒
            start = end = ""
            unix_els = a.select("td.col-date span[data-unix]") or a.select("span[data-unix]")
            if unix_els:
                start = _unix_to_date(unix_els[0].get("data-unix", ""))
                end = _unix_to_date(unix_els[1].get("data-unix", "")) if len(unix_els) > 1 else start
            if not start:
                date_txt = a.select_one(".col-date")
                start, end = self._parse_event_dates(date_txt.get_text(" ", strip=True) if date_txt else "", href)
            # 奖金：td.col-value 中 title/文本以 $ 开头的
            prize = ""
            for td in a.select("td.col-value"):
                t = td.get("title") or td.get_text(strip=True)
                if t and t.startswith("$"):
                    prize = _norm_name(t)
                    break
            if not prize:
                pel = a.select_one(".prizePoolEllipsis, .prize-pool")
                if pel:
                    prize = _norm_name(pel.get_text(" ", strip=True))
            # 赛事图标（HLTV /events 页的方形 eventlogo，与队标同一套本地化/白底逻辑）
            logo = ""
            logo_img = a.select_one("img.logo.day-only") or a.select_one("img.logo")
            if logo_img is not None:
                logo = _best_logo_url(logo_img)
            out.append({
                "series": "CS2", "round": None, "name": name, "short_name": name,
                "venue": location, "country": "", "flag": "",
                "start": start, "end": end, "status": event_status(start, end),
                "url": HLTV + href if href.startswith("/") else href,
                "extra": {"prize_pool": prize, "event_id": eid, "logo": logo},
            })
        return out

    @staticmethod
    def _parse_event_dates(date_txt: str, href: str, soup=None, el=None) -> tuple[str, str]:
        if not date_txt:
            return "", ""
        # 年份：优先取月份区块标题，如 "August 2026"
        year = ""
        if soup is not None:
            head = el.find_previous("div", class_=re.compile("events-month"))
            if head:
                m = re.search(r"(\d{4})", head.get_text(" ", strip=True))
                if m:
                    year = m.group(1)
        def _mk(mon, d):
            y = year
            if not y:
                y = str(_dt.date.today().year)
            return f"{y}-{_month_num(mon):02d}-{int(d):02d}"
        # Aug 26th - Sep 6th
        m = re.search(r"([A-Za-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?\s*-\s*([A-Za-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?", date_txt)
        if m:
            return _mk(m.group(1), m.group(2)), _mk(m.group(3), m.group(4))
        # Aug 26th
        m = re.search(r"([A-Za-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?", date_txt)
        if m:
            d = _mk(m.group(1), m.group(2))
            return d, d
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", date_txt)
        if m:
            d, mo, y = m.groups()
            y = "20" + y if len(y) == 2 else y
            return f"{y}-{int(mo):02d}-{int(d):02d}", f"{y}-{int(mo):02d}-{int(d):02d}"
        return "", ""

    @staticmethod
    def _derive_events_from_results(html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        out = {}
        for sub in soup.select(".results-sublist"):
            date = ""
            prev = sub.find_previous("div", class_=re.compile("standard-headline"))
            if prev:
                date = CS2Scraper._parse_date_headline(prev.get_text(" ", strip=True))
            for con in sub.select(".result-con"):
                ev = con.select_one(".event-name")
                if not ev:
                    continue
                name = _norm_name(ev.get_text(" ", strip=True))
                if not name or name in out:
                    continue
                eid = str(abs(hash(name)))
                out[name] = {
                    "series": "CS2", "round": None, "name": name, "short_name": name,
                    "venue": "", "country": "", "flag": "",
                    "start": date, "end": date, "status": event_status(date, date),
                    "url": HLTV, "extra": {"prize_pool": "", "event_id": eid, "derived": True, "logo": ""},
                }
        return list(out.values())

    @staticmethod
    def _parse_date_headline(txt: str) -> str:
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})", txt)
        if m:
            mon, d, y = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{_month_num(mon):02d}-{d:02d}"
        return ""

    # ------------------------------------------------------------------
    # 对阵与赛果
    # ------------------------------------------------------------------
    def fetch_matches(self, limit: int = 40) -> dict:
        out = {"series": "CS2", "title": "近期对阵与赛果", "rows": [], "extra": {}}
        seen = set()
        sections_ok = 0
        # 近期赛果（结构已确认）
        try:
            html = self._get("/results")
            for row in self._parse_results_page(html):
                key = row.get("url", "")
                if key in seen:
                    continue
                seen.add(key)
                out["rows"].append(row)
            sections_ok += 1
        except Exception:
            pass
        # 即将进行的比赛（结构可能随站点更新，容错解析）
        try:
            html = self._get("/matches")
            for row in self._parse_upcoming_page(html):
                key = row.get("url", "")
                if key in seen:
                    continue
                seen.add(key)
                out["rows"].append(row)
            sections_ok += 1
        except Exception:
            pass
        # 即将进行排前面（按时间先后），近期赛果按最新在前跟在后面
        upcoming = [r for r in out["rows"] if r.get("status") != "finished"]
        finished = [r for r in out["rows"] if r.get("status") == "finished"]
        upcoming.sort(key=lambda m: m.get("date") or "9999")
        finished.sort(key=lambda m: m.get("date") or "0000", reverse=True)
        out["rows"] = upcoming + finished
        if limit and limit > 0:
            out["rows"] = out["rows"][:limit]
        if not out["rows"] and sections_ok == 0:
            raise SourceError("HLTV 对阵/赛果页均不可用")
        return out

    def _parse_results_page(self, html: str) -> list:
        soup = self._soup(html)
        rows = []
        seen_urls = set()
        for sub in soup.select(".results-sublist"):
            date = ""
            head = sub.select_one("span.standard-headline, div.standard-headline")
            if head:
                date = self._parse_date_headline(head.get_text(" ", strip=True))
            for con in sub.select(".result-con"):
                row = self._parse_result_con(con, date)
                if row and row.get("url") not in seen_urls:
                    seen_urls.add(row["url"])
                    rows.append(row)
        # 未分组 / featured
        for con in soup.select(".result-con"):
            if con.find_parent(class_="results-sublist"):
                continue
            row = self._parse_result_con(con, "")
            if row and row.get("url") not in seen_urls:
                seen_urls.add(row["url"])
                rows.append(row)
        return rows

    def _parse_result_con(self, con, date: str) -> dict | None:
        a = con.find("a", href=True) if con.name != "a" else con
        if a is None or "matches" not in (a.get("href") or ""):
            return None
        href = a["href"]
        mid = re.search(r"/matches/(\d+)", href)
        # 行内 unix 时间戳优先
        unix = con.get("data-zonedgrouping-entry-unix") or ""
        if unix:
            d = _unix_to_date(unix)
            if d:
                date = d
        t1 = con.select_one(".line-align.team1 .team")
        t2 = con.select_one(".line-align.team2 .team")
        lost = con.select_one(".result-score .score-lost")
        won = con.select_one(".result-score .score-won")
        ev = con.select_one(".event-name")
        box = con.select_one(".map.map-text, .map-text")
        score = ""
        if lost is not None and won is not None:
            score = f"{lost.get_text(strip=True)} : {won.get_text(strip=True)}"
        logo1 = _team_logo_url(con, ".line-align.team1")
        logo2 = _team_logo_url(con, ".line-align.team2")
        return {
            "series": "CS2",
            "event": _norm_name(ev.get_text(" ", strip=True)) if ev else "",
            "date": date,
            "team1": {"name": _norm_name(t1.get_text(" ", strip=True)) if t1 else "",
                      "logo": logo1},
            "team2": {"name": _norm_name(t2.get_text(" ", strip=True)) if t2 else "",
                      "logo": logo2},
            "map_scores": [],
            "best_of": 0,
            "status": "finished",
            "url": HLTV + href,
            "extra": {"match_id": mid.group(1) if mid else "",
                      "score_text": score,
                      "format": _norm_name(box.get_text(" ", strip=True)) if box else ""},
        }

    def _parse_upcoming_page(self, html: str) -> list:
        soup = self._soup(html)
        rows = []
        seen = set()
        # 新版页面：每个比赛是一个 div.match（含赛事名/时间/两队）
        for m in soup.select("div.match"):
            a = m.select_one("a[href*='/matches/']")
            if a is None:
                continue
            href = a.get("href", "")
            mid = re.search(r"/matches/(\d+)", href)
            if not mid:
                continue
            if mid.group(1) in seen:
                continue
            seen.add(mid.group(1))
            t1 = m.select_one(".match-teams .match-team.team1 .match-teamname")
            t2 = m.select_one(".match-teams .match-team.team2 .match-teamname")
            tm = m.select_one(".match-time")
            ev = m.select_one(".match-event")
            meta = m.select_one(".match-meta")
            live = m.select_one(".match-rating.matchLive") is not None
            date = _unix_to_date(tm.get("data-unix", "")) if tm else ""
            ev_name = ""
            if ev is not None:
                ev_name = ev.get("data-event-headline") or ev.get_text(" ", strip=True)
            best_of = 0
            if meta is not None:
                bm = re.search(r"bo(\d+)", _norm_name(meta.get_text(" ", strip=True)), re.I)
                if bm:
                    best_of = int(bm.group(1))
            rows.append({
                "series": "CS2",
                "event": _norm_name(ev_name),
                "date": date,
                "team1": {"name": _norm_name(t1.get_text(" ", strip=True)) if t1 else "TBD",
                          "logo": _team_logo_url(m, ".match-team.team1")},
                "team2": {"name": _norm_name(t2.get_text(" ", strip=True)) if t2 else "TBD",
                          "logo": _team_logo_url(m, ".match-team.team2")},
                "map_scores": [],
                "best_of": best_of,
                "status": "ongoing" if live else "upcoming",
                "url": HLTV + href if href.startswith("/") else href,
                "extra": {"match_id": mid.group(1),
                          "event_id": ev.get("data-event-id") if ev is not None else ""},
            })
        return rows

    @staticmethod
    def _parse_match_time(txt: str) -> str:
        if not txt:
            return ""
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", txt)
        if m:
            d, mo, y = m.groups()
            y = "20" + y if len(y) == 2 else y
            return f"{y}-{int(mo):02d}-{int(d):02d}"
        m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})", txt)
        if m:
            d, mo, y = m.groups()
            months = {name[:3].title(): i for i, name in enumerate(
                ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
            return f"{y}-{months.get(mo[:3].title(), 1):02d}-{int(d):02d}"
        return ""

    # ------------------------------------------------------------------
    # 单场比赛详情（各局比分）— 用户点击时按需抓取
    # ------------------------------------------------------------------
    def fetch_match_detail(self, match_id: str) -> dict:
        html = self._get(f"/matches/{match_id}")
        soup = self._soup(html)
        out = {"match_id": match_id, "team1": "", "team2": "", "event": "", "map_scores": []}
        t1 = soup.select_one(".team1 .teamName, .team-left .teamName, .team1 .team")
        t2 = soup.select_one(".team2 .teamName, .team-right .teamName, .team2 .team")
        out["team1"] = _norm_name(t1.get_text(" ", strip=True)) if t1 else ""
        out["team2"] = _norm_name(t2.get_text(" ", strip=True)) if t2 else ""
        ev = soup.select_one(".event .text, .tournament, .event-name, .event")
        if ev:
            out["event"] = _norm_name(ev.get_text(" ", strip=True))
        for holder in soup.select(".mapholder"):
            mapname = holder.select_one(".mapname")
            left = holder.select_one(".results-left, .results-team-score, .score-left, .results .results-team-score")
            right = holder.select_one(".results-right, .results-opponent-score, .score-right, .results .results-opponent-score")
            m = {"map": mapname.get_text(" ", strip=True) if mapname else ""}
            if left is not None and right is not None:
                m["t1"] = left.get_text(strip=True)
                m["t2"] = right.get_text(strip=True)
            else:
                txt = _norm_name(holder.get_text(" ", strip=True))
                mm = re.search(r"(\d+)\s*[:\-]\s*(\d+)", txt)
                if mm:
                    m["t1"], m["t2"] = mm.group(1), mm.group(2)
            out["map_scores"].append(m)
        return out

    # ------------------------------------------------------------------
    # 队伍世界排名 (HLTV)
    # ------------------------------------------------------------------
    def fetch_ranking(self) -> dict:
        html = self._get("/ranking/teams")
        soup = self._soup(html)
        out = {"series": "CS2", "title": "HLTV 世界排名", "rows": []}
        for team in soup.select(".ranked-team"):
            rank = team.select_one(".rank, .rank-number, .position, .wide-position")
            name = team.select_one(".team-name, .teamName, .name, .team .team-name")
            points = team.select_one(".points")
            change = team.select_one(".change, .rank-change")
            name_txt = _norm_name(name.get_text(" ", strip=True)) if name else ""
            if not name_txt:
                continue
            logo = ""
            if _is_black_bg_team(name_txt):
                logo_el = team.select_one(".team-logo img.night-only") or team.select_one(".team-logo img")
            else:
                logo_el = team.select_one(".team-logo img")
            if logo_el is not None:
                logo = _best_logo_url(logo_el)
            out["rows"].append({
                "pos": _clean_rank_pos(rank.get_text(" ", strip=True) if rank else ""),
                "name": name_txt,
                "points": _clean_points(points.get_text(" ", strip=True) if points else ""),
                "change": _norm_name(change.get_text(" ", strip=True) if change else ""),
                "extra": {"logo": logo},
            })
        if not out["rows"]:
            raise SourceError("HLTV 排名页解析为空")
        return out

    # ------------------------------------------------------------------
    # V社积分排行 (Valve Regional Standing, VRS) - /valve-ranking/teams
    # ------------------------------------------------------------------
    def fetch_valve_ranking(self) -> dict:
        """抓取 HLTV 的 V社（Valve）积分排行页，结构与 /ranking 类似但带地区。"""
        html = self._get("/valve-ranking/teams")
        soup = self._soup(html)
        out = {"series": "CS2", "title": "V社积分排行 (VRS)", "rows": []}
        for team in soup.select(".ranked-team"):
            rank = team.select_one(".rank, .rank-number, .position, .wide-position")
            name = team.select_one(".team-name, .teamName, .name, .team .team-name")
            points = team.select_one(".points")
            region = team.select_one(".region")
            name_txt = _norm_name(name.get_text(" ", strip=True)) if name else ""
            if not name_txt:
                continue
            logo = ""
            if _is_black_bg_team(name_txt):
                logo_el = team.select_one(".team-logo img.night-only") or team.select_one(".team-logo img")
            else:
                logo_el = team.select_one(".team-logo img")
            if logo_el is not None:
                logo = _best_logo_url(logo_el)
            out["rows"].append({
                "pos": _clean_rank_pos(rank.get_text(" ", strip=True) if rank else ""),
                "name": name_txt,
                "points": _clean_points(points.get_text(" ", strip=True) if points else ""),
                "region": _norm_name(region.get_text(" ", strip=True) if region else ""),
                "extra": {"logo": logo},
            })
        if not out["rows"]:
            raise SourceError("HLTV VRS 排行页解析为空")
        return out
