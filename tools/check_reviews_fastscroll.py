"""Проверка: не пропадают ли карточки отзывов при БЫСТРОЙ прокрутке на телефоне.

Карточки отзывов помечены data-reveal: они невидимы (opacity 0), пока скрипт
не добавит класс .shown по факту попадания в экран (IntersectionObserver).
Если при быстрой прокрутке наблюдатель не успевает сработать, человек видит
заголовок «Відгуки клієнтів» и пустое место — «отзывы отсутствуют».

Запуск:
    pwenv\\Scripts\\python.exe tools\\check_reviews_fastscroll.py [адрес]
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://osillytweb.alwaysdata.net/"
OUT = Path(__file__).resolve().parent.parent / "data"


def measure(page, label):
    data = page.evaluate("""() => {
        const cards = Array.from(document.querySelectorAll('#reviews .review'));
        return {
            cards: cards.length,
            shown: cards.map(c => c.classList.contains('shown')),
            opacity: cards.map(c => Math.round(parseFloat(getComputedStyle(c).opacity) * 100) / 100),
        };
    }""")
    print(f"{label}: карточек={data['cards']} .shown={data['shown']} opacity={data['opacity']}")
    return data


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
            user_agent=("Mozilla/5.0 (Linux; Android 12; SM-M325FV) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"))
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1200)

        # 1. быстрая прокрутка: как флик пальцем — крупными шагами без пауз
        page.evaluate("""() => {
            const step = Math.round(window.innerHeight * 0.9);
            for (let y = 0; y <= 9200; y += step) window.scrollTo(0, y);
            window.scrollTo(0, 8800);       // оказываемся у блока отзывов
        }""")
        page.wait_for_timeout(1500)
        fast = measure(page, "после быстрой прокрутки")

        page.screenshot(path=str(OUT / "fastscroll_reviews.png"))
        print("скриншот:", OUT / "fastscroll_reviews.png")

        # 2. для сравнения — плавная прокрутка к блоку
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        page.evaluate("document.getElementById('reviews').scrollIntoView({block:'start'})")
        page.wait_for_timeout(1500)
        slow = measure(page, "после прокрутки к блоку")

        page.screenshot(path=str(OUT / "slowscroll_reviews.png"))
        print("скриншот:", OUT / "slowscroll_reviews.png")

        bad = [i for i, o in enumerate(fast["opacity"]) if o < 0.5]
        browser.close()
        if bad:
            print(f"\nИТОГ: ПРОБЛЕМА — после быстрой прокрутки карточки {bad} остались невидимыми")
            return 2
        print("\nИТОГ: карточки видны и после быстрой прокрутки")
        return 0


if __name__ == "__main__":
    sys.exit(main())
