"""Проверка админки: не обрезается ли текст при обычном и увеличенном шрифте.

Страница входа доступна без пароля, поэтому проверяем её и общие правила
admin.css (кнопки, поля, переключатели статуса).

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_admin_overflow.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501").rstrip("/")
URL = BASE + "/admin"

SCRIPT = """() => {
  const out = [];
  document.querySelectorAll('.btn, button, input, select, .seg-btn, .pill, .tab, .chip').forEach(el => {
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
    total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for font in (16, 24):
            for width, label in ((390, "телефон"), (1280, "компьютер")):
                ctx = browser.new_context(viewport={"width": width, "height": 900},
                                          is_mobile=(width == 390), has_touch=(width == 390))
                page = ctx.new_page()
                if font != 16:
                    cdp = ctx.new_cdp_session(page)
                    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": font, "fixed": font}})
                page.goto(URL, wait_until="load", timeout=60000)
                page.wait_for_timeout(1000)
                bad = page.evaluate(SCRIPT)
                print(f"админка, шрифт {font}, {label}: обрезанных — {len(bad)}")
                for b in bad:
                    print(f"    · «{b['text']}» {b['cls']} {b['w']}×{b['h']} "
                          f"выход Y={b['overY']} X={b['overX']}")
                    total += 1
                ctx.close()
        browser.close()
    print("\nИТОГ:", "есть обрезанные" if total else "ничего не обрезано")
    return 2 if total else 0


if __name__ == "__main__":
    sys.exit(main())
