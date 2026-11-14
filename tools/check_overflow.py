"""Проверка: не обрезается ли текст в кнопках и полях после выравнивания размеров.

Смотрим, влезает ли содержимое в заданную высоту: если scrollHeight больше
clientHeight или scrollWidth больше clientWidth — текст обрезан или вылезает.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_overflow.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"

SCRIPT = """() => {
  const out = [];
  document.querySelectorAll('.btn, input, select, textarea, .rev-filters a, .rev-pager a, .fc-call, .lead-mode label, .day, .time, .model-chip, .chip').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    const overY = el.scrollHeight - el.clientHeight;
    const overX = el.scrollWidth - el.clientWidth;
    if (overY > 1 || overX > 1) {
      out.push({ text: (el.innerText || el.value || '').replace(/\\s+/g,' ').slice(0, 26),
                 cls: (el.className||'').toString().slice(0,30),
                 w: Math.round(r.width), h: Math.round(r.height),
                 overY: Math.round(overY), overX: Math.round(overX) });
    }
  });
  return out;
}"""


def main():
    pages = [URL, URL.rstrip("/") + "/reviews", URL.rstrip("/") + "/order"]
    bad_total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, label in ((390, "телефон"), (1280, "компьютер")):
            ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1,
                                      is_mobile=(width == 390), has_touch=(width == 390))
            page = ctx.new_page()
            for url in pages:
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(600)
                bad = page.evaluate(SCRIPT)
                print(f"{label} {url}: обрезанных элементов — {len(bad)}")
                for b in bad:
                    print(f"    · «{b['text']}» {b['cls']} {b['w']}×{b['h']} "
                          f"выход по Y={b['overY']} X={b['overX']}")
                    bad_total += 1
            ctx.close()
        browser.close()
    print("\nИТОГ:", "есть обрезанные элементы" if bad_total else "ничего не обрезано")
    return 2 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
