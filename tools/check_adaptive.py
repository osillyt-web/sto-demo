"""Проверка адаптивности: поведение сайта на десяти ширинах экрана.

Смотрим три вещи, которые ломают адаптивность:
  1) горизонтальная прокрутка страницы (появился «бегунок» вбок);
  2) элементы, вылезшие за правый край окна;
  3) обрезанный текст в кнопках и полях;
плюс собираем самый мелкий размер шрифта на странице — он отвечает за читаемость.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_adaptive.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net").rstrip("/")
WIDTHS = [320, 360, 390, 414, 480, 600, 768, 1024, 1280, 1440, 1920]
PAGES = ["", "/reviews", "/order", "/services", "/cases"]

CHECK = """() => {
  const doc = document.documentElement;
  const overflowX = doc.scrollWidth - window.innerWidth;
  const outside = [];
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (r.right > window.innerWidth + 1) {
      outside.push({ tag: el.tagName.toLowerCase(),
                     cls: (el.className||'').toString().slice(0,26),
                     right: Math.round(r.right),
                     text: (el.innerText||'').replace(/\\s+/g,' ').slice(0,20) });
    }
  });
  const cut = [];
  document.querySelectorAll('.btn, input, select, textarea, .day, .time, .lead-mode label').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (el.scrollHeight - el.clientHeight > 1 || el.scrollWidth - el.clientWidth > 1) {
      cut.push((el.innerText||el.value||'').replace(/\\s+/g,' ').slice(0,22));
    }
  });
  let smallest = 999, smallestText = '';
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || !el.innerText || el.children.length) return;
    const size = parseFloat(cs.fontSize);
    if (size < smallest) { smallest = size; smallestText = el.innerText.replace(/\\s+/g,' ').slice(0,22); }
  });
  return { overflowX, outside: outside.slice(0, 4), cut, smallest, smallestText };
}"""


def main():
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w in WIDTHS:
            ctx = browser.new_context(viewport={"width": w, "height": 900},
                                      is_mobile=(w <= 600), has_touch=(w <= 600))
            page = ctx.new_page()
            for path in PAGES:
                page.goto(BASE + path, wait_until="load", timeout=60000)
                page.wait_for_timeout(700)
                d = page.evaluate(CHECK)
                flags = []
                if d["overflowX"] > 1:
                    flags.append(f"прокрутка вбок +{d['overflowX']}px")
                if d["outside"]:
                    flags.append("вылезло: " + "; ".join(
                        f"{o['tag']}.{o['cls']} до {o['right']}" for o in d["outside"]))
                if d["cut"]:
                    flags.append("обрезано: " + ", ".join(d["cut"]))
                status = " | ".join(flags) if flags else "ок"
                if flags:
                    problems += 1
                print(f"{w:5} {path or '/':10} {status}  (мин. шрифт {d['smallest']:.0f}px «{d['smallestText'][:14]}»)")
            ctx.close()
        browser.close()
    print(f"\nИТОГ: мест с замечаниями — {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
