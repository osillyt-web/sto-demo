"""Прогон axe-core (движок доступности Deque, тот же, что внутри Lighthouse)
по ключевым страницам демо на двух размерах экрана.

Запуск:  pwenv\\Scripts\\python.exe tools\\axe_check.py
Требует интернет (axe.min.js тянется с CDN jsdelivr).
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
PAGES = ["/", "/cases", "/pricing", "/order", "/services", "/services/to", "/brands", "/privacy", "/admin/login", "/nope"]
VIEWS = [("ПК 1440x900", 1440, 900, False), ("телефон 390x844", 390, 844, True)]
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]


def fetch_axe():
    cache = os.path.join(os.path.dirname(__file__), "axe.min.js")
    if os.path.exists(cache) and os.path.getsize(cache) > 100000:
        return open(cache, encoding="utf-8").read()
    with urllib.request.urlopen(AXE_URL, timeout=60) as r:
        src = r.read().decode("utf-8")
    open(cache, "w", encoding="utf-8").write(src)
    return src


def main():
    from playwright.sync_api import sync_playwright
    axe_src = fetch_axe()
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, w, h, mobile in VIEWS:
            # bypass_csp: сайт отдаёт строгий CSP script-src 'self' (это правильно),
            # поэтому axe подключаем в обход CSP — только на время проверки
            ctx = browser.new_context(viewport={"width": w, "height": h}, bypass_csp=True,
                                      is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
            page = ctx.new_page()
            for path in PAGES:
                page.goto(BASE + path, wait_until="load")
                page.wait_for_timeout(600)
                page.add_script_tag(content=axe_src)
                res = page.evaluate("""async (tags) => {
                    const r = await axe.run(document, {runOnly: {type: 'tag', values: tags}});
                    return {violations: r.violations.map(v => ({
                        id: v.id, impact: v.impact, help: v.help,
                        nodes: v.nodes.length,
                        target: v.nodes[0] ? v.nodes[0].target : null,
                        summary: v.nodes[0] ? (v.nodes[0].failureSummary || '').slice(0, 160) : ''
                    })), incomplete: r.incomplete.length, passes: r.passes.length};
                }""", TAGS)
                report.append({"view": label, "page": path, **res})
                mark = "OK " if not res["violations"] else "ЕСТЬ"
                print(f"{mark} [{label}] {path:16} нарушений: {len(res['violations']):2} | "
                      f"проверок пройдено: {res['passes']:3} | требуют ручной проверки: {res['incomplete']}")
                for v in res["violations"]:
                    print(f"      · {v['impact']:8} {v['id']:28} узлов {v['nodes']:2} | {v['help'][:70]}")
            ctx.close()
        browser.close()
    out = os.path.join(os.path.dirname(__file__), "axe_report.json")
    open(out, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=1))
    total = sum(len(r["violations"]) for r in report)
    print(f"\nИТОГ: проверок {len(report)}, страниц с нарушениями "
          f"{sum(1 for r in report if r['violations'])}, всего нарушений {total}")
    print("отчёт:", out)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
