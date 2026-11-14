"""Оценка гармонии: объективные замеры по страницам.

Собираем то, что можно измерить, а не обсудить:
  1) сколько разных размеров шрифта реально в вёрстке страницы (шкала);
  2) сколько разных отступов между секциями (ритм);
  3) сколько разных скруглений (единообразие форм);
  4) контраст основных пар «текст / фон» по WCAG (AA: 4.5 для текста, 3.0 для крупного);
  5) высота кликабельных зон (палец: минимум 44 px).

Запуск:
    python tools/check_harmony.py [адрес]
"""
import sys
import json
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net").rstrip("/")
PAGES = ["", "/services", "/cases", "/reviews", "/order", "/contacts"]

SCRIPT = """() => {
  const fonts = new Set(), radii = new Set(), heights = [];
  const gaps = new Set();
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (el.children.length === 0 && el.innerText && el.innerText.trim()) {
      fonts.add(Math.round(parseFloat(cs.fontSize) * 10) / 10);
    }
    if (cs.borderTopLeftRadius !== '0px') radii.add(cs.borderTopLeftRadius);
    if (el.matches('a, button, input, select, .btn, .day, .time, .lead-mode label')) {
      heights.push(Math.round(r.height));
    }
  });
  // ритм: нижние отступы секций и блоков
  document.querySelectorAll('section, .section, main > div, .cards > *, .grid > *').forEach(el => {
    const mb = parseFloat(getComputedStyle(el).marginBottom);
    if (mb > 0) gaps.add(Math.round(mb));
  });
  const root = getComputedStyle(document.documentElement);
  const vars = {};
  ['--bg','--panel','--card','--text','--muted','--accent','--line'].forEach(v => {
    vars[v] = root.getPropertyValue(v).trim();
  });
  return { fonts: [...fonts].sort((a,b) => a-b), radii: [...radii].sort(),
           heights: [...new Set(heights)].sort((a,b) => a-b),
           margins: [...gaps].sort((a,b) => a-b), vars };
}"""


def luminance(color: str):
    """Относительная яркость для контраста (WCAG)."""
    c = color.strip()
    if c.startswith("#"):
        c = c[1:]
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    else:
        nums = [float(x) for x in c.replace("rgb(", "").replace(")", "").split(",")[:3]]
        r, g, b = (n / 255 for n in nums)
    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (390, 1280):
            ctx = b.new_context(viewport={"width": w, "height": 900}, is_mobile=(w <= 600), has_touch=(w <= 600))
            pg = ctx.new_page()
            print(f"\n===== ширина {w}px =====")
            for path in PAGES:
                pg.goto(BASE + path, wait_until="load", timeout=60000)
                pg.wait_for_timeout(800)
                d = pg.evaluate(SCRIPT)
                small = [h for h in d["heights"] if h < 44]
                print(f"{path or '/':10} шрифтов {len(d['fonts']):2} | скруглений {len(d['radii']):2} | "
                      f"отступов {len(d['margins']):2} | кликов {len(d['heights']):2}"
                      f"{'  ВНИМАНИЕ: мелких зон ' + str(small) if small else ''}")
            if w == 390:
                v = d["vars"]
                print("\n--- контраст (WCAG; AA для текста 4.5, для крупного 3.0) ---")
                bg = v.get("--bg") or "#0b0e13"
                for name, val in (("основной текст", v.get("--text")), ("второстепенный", v.get("--muted")),
                                  ("акцент", v.get("--accent")), ("панель", v.get("--panel"))):
                    if val:
                        c = contrast(val, bg)
                        mark = "ок" if c >= 4.5 else ("только крупный" if c >= 3 else "мало")
                        print(f"   {name:16} {val:10} на фоне {bg:10} = {c:5}  {mark}")
            ctx.close()
        b.close()


if __name__ == "__main__":
    main()
