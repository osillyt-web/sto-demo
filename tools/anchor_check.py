#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка якорей в реальном браузере: при переходе по ссылке цель не должна
заезжать под липкую шапку. Печатает таблицу и ИТОГ, код возврата 0/1.

Запуск (нужен Playwright, он не входит в зависимости сайта):
    python tools/anchor_check.py
    BASE=https://адрес python tools/anchor_check.py

Смысл: test_flow.py проверяет только разметку и CSS, а положение заголовка
на экране видно лишь в браузере. Без этой проверки ошибка вроде «на телефоне
заголовок под шапкой» проходит незамеченной.
"""
import os
import sys

BASE = os.environ.get("BASE", "http://127.0.0.1:8000").rstrip("/")

# страница -> якоря, которые на ней есть (берём из меню и подвала)
PAGES = {
    "/": ["prices", "services", "calc", "book", "reviews", "works", "contacts"],
    "/cases": ["case-sto", "case-gsm", "contact"],
}

# ширина, высота, подпись: 901 и 899 — по обе стороны от брейкпоинта 900px
WIDTHS = [
    (1440, 900, "ПК 1440"),
    (1224, 800, "ПК 1224"),
    (1024, 800, "ноут 1024"),
    (901, 800, "граница 901"),
    (899, 800, "граница 899"),
    (768, 1024, "планшет 768"),
    (412, 915, "телефон 412"),
    (360, 780, "узкий 360"),
]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Нужен Playwright: uv pip install playwright && playwright install chromium")
        return 2

    fails = []
    checks = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h, label in WIDTHS:
            ctx = browser.new_context(viewport={"width": w, "height": h},
                                      is_mobile=w < 500, has_touch=w < 500)
            page = ctx.new_page()

            # вкладки портфолио должны быть видны на любой ширине: они показывают,
            # что кейсов два, и без них с телефона между кейсами не перейти
            page.goto(BASE + "/cases", wait_until="load", timeout=60000)
            page.wait_for_timeout(350)
            tabs = page.evaluate("""() => {
                const n = document.querySelector(".nav");
                if (!n) return null;
                const links = [...n.querySelectorAll("a")];
                return {total: links.length,
                        visible: links.filter(a => a.offsetParent !== null).length,
                        minHeight: Math.round(Math.min(...links.map(a => a.getBoundingClientRect().height)))};
            }""")
            checks += 1
            if not tabs or tabs["visible"] != tabs["total"]:
                print("FAIL %-13s /cases  вкладки портфолио скрыты (%s из %s)"
                      % (label, tabs["visible"] if tabs else "?", tabs["total"] if tabs else "?"))
                fails.append("%s вкладки портфолио" % label)
            else:
                print("PASS %-13s /cases  вкладки портфолио видны: %d, высота %d px"
                      % (label, tabs["visible"], tabs["minHeight"]))

            for path, anchors in PAGES.items():
                for a in anchors:
                    page.goto(BASE + path, wait_until="load", timeout=60000)
                    page.wait_for_timeout(350)
                    # так же, как это делает человек: нажатие ссылки
                    page.evaluate('location.hash=""')
                    page.wait_for_timeout(120)
                    page.evaluate('location.hash="#%s"' % a)
                    page.wait_for_timeout(900)
                    m = page.evaluate("""(a) => {
                        const e = document.getElementById(a);
                        if (!e) return null;
                        const hd = document.querySelector("header").getBoundingClientRect();
                        return {top: Math.round(e.getBoundingClientRect().top),
                                head: Math.round(hd.height),
                                sm: getComputedStyle(e).scrollMarginTop};
                    }""", a)
                    checks += 1
                    if m is None:
                        print("FAIL %-13s %-8s #%-10s цели нет на странице" % (label, path, a))
                        fails.append("%s %s #%s" % (label, path, a))
                        continue
                    ok = m["top"] >= m["head"] - 1
                    if not ok:
                        fails.append("%s %s #%s" % (label, path, a))
                    print("%s %-13s %-8s #%-10s верх %4d px, шапка %3d px, scroll-margin-top %s"
                          % ("PASS" if ok else "FAIL", label, path, a, m["top"], m["head"], m["sm"]))
            ctx.close()
        browser.close()

    print()
    print("ИТОГ: проверок %d, провалено %d" % (checks, len(fails)))
    if fails:
        print("провалы: " + ", ".join(fails))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
