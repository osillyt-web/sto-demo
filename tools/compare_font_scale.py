"""Снимки сайта при обычном и увеличенном размере шрифта (для сравнения).

Делает два снимка одного экрана: шрифт 16 и шрифт 24 (как при увеличенном
размере шрифта в настройках браузера). Склейка — отдельным шагом.

Запуск:
    pwenv\\Scripts\\python.exe tools\\compare_font_scale.py [адрес]
Результат: data/_fs16.png и data/_fs24.png
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "data"


def shot(browser, font: int, path: Path):
    ctx = browser.new_context(viewport={"width": 390, "height": 720}, device_scale_factor=2,
                              is_mobile=True, has_touch=True)
    page = ctx.new_page()
    if font != 16:
        cdp = ctx.new_cdp_session(page)
        cdp.send("Page.setFontSizes", {"fontSizes": {"standard": font, "fixed": font}})
    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.evaluate("document.getElementById('book').scrollIntoView({block:'start'})")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(path))
    ctx.close()
    print("снято:", path)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        shot(browser, 16, OUT / "_fs16.png")
        shot(browser, 24, OUT / "_fs24.png")
        browser.close()


if __name__ == "__main__":
    main()
