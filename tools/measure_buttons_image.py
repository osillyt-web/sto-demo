"""Измерение кнопок прямо по снимку экрана телефона (пиксели, без догадок).

Находит оранжевую кнопку по цвету заливки и серую кнопку по рамке в той же
строке, возвращает их ширину и высоту в пикселях снимка и в CSS-пикселях.

Запуск:
    python tools/measure_buttons_image.py data/phone_hero2.png
"""
import sys
from PIL import Image

path = sys.argv[1]
im = Image.open(path).convert("RGB")
W, H = im.size
px = im.load()
print("снимок:", path, W, "×", H)


def is_orange(c):
    r, g, b = c
    return r > 180 and 60 < g < 145 and b < 80


def is_light(c):
    r, g, b = c
    return r > 120 and g > 120 and b > 120


# ищем строки, где много оранжевых пикселей — это оранжевая кнопка
rows = []
for y in range(0, H, 4):
    cnt = sum(1 for x in range(0, W, 4) if is_orange(px[x, y]))
    if cnt > 20:
        rows.append((y, cnt))
if not rows:
    print("оранжевая кнопка не найдена")
    sys.exit(1)

top = rows[0][0]
# группируем подряд идущие строки в блоки
blocks, cur = [], [rows[0]]
for item in rows[1:]:
    if item[0] - cur[-1][0] <= 8:
        cur.append(item)
    else:
        blocks.append(cur)
        cur = [item]
blocks.append(cur)

for bi, block in enumerate(blocks):
    y0, y1 = block[0][0], block[-1][0]
    mid = (y0 + y1) // 2
    xs = [x for x in range(W) if is_orange(px[x, mid])]
    if not xs:
        continue
    x0, x1 = min(xs), max(xs)
    print(f"\nоранжевая кнопка #{bi+1}: y {y0}..{y1} (высота {y1-y0}), "
          f"x {x0}..{x1} (ширина {x1-x0})")

    # в той же строке справа ищем кнопку с рамкой (светлые пиксели по краям)
    y_scan = mid
    edges = [x for x in range(x1 + 10, W) if is_light(px[x, y_scan])]
    if edges:
        print(f"   соседняя кнопка (по рамке): x {min(edges)}..{max(edges)} "
              f"(ширина {max(edges)-min(edges)})")

print("\nмасштаб экрана: физических пикселей на CSS-пиксель = 1080/390 ≈ 2.77")
