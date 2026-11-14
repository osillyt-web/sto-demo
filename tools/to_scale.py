"""Приведение размеров к единой шкале (дизайн-система сайта).

Шаги:
  1. Размеры шрифта: 25 значений -> 8 ступеней (12, 14, 16, 18, 20, 24, 30, 38).
  2. Отступы gap: значения от 6px и выше -> шкала (8, 12, 16, 24, 32);
     мелкие 1-5px не трогаем — это склейка строк внутри плиток, а не отступы.
  3. Скругления: -> 4 ступени (4, 10, 14, 999); всё от 40px и выше — пилюля.
  4. Насыщенность: -> 3 ступени (400, 600, 800); заголовок h3 и крупная цифра
     рейтинга остаются жирными (800), прочие 700/650 -> 600.
  5. Межстрочный: -> 4 значения (1, 1.2, 1.45, 1.6).
  6. clamp(): средний член получает rem-базу так, чтобы при ширине 390px
     заголовок был как нижняя граница, а при 1440px — как верхняя.

Запуск:
    python tools/to_scale.py            # предпросмотр
    python tools/to_scale.py --write    # запись (с копией рядом)
"""
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILES = ["static/style.css", "static/admin.css"]

FONT_STEPS = [12, 14, 16, 18, 20, 24, 30, 38]
GAP_STEPS = [4, 8, 12, 16, 24, 32]
GAP_SKIP_BELOW = 6           # мельче — не отступы сетки, а склейка строк
RADIUS_STEPS = [4, 10, 14]
RADIUS_PILL_FROM = 40
WEIGHTS = {"400": "400", "600": "600", "650": "600", "700": "600", "800": "800"}
WEIGHT_BOLD_SELECTORS = ("h3", ".rev-score")   # им оставляем 800
LINE_HEIGHTS = {"1": "1", "1.05": "1.2", "1.08": "1.2", "1.1": "1.2", "1.12": "1.2",
                "1.15": "1.2", "1.2": "1.2", "1.25": "1.2", "1.35": "1.45", "1.4": "1.45",
                "1.45": "1.45", "1.5": "1.45", "1.55": "1.45", "1.6": "1.6", "1.65": "1.6",
                "1.7": "1.6"}


def nearest(value: float, steps: list, up_on_tie: bool = False) -> float:
    """Ближайшая ступень. up_on_tie=True — при равном расстоянии берём большую."""
    return min(steps, key=lambda s: (abs(s - value), -s if up_on_tie else s))


def px_to_rem(px: float) -> str:
    return f"{px / 16:.4f}".rstrip("0").rstrip(".") + "rem"


def scale_fonts(css: str):
    changed = {}

    def repl(m):
        px = round(float(m.group(1)) * 16, 2)
        new = nearest(px, FONT_STEPS, up_on_tie=True)
        if new != px:
            changed[px] = new
        return f"font-size:{px_to_rem(new)}"

    return re.sub(r"font-size:\s*([0-9.]+)rem", repl, css), changed


def scale_gaps(css: str):
    changed = {}

    def repl(m):
        px = float(m.group(1))
        if px < GAP_SKIP_BELOW:
            return m.group(0)
        new = int(nearest(px, GAP_STEPS, up_on_tie=True))
        if new != px:
            changed[px] = new
        return f"gap:{new}px"

    return re.sub(r"gap:\s*([0-9.]+)px", repl, css), changed


def scale_radii(css: str):
    changed = {}

    def repl(m):
        px = float(m.group(1))
        new = 999 if px >= RADIUS_PILL_FROM else int(nearest(px, RADIUS_STEPS))
        if new != px:
            changed[px] = new
        return f"border-radius:{new}px"

    return re.sub(r"border-radius:\s*([0-9.]+)px", repl, css), changed


def scale_weights(css: str):
    """Вес правим по правилам: внутри правил заголовков h3 и оценки — 800."""
    changed = {}
    out = []
    for block in re.split(r"(?<=\})", css):
        head = block.split("{", 1)[0] if "{" in block else block
        bold = any(sel in head for sel in WEIGHT_BOLD_SELECTORS)

        def repl(m, bold=bold):
            w = m.group(1)
            new = "800" if (bold and w in ("700", "650")) else WEIGHTS.get(w, w)
            if new != w:
                changed[w] = new
            return f"font-weight:{new}"

        out.append(re.sub(r"font-weight:\s*([0-9]+)", repl, block))
    return "".join(out), changed


def scale_line_heights(css: str):
    changed = {}

    def repl(m):
        lh = m.group(1)
        new = LINE_HEIGHTS.get(lh, str(nearest(float(lh), [1, 1.2, 1.45, 1.6])))
        if new != lh:
            changed[lh] = new
        return f"line-height:{new}"

    return re.sub(r"line-height:\s*([0-9.]+)(?=[;}])", repl, css), changed


def rem_base_clamp(css: str):
    """clamp(2rem,5vw,3.625rem) -> clamp(2rem,1.394rem + 2.48vw,3.625rem).

    Средний член подбираем так, чтобы при 390px заголовок совпал с нижней
    границей, а при 1440px — с верхней. Тогда при увеличении размера шрифта
    в браузере заголовок растёт плавно, а не только через границы.
    """
    changed = []

    def repl(m):
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) != 3:
            return m.group(0)
        low, mid, high = parts
        if not (low.endswith("rem") and high.endswith("rem")) or not mid.endswith("vw"):
            return m.group(0)
        lo_px, hi_px = float(low[:-3]) * 16, float(high[:-3]) * 16
        k = (hi_px - lo_px) / (1440 - 390)          # прирост на 1px ширины
        base_px = lo_px - k * 390                    # значение при нулевой ширине
        base_rem = round(base_px / 16, 3)
        vw = round(k * 100, 3)
        new = f"clamp({low},{base_rem}rem + {vw}vw,{high})"
        changed.append((m.group(0), new, round(lo_px), round(hi_px)))
        return new

    return re.sub(r"clamp\(([^)]*)\)", repl, css), changed


def main():
    write = "--write" in sys.argv
    for rel in FILES:
        path = BASE / rel
        css = path.read_bytes().decode("utf-8")
        css, f = scale_fonts(css)
        css, g = scale_gaps(css)
        css, r = scale_radii(css)
        css, w = scale_weights(css)
        css, l = scale_line_heights(css)
        css, c = rem_base_clamp(css)

        print(f"\n=== {rel}")
        print(f"  шрифты:       {len(f)}  {dict(sorted(f.items()))}")
        print(f"  отступы gap:  {len(g)}  {dict(sorted(g.items()))}")
        print(f"  скругления:   {len(r)}  {dict(sorted(r.items()))}")
        print(f"  насыщенность: {len(w)}  {w}")
        print(f"  межстрочные:  {len(l)}  {dict(sorted(l.items()))}")
        print(f"  clamp:        {len(c)}")
        for old, new, lo, hi in c:
            print(f"      {old}  ->  {new}   (390px: {lo}, 1440px: {hi})")

        if write:
            backup = path.with_suffix(path.suffix + f".scalebak-{datetime.now():%Y%m%d_%H%M%S}")
            shutil.copy2(path, backup)
            path.write_bytes(css.encode("utf-8"))
            print(f"  записано, копия: {backup.name}")

    if not write:
        print("\nпредпросмотр — для записи запусти с --write")


if __name__ == "__main__":
    main()
