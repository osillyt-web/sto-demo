# -*- coding: utf-8 -*-
"""Админка: приводит файл к единой системе сайта (гармония).

1. Значения к шкалам сайта: отступы 4/8/12/16/24/32, скругления 4/10/14/999,
   веса 400/600/800, межстрочный 1/1.2/1.45/1.6.
2. Элементы управления — как на сайте:
   - компактные кнопки .btn-sm: высота 44, шрифт 1rem;
   - переключатели .seg-btn: высота 44, шрифт 1rem;
   - кнопки-иконки .icon-btn: 44 на 44;
   - поля ввода: высота 52, шрифт 1rem.

Запуск:  python tools/admin_harmony.py            предпросмотр
         python tools/admin_harmony.py --write    запись
"""
import re
import sys

SPACING_SCALE = [4, 8, 12, 16, 24, 32]
RADIUS_SCALE = [4, 10, 14, 999]
WEIGHT_SCALE = [400, 600, 800]
LH_SCALE = [1, 1.2, 1.45, 1.6]
PROPS = ('padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
         'gap', 'row-gap', 'column-gap', 'margin', 'margin-top', 'margin-right',
         'margin-bottom', 'margin-left')

# что становится каким размером: элементы управления админки
CONTROLS = (
    ('.btn-sm', 'min-height', '44px'),
    ('.btn-sm', 'font-size', '1rem'),
    ('.seg-btn', 'min-height', '44px'),
    ('.seg-btn', 'font-size', '1rem'),
    ('.icon-btn', 'width', '44px'),
    ('.icon-btn', 'height', '44px'),
    ('.search', 'font-size', '1rem'),
    ('.note-input', 'font-size', '1rem'),
)


def near(value, scale):
    return min(scale, key=lambda s: (abs(s - value), s))


def rem(px):
    return format(px / 16.0, '.4f').rstrip('0').rstrip('.') + 'rem'


def scale_spacing(sel, body, changes):
    def repl(m):
        prop, val = m.group(1), m.group(2)
        if prop not in PROPS:
            return m.group(0)

        def conv(x):
            px = float(x.group(1)) * 16
            if px < 2 or px > 40:
                return x.group(0)
            n = near(round(px, 2), SPACING_SCALE)
            if abs(n - px) < 0.01:
                return x.group(0)
            changes.append((sel, prop, x.group(1) + 'rem', rem(n)))
            return rem(n)

        return prop + ':' + re.sub(r'(\d+(?:\.\d+)?)rem', conv, val)

    return re.sub(r'([a-z-]+)\s*:\s*([^;}]+)', repl, body)


def scale_radius(sel, body, changes):
    def repl(m):
        prop, val = m.group(1), m.group(2)
        if prop != 'border-radius':
            return m.group(0)

        def conv(x):
            px = float(x.group(1))
            if px > 200:      # 999px — «пилюля», оставляем
                return x.group(0)
            n = near(px, RADIUS_SCALE)
            if abs(n - px) < 0.01:
                return x.group(0)
            changes.append((sel, prop, x.group(1) + 'px', str(n) + 'px'))
            return str(n) + 'px'

        return prop + ':' + re.sub(r'(\d+(?:\.\d+)?)px', conv, val)

    return re.sub(r'([a-z-]+)\s*:\s*([^;}]+)', repl, body)


def scale_weight_lh(sel, body, changes):
    def repl(m):
        prop, val = m.group(1), m.group(2)
        if prop == 'font-weight':
            nums = re.findall(r'\d+', val)
            if nums:
                n = near(int(nums[0]), WEIGHT_SCALE)
                if str(n) != nums[0]:
                    changes.append((sel, prop, nums[0], str(n)))
                return prop + ':' + str(n)
        if prop == 'line-height':
            nums = re.findall(r'(\d+(?:\.\d+)?)', val)
            if nums:
                v = float(nums[0])
                if 0.9 <= v <= 2.0:
                    n = near(v, LH_SCALE)
                    if abs(n - v) > 0.01:
                        changes.append((sel, prop, nums[0], str(n)))
                    return prop + ':' + str(n)
        return m.group(0)

    return re.sub(r'([a-z-]+)\s*:\s*([^;}]+)', repl, body)


def main():
    path = 'static/admin.css'
    src = open(path, encoding='utf-8', newline='').read()
    changes = []

    def walk(m):
        sel, body = m.group(1), m.group(2)
        name = sel.strip().split('\n')[-1].strip()
        if not name or name.startswith('@'):
            return m.group(0)
        body = scale_spacing(name, body, changes)
        body = scale_radius(name, body, changes)
        body = scale_weight_lh(name, body, changes)
        for target, prop, value in CONTROLS:
            if name.startswith(target) or (',' in name and target in name):
                body = re.sub(r'\b' + prop + r'\s*:\s*[^;}]+', prop + ':' + value, body, count=1)
                if prop not in body:
                    body = body.rstrip(';') + ';' + prop + ':' + value
                changes.append((target, prop, '(было своё)', value))
        return sel + '{' + body + '}'

    out = re.sub(r'([^{}]+)\{([^{}]*)\}', walk, src)

    print("изменений: %d" % len(changes))
    seen = set()
    for sel, prop, old, new in changes:
        key = (sel, prop, old, new)
        if key in seen:
            continue
        seen.add(key)
        print("  %-24s %-13s %-16s -> %s" % (sel[:24], prop, old, new))

    if '--write' in sys.argv:
        if out.count('{') != out.count('}'):
            print("ОШИБКА: нарушен баланс скобок — запись отменена")
            return
        open(path, 'wb').write(out.encode('utf-8'))
        print("записано:", path)
    else:
        print("предпросмотр (запись не выполнена)")


main()
