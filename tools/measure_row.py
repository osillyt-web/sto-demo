"""Поиск рамки серой кнопки в строке снимка (чтобы сравнить её ширину с оранжевой).

Запуск:
    python tools/measure_row.py data/phone_hero2.png 712
"""
import sys
from PIL import Image

path, y = sys.argv[1], int(sys.argv[2])
im = Image.open(path).convert("RGB")
W, H = im.size
px = im.load()

near_line = []
for x in range(W):
    r, g, b = px[x, y]
    # рамка кнопки — серо-синий тон, светлее фона
    if 45 <= r <= 90 and 55 <= g <= 105 and 65 <= b <= 120 and b >= r:
        near_line.append(x)

# группируем: рамки — это короткие серии по 1-4 пикселя
groups, cur = [], []
for x in near_line:
    if cur and x - cur[-1] > 3:
        groups.append((cur[0], cur[-1]))
        cur = []
    cur.append(x)
if cur:
    groups.append((cur[0], cur[-1]))

print(f"строка y={y}: найдено вертикальных линий рамки: {len(groups)}")
for a, b in groups[:12]:
    print(f"   рамка x={a}..{b}")
if len(groups) >= 2:
    print(f"\nширина кнопки между дальними рамками: {groups[-1][0] - groups[0][0]} px")
