# -*- coding: utf-8 -*-
"""Правки по аудиту 11.11.2026: 5 пунктов кода + закрытие вывода пароля.

Каждая замена обязана встречаться ровно один раз, иначе скрипт падает.
Запуск: python tools/audit_fixes.py            предпросмотр
        python tools/audit_fixes.py --write    запись
"""
import sys

PATH = 'server.py'
raw = open(PATH, encoding='utf-8', newline='').read()
CRLF = '\r\n' in raw
src = raw.replace('\r\n', '\n') if CRLF else raw
edits = []


def sub(old, new, label):
    global src
    n = src.count(old)
    assert n == 1, f'{label}: найдено {n} совпадений вместо 1'
    src = src.replace(old, new, 1)
    edits.append(label)


# ---- 1. импорты: socket (таймаут чтения тела) и urlsplit (точная CSRF-проверка)
sub("import mimetypes\nimport threading",
    "import mimetypes\nimport socket\nimport threading",
    "импорт socket")
sub("from urllib.parse import urlparse, parse_qs, unquote, quote",
    "from urllib.parse import urlparse, urlsplit, parse_qs, unquote, quote",
    "импорт urlsplit")

# ---- 2. путь к базе можно переопределить переменной STO_DB (изолированные тесты)
sub('DB_PATH = os.path.join(DATA_DIR, "sto.db")',
    'DB_PATH = os.environ.get("STO_DB") or os.path.join(DATA_DIR, "sto.db")',
    "STO_DB для тестов")

# ---- 3. пределы тела запроса
sub('ERRORS_LOG = os.path.join(DATA_DIR, "errors.log")',
    'ERRORS_LOG = os.path.join(DATA_DIR, "errors.log")\n'
    'MAX_BODY_BYTES = 64 * 1024      # предел тела запроса: больше — ответ 413\n'
    'READ_TIMEOUT_S = 15             # предел ожидания тела, иначе медленный клиент держит поток',
    "пределы тела запроса")

# ---- 4. запись ошибок на уровне модуля (нужна фоновому потоку напоминаний)
sub("class Handler(BaseHTTPRequestHandler):",
    'def write_error(fmt, *args):\n'
    '    """Ошибки пишем в data/errors.log: на хостинге stdout теряется."""\n'
    '    try:\n'
    '        os.makedirs(DATA_DIR, exist_ok=True)\n'
    '        with open(ERRORS_LOG, "a", encoding="utf-8") as fh:\n'
    '            fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} " + (fmt % args) + "\\n")\n'
    '    except Exception:\n'
    '        pass\n'
    '\n'
    '\n'
    "class Handler(BaseHTTPRequestHandler):",
    "функция write_error")

sub('''    def log_error(self, fmt, *args):
        """Ошибки пишем в data/errors.log — иначе на хостинге они теряются."""
        try:
            with open(ERRORS_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} " + (fmt % args) + "\\n")
        except Exception:
            pass
        return super().log_error(fmt, *args)''',
    '''    def log_error(self, fmt, *args):
        """Ошибки пишем в data/errors.log — иначе на хостинге они теряются."""
        write_error(fmt, *args)
        return super().log_error(fmt, *args)''',
    "log_error через write_error")

# ---- 5. обёртки маршрутов: необработанная ошибка → errors.log и 500, а не обрыв
sub("    def do_GET(self):\n        u = urlparse(self.path)",
    '''    def do_GET(self):
        try:
            return self._route_get()
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception as exc:
            write_error("do_GET %s: %r", self.path, exc)
            try:
                self.json_out({"error": "Помилка сервера"}, 500)
            except Exception:
                pass

    def _route_get(self):
        u = urlparse(self.path)''',
    "обёртка do_GET")

sub("    def do_POST(self):\n        path = urlparse(self.path).path",
    '''    def do_POST(self):
        try:
            return self._route_post()
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception as exc:
            write_error("do_POST %s: %r", self.path, exc)
            try:
                self.json_out({"error": "Помилка сервера"}, 500)
            except Exception:
                pass

    def _route_post(self):
        path = urlparse(self.path).path''',
    "обёртка do_POST")

sub('''        data = self.body()

        if path == "/api/hit":''',
    '''        data = self.body()
        if data is None:                      # 413 / 400 / 408 уже отправлены клиенту
            return

        if path == "/api/hit":''',
    "выход при ошибке тела")

# ---- 6. body(): предел размера, таймаут чтения, корректность JSON и типов полей
sub('''    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        ctype = self.headers.get("Content-Type") or ""
        # sendBeacon с обычной строкой приходит как text/plain — тело всё равно JSON
        if ctype.startswith("application/json") or raw.lstrip().startswith("{"):
            try:
                return json.loads(raw or "{}")
            except json.JSONDecodeError:
                return {}
        return {k: v[0] for k, v in parse_qs(raw).items()}''',
    '''    def body(self):
        """Тело запроса с пределами: размер, время ожидания, корректность JSON и типов.

        Возвращает словарь или None — во втором случае ответ клиенту уже отправлен.
        """
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            self.json_out({"error": "Некоректна довжина тіла"}, 400)
            return None
        if n < 0:
            self.json_out({"error": "Некоректна довжина тіла"}, 400)
            return None
        if n > MAX_BODY_BYTES:
            self.close_connection = True
            self.json_out({"error": "Занадто великий запит", "limit": MAX_BODY_BYTES}, 413)
            return None
        try:
            self.connection.settimeout(READ_TIMEOUT_S)
        except OSError:
            pass
        try:
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        except (socket.timeout, TimeoutError):
            self.close_connection = True
            self.json_out({"error": "Час очікування вичерпано"}, 408)
            return None
        ctype = self.headers.get("Content-Type") or ""
        # sendBeacon с обычной строкой приходит как text/plain — тело всё равно JSON
        if ctype.startswith("application/json") or raw.lstrip().startswith("{"):
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError:
                self.json_out({"error": "Некоректний JSON"}, 400)
                return None
            if not isinstance(parsed, dict):
                self.json_out({"error": "Очікується об'єкт JSON"}, 400)
                return None
            bad = [k for k, v in parsed.items()
                   if v is not None and not isinstance(v, (str, int, float, bool))]
            if bad:
                self.json_out({"error": "Некоректний тип поля: " + str(bad[0])[:40]}, 400)
                return None
            return parsed
        return {k: v[0] for k, v in parse_qs(raw).items()}''',
    "body(): 413 / 408 / 400")

# ---- 7. CSRF: точное сравнение схемы, хоста и порта
sub('''    def same_origin(self):
        """CSRF-барьер: изменяющие запросы с чужого Origin не проходят."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return origin.endswith(self.headers.get("Host") or "\\0")''',
    '''    def same_origin(self):
        """CSRF-барьер: изменяющие запросы с чужого Origin не проходят.

        Сравниваем имя хоста и порт точно. Прежняя проверка `origin.endswith(host)`
        пропускала чужие домены с тем же окончанием, например evil-osillytweb.alwaysdata.net.
        """
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return False
        origin_port = parts.port or (443 if parts.scheme == "https" else 80)
        host_name, _, host_port = host.partition(":")
        if (parts.hostname or "").lower() != host_name:
            return False
        if host_port:
            try:
                if int(host_port) != origin_port:
                    return False
            except ValueError:
                return False
        return True''',
    "same_origin: точное сравнение")

# ---- 8. слот: проверка вместимости и вставка в одной транзакции (BEGIN IMMEDIATE)
sub('''            slot_date = (data.get("slot_date") or "").strip()
            slot_time = (data.get("slot_time") or "").strip()
            conn = get_db()
            if slot_date or slot_time:
                day = parse_day(slot_date)
                if not day or slot_time not in slot_times(conn):
                    conn.close()
                    return self.json_out({"ok": False, "error": "Оберіть вільний час"}, 400)
                today = datetime.date.today()
                if day < today or day > today + datetime.timedelta(days=SLOT_DAYS_AHEAD):
                    conn.close()
                    return self.json_out({"ok": False, "error": "Дата поза доступним періодом"}, 400)
                if day.weekday() == 6:
                    conn.close()
                    return self.json_out({"ok": False, "error": "Неділя — за домовленістю, оберіть інший день"}, 400)
                taken = booked_map(conn, day, day).get((day.isoformat(), slot_time), 0)
                if taken >= slot_capacity(conn):
                    conn.close()
                    return self.json_out({"ok": False, "error": "Цей час щойно зайняли — оберіть інший"}, 409)
                when_at = f"{day.strftime('%d.%m.%Y')} {slot_time}"
            else:
                when_at = (data.get("when_at") or "").strip()[:40]

            utm_source = (data.get("utm_source") or "").strip()[:60]
            utm_medium = (data.get("utm_medium") or "").strip()[:60]
            utm_campaign = (data.get("utm_campaign") or "").strip()[:60]
            referrer = (data.get("referrer") or "").strip()[:80]
            source = utm_source or referrer or "Прямий захід"

            if not rate_ok(LEAD_HITS, self.ip(), LEAD_LIMIT, LEAD_WINDOW_S):
                return self.json_out({"ok": False, "error": "Забагато заявок"}, 429)
            lead_token = secrets.token_urlsafe(9)''',
    '''            slot_date = (data.get("slot_date") or "").strip()
            slot_time = (data.get("slot_time") or "").strip()
            conn = get_db()
            try:
                if slot_date or slot_time:
                    day = parse_day(slot_date)
                    if not day or slot_time not in slot_times(conn):
                        return self.json_out({"ok": False, "error": "Оберіть вільний час"}, 400)
                    today = datetime.date.today()
                    if day < today or day > today + datetime.timedelta(days=SLOT_DAYS_AHEAD):
                        return self.json_out({"ok": False, "error": "Дата поза доступним періодом"}, 400)
                    if day.weekday() == 6:
                        return self.json_out({"ok": False, "error": "Неділя — за домовленістю, оберіть інший день"}, 400)
                    when_at = f"{day.strftime('%d.%m.%Y')} {slot_time}"
                else:
                    when_at = (data.get("when_at") or "").strip()[:40]

                utm_source = (data.get("utm_source") or "").strip()[:60]
                utm_medium = (data.get("utm_medium") or "").strip()[:60]
                utm_campaign = (data.get("utm_campaign") or "").strip()[:60]
                referrer = (data.get("referrer") or "").strip()[:80]
                source = utm_source or referrer or "Прямий захід"

                if not rate_ok(LEAD_HITS, self.ip(), LEAD_LIMIT, LEAD_WINDOW_S):
                    return self.json_out({"ok": False, "error": "Забагато заявок"}, 429)

                # P0: проверка вместимости и вставка — в одной транзакции с блокировкой
                # записи. Без блокировки две одновременные заявки проходят проверку до
                # вставки и занимают один час сверх вместимости.
                if conn.in_transaction:
                    conn.commit()
                conn.execute("BEGIN IMMEDIATE")
                try:
                    if slot_date or slot_time:
                        taken = booked_map(conn, day, day).get((day.isoformat(), slot_time), 0)
                        if taken >= slot_capacity(conn):
                            conn.rollback()
                            return self.json_out(
                                {"ok": False, "error": "Цей час щойно зайняли — оберіть інший"}, 409)
                    lead_token = secrets.token_urlsafe(9)''',
    "слот: начало транзакции")

sub('''                          utm_source, utm_medium, utm_campaign, kind, lead_token))
            lead_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO events (name, path, session) VALUES ('lead', '/', ?)",
                         ((data.get("sid") or "")[:32],))
            conn.commit()
            conn.close()''',
    '''                          utm_source, utm_medium, utm_campaign, kind, lead_token))
                    lead_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute("INSERT INTO events (name, path, session) VALUES ('lead', '/', ?)",
                                 ((data.get("sid") or "")[:32],))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            finally:
                conn.close()''',
    "слот: коммит и закрытие")

# ---- 9. напоминания: сбои не прячем, соединение закрываем всегда
sub('''    while True:
        try:
            conn = get_db()
            now = datetime.datetime.now()''',
    '''    while True:
        conn = None
        try:
            conn = get_db()
            now = datetime.datetime.now()''',
    "reminder_loop: соединение вне try")

sub('''                try:
                    dt = datetime.datetime.strptime(f"{lead['slot_date']} {lead['slot_time']}", "%Y-%m-%d %H:%M")
                except Exception:
                    continue''',
    '''                try:
                    dt = datetime.datetime.strptime(f"{lead['slot_date']} {lead['slot_time']}", "%Y-%m-%d %H:%M")
                except Exception as exc:
                    write_error("reminder: заявка %s — некорректная дата %r", lead["id"], exc)
                    continue''',
    "reminder_loop: лог даты")

sub('''                    if ok:
                        conn.execute("UPDATE leads SET reminded=1 WHERE id=?", (lead["id"],))
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(900)''',
    '''                    if ok:
                        conn.execute("UPDATE leads SET reminded=1 WHERE id=?", (lead["id"],))
                        conn.commit()
        except Exception as exc:
            write_error("reminder_loop: %r", exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception as exc:
                    write_error("reminder_loop: закрытие базы — %r", exc)
        time.sleep(900)''',
    "reminder_loop: лог сбоя и закрытие")

# ---- 10. страница входа больше не показывает пароль
sub('''    hint = ""
    if is_default_password():
        hint = ('<form class="demo-login" method="post" action="/admin/login">'
                '<input type="hidden" name="password" value="' + esc(INITIAL_PASSWORD) + '">'
                '<button class="btn btn-accent btn-wide" type="submit">Увійти з демо-паролем</button>'
                '</form>'
                '<p class="hint">Пароль: <b>' + esc(INITIAL_PASSWORD) + '</b> · '
                'змінюється в панелі або змінною ADMIN_PASSWORD</p>')''',
    '''    hint = ""
    if is_default_password():
        # Пароль на странице не показываем: подсказка раскрывала значение всему интернету.
        hint = ('<p class="hint">Демо-режим: пароль задається змінною ADMIN_PASSWORD '
                'і змінюється в панелі після входу.</p>')''',
    "вход: без вывода пароля")

print("правок применено:", len(edits))
for e in edits:
    print("   +", e)

if '--write' in sys.argv:
    out = src.replace('\n', '\r\n') if CRLF else src
    open(PATH, 'wb').write(out.encode('utf-8'))
    print("записано:", PATH, "(CRLF)" if CRLF else "(LF)")
else:
    print("предпросмотр (запись не выполнена)")