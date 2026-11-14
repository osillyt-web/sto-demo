"""Инвентарь значений: какой размер где применяется.

Печатает для каждого уникального значения размера шрифта список селекторов,
где оно встречается. Нужно, чтобы свести 25 значений к шкале, не сломав
иерархию (заголовок не должен стать мельче подписи).

Запуск:
    python tools/inventory_values.py [файл.css]
"""
import re
import sys
import collections
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("static/style.css")
css = path.read_text(encoding="utf-8")

# режем на правила: селектор { тело }
rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)

print(f"=== {path}: размеры шрифта по селекторам\n")
by_size = collections.defaultdict(list)
for sel, body in rules:
    sel_clean = " ".join(sel.split())[:70]
    for m in re.finditer(r"font-size:\s*([0-9.]+)rem", body):
        px = round(float(m.group(1)) * 16, 1)
        by_size[px].append(sel_clean)

for px in sorted(by_size):
    sels = by_size[px]
    print(f"{px:5} px  ({len(sels):2} шт): {', '.join(sels[:4])}{' …' if len(sels) > 4 else ''}")

print("\n=== прочие шкалы\n")
for prop, pat in (("gap", r"gap:\s*([0-9.]+px)"),
                  ("border-radius", r"border-radius:\s*([0-9.]+px)"),
                  ("font-weight", r"font-weight:\s*([0-9]+)"),
                  ("line-height", r"line-height:\s*([0-9.]+)[;}]")):
    c = collections.Counter(re.findall(pat, css))
    print(f"{prop:14} {len(c):2} значений: {sorted(c.items(), key=lambda kv: -kv[1])}")
