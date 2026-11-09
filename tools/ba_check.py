#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка блока «до/після» на живой странице: ползунок реально меняет картинку,
левая половина — чёрно-белая, правая — цветная. Печатает PASS/FAIL, код 0/1."""
import os
import sys
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat

URL = "http://127.0.0.1:8000/"
SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shots", "ba_check.png")
fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (" :: %s" % extra if extra else ""))
    if not cond:
        fails.append(name)


def saturation(img, box):
    """Средняя насыщенность области: 0 — чёрно-белое, заметно больше — цветное."""
    s_channel = img.crop(box).convert("HSV").split()[1]
    return ImageStat.Stat(s_channel).mean[0]


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(1200)

        frames = pg.query_selector_all(".ba-block .ba-frame")
        check("на головній два блоки порівняння", len(frames) == 2, len(frames))

        for i, frame in enumerate(frames, 1):
            frame.scroll_into_view_if_needed()
            pg.wait_for_timeout(400)
            handle = frame.query_selector(".ba-handle")
            check("блок %d: повзунок на місці" % i, handle is not None)
            if not handle:
                continue

            # сдвигаем ползунок влево и вправо — видимая часть должна меняться
            box = frame.bounding_box()
            pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
            pg.mouse.down()
            pg.mouse.move(box["x"] + box["width"] * 0.78, box["y"] + box["height"] / 2, steps=8)
            pg.mouse.up()
            pg.wait_for_timeout(300)
            wide = pg.evaluate("""(el) => el.querySelector('.ba-before').style.clipPath""", frame)
            pg.mouse.move(box["x"] + box["width"] * 0.78, box["y"] + box["height"] / 2)
            pg.mouse.down()
            pg.mouse.move(box["x"] + box["width"] * 0.22, box["y"] + box["height"] / 2, steps=8)
            pg.mouse.up()
            pg.wait_for_timeout(300)
            narrow = pg.evaluate("""(el) => el.querySelector('.ba-before').style.clipPath""", frame)
            check("блок %d: ползунок меняет открытую часть фото" % i, wide != narrow,
                  "%s -> %s" % (wide, narrow))

            # ставим ровно половину и смотрим цвета слева и справа
            pg.mouse.move(box["x"] + box["width"] * 0.22, box["y"] + box["height"] / 2)
            pg.mouse.down()
            pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8)
            pg.mouse.up()
            pg.wait_for_timeout(400)
            path = os.path.join(os.path.dirname(SHOT), "ba_block_%d.png" % i)
            frame.screenshot(path=path)
            im = Image.open(path)
            w, h = im.size
            left = saturation(im, (int(w * 0.05), int(h * 0.3), int(w * 0.20), int(h * 0.7)))
            right = saturation(im, (int(w * 0.80), int(h * 0.3), int(w * 0.95), int(h * 0.7)))
            check("блок %d: слева чёрно-белое (насыщенность %.1f)" % (i, left), left < 5,
                  "слева %.1f" % left)
            check("блок %d: справа цветное, заметно живее левого края" % i, right > left + 8,
                  "слева %.1f / справа %.1f" % (left, right))

        b.close()

    print("ИТОГ: %s" % ("ВСЁ ЗЕЛЁНОЕ" if not fails else "ПРОВАЛЕНО %d: %s" % (len(fails), fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
