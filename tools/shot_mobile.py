"""Снимки мобильного вида: нижняя панель с кнопками и блок отзывов.

Запуск:
    pwenv\\Scripts\\python.exe tools\\shot_mobile.py [адрес]
Снимки кладутся в папку data/.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"
OUT = Path(__file__).resolve().parent.parent / "data"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        page = ctx.new_page()

        # 1. нижняя панель: прокручиваем вниз, чтобы она появилась
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1200)
        page.evaluate("window.scrollTo(0, 1200)")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "shot_bar.png"))
        print("панель:", OUT / "shot_bar.png")

        # 2. блок отзывов
        page.evaluate("document.getElementById('reviews').scrollIntoView({block:'start'})")
        page.wait_for_timeout(1400)
        page.screenshot(path=str(OUT / "shot_reviews.png"))
        print("отзывы:", OUT / "shot_reviews.png")

        # 3. форма записи — там стояли рядом кнопки разной высоты
        page.evaluate("document.getElementById('book').scrollIntoView({block:'start'})")
        page.wait_for_timeout(1400)
        page.screenshot(path=str(OUT / "shot_book.png"))
        print("форма записи:", OUT / "shot_book.png")

        # 4. элементы выбора: плитки дней и часы
        page.evaluate("""() => {
            const el = document.querySelector('.slot-pick') || document.getElementById('book');
            el.scrollIntoView({block: 'start'});
            window.scrollBy(0, 120);
        }""")
        page.wait_for_timeout(1400)
        page.screenshot(path=str(OUT / "shot_slots.png"))
        print("дни и часы:", OUT / "shot_slots.png")
        browser.close()


if __name__ == "__main__":
    main()
