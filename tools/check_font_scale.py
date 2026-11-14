"""Проверка: реагирует ли сайт на увеличение шрифта в браузере.

Настройка «Размер шрифта» в браузере меняет базовый размер (1rem). Если размеры
заданы в px, они её игнорируют — текст не увеличивается, человек с плохим зрением
не получает крупнее. Проверяем фактом: замер до и после смены базового размера.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_font_scale.py [адрес]
"""
import sys
import json
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501/"

MEASURE = """() => {
  const pick = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { font: cs.fontSize, h: Math.round(r.height), text: (el.innerText||'').replace(/\\s+/g,' ').slice(0,18) };
  };
  return {
    body: pick('body'),
    btn: pick('.btn'),
    day: pick('.day'),
    time: pick('.time'),
    h1: pick('h1'),
    field: pick('input[type=text]'),
  };
}"""


def show(label, data):
    print(f"  {label}")
    for k, v in data.items():
        if v:
            print(f"    {k:6} шрифт {v['font']:7} высота {v['h']:4}  «{v['text']}»")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo(0, 1400)")
        page.wait_for_timeout(800)

        base = page.evaluate(MEASURE)
        show("обычный размер шрифта:", base)

        # эмулируем настройку браузера «Размер шрифта» = 24 вместо 16
        cdp = ctx.new_cdp_session(page)
        cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
        page.reload(wait_until="load")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo(0, 1400)")
        page.wait_for_timeout(800)
        big = page.evaluate(MEASURE)
        show("размер шрифта в браузере увеличен (24):", big)

        print()
        changed = [k for k in base if base[k] and big[k] and base[k]["font"] != big[k]["font"]]
        if changed:
            print("Отреагировали на настройку:", ", ".join(changed))
        else:
            print("ИТОГ: НИ ОДИН элемент не увеличился — вёрстка игнорирует настройку шрифта в браузере")
        browser.close()


if __name__ == "__main__":
    main()
