"""Массовый сбор карточек автосервисов из Google Maps с отбором «нет сайта, но есть телефон».

Пишет каждый результат сразу в JSONL (data/maps_cards.jsonl), поэтому падение
не теряет уже собранное. Дубликаты отсекаются по названию+телефону.

Запуск:  python tools/maps_collect.py --per-query 40 --max 400
"""
import argparse
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")
DATA = r"C:\Users\Alex\sto_demo\data\maps_cards.jsonl"

QUERIES = [
    "СТО Київ", "автосервіс Київ", "детейлінг Київ", "шиномонтаж Київ",
    "СТО Поділ Київ", "СТО Оболонь Київ", "СТО Троєщина", "СТО Позняки",
    "СТО Виноградар", "СТО Солом'янка", "СТО Дарниця", "СТО Борщагівка",
    "СТО Бровари", "СТО Ірпінь", "СТО Бориспіль", "СТО Вишневе", "СТО Вишгород",
]


def load_seen():
    seen = set()
    if os.path.exists(DATA):
        for line in open(DATA, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            seen.add((d.get("name", "").strip().lower(), d.get("phone", "")))
    return seen


def collect_links(pg, query, want):
    pg.goto("https://www.google.com/maps/search/" + query.replace(" ", "+") + "?hl=uk",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)
    seen = {}
    for _ in range(14):
        cards = pg.evaluate("""() => [...document.querySelectorAll('a[href*="/maps/place/"]')]
            .map(a => ({href: a.href.split('?')[0], name: (a.getAttribute('aria-label') || '').trim()}))""")
        for c in cards:
            if c["href"] and c["href"] not in seen:
                seen[c["href"]] = c["name"]
        if len(seen) >= want:
            break
        pg.evaluate("""() => { const f = document.querySelector('div[role="feed"]');
            if (f) { f.scrollTop = f.scrollHeight; } }""")
        pg.wait_for_timeout(1700)
    return list(seen.items())[:want]


def details(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(2000)
    d = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const g = (s, attr) => q(s) ? (q(s).getAttribute(attr) || '') : '';
      return {
        name: q('h1') ? q('h1').innerText.trim() : '',
        site: q('a[data-item-id="authority"]') ? q('a[data-item-id="authority"]').href : '',
        phone: g('button[data-item-id^="phone"]', 'aria-label'),
        addr: g('button[data-item-id="address"]', 'aria-label'),
        rating: g('div[role="img"][aria-label*="зірк"]', 'aria-label')
      };
    }""")
    for k in ("phone", "addr", "rating"):
        d[k] = re.sub(r"^[^:]+:\s*", "", d.get(k) or "").strip()
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=40)
    ap.add_argument("--max", type=int, default=400)
    args = ap.parse_args()

    seen = load_seen()
    out = open(DATA, "a", encoding="utf-8")
    total = hits = 0
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, user_agent=UA, locale="uk-UA")
        pg = ctx.new_page()
        for query in QUERIES:
            if total >= args.max:
                break
            try:
                links = collect_links(pg, query, args.per_query)
            except Exception as e:
                print(f"[{query}] лента не открылась: {type(e).__name__}", flush=True)
                continue
            print(f"[{query}] карточек: {len(links)}", flush=True)
            for url, name in links:
                if total >= args.max:
                    break
                try:
                    d = details(pg, url)
                except Exception:
                    continue
                key = ((d.get("name") or name).strip().lower(), d.get("phone", ""))
                if key in seen:
                    continue
                seen.add(key)
                d["query"] = query
                d["maps_url"] = url
                d["no_site"] = not d.get("site")
                out.write(json.dumps(d, ensure_ascii=False) + "\n")
                out.flush()
                total += 1
                if d["no_site"] and d.get("phone"):
                    hits += 1
                    print(f"  + {(d.get('name') or name)[:40]:40} | {d['phone'][:16]:16} | БЕЗ САЙТА", flush=True)
                time.sleep(1.0)
        ctx.close(); b.close()
    out.close()
    print(f"\nсобрано карточек: {total} | из них без сайта и с телефоном: {hits}", flush=True)


if __name__ == "__main__":
    main()
