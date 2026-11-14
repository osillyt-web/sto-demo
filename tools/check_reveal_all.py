"""Проверка: все блоки с анимацией появления видны после быстрой прокрутки.

Блоки с атрибутом data-reveal скрыты, пока скрипт не добавит класс .shown.
Скрипт проходит страницу быстрыми шагами (как флик пальцем) и проверяет,
что ни один блок не остался прозрачным.

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_reveal_all.py [адрес]
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1200)

        total = page.evaluate("document.querySelectorAll('[data-reveal]').length")

        # быстрая прокрутка вниз и обратно
        page.evaluate("""() => {
            const step = Math.round(window.innerHeight * 0.9);
            const bottom = document.documentElement.scrollHeight;
            for (let y = 0; y <= bottom; y += step) window.scrollTo(0, y);
            for (let y = bottom; y >= 0; y -= step * 3) window.scrollTo(0, y);
            window.scrollTo(0, bottom);
        }""")
        page.wait_for_timeout(2000)

        data = page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('[data-reveal]'));
            const invisible = els.filter(el => parseFloat(getComputedStyle(el).opacity) < 0.5);
            return {
                total: els.length,
                shown: els.filter(el => el.classList.contains('shown')).length,
                invisible: invisible.length,
                sample: invisible.slice(0, 5).map(el => (el.className || el.tagName) + ' @ ' +
                        Math.round(el.getBoundingClientRect().top + window.scrollY)),
            };
        }""")
        browser.close()

        print("адрес:", URL)
        print("блоков с анимацией:", data["total"], "| показано:", data["shown"],
              "| невидимых:", data["invisible"])
        if data["sample"]:
            print("невидимые:", data["sample"])
        if data["invisible"]:
            print("\nИТОГ: ПРОБЛЕМА — часть блоков осталась прозрачной")
            return 2
        print("\nИТОГ: все блоки видны")
        return 0


if __name__ == "__main__":
    sys.exit(main())
