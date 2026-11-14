"""Перевод размеров шрифта из пикселей в rem и высот — в min-height.

Зачем: пиксельный размер шрифта не реагирует на настройку «Размер шрифта»
в браузере — человек со слабым зрением крупнее ничего не увидит. rem привязан
к базовому размеру браузера и растёт вместе с ним. Высоты переводим в min-height,
чтобы увеличенный текст не обрезался.

Что делает:
  font-size: 16px            -> font-size: 1rem
  clamp(32px,5vw,58px)       -> clamp(2rem,5vw,3.625rem)
  height: 50px (у кнопок)    -> min-height: 50px

Запуск:
    python tools/to_rem.py            # показать, что изменится
    python tools/to_rem.py --write    # записать (с копией рядом)
"""
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILES = ["static/style.css", "static/admin.css"]

# селекторы, у которых фиксированную высоту меняем на min-height:
# текст внутри должен иметь право увеличиться при крупном шрифте
HEIGHT_TO_MIN = [
    ".btn-lg", ".btn", ".day", ".time", ".fc-book",
    "rev-filters a", "rev-pager a", "lead-mode label",
]

# тут высоту трогать нельзя: квадратная кнопка-иконка и скрытое поле
HEIGHT_KEEP = [".fc-call", ".hp"]


def px_to_rem(value: str) -> str:
    """16px -> 1rem, 13.5px -> 0.8438rem."""
    rem = float(value) / 16
    text = f"{rem:.4f}".rstrip("0").rstrip(".")
    return f"{text}rem"


def convert_font_sizes(css: str) -> tuple[str, int]:
    count = 0

    def repl(match):
        nonlocal count
        count += 1
        return f"font-size:{px_to_rem(match.group(1))}"

    css = re.sub(r"font-size:\s*([0-9.]+)px", repl, css)
    return css, count


def convert_clamps(css: str) -> tuple[str, int]:
    """clamp(32px,5vw,58px) -> clamp(2rem,5vw,3.625rem)."""
    count = 0

    def repl(match):
        nonlocal count
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) != 3:
            return match.group(0)
        low, mid, high = parts
        if not (low.endswith("px") and high.endswith("px")):
            return match.group(0)
        count += 1
        return f"clamp({px_to_rem(low[:-2])},{mid},{px_to_rem(high[:-2])})"

    css = re.sub(r"clamp\(([^)]*)\)", repl, css)
    return css, count


def convert_heights(css: str) -> tuple[str, int]:
    """У названных элементов меняем height на min-height."""
    out, count = [], 0
    for block in re.split(r"(?<=\})", css):
        head = block.split("{", 1)[0] if "{" in block else block
        target = any(name in head for name in HEIGHT_TO_MIN)
        keep = any(name in head for name in HEIGHT_KEEP)
        if target and not keep and "height:" in block:
            block, n = re.subn(r"(?<![-\w])height:", "min-height:", block)
            count += n
        out.append(block)
    return "".join(out), count


def main():
    write = "--write" in sys.argv
    total = 0
    for rel in FILES:
        path = BASE / rel
        css = path.read_bytes().decode("utf-8")
        css, n_font = convert_font_sizes(css)
        css, n_clamp = convert_clamps(css)
        css, n_h = convert_heights(css)
        total += n_font + n_clamp + n_h
        print(f"{rel}: шрифтов {n_font}, clamp {n_clamp}, height->min-height {n_h}")
        if write:
            backup = path.with_suffix(path.suffix + f".bak-{datetime.now():%Y%m%d_%H%M%S}")
            shutil.copy2(path, backup)
            path.write_bytes(css.encode("utf-8"))
            print(f"   записано, копия: {backup.name}")
    print("итого изменений:", total)
    if not write:
        print("\nэто предпросмотр — для записи запусти с --write")


if __name__ == "__main__":
    main()
