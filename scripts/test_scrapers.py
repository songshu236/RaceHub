import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\19819\Documents\ChatGPT\赛事日历')
from racehub.scrapers import F1Scraper, WECScraper

print('===== F1 =====')
f1 = F1Scraper()
cal = f1.fetch_calendar()
print('calendar:', len(cal))
for e in cal[:5]:
    print(' ', e['round'], e['name'], e['start'], e['status'], e['venue'])
res = f1.fetch_results()
print('results races:', len(res['rows']))
if res['rows']:
    r0 = res['rows'][-1]
    print(' last race:', r0['event_name'], 'rows:', len(r0['rows']))
    print('  row0:', r0['rows'][0])
st = f1.fetch_standings()
for t in st['tables']:
    print(' standings:', t['title'], 'rows:', len(t['rows']), 'top3:', [(r['pos'], r['name'], r['points']) for r in t['rows'][:3]])

print()
print('===== WEC =====')
wec = WECScraper(year=2026)
cal = wec.fetch_calendar()
print('calendar:', len(cal))
for e in cal[:6]:
    print(' ', e['name'], e['start'], '->', e['end'], e['status'], e['country'], e['flag'])
st = wec.fetch_standings(year=2026)
print('standings tables:', len(st['tables']))
for t in st['tables']:
    print(' ', t['title'], 'rows:', len(t['rows']), 'top2:', [(r['pos'], r['name'], r['points']) for r in t['rows'][:2]])
res = wec.fetch_results(year=2026)
print('results events:', len(res['rows']))
for r in res['rows'][:3]:
    print(' ', r['event_name'], 'rows:', len(r['rows']), 'row0:', {k: r['rows'][0].get(k) for k in ('pos','team','drivers','car','cls','laps','total_time','gap')})
