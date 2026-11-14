"""Контроль: как ведут себя px и rem при увеличенном размере шрифта в браузере."""
import json
from playwright.sync_api import sync_playwright

URL = "file:///C:/Users/Alex/sto_demo/data/check_px_rem.html"

MEASURE = """() => {
  const m = (sel) => {
    const el = document.querySelector(sel);
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { font: cs.fontSize, h: Math.round(r.height) };
  };
  return { px: m('.btn-px'), rem: m('.btn-rem') };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 600})
    page = ctx.new_page()
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(400)
    print("обычный размер шрифта:      ", json.dumps(page.evaluate(MEASURE), ensure_ascii=False))
    cdp = ctx.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.reload(wait_until="load")
    page.wait_for_timeout(400)
    print("шрифт в браузере увеличен:  ", json.dumps(page.evaluate(MEASURE), ensure_ascii=False))
    page.screenshot(path="C:/Users/Alex/sto_demo/data/px_rem_test.png")
    b.close()
