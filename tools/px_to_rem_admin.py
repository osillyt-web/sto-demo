# -*- coding: utf-8 -*-
"""Админка: переводит в rem отступы, связанные с текстом (padding / gap / margin),
   как на сайте. Каркас страницы (шапка, боковое меню как блок, подвал, контейнер),
   ширины, высоты, рамки и скругления остаются в px.

   Запуск:  python tools/px_to_rem_admin.py            предпросмотр
            python tools/px_to_rem_admin.py --write    запись
"""
import re
import sys

# каркас: внешняя геометрия, к тексту не привязана — не трогаем
EXCLUDE = ('.adm-body', 'body.adm', '.adm-main', '.adm-head', '.adm-head-inner',
           '.adm-foot', '.adm-shell', '.wrap')
PROPS = ('padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
         'padding-block', 'padding-inline', 'gap', 'row-gap', 'column-gap',
         'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
         'margin-block', 'margin-inline')
MIN_PX = 4      # микро-зазоры 1-3 px (рамки, бейджи) не трогаем
ROOT = 16.0     # 1rem = 16px


def clean(selector):
    s = re.sub(r'/\*.*?\*/', ' ', selector, flags=re.S)
    return re.sub(r'\s+', ' ', s).strip()


def to_rem(px):
    return ('%.4f' % (float(px) / ROOT)).rstrip('0').rstrip('.') + 'rem'


def is_excluded(selector):
    s = clean(selector).lower()
    return any(x in s for x in EXCLUDE)


def convert_block(selector, body, changes):
    def repl(m):
        prop, value = m.group(1), m.group(2)
        if prop not in PROPS:
            return m.group(0)
        new = re.sub(r'(\d+(?:\.\d+)?)px',
                     lambda mm: to_rem(mm.group(1)) if float(mm.group(1)) >= MIN_PX else mm.group(0),
                     value)
        if new != value:
            changes.append((clean(selector), prop, value.strip(), new.strip()))
        return prop + ':' + new

    return re.sub(r'([a-z-]+)\s*:\s*([^;}]+)', repl, body)


def main():
    path = 'static/admin.css'
    src = open(path, encoding='utf-8', newline='').read()
    changes = []

    def walk(m):
        selector, body = m.group(1), m.group(2)
        s = clean(selector).lower()
        if s and not s.startswith('@') and not is_excluded(selector):
            body = convert_block(selector, body, changes)
        return selector + '{' + body + '}'

    out = re.sub(r'([^{}]+)\{([^{}]*)\}', walk, src)

    print("изменений: %d" % len(changes))
    for sel, prop, old, new in changes:
        print("  %-34s %-13s %-16s -> %s" % (sel[:34], prop, old, new))

    print("каркас (остаётся в px):", ", ".join(EXCLUDE))

    if '--write' in sys.argv:
        if out.count('{') != out.count('}'):
            print("ОШИБКА: нарушен баланс скобок — запись отменена")
            return
        open(path, 'wb').write(out.encode('utf-8'))
        print("записано:", path)
    else:
        print("предпросмотр (запись не выполнена)")


main()