# -*- coding: utf-8 -*-
"""Переводит в rem отступы, связанные с текстом:
   паддинги кнопок и полей, паддинги карточек, интервалы вокруг заголовков.
   Внешние отступы секций, шапка, футер, рамки и скругления — не трогает.
   Запуск: python tools/px_to_rem_text.py [--write]
"""
import re
import sys

# селекторы, у которых отступы связаны с текстом (проверка по подстроке)
TARGETS = (
    # заголовки — интервалы
    'h1', 'h2', 'h3', 'h4', '.page-h1', '.sec-h', '.card-h', '.sec-head', '.legal h2',
    # кнопки и элементы управления
    '.btn', 'button', '.chip', '.pill', '.tab', '.day', '.slot', '.seg', '.filter',
    '.check', '.rev-filters', '.top-actions', '.hero-cta',
    # поля ввода
    'input', 'select', 'textarea', '.field', '.form', '.appeal',
    # карточки и текстовые блоки
    '.card', '.review', '.case', '.svc', '.step', '.stat', '.fact', '.note', '.alert',
    '.faq', '.acc', '.info', '.price', '.plan', '.lead', '.prose', '.stack',
)
# свойства, которые переводятся
SPACING = ('padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
           'padding-block', 'padding-inline', 'gap', 'row-gap', 'column-gap')
HEADING_ONLY = ('margin', 'margin-top', 'margin-bottom', 'margin-block', 'margin-block-start',
                'margin-block-end')
MIN_PX = 4          # мелочь 1–3 px (линии, микро-зазоры) не трогаем
ROOT = 16.0         # базовый размер: 1rem = 16px


def to_rem(px):
    val = round(float(px) / ROOT, 4)
    txt = ('%.4f' % val).rstrip('0').rstrip('.')
    return txt + 'rem'


def clean(selector):
    """убирает комментарии — иначе они попадают в имя селектора"""
    s = re.sub(r'/\*.*?\*/', ' ', selector, flags=re.S)
    return re.sub(r'\s+', ' ', s).strip()


def is_target(selector):
    s = clean(selector).lower()
    if not s or s.startswith('@'):
        return False
    return any(t in s for t in TARGETS)


def is_heading(selector):
    s = clean(selector).lower()
    return any(h in s for h in ('h1', 'h2', 'h3', 'h4', 'page-h1', 'sec-h', 'card-h', 'sec-head'))


def convert_block(selector, body, changes):
    props = list(SPACING) + (list(HEADING_ONLY) if is_heading(selector) else [])

    def repl(m):
        prop, value = m.group(1), m.group(2)
        if prop not in props:
            return m.group(0)
        new_value = re.sub(r'(\d+(?:\.\d+)?)px',
                           lambda mm: to_rem(mm.group(1)) if float(mm.group(1)) >= MIN_PX else mm.group(0),
                           value)
        if new_value != value:
            changes.append((clean(selector), prop, value.strip(), new_value.strip()))
        return prop + ':' + new_value

    body = re.sub(r'([a-z-]+)\s*:\s*([^;}]+)', repl, body)
    return body


def main():
    path = 'static/style.css'
    src = open(path, encoding='utf-8', newline='').read()
    changes = []

    def walk(m):
        selector, body = m.group(1), m.group(2)
        if is_target(selector):
            body = convert_block(selector, body, changes)
        return selector + '{' + body + '}'

    out = re.sub(r'([^{}]+)\{([^{}]*)\}', walk, src)
    print("изменений: %d" % len(changes))
    seen = set()
    for sel, prop, old, new in changes:
        key = (sel, prop)
        if key in seen:
            continue
        seen.add(key)
        print("  %-34s %-14s %-16s -> %s" % (sel[:34], prop, old, new))
    if '--write' in sys.argv:
        # база страницы: 16px -> 1rem (тогда базовый текст тоже масштабируется)
        before = out
        out = out.replace('font:16px/1.6 ', 'font:1rem/1.6 ')
        out = out.replace('font-size:16px', 'font-size:1rem')
        print("база body: 16px -> 1rem:", "да" if out != before else "нет совпадения")
        open(path, 'wb').write(out.encode('utf-8'))
        print("записано в", path)
    else:
        print("предпросмотр (запись не выполнена)")


main()
