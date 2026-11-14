"""Замер кнопок и селекторов: высота, ширина, шрифт, отступы.

Задача — найти элементы одного типа, которые выглядят по-разному
(разная высота кнопок, разный шрифт в фильтрах и т.п.).

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_buttons_size.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"

SCRIPT = """() => {
  const sel = 'a.btn, button.btn, .btn, .seg-btn, .rev-filters a, .rev-pager a, .rev-pager span, ' +
              'button[type=submit], .mobile-bar a, .mobile-bar button, .star-picker label, ' +
              '.filters button, .filter, input[type=text], textarea, select';
  const out = [];
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    out.push({
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 42),
      text: (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').slice(0, 26),
      w: Math.round(r.width), h: Math.round(r.height),
      font: cs.fontSize, pad: cs.paddingTop + '/' + cs.paddingLeft,
      radius: cs.borderRadius, weight: cs.fontWeight,
    });
  });
  return out;
}"""


def report(page, label):
    items = page.evaluate(SCRIPT)
    print(f"\n=== {label} — элементов: {len(items)}")
    # группируем по «классу вида»: берём первые классы
    seen = {}
    for it in items:
        key = it["cls"] or it["tag"]
        seen.setdefault(key, []).append(it)
    for key, group in seen.items():
        hs = sorted({g["h"] for g in group})
        ws = sorted({g["w"] for g in group})
        fs = sorted({g["font"] for g in group})
        print(f"  {key:44} шт={len(group):2}  высота={hs}  шрифт={fs}")
        for g in group[:6]:
            print(f"      · {g['text'][:24]:26} {g['w']}×{g['h']}  шрифт {g['font']}  pad {g['pad']}  r {g['radius']}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        page = ctx.new_page()
        for url, label in ((URL, "главная"), (URL.rstrip("/") + "/reviews", "страница Відгуки"),
                           (URL.rstrip("/") + "/order", "страница Замовлення")):
            try:
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(1200)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(900)
                report(page, label + " (" + url + ")")
            except Exception as exc:
                print(f"ПРОВАЛ на {url}: {exc}")
        browser.close()


if __name__ == "__main__":
    main()
