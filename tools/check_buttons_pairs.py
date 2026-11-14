"""Проверка: кнопки, стоящие рядом в одном блоке, одного размера.

Если в одном контейнере лежат две и более кнопки, они должны быть одинаковой
ширины и высоты — иначе блок выглядит неаккуратно, даже когда каждая кнопка
сама по себе правильная.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_buttons_pairs.py [адрес] [ширина]
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 390

SCRIPT = """() => {
  const groups = [];
  document.querySelectorAll('div, section, footer, form').forEach(box => {
    const btns = Array.from(box.querySelectorAll(':scope > .btn, :scope > a.btn, :scope > button'));
    if (btns.length < 2) return;
    const visible = btns.filter(b => {
      const cs = getComputedStyle(b);
      const r = b.getBoundingClientRect();
      return cs.display !== 'none' && r.width > 1 && r.height > 1;
    });
    if (visible.length < 2) return;
    groups.push({
      where: (box.className || box.tagName).toString().slice(0, 28),
      items: visible.map(b => ({ text: (b.innerText||'').replace(/\\s+/g,' ').slice(0,22),
                                 w: Math.round(b.getBoundingClientRect().width),
                                 h: Math.round(b.getBoundingClientRect().height) })),
    });
  });
  return groups;
}"""


def main():
    pages = [URL, URL.rstrip("/") + "/order", URL.rstrip("/") + "/cases"]
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": WIDTH, "height": 900},
                                  is_mobile=(WIDTH <= 600), has_touch=(WIDTH <= 600))
        page = ctx.new_page()
        for url in pages:
            page.goto(url, wait_until="load", timeout=60000)
            page.wait_for_timeout(1200)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(800)
            for g in page.evaluate(SCRIPT):
                ws = sorted({i["w"] for i in g["items"]})
                hs = sorted({i["h"] for i in g["items"]})
                mark = "" if len(ws) == 1 and len(hs) == 1 else "  <-- РАЗНЫЕ"
                if mark:
                    bad += 1
                print(f"{url}\n  блок «{g['where']}»: ширина {ws}, высота {hs}{mark}")
                for i in g["items"]:
                    print(f"     · {i['text']:24} {i['w']}×{i['h']}")
        browser.close()
    print("\nИТОГ:", f"групп с разными кнопками — {bad}" if bad else "во всех блоках кнопки одного размера")
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
