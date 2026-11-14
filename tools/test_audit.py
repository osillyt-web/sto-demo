# -*- coding: utf-8 -*-
"""Проверка правок по аудиту 11.11.2026 на изолированной базе.

Поднимает отдельный сервер (порт 8599, своя база data/test_audit.db) и проверяет:
  1. гонку слотов: 10 одновременных заявок при вместимости 2 → принято не больше 2;
  2. предел тела запроса: 70 КБ → 413;
  3. битый JSON → 400, нестроковое поле → 400;
  4. CSRF: чужой Origin и домен с тем же окончанием → 403, свой → 200;
  5. необработанная ошибка → 500 и запись в data/errors.log;
  6. страница входа не раскрывает пароль.

Рабочую базу не трогает: путь передаётся переменной STO_DB.
Запуск: python tools/test_audit.py
"""
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8599
DB = os.path.join(BASE, 'data', 'test_audit.db')
ERRORS = os.path.join(BASE, 'data', 'errors.log')
PASSWORD = 'AuditTest-2026-XyZ'
URL = f'http://127.0.0.1:{PORT}'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Без авто-перехода: иначе 302 на /admin скрывает и код, и cookie сессии."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirect)
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('  ОК   ' if ok else ' ПРОВАЛ ') + name + (('  — ' + detail) if detail else ''))


def request(method, path, payload=None, raw=None, cookie=None, origin=None, ctype='application/json'):
    data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    headers = {}
    if data is not None:
        headers['Content-Type'] = ctype
    if cookie:
        headers['Cookie'] = cookie
    if origin:
        headers['Origin'] = origin
    req = urllib.request.Request(URL + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace'), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace'), dict(e.headers)


def wait_ready(deadline=40):
    end = time.time() + deadline
    while time.time() < end:
        try:
            code, _, _ = request('GET', '/api/health')
            if code == 200:
                return True
        except Exception:
            time.sleep(0.4)
    return False


def next_working_day():
    day = datetime.date.today() + datetime.timedelta(days=1)
    while day.weekday() == 6:                      # воскресенье закрыто
        day += datetime.timedelta(days=1)
    return day


def main():
    for f in (DB, DB + '-wal', DB + '-shm'):
        if os.path.exists(f):
            os.remove(f)
    auth = os.path.join(BASE, 'data', 'test_audit_auth.json')      # свой файл пароля: чужой не трогаем
    if os.path.exists(auth):
        os.remove(auth)
    env = dict(os.environ, STO_DB=DB, STO_AUTH=auth, PORT=str(PORT), HOST='127.0.0.1',
               ADMIN_PASSWORD=PASSWORD, PYTHONUTF8='1', LEAD_LIMIT='500', ATTEMPT_LIMIT='500')
    log = open(os.path.join(BASE, 'data', 'test_audit.log'), 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, 'server.py'], cwd=BASE, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_ready():
            print('ПРОВАЛ: сервер не поднялся'); return 1
        print(f'изолированный сервер поднят: {URL}, база {os.path.relpath(DB, BASE)}\n')

        # вместимость часа — 2 машины
        conn = sqlite3.connect(DB)
        conn.execute("INSERT INTO settings(key, value) VALUES('slot_capacity','2') "
                     "ON CONFLICT(key) DO UPDATE SET value='2'")
        conn.commit(); conn.close()

        day = next_working_day().isoformat()

        # ---- 1. гонка слотов
        payload = {"name": 'Перевірка', "phone": '+380 44 111 22 33', "consent": '1',
                   "service": 'Діагностика', "slot_date": day, "slot_time": '09:00'}
        with ThreadPoolExecutor(max_workers=10) as ex:
            answers = list(ex.map(lambda _: request('POST', '/api/leads', payload)[0], range(10)))
        accepted = answers.count(200)
        conflicts = answers.count(409)
        conn = sqlite3.connect(DB)
        stored = conn.execute("SELECT COUNT(*) FROM leads WHERE slot_date=? AND slot_time='09:00'",
                              (day,)).fetchone()[0]
        conn.close()
        check('гонка слотов: принято не больше вместимости (2)',
              accepted <= 2 and stored <= 2,
              f'принято {accepted} из 10, отказ 409 — {conflicts}, в базе {stored}')

        # ---- 2. предел тела запроса
        code, body, _ = request('POST', '/api/leads', raw=b'x' * 70000)
        check('тело 70 КБ → 413', code == 413, f'код {code}')
        code, body, _ = request('POST', '/api/leads', raw=b'x' * 70000)
        check('ответ 413 объясняет предел', 'limit' in body or 'великий' in body, body[:80])

        # ---- 3. некорректный JSON и типы
        code, body, _ = request('POST', '/api/leads', raw=b'{"name": "a", ')
        check('битый JSON → 400', code == 400, f'код {code}')
        code, body, _ = request('POST', '/api/leads', payload={"name": ["a", "b"], "consent": '1'})
        check('поле-список → 400', code == 400, f'код {code} {body[:60]}')

        # ---- 4. CSRF
        code, body, headers = request('POST', '/admin/login', payload={"password": PASSWORD})
        cookie = ''
        for k, v in headers.items():
            if k.lower() == 'set-cookie' and 'sid=' in v:
                cookie = v.split(';')[0]
        check('вход в админку работает', code in (200, 302) and cookie.startswith('sid='),
              f'код {code}, cookie {"есть" if cookie else "нет"}')
        host_ok = f'http://127.0.0.1:{PORT}'
        code, _, _ = request('POST', '/admin/lead', payload={"id": 1, "status": 'new'},
                             cookie=cookie, origin=host_ok)
        check('свой Origin принимается', code == 200, f'код {code}')
        for bad in (f'http://evil-127.0.0.1:{PORT}', f'http://127.0.0.1:{PORT}.evil.com',
                    f'https://127.0.0.1:{PORT + 1}'):
            code, _, _ = request('POST', '/admin/lead', payload={"id": 1, "status": 'new'},
                                 cookie=cookie, origin=bad)
            check(f'чужой Origin отвергнут ({bad[:38]})', code == 403, f'код {code}')

        # ---- 5. необработанная ошибка → 500 и запись в errors.log
        before = os.path.getsize(ERRORS) if os.path.exists(ERRORS) else 0
        code, _, _ = request('POST', '/admin/lead', payload={"id": 'не число', "status": 'new'},
                             cookie=cookie, origin=host_ok)
        after = os.path.getsize(ERRORS) if os.path.exists(ERRORS) else 0
        check('некорректное значение → 500, а не обрыв соединения', code == 500, f'код {code}')
        check('сбой записан в errors.log', after > before, f'было {before} Б, стало {after} Б')

        # ---- 6. страница входа без пароля
        code, body, _ = request('GET', '/admin/login')
        check('страница входа не содержит пароль',
              PASSWORD not in body and 'name="password" value=' not in body,
              f'код {code}, длина {len(body)}')

        print()
        bad = [n for n, ok in results if not ok]
        print(f'ИТОГ: проверок {len(results)}, провалов {len(bad)}' + (f' — {bad}' if bad else ' — все прошли'))
        return 1 if bad else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


if __name__ == '__main__':
    sys.exit(main())