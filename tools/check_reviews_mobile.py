"""Проверка блока отзывов на телефоне: видно ли карточки после прокрутки.

Запуск (из корня проекта):
    pwenv\\Scripts\\python.exe tools\\check_reviews_mobile.py [адрес]

Скрипт открывает сайт в мобильном размере, прокручивает к блоку отзывов
и смотрит глазами на вычисленные стили: если карточки остались с opacity 0,
значит анимация появления их так и не показала — это и есть «отзывы отсутствуют».
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"
SHOT = Path(__file__).resolve().parent.parent / "data" / "mobile_reviews_check.png"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent=("Mozilla/5.0 (Linux; Android 12; SM-M325FV) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"),
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)

        section = page.query_selector("#reviews") or page.query_selector(".rev-grid")
        if not section:
            print("ПРОВАЛ: на странице нет блока отзывов (#reviews или .rev-grid)")
            return 1

        # прокручиваем к блоку так, как это делает человек на телефоне
        if page.query_selector("#reviews"):
            page.evaluate("document.getElementById('reviews').scrollIntoView({block:'start'})")
        else:
            page.evaluate("document.querySelector('.rev-grid').scrollIntoView({block:'start'})")
        page.wait_for_timeout(1800)

        data = page.evaluate("""() => {
            const sec = document.getElementById('reviews') || document.querySelector('.rev-grid');
            const cards = Array.from(sec.querySelectorAll('.review'));
            const rect = sec.getBoundingClientRect();
            const head = sec.querySelector('h2, h1');
            return {
                cards: cards.length,
                shown: cards.map(c => c.classList.contains('shown')),
                opacity: cards.map(c => getComputedStyle(c).opacity),
                heights: cards.map(c => Math.round(c.getBoundingClientRect().height)),
                sectionTop: Math.round(rect.top),
                scrollY: Math.round(window.scrollY),
                viewportH: window.innerHeight,
                headerText: head ? head.innerText : '',
            };
        }""")

        print("адрес:", URL)
        print("карточек в блоке:", data["cards"])
        print("класс .shown:", data["shown"])
        print("opacity:", data["opacity"])
        print("высота карточек:", data["heights"])
        print("позиция блока в окне:", data["sectionTop"], "| прокрутка:", data["scrollY"],
              "| высота окна:", data["viewportH"])

        page.screenshot(path=str(SHOT))
        print("скриншот:", SHOT)

        visible = [o for o in data["opacity"] if float(o) > 0.05]
        if data["cards"] and len(visible) == data["cards"]:
            print("\nИТОГ: карточки видны — блок в порядке")
            browser.close()
            return 0
        print("\nИТОГ: ПРОБЛЕМА — карточки в блоке не показаны (opacity 0)")
        browser.close()
        return 2


if __name__ == "__main__":
    sys.exit(main())
