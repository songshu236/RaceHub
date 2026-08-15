"""生成内置示例数据（data/demo/*.json）。
F1/WEC 使用真实在线数据生成；CS2 使用精心构造的示例数据（HLTV 结构）。
"""
from __future__ import annotations

import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEMO = ROOT / "data" / "demo"
DEMO.mkdir(parents=True, exist_ok=True)


def save(name: str, payload):
    p = DEMO / name
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", p.name)


def gen_real():
    from racehub.scrapers import F1Scraper, WECScraper
    try:
        f1 = F1Scraper()
        save("F1_calendar.json", f1.fetch_calendar())
        save("F1_results.json", f1.fetch_results())
        save("F1_standings.json", f1.fetch_standings())
        print("F1 demo generated from live data")
    except Exception as e:
        print("F1 live failed:", str(e)[:200])
    try:
        wec = WECScraper(year=2026)
        save("WEC_calendar.json", wec.fetch_calendar())
        save("WEC_results.json", wec.fetch_results(year=2026))
        save("WEC_standings.json", wec.fetch_standings(year=2026))
        print("WEC demo generated from live data")
    except Exception as e:
        print("WEC live failed:", str(e)[:200])


def gen_cs2():
    # 优先抓取 HLTV 实时数据；失败时使用内置示例数据
    try:
        from racehub.scrapers.cs2 import CS2Scraper
        s = CS2Scraper(max_attempts=4)
        cal = s.fetch_events()
        if cal:
            save("CS2_calendar.json", cal)
        ms = s.fetch_matches(limit=40)
        if ms.get("rows"):
            save("CS2_matches.json", ms)
        rk = s.fetch_ranking()
        if rk.get("rows"):
            save("CS2_ranking.json", rk)
        print("CS2 demo generated from HLTV live data")
        return
    except Exception as e:
        print("CS2 live failed, use curated demo:", str(e)[:120])

    # ---------------- CS2 赛事日历（示例） ----------------
    cal = [
        {"series": "CS2", "round": None, "name": "IEM Cologne 2026", "short_name": "IEM Cologne 2026",
         "venue": "LANXESS Arena, Cologne", "country": "德国", "flag": "🇩🇪",
         "start": "2026-07-10", "end": "2026-07-26", "status": "completed",
         "url": "https://www.hltv.org/events/5870/iem-cologne-2026",
         "extra": {"prize_pool": "$1,000,000", "event_id": "5870"}},
        {"series": "CS2", "round": None, "name": "ESL Pro League Season 22", "short_name": "EPL S22",
         "venue": "Online / St. Julian's", "country": "马耳他", "flag": "🇲🇹",
         "start": "2026-08-05", "end": "2026-09-21", "status": "ongoing",
         "url": "https://www.hltv.org/events/5891/esl-pro-league-season-22",
         "extra": {"prize_pool": "$850,000", "event_id": "5891"}},
        {"series": "CS2", "round": None, "name": "BLAST Premier: Fall Final 2026", "short_name": "BLAST Fall Final",
         "venue": "Copenhagen", "country": "丹麦", "flag": "🇩🇰",
         "start": "2026-09-23", "end": "2026-09-27", "status": "upcoming",
         "url": "https://www.hltv.org/events/5899/blast-premier-fall-final-2026",
         "extra": {"prize_pool": "$425,000", "event_id": "5899"}},
        {"series": "CS2", "round": None, "name": "PGL Major Copenhagen 2026", "short_name": "PGL Major 2026",
         "venue": "Royal Arena, Copenhagen", "country": "丹麦", "flag": "🇩🇰",
         "start": "2026-10-11", "end": "2026-10-25", "status": "upcoming",
         "url": "https://www.hltv.org/events/5903/pgl-major-copenhagen-2026",
         "extra": {"prize_pool": "$1,250,000", "event_id": "5903"}},
        {"series": "CS2", "round": None, "name": "BLAST Premier: World Final 2026", "short_name": "BLAST World Final",
         "venue": "Singapore", "country": "新加坡", "flag": "🇸🇬",
         "start": "2026-11-03", "end": "2026-11-08", "status": "upcoming",
         "url": "https://www.hltv.org/events/5911/blast-premier-world-final-2026",
         "extra": {"prize_pool": "$1,000,000", "event_id": "5911"}},
        {"series": "CS2", "round": None, "name": "Perfect World Shanghai Major 2026", "short_name": "Shanghai Major",
         "venue": "Shanghai", "country": "中国", "flag": "🇨🇳",
         "start": "2026-12-01", "end": "2026-12-13", "status": "upcoming",
         "url": "https://www.hltv.org/events/5918/perfect-world-shanghai-major-2026",
         "extra": {"prize_pool": "$1,250,000", "event_id": "5918"}},
        {"series": "CS2", "round": None, "name": "IEM Katowice 2027", "short_name": "IEM Katowice 2027",
         "venue": "Spodek Arena, Katowice", "country": "波兰", "flag": "🇵🇱",
         "start": "2027-02-07", "end": "2027-02-14", "status": "upcoming",
         "url": "https://www.hltv.org/events/5926/iem-katowice-2027",
         "extra": {"prize_pool": "$1,000,000", "event_id": "5926"}},
    ]
    save("CS2_calendar.json", cal)

    # ---------------- CS2 对阵与赛果（示例，含各局比分） ----------------
    matches = [
        {"series": "CS2", "event": "IEM Cologne 2026", "date": "2026-07-26",
         "team1": {"name": "Vitality"}, "team2": {"name": "FaZe"},
         "map_scores": [{"map": "Inferno", "t1": 13, "t2": 7}, {"map": "Nuke", "t1": 11, "t2": 13}, {"map": "Mirage", "t1": 13, "t2": 9}],
         "best_of": 3, "status": "finished", "url": "https://www.hltv.org/matches/2381100/vitality-vs-faze-iem-cologne-2026",
         "extra": {"match_id": "2381100", "score_text": "2 : 1"}},
        {"series": "CS2", "event": "IEM Cologne 2026", "date": "2026-07-25",
         "team1": {"name": "Spirit"}, "team2": {"name": "Vitality"},
         "map_scores": [{"map": "Dust2", "t1": 13, "t2": 10}, {"map": "Anubis", "t1": 9, "t2": 13}, {"map": "Ancient", "t1": 11, "t2": 13}],
         "best_of": 3, "status": "finished", "url": "https://www.hltv.org/matches/2381090/spirit-vs-vitality-iem-cologne-2026",
         "extra": {"match_id": "2381090", "score_text": "1 : 2"}},
        {"series": "CS2", "event": "IEM Cologne 2026", "date": "2026-07-24",
         "team1": {"name": "MOUZ"}, "team2": {"name": "FaZe"},
         "map_scores": [{"map": "Mirage", "t1": 10, "t2": 13}, {"map": "Nuke", "t1": 13, "t2": 6}, {"map": "Inferno", "t1": 8, "t2": 13}],
         "best_of": 3, "status": "finished", "url": "https://www.hltv.org/matches/2381082/mouz-vs-faze-iem-cologne-2026",
         "extra": {"match_id": "2381082", "score_text": "1 : 2"}},
        {"series": "CS2", "event": "ESL Pro League Season 22", "date": "2026-08-14",
         "team1": {"name": "NAVI"}, "team2": {"name": "G2"},
         "map_scores": [{"map": "Anubis", "t1": 13, "t2": 9}, {"map": "Inferno", "t1": 16, "t2": 14}],
         "best_of": 2, "status": "finished", "url": "https://www.hltv.org/matches/2381500/navi-vs-g2-esl-pro-league-season-22",
         "extra": {"match_id": "2381500", "score_text": "2 : 0"}},
        {"series": "CS2", "event": "ESL Pro League Season 22", "date": "2026-08-15",
         "team1": {"name": "Liquid"}, "team2": {"name": "FURIA"},
         "map_scores": [], "best_of": 3, "status": "upcoming",
         "url": "https://www.hltv.org/matches/2381520/liquid-vs-furia-esl-pro-league-season-22",
         "extra": {"match_id": "2381520"}},
        {"series": "CS2", "event": "ESL Pro League Season 22", "date": "2026-08-16",
         "team1": {"name": "MOUZ"}, "team2": {"name": "Eternal Fire"},
         "map_scores": [], "best_of": 3, "status": "upcoming",
         "url": "https://www.hltv.org/matches/2381533/mouz-vs-eternal-fire-esl-pro-league-season-22",
         "extra": {"match_id": "2381533"}},
        {"series": "CS2", "event": "ESL Pro League Season 22", "date": "2026-08-17",
         "team1": {"name": "Falcons"}, "team2": {"name": "Virtus.pro"},
         "map_scores": [], "best_of": 3, "status": "upcoming",
         "url": "https://www.hltv.org/matches/2381541/falcons-vs-virtus-pro-esl-pro-league-season-22",
         "extra": {"match_id": "2381541"}},
        {"series": "CS2", "event": "BLAST Premier: Fall Final 2026", "date": "2026-09-23",
         "team1": {"name": "Vitality"}, "team2": {"name": "Spirit"},
         "map_scores": [], "best_of": 3, "status": "upcoming",
         "url": "https://www.hltv.org/matches/2382100/vitality-vs-spirit-blast-premier-fall-final-2026",
         "extra": {"match_id": "2382100"}},
        {"series": "CS2", "event": "PGL Major Copenhagen 2026", "date": "2026-10-11",
         "team1": {"name": "NAVI"}, "team2": {"name": "MOUZ"},
         "map_scores": [], "best_of": 1, "status": "upcoming",
         "url": "https://www.hltv.org/matches/2383000/navi-vs-mouz-pgl-major-copenhagen-2026",
         "extra": {"match_id": "2383000"}},
    ]
    save("CS2_matches.json", {"series": "CS2", "title": "近期对阵与赛果", "rows": matches, "extra": {}})

    # ---------------- CS2 世界排名（示例，仿 HLTV 排名页） ----------------
    ranking = [
        {"pos": "1", "name": "Vitality", "points": "997", "change": "-", "extra": {}},
        {"pos": "2", "name": "Spirit", "points": "921", "change": "+1", "extra": {}},
        {"pos": "3", "name": "FaZe", "points": "885", "change": "-1", "extra": {}},
        {"pos": "4", "name": "NAVI", "points": "802", "change": "-", "extra": {}},
        {"pos": "5", "name": "MOUZ", "points": "744", "change": "-", "extra": {}},
        {"pos": "6", "name": "G2", "points": "689", "change": "+2", "extra": {}},
        {"pos": "7", "name": "Liquid", "points": "641", "change": "-1", "extra": {}},
        {"pos": "8", "name": "Falcons", "points": "598", "change": "-1", "extra": {}},
        {"pos": "9", "name": "Virtus.pro", "points": "547", "change": "+1", "extra": {}},
        {"pos": "10", "name": "Eternal Fire", "points": "512", "change": "-1", "extra": {}},
        {"pos": "11", "name": "FURIA", "points": "468", "change": "-", "extra": {}},
        {"pos": "12", "name": "MongolZ", "points": "433", "change": "+2", "extra": {}},
        {"pos": "13", "name": "The MongolZ", "points": "431", "change": "-", "extra": {}},
        {"pos": "14", "name": "Astralis", "points": "402", "change": "-2", "extra": {}},
        {"pos": "15", "name": "3DMAX", "points": "371", "change": "+1", "extra": {}},
        {"pos": "16", "name": "Heroic", "points": "340", "change": "-1", "extra": {}},
        {"pos": "17", "name": "paiN", "points": "312", "change": "+1", "extra": {}},
        {"pos": "18", "name": "Complexity", "points": "288", "change": "-1", "extra": {}},
        {"pos": "19", "name": "BIG", "points": "255", "change": "-", "extra": {}},
        {"pos": "20", "name": "Imperial", "points": "231", "change": "-", "extra": {}},
        {"pos": "21", "name": "ENCE", "points": "205", "change": "+1", "extra": {}},
        {"pos": "22", "name": "BetBoom", "points": "184", "change": "-1", "extra": {}},
        {"pos": "23", "name": "9 Pandas", "points": "160", "change": "+2", "extra": {}},
        {"pos": "24", "name": "Sashi", "points": "142", "change": "-1", "extra": {}},
        {"pos": "25", "name": "GamerLegion", "points": "121", "change": "-1", "extra": {}},
        {"pos": "26", "name": "Rare Atom", "points": "105", "change": "+1", "extra": {}},
        {"pos": "27", "name": "Lynn Vision", "points": "88", "change": "-1", "extra": {}},
        {"pos": "28", "name": "TYLOO", "points": "70", "change": "-", "extra": {}},
        {"pos": "29", "name": "JiJieHao", "points": "55", "change": "+1", "extra": {}},
        {"pos": "30", "name": "The Huns", "points": "41", "change": "-1", "extra": {}},
    ]
    save("CS2_ranking.json", {"series": "CS2", "title": "HLTV 世界排名", "rows": ranking})


if __name__ == "__main__":
    gen_real()
    gen_cs2()
    print("demo data generation done")
