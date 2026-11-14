"""Замер кнопок нижней панели телефона и шапки: высоты и отступы.

Проверяет, одинаковой ли высоты кнопки, которые стоят рядом друг с другом
(в нижней панели, в шапке, в блоке отзывов) — разнобой виден глазом как дисгармония.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_bar_size.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"

SCRIPT = """() => {
  const out = [];
  const push = (label, el) => {
    if (!el) return;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.push({ where: label, text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g,' ').slice(0,24),
               w: Math.round(r.width), h: Math.round(r.height), font: cs.fontSize, pad: cs.padding,
               radius: cs.borderRadius, line: cs.lineHeight, display: cs.display });
  };
  const bar = document.querySelector('.mobile-bar') || document.querySelector('.mobile-actions');
  if (bar) {
    bar.querySelectorAll('a, button').forEach(el => push('нижняя панель', el));
  }
  const top = document.querySelector('.top-actions');
  if (top) top.querySelectorAll('a, button').forEach(el => push('шапка', el));
  const rev = document.getElementById('reviews');
  if (rev) rev.querySelectorAll('.reviews-more a, .btn').forEach(el => push('блок отзывов', el));
  const book = document.getElementById('book');
  if (book) book.querySelectorAll('button, .btn').forEach(el => push('форма записи', el));
  return out;
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate("document.getElementById('reviews').scrollIntoView({block:'start'})")
        page.wait_for_timeout(900)

        rows = page.evaluate(SCRIPT)
        print("адрес:", URL)
        print(f"{'место':16} {'текст':26} {'размер':12} шрифт  паддинг        radius  line-height")
        for r in rows:
            print(f"{r['where']:16} {r['text'][:25]:26} {r['w']}×{r['h']:<7} {r['font']:7} "
                  f"{r['pad']:14} {r['radius']:7} {r['line']}")

        # ищем разнобой: одинаковые по смыслу кнопки с разной высотой
        heights = {}
        for r in rows:
            heights.setdefault(r["where"], set()).add(r["h"])
        print()
        bad = {k: v for k, v in heights.items() if len(v) > 1}
        if bad:
            for k, v in bad.items():
                print(f"РАЗНОБОЙ в «{k}»: высоты {sorted(v)}")
        else:
            print("Разнобоя по высоте нет — все кнопки в каждом месте одинаковы")
        browser.close()
        return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
