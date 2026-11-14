# -*- coding: utf-8 -*-
"""Проверка настроек Telegram и журнала на боевом сервере (значения секретов не печатаем)."""
import sqlite3

c = sqlite3.connect('data/sto.db')
c.row_factory = sqlite3.Row
rows = {r['key']: (r['value'] or '') for r in c.execute('SELECT key, value FROM settings')}
print('настройки связи:')
for k in ('tg_token', 'tg_chat', 'tg_enabled'):
    v = rows.get(k)
    if v is None:
        print('  ', k, '— НЕТ в базе')
    elif k == 'tg_token':
        print('  ', k, '— задан, длина', len(v), '| вид:', v[:6] + '…' + v[-4:])
    else:
        print('  ', k, '=', v)
print('  всего настроек:', len(rows))

print('последние действия в админке:')
for r in c.execute('SELECT at, action, target FROM audit ORDER BY id DESC LIMIT 6'):
    print('  ', r['at'], '|', r['action'], '|', r['target'] or '')

print('заявок в базе:', c.execute('SELECT COUNT(*) FROM leads').fetchone()[0])
c.close()
