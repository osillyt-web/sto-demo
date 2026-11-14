"""Контроль: px, rem и clamp при обычном и увеличенном размере шрифта в браузере.

Проверяет две вещи сразу:
  1) реагирует ли размер на настройку «Размер шрифта» в браузере (доступность);
  2) реагирует ли он на ширину окна (адаптивность) — прогон на 390 и 1280 px.
"""
import json
from playwright.sync_api import sync_playwright

URL = "file:///C:/Users/Alex/sto_demo/data/check_units_test.html"
MEASURE = """() => {
  const m = (sel) => {
    const el = document.querySelector(sel);
    const cs = getComputedStyle(el);
    return { font: cs.fontSize, h: Math.round(el.getBoundingClientRect().height) };
  };
  return { '1_px': m('.a'), '2_rem': m('.b'), '3_clamp_px': m('.c'), '4_clamp_rem': m('.d') };
}"""


def run(browser, width, font_px, label):
    ctx = browser.new_context(viewport={"width": width, "height": 700})
    page = ctx.new_page()
    if font_px != 16:
        cdp = ctx.new_cdp_session(page)
        cdp.send("Page.setFontSizes", {"fontSizes": {"standard": font_px, "fixed": font_px}})
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(300)
    data = page.evaluate(MEASURE)
    print(f"{label:44} " + "  ".join(f"{k}: {v['font']}" for k, v in data.items()))
    return data


with sync_playwright() as p:
    b = p.chromium.launch()
    print("шрифт браузера / ширина окна -> размер шрифта элемента")
    run(b, 390, 16, "обычный шрифт, телефон 390")
    run(b, 390, 24, "шрифт 24, телефон 390")
    run(b, 1280, 16, "обычный шрифт, компьютер 1280")
    run(b, 1280, 24, "шрифт 24, компьютер 1280")

    # картинка для наглядности: увеличенный шрифт на телефоне
    ctx = b.new_context(viewport={"width": 390, "height": 700}, device_scale_factor=2)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(400)
    page.screenshot(path="C:/Users/Alex/sto_demo/data/units_test.png")
    b.close()
