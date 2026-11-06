#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АвтоТочка — сайт СТО/детейлинг + админ-панель (демо для портфолио).
Без внешних зависимостей: только стандартная библиотека Python 3.10+.

Запуск:  python server.py
Сайт:    http://127.0.0.1:8000/
Админка: http://127.0.0.1:8000/admin
"""

import os
import sys
import re
import csv
import io
import json
import gzip
import glob
import time
import hmac
import base64
import sqlite3
import secrets
import datetime
import mimetypes
import threading
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote, quote

from content import SERVICES, BRANDS, SERVICE_SLUG_BY_TITLE
import seo_pages
import ops

BASE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path):
    """Простой .env без зависимостей: KEY=VALUE, '#' — комментарий, уже заданные не перетираем."""
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv(os.path.join(BASE, ".env"))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA_DIR, "sto.db")
AUTH_PATH = os.path.join(DATA_DIR, "auth.json")
INITIAL_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
PORT = int(os.environ.get("PORT", "8000"))
# локально слушаем только 127.0.0.1; на хостинге (Render) задаётся HOST=0.0.0.0
HOST = os.environ.get("HOST", "127.0.0.1")
SITE_URL = (os.environ.get("SITE_URL")
            or os.environ.get("RENDER_EXTERNAL_URL")
            or f"http://127.0.0.1:{PORT}")

# сколько заявок с одного IP принимаем за окно (защита от спама); на демо-стенде можно поднять
LEAD_LIMIT = int(os.environ.get("LEAD_LIMIT", "60"))      # принятых заявок с одного IP
LEAD_WINDOW_S = int(os.environ.get("LEAD_WINDOW_S", "600"))
ATTEMPT_LIMIT = int(os.environ.get("ATTEMPT_LIMIT", "200"))  # любых обращений к форме

BACKUPS_DIR = os.path.join(BASE, "backups")
ERRORS_LOG = os.path.join(DATA_DIR, "errors.log")
VERSION = "3.2"
STARTED_AT = datetime.datetime.now()

SESSIONS = {}          # token -> datetime истечения
LOGIN_TRIES = {}       # ip -> [время неудачных попыток]
LEAD_HITS = {}         # ip -> [время принятых заявок]
ATTEMPT_HITS = {}      # ip -> [время любых обращений к форме]
HIT_HITS = {}          # ip -> [время событий аналитики]

CLASSES = {
    "a": ("Легкове / універсал", 1.0),
    "b": ("Кросовер / позашляховик", 1.25),
    "c": ("Преміум / спорт", 1.5),
    "d": ("Мікроавтобус / пікап", 1.35),
}

SEED_SERVICES = [
    ("Діагностика", "450 ₴", "Сканування помилок і висновок майстра за 20 хвилин", 450, "diag"),
    ("Технічне обслуговування", "від 1 900 ₴", "Мастило, фільтри, рідини — за регламентом виробника", 1900, "wrench"),
    ("Шиномонтаж", "від 700 ₴", "Сезонна заміна, балансування, зберігання комплекту", 700, "wheel"),
    ("Кузовний ремонт", "від 3 500 ₴", "Оцінка, ремонт, фарбування — з фото-звітом на кожному етапі", 3500, "spray"),
    ("Полірування кузова", "від 2 400 ₴", "Абразивне або захисне, з усуненням дрібних подряпин", 2400, "shine"),
    ("Хімчистка салону", "від 1 800 ₴", "Салон, підлога, багажник — з сушінням за 4 години", 1800, "seat"),
]

FAQ = [
    ("Скільки часу займає ремонт?",
     "Діагностика — 20 хвилин, ТО — 1,5–2 години, полірування — від 4 годин, "
     "кузовні роботи — від 1 до 3 днів. Точний строк майстер називає після огляду, "
     "до початку робіт, і фіксує в замовленні."),
    ("Чому ціна в калькуляторі неточна?",
     "Калькулятор показує діапазон за прайсом і класом авто. Остаточну суму "
     "підтверджуємо після огляду — і вона не змінюється без вашої згоди."),
    ("Чи можна приїхати зі своїми запчастинами?",
     "Так. У такому разі гарантія 12 місяців поширюється на роботи, а на деталі — "
     "гарантія постачальника."),
    ("Що робите, якщо не встигаєте в строк?",
     "Передзвонюємо заздалегідь і пропонуємо варіанти: підміна авто або перенесення "
     "з пріоритетом. Мовчки не затримуємо — це принцип."),
    ("Чи є гарантія і на що саме?",
     "12 місяців на виконані роботи, письмово в замовленні. На запчастини, які "
     "постачаємо ми, — гарантія виробника."),
]

REVIEWS = [
    ("Олена К.", "Skoda Octavia", 5,
     "Записалась через сайт о 22:00, о 9:00 вже передзвонили. Порахували в калькуляторі "
     "2 300 ₴, на місці вийшло 2 250 ₴ — без сюрпризів."),
    ("Андрій М.", "Toyota RAV4", 5,
     "Полірування і кераміка. Показували фото на кожному етапі, машину віддали чисту, "
     "навіть пороги вимили. Через місяць ні однієї нової подряпини."),
    ("Дмитро С.", "Ford Focus", 5,
     "Приїхав зі стуком у підвісці. Знайшли за 20 хвилин, показали на підйомнику. "
     "Замінили тільки те, що треба — не нав'язували комплекс."),
]

# ----------------------------------------------------------------- слоты запису

SLOT_TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00",
              "14:00", "15:00", "16:00", "17:00", "18:00"]
DEFAULT_CAPACITY = 2          # скільки авто бере одна година
SLOT_DAYS_AHEAD = 14          # на скільки днів вперед показуємо вільні слоти

CONTACT_DEFAULTS = {
    "phone": "+380 44 000-00-00",
    "phone_raw": "+380440000000",
    "address": "Київ, вул. Автосервісна, 12",
    "hours": "Пн–Сб, 9:00–19:00",
    "telegram": "https://t.me/autotochka_demo",
    "viber": "viber://chat?number=%2B380440000000",
    "whatsapp": "https://wa.me/380440000000",
    "reviews_url": "https://maps.google.com/?q=Kyiv,+%D0%B2%D1%83%D0%BB.+%D0%90%D0%B2%D1%82%D0%BE%D1%81%D0%B5%D1%80%D0%B2%D1%96%D1%81%D0%BD%D0%B0,+12",
    "reviews_note": "4.9 з 5 · 213 відгуків у Google",
}

WEEKDAYS_UK = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

# Стоимость хеширования пароля (OWASP: для PBKDF2-SHA256 не меньше 600 000 итераций).
# Хранится вместе с хешем, поэтому старые пароли продолжают работать.
PBKDF2_ITERATIONS = int(os.environ.get("PBKDF2_ITERATIONS", "600000"))

# ----------------------------------------------------------------- авторизация

def _hash_password(password, salt=None, iterations=None):
    iterations = iterations or PBKDF2_ITERATIONS
    salt = salt or secrets.token_bytes(16)
    digest = hashlib_pbkdf2(password, salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iter": iterations}


def hashlib_pbkdf2(password, salt, iterations):
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def load_auth():
    """Пароль хранится хешем. При первом запуске берём его из ADMIN_PASSWORD."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(AUTH_PATH):
        payload = _hash_password(INITIAL_PASSWORD)
        with open(AUTH_PATH, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return payload
    with open(AUTH_PATH, encoding="utf-8") as fh:
        return json.load(fh)


WEAK_PASSWORDS = {"admin123", "12345678", "123456789", "password", "qwerty123", "11111111"}


def password_problem(password):
    """Текст проблемы или пустая строка, если пароль годный."""
    if len(password or "") < 10:
        return "Пароль — мінімум 10 символів"
    if password in WEAK_PASSWORDS or password == INITIAL_PASSWORD:
        return "Цей пароль занадто простий — оберіть інший"
    if not re.search(r"[A-Za-zА-Яа-яЇїІіЄєҐґ]", password) or not re.search(r"\d", password):
        return "Додайте в пароль літери та цифри"
    return ""


def is_default_password():
    """True, пока в системе стоит демо-пароль из ADMIN_PASSWORD (по умолчанию admin123)."""
    try:
        return verify_password(INITIAL_PASSWORD)
    except Exception:
        return False


def verify_password(password, upgrade=True):
    """Проверка пароля. Если хеш старый (меньше итераций) — при верном пароле
    пересчитываем его дороже и сохраняем: вход не требует ничьих действий."""
    auth = load_auth()
    iterations = int(auth.get("iter") or 200_000)
    digest = hashlib_pbkdf2(password or "", bytes.fromhex(auth["salt"]), iterations)
    if not hmac.compare_digest(digest.hex(), auth["hash"]):
        return False
    if upgrade and iterations < PBKDF2_ITERATIONS:
        try:
            _save_auth(_hash_password(password, iterations=PBKDF2_ITERATIONS))
        except Exception:
            pass                                   # не мешаем входу, если диск недоступен
    return True


def _save_auth(payload):
    with open(AUTH_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def set_password(password):
    payload = _hash_password(password)
    _save_auth(payload)
    SESSIONS.clear()          # после смены пароля все сессии сбрасываются
    return payload


# ----------------------------------------------------------------- база

def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price TEXT NOT NULL,
        note TEXT DEFAULT '',
        base INTEGER DEFAULT 0,
        icon TEXT DEFAULT 'wrench',
        photo TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        sort INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, phone TEXT, service TEXT, car TEXT,
        when_at TEXT, comment TEXT,
        note TEXT DEFAULT '',
        estimate TEXT DEFAULT '',
        source TEXT DEFAULT 'Сайт',
        status TEXT DEFAULT 'new',
        created_at TEXT DEFAULT (datetime('now','localtime')))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        path TEXT DEFAULT '',
        session TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT '')""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, created_at)")

    # мягкие миграции старых баз
    lead_cols = {r["name"] for r in conn.execute("PRAGMA table_info(leads)")}
    for col, ddl in (("note", "ALTER TABLE leads ADD COLUMN note TEXT DEFAULT ''"),
                     ("estimate", "ALTER TABLE leads ADD COLUMN estimate TEXT DEFAULT ''"),
                     ("source", "ALTER TABLE leads ADD COLUMN source TEXT DEFAULT 'Сайт'"),
                     ("slot_date", "ALTER TABLE leads ADD COLUMN slot_date TEXT DEFAULT ''"),
                     ("slot_time", "ALTER TABLE leads ADD COLUMN slot_time TEXT DEFAULT ''"),
                     ("utm_source", "ALTER TABLE leads ADD COLUMN utm_source TEXT DEFAULT ''"),
                     ("utm_medium", "ALTER TABLE leads ADD COLUMN utm_medium TEXT DEFAULT ''"),
                     ("utm_campaign", "ALTER TABLE leads ADD COLUMN utm_campaign TEXT DEFAULT ''"),
                     ("kind", "ALTER TABLE leads ADD COLUMN kind TEXT DEFAULT 'book'"),
                     ("token", "ALTER TABLE leads ADD COLUMN token TEXT DEFAULT ''"),
                     ("reminded", "ALTER TABLE leads ADD COLUMN reminded INTEGER DEFAULT 0"),
                     ("confirmed", "ALTER TABLE leads ADD COLUMN confirmed TEXT DEFAULT ''"),
                     ("review_asked", "ALTER TABLE leads ADD COLUMN review_asked INTEGER DEFAULT 0")):
        if col not in lead_cols:
            conn.execute(ddl)
    for row in conn.execute("SELECT id FROM leads WHERE token IS NULL OR token=''").fetchall():
        conn.execute("UPDATE leads SET token=? WHERE id=?",
                     (secrets.token_urlsafe(9), row["id"]))
    svc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(services)")}
    for col, ddl in (("base", "ALTER TABLE services ADD COLUMN base INTEGER DEFAULT 0"),
                     ("icon", "ALTER TABLE services ADD COLUMN icon TEXT DEFAULT 'wrench'"),
                     ("active", "ALTER TABLE services ADD COLUMN active INTEGER DEFAULT 1"),
                     ("photo", "ALTER TABLE services ADD COLUMN photo TEXT DEFAULT ''")):
        if col not in svc_cols:
            conn.execute(ddl)
    for row in conn.execute("SELECT id, price FROM services WHERE base=0").fetchall():
        digits = re.sub(r"\D", "", row["price"] or "")
        if digits:
            conn.execute("UPDATE services SET base=? WHERE id=?", (int(digits), row["id"]))
    conn.commit()
    return conn


def seed():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        photos = ["", "engine", "tires", "paint", "polish", "seatclean"]
        conn.executemany(
            "INSERT INTO services (title, price, note, base, icon, sort, photo) VALUES (?,?,?,?,?,?,?)",
            [(t, p, n, b, i, k, photos[k] if k < len(photos) else "") for k, (t, p, n, b, i) in enumerate(SEED_SERVICES)])
        conn.commit()
    conn.close()


def get_setting(conn, key, default=""):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def put_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key, value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def contact_settings(conn):
    """Контакти, які власник СТО редагує в адмінці."""
    return {k: get_setting(conn, "c_" + k, v) for k, v in CONTACT_DEFAULTS.items()}


def slot_capacity(conn):
    try:
        return max(1, min(20, int(get_setting(conn, "slot_capacity", str(DEFAULT_CAPACITY)))))
    except ValueError:
        return DEFAULT_CAPACITY


def slot_times(conn):
    raw = get_setting(conn, "slot_times", ",".join(SLOT_TIMES))
    times = [t.strip() for t in raw.split(",") if re.fullmatch(r"\d{1,2}:\d{2}", t.strip())]
    return times or SLOT_TIMES


def parse_day(value):
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def booked_map(conn, date_from, date_to):
    """Скільки зайнято по кожному дню та годині."""
    rows = conn.execute(
        "SELECT slot_date, slot_time, COUNT(*) c FROM leads "
        "WHERE slot_date != '' AND slot_date BETWEEN ? AND ? AND status != 'cancelled' "
        "GROUP BY slot_date, slot_time", (date_from.isoformat(), date_to.isoformat())).fetchall()
    out = {}
    for r in rows:
        out[(r["slot_date"], r["slot_time"])] = r["c"]
    return out


def day_slots(conn, day, booked=None, capacity=None):
    """Вільні години на конкретний день з урахуванням графіка та вже зайнятих."""
    capacity = capacity or slot_capacity(conn)
    booked = booked if booked is not None else booked_map(conn, day, day)
    now = datetime.datetime.now()
    sunday = day.weekday() == 6
    out = []
    for t in slot_times(conn):
        taken = booked.get((day.isoformat(), t), 0)
        state = "free"
        if sunday:
            state = "closed"
        elif day == now.date():
            hh, mm = (int(x) for x in t.split(":"))
            if (hh, mm) <= (now.hour, now.minute):
                state = "past"
        elif day < now.date():
            state = "past"
        if state == "free" and taken >= capacity:
            state = "full"
        out.append({"time": t, "booked": taken, "capacity": capacity,
                    "free": max(0, capacity - taken), "state": state})
    return out


def slots_overview(conn, days=SLOT_DAYS_AHEAD):
    """Дні з кількістю вільних місць — для вибору дати на сайті."""
    today = datetime.date.today()
    end = today + datetime.timedelta(days=days - 1)
    booked = booked_map(conn, today, end)
    capacity = slot_capacity(conn)
    result = []
    for i in range(days):
        day = today + datetime.timedelta(days=i)
        slots = day_slots(conn, day, booked, capacity)
        free = sum(s["free"] for s in slots if s["state"] == "free")
        label = "Сьогодні" if i == 0 else ("Завтра" if i == 1 else WEEKDAYS_UK[day.weekday()])
        result.append({"date": day.isoformat(), "label": label,
                       "day": day.day, "month": day.strftime("%m"),
                       "weekday": WEEKDAYS_UK[day.weekday()],
                       "free": free, "capacity": capacity * len(slots),
                       "closed": day.weekday() == 6})
    return result


def esc(v):
    return (str(v if v is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def asset_v():
    """Версия статики по времени изменения — чтобы браузер не держал старый CSS/JS."""
    newest = 0
    for pat in ("static/*.css", "static/*.js"):
        for f in glob.glob(os.path.join(BASE, pat)):
            newest = max(newest, int(os.path.getmtime(f)))
    return str(newest)


def tpl(name):
    with open(os.path.join(BASE, "templates", name), encoding="utf-8") as fh:
        return fh.read().replace("{{ASSET_V}}", asset_v())


def rate_ok(bucket, ip, limit, window_s):
    """Не больше limit событий за window_s секунд с одного адреса."""
    now = datetime.datetime.now()
    stamps = [t for t in bucket.get(ip, []) if (now - t).total_seconds() < window_s]
    if len(stamps) >= limit:
        bucket[ip] = stamps
        return False
    stamps.append(now)
    bucket[ip] = stamps
    return True


# ----------------------------------------------------------------- телеграм

def send_telegram(text):
    """Уведомление о заявке. Тихо пропускаем, если токен не настроен."""
    conn = get_db()
    token = get_setting(conn, "tg_token")
    chat = get_setting(conn, "tg_chat")
    enabled = get_setting(conn, "tg_enabled", "0")
    conn.close()
    if not token or not chat or enabled != "1":
        return False, "не настроено"
    payload = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                          "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=payload,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("ok", False), "ok"
    except Exception as exc:                      # сеть, неверный токен, блокировка
        return False, str(exc)[:200]


def notify_async(text):
    threading.Thread(target=send_telegram, args=(text,), daemon=True).start()


# ----------------------------------------------------------------- сервер


# ------------------------------------------------------- напоминание о записи

UK_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
             "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def lead_when(lead):
    """(дата словами, час) для заявки — по слотам либо по свободному тексту."""
    sd = (lead["slot_date"] if "slot_date" in lead.keys() else "") or ""
    st = (lead["slot_time"] if "slot_time" in lead.keys() else "") or ""
    try:
        d = datetime.date.fromisoformat(sd)
        label = f"{WEEKDAYS_UK[d.weekday()]}, {d.day} {UK_MONTHS[d.month - 1]}"
        return label, st or ""
    except Exception:
        raw = (lead["when_at"] or "").strip()
        parts = raw.rsplit(" ", 1)
        return (raw, "") if len(parts) == 1 else (parts[0], parts[1])


def reminder_url(conn, token):
    base = get_setting(conn, "public_url") or SITE_URL
    return f"{base.rstrip('/')}/r/{token}"


def lead_by_token(conn, token):
    return conn.execute("SELECT * FROM leads WHERE token=?", (token,)).fetchone()


def render_reminder(conn, lead, state=""):
    contacts = contact_settings(conn)
    date_label, time_label = lead_when(lead)
    if state == "confirmed":
        block = '<div class="r-done">Запис підтверджено. Чекаємо вас — якщо щось зміниться, подзвоніть.</div>'
    elif state == "cancelled":
        block = '<div class="r-done cancel">Запис скасовано. Якщо це помилка — подзвоніть, повернемо час.</div>'
    else:
        block = ""
    html = (tpl("reminder.html")
            .replace("{{TOKEN}}", esc(lead["token"] or ""))
            .replace("{{WHEN_DATE}}", esc(date_label))
            .replace("{{WHEN_TIME}}", esc(time_label or "час уточнимо"))
            .replace("{{SERVICE}}", esc(lead["service"] or "Сервіс"))
            .replace("{{CAR}}", esc(lead["car"] or "—"))
            .replace("{{ADDRESS}}", esc(contacts["address"]))
            .replace("{{HOURS}}", esc(contacts["hours"]))
            .replace("{{PHONE}}", esc(contacts["phone"]))
            .replace("{{PHONE_RAW}}", esc(contacts["phone_raw"]))
            .replace("{{STATE_HTML}}", block))
    return html


def reminder_text(conn, lead):
    """Готовый текст напоминания — владелец отправляет клиенту в Viber/Telegram/SMS."""
    date_label, time_label = lead_when(lead)
    contacts = contact_settings(conn)
    name = (lead["name"] or "").split()[0] if lead["name"] else ""
    url = reminder_url(conn, lead["token"] or "")
    return (f"{name + ', н' if name else 'Н'}агадуємо про запис в АвтоТочка: "
            f"{date_label} о {time_label}. {lead['service'] or ''}".replace("  ", " ").strip()
            + f". Адреса: {contacts['address']}. Якщо плани змінилися — підтвердьте або скасуйте тут: {url}")


def backup_loop():
    """Раз в сутки в 03:00 — копия базы; при старте — если последней копии нет или она старше 20 ч."""
    while True:
        try:
            if ops.backup_is_stale(BACKUPS_DIR):
                path = ops.backup_db(DB_PATH, BACKUPS_DIR)
                print(f"[backup] {os.path.basename(path)}")
        except Exception as exc:
            print(f"[backup] ошибка: {exc}")
        now = datetime.datetime.now()
        nxt = (now + datetime.timedelta(days=1)).replace(hour=3, minute=0, second=0, microsecond=0)
        time.sleep(max(60, (nxt - now).total_seconds()))


def reminder_loop():
    """Раз в 15 минут: заявка на завтра-сегодня без подтверждения → напомнить владельцу."""
    while True:
        try:
            conn = get_db()
            now = datetime.datetime.now()
            rows = conn.execute(
                "SELECT * FROM leads WHERE slot_date<>'' AND token<>'' AND reminded=0 "
                "AND (confirmed IS NULL OR confirmed='') AND status<>'cancelled'").fetchall()
            for lead in rows:
                try:
                    dt = datetime.datetime.strptime(f"{lead['slot_date']} {lead['slot_time']}", "%Y-%m-%d %H:%M")
                except Exception:
                    continue
                hours = (dt - now).total_seconds() / 3600
                if 1 <= hours <= 26:
                    ok, _ = send_telegram("⏰ <b>Нагадати клієнту</b>\n" + esc(reminder_text(conn, lead)))
                    if ok:
                        conn.execute("UPDATE leads SET reminded=1 WHERE id=?", (lead["id"],))
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(900)



# страницы услуг и марок: передаём зависимости, чтобы не было циклического импорта
seo_pages.configure(esc, SITE_URL, tpl, contact_settings)

class Handler(BaseHTTPRequestHandler):
    server_version = "AutoTochka/3.2"

    def log_error(self, fmt, *args):
        """Ошибки пишем в data/errors.log — иначе на хостинге они теряются."""
        try:
            with open(ERRORS_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} " + (fmt % args) + "\n")
        except Exception:
            pass
        return super().log_error(fmt, *args)

    # ------------------------------------------------------------ служебное
    def send(self, code, body, ctype="text/html; charset=utf-8", extra=None, cache=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers = {
            "Content-Type": ctype,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Frame-Options": "SAMEORIGIN",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": (
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; frame-src https://www.google.com; "
                "connect-src 'self'; form-action 'self'; base-uri 'self'"),
        }
        if cache:
            headers["Cache-Control"] = cache
        gz = (len(data) > 1200 and "text" in ctype
              and "gzip" in (self.headers.get("Accept-Encoding") or ""))
        if gz:
            data = gzip.compress(data, 6)
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
        headers["Content-Length"] = str(len(data))
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def json_out(self, obj, code=200):
        self.send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8",
                  cache="no-store")

    def redirect(self, to, cookie=None):
        extra = {"Location": to}
        if cookie is not None:
            extra["Set-Cookie"] = cookie
        self.send(302, "", extra=extra)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        ctype = self.headers.get("Content-Type") or ""
        # sendBeacon с обычной строкой приходит как text/plain — тело всё равно JSON
        if ctype.startswith("application/json") or raw.lstrip().startswith("{"):
            try:
                return json.loads(raw or "{}")
            except json.JSONDecodeError:
                return {}
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def ip(self):
        return self.client_address[0]

    def session_ok(self):
        now = datetime.datetime.now()
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid":
                exp = SESSIONS.get(v)
                if exp and exp > now:
                    return True
                SESSIONS.pop(v, None)
        return False

    def same_origin(self):
        """CSRF-барьер: изменяющие запросы с чужого Origin не проходят."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return origin.endswith(self.headers.get("Host") or "\0")

    def static_file(self, rel):
        path = os.path.normpath(os.path.join(BASE, rel.replace("/", os.sep)))
        if not path.startswith(os.path.join(BASE, "static")) or not os.path.isfile(path):
            return self.send(404, "not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype in ("font/woff2", "image/webp", "image/svg+xml"):
            pass
        cache = "public, max-age=604800" if "/img/" in path.replace(os.sep, "/") else "public, max-age=3600"
        with open(path, "rb") as fh:
            self.send(200, fh.read(), ctype, cache=cache)

    # ------------------------------------------------------------ GET
    def do_HEAD(self):
        """HEAD нужен мониторингу и линк-чекерам: отдаём заголовки без тела."""
        self.do_GET()

    JUNK_TAIL = "»«\"'`.,;:!?* \t"

    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)

        # адреса часто копируют из чата вместе с кавычками: /admin» , /privacy" ,
        # /services/to.  Такие «хвосты» не должны превращаться в 404 — срезаем и уводим на чистый адрес
        decoded = unquote(path)
        clean = decoded.rstrip(self.JUNK_TAIL)
        if clean != decoded and clean not in ("", "/"):
            query = ("?" + u.query) if u.query else ""
            return self.send(301, "", extra={"Location": quote(clean, safe="/") + query})
        path = clean or "/"

        if path == "/":
            return self.render_index()
        if path == "/cases":
            page = (tpl("cases.html")
                    .replace("{{YEAR}}", str(datetime.date.today().year))
                    .replace("{{SITE_URL}}", SITE_URL))
            return self.send(200, page, cache="public, max-age=600")
        if path == "/api/slots/days":
            conn = get_db()
            data = {"days": slots_overview(conn), "capacity": slot_capacity(conn)}
            conn.close()
            return self.json_out(data)
        if path == "/api/slots":
            day = parse_day((qs.get("date") or [""])[0])
            if not day:
                return self.json_out({"error": "Вкажіть дату"}, 400)
            conn = get_db()
            data = {"date": day.isoformat(), "slots": day_slots(conn, day),
                    "capacity": slot_capacity(conn)}
            conn.close()
            return self.json_out(data)
        if path in ("/services", "/services/"):
            conn = get_db()
            try:
                title, desc, p, body, ld, og = seo_pages.build_services_index(conn)
                page = seo_pages.render_page(conn, title, desc, p, body, ld, og)
            finally:
                conn.close()
            return self.send(200, page, cache="public, max-age=3600")

        if path.startswith("/services/"):
            slug = path[len("/services/"):].strip("/")
            if slug not in SERVICES:
                return self.not_found()
            conn = get_db()
            try:
                title, desc, p, body, ld, og = seo_pages.build_service_page(conn, slug)
                page = seo_pages.render_page(conn, title, desc, p, body, ld, og)
            finally:
                conn.close()
            return self.send(200, page, cache="public, max-age=3600")

        if path in ("/brands", "/brands/"):
            conn = get_db()
            try:
                title, desc, p, body, ld, og = seo_pages.build_brands_index(conn)
                page = seo_pages.render_page(conn, title, desc, p, body, ld, og)
            finally:
                conn.close()
            return self.send(200, page, cache="public, max-age=3600")

        if path.startswith("/brands/"):
            slug = path[len("/brands/"):].strip("/")
            if slug not in BRANDS:
                return self.not_found()
            conn = get_db()
            try:
                title, desc, p, body, ld, og = seo_pages.build_brand_page(conn, slug)
                page = seo_pages.render_page(conn, title, desc, p, body, ld, og)
            finally:
                conn.close()
            return self.send(200, page, cache="public, max-age=3600")

        if path.startswith("/r/") and path.count("/") == 2:
            token = path.split("/")[2]
            conn = get_db()
            try:
                lead = lead_by_token(conn, token)
                if not lead:
                    return self.not_found()
                page = render_reminder(conn, lead)
            finally:
                conn.close()
            return self.send(200, page, cache="no-store")

        if path == "/api/admin/remind":
            if not self.session_ok():
                return self.json_out({"error": "Потрібен вхід"}, 401)
            try:
                lead_id = int((qs.get("id") or ["0"])[0])
            except ValueError:
                return self.json_out({"error": "Поганий id"}, 400)
            conn = get_db()
            try:
                lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
                if not lead:
                    return self.json_out({"error": "Заявку не знайдено"}, 404)
                if not lead["token"]:
                    conn.execute("UPDATE leads SET token=? WHERE id=?",
                                 (secrets.token_urlsafe(9), lead_id))
                    conn.commit()
                    lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
                data = {"ok": True, "text": reminder_text(conn, lead),
                        "url": reminder_url(conn, lead["token"])}
            finally:
                conn.close()
            return self.json_out(data)

        if path == "/privacy":
            conn = get_db()
            try:
                pc = contact_settings(conn)
            finally:
                conn.close()
            page = (tpl("privacy.html")
                    .replace("{{SITE_URL}}", SITE_URL)
                    .replace("{{C_PHONE}}", esc(pc["phone"]))
                    .replace("{{C_PHONE_RAW}}", esc(pc["phone_raw"]))
                    .replace("{{C_ADDRESS}}", esc(pc["address"]))
                    .replace("{{C_HOURS}}", esc(pc["hours"]))
                    .replace("{{YEAR}}", str(datetime.date.today().year)))
            return self.send(200, page, cache="public, max-age=3600")
        if path == "/robots.txt":
            body = ("User-agent: *\nAllow: /\nDisallow: /admin\n"
                    f"Sitemap: {SITE_URL}/sitemap.xml\n")
            return self.send(200, body, "text/plain; charset=utf-8", cache="public, max-age=3600")
        if path == "/sitemap.xml":
            today = datetime.date.today().isoformat()
            body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                    f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod>"
                    "<changefreq>weekly</changefreq><priority>1.0</priority></url>\n"
                    f"  <url><loc>{SITE_URL}/privacy</loc><lastmod>{today}</lastmod>"
                    "<changefreq>yearly</changefreq><priority>0.3</priority></url>\n"
                    f"  <url><loc>{SITE_URL}/cases</loc><lastmod>{today}</lastmod>"
                    "<changefreq>monthly</changefreq><priority>0.6</priority></url>\n"
                    + "".join(
                        f"  <url><loc>{SITE_URL}/services/{slug}</loc><lastmod>{today}</lastmod>"
                        "<changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
                        for slug in SERVICES)
                    + f"  <url><loc>{SITE_URL}/services</loc><lastmod>{today}</lastmod>"
                    "<changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
                    + "".join(
                        f"  <url><loc>{SITE_URL}/brands/{slug}</loc><lastmod>{today}</lastmod>"
                        "<changefreq>monthly</changefreq><priority>0.6</priority></url>\n"
                        for slug in BRANDS)
                    + f"  <url><loc>{SITE_URL}/brands</loc><lastmod>{today}</lastmod>"
                    "<changefreq>monthly</changefreq><priority>0.6</priority></url>\n"
                    "</urlset>\n")
            return self.send(200, body, "application/xml; charset=utf-8", cache="public, max-age=3600")
        if path in ("/favicon.ico", "/favicon.svg"):
            svg = os.path.join(BASE, "static", "img", "favicon.svg")
            if os.path.isfile(svg):
                with open(svg, "rb") as fh:
                    return self.send(200, fh.read(), "image/svg+xml", cache="public, max-age=604800")
            return self.send(404, "")
        if path == "/admin":
            return self.send(200, tpl("admin.html"), cache="no-store") if self.session_ok() \
                else self.redirect("/admin/login")
        if path == "/admin/login":
            return self.send(200, tpl("login.html").replace("{{ERROR}}", ""), cache="no-store")
        if path == "/api/services":
            conn = get_db()
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM services WHERE active=1 ORDER BY sort, id")]
            conn.close()
            return self.json_out(rows)
        if path == "/api/calc":
            conn = get_db()
            services = [{"title": r["title"], "base": r["base"]} for r in conn.execute(
                "SELECT * FROM services WHERE active=1 ORDER BY sort, id")]
            conn.close()
            return self.json_out({"services": services,
                                  "classes": [{"key": k, "title": v[0], "mult": v[1]}
                                              for k, v in CLASSES.items()]})
        if path in ("/api/health", "/health", "/status"):
            health = {"ok": False, "version": VERSION, "time": datetime.datetime.now().isoformat(timespec="seconds")}
            try:
                conn = get_db()
                try:
                    conn.execute("SELECT 1").fetchone()
                    health["db"] = "ok"
                    health["leads"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
                    health["settings"] = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
                    health["slot_capacity"] = slot_capacity(conn)
                finally:
                    conn.close()
                health["ok"] = True
                health["uptime_s"] = int((datetime.datetime.now() - STARTED_AT).total_seconds())
                lb = ops.last_backup(BACKUPS_DIR)
                health["last_backup"] = lb["name"] if lb else None
                health["backup_age_h"] = lb["age_hours"] if lb else None
                if self.session_ok():
                    health["default_password"] = is_default_password()
                return self.json_out(health)
            except Exception as exc:
                health["db"] = f"error: {str(exc)[:120]}"
                return self.json_out(health, 503)

        if path == "/api/admin/state":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            conn = get_db()
            try:
                db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
                lb = ops.last_backup(BACKUPS_DIR)
                state = {"ok": True, "version": VERSION,
                         "default_password": is_default_password(),
                         "db_size_kb": round(db_size / 1024),
                         "last_backup": lb["name"] if lb else None,
                         "backup_age_h": lb["age_hours"] if lb else None,
                         "uptime_s": int((datetime.datetime.now() - STARTED_AT).total_seconds()),
                         "errors_log_kb": round(os.path.getsize(ERRORS_LOG) / 1024)
                                          if os.path.exists(ERRORS_LOG) else 0}
                return self.json_out(state)
            finally:
                conn.close()

        if path == "/api/admin/audit":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            try:
                limit = int((qs.get("limit") or ["40"])[0])
            except ValueError:
                limit = 40
            conn = get_db()
            try:
                rows = ops.audit_tail(conn, limit)
            finally:
                conn.close()
            return self.json_out({"ok": True, "rows": rows})

        if path == "/api/admin/leads":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            status = (qs.get("status") or ["all"])[0]
            query = (qs.get("q") or [""])[0].strip()
            sql, args = "SELECT * FROM leads WHERE 1=1", []
            if status in ("new", "done"):
                sql += " AND status=?"
                args.append(status)
            if query:
                sql += " AND (name LIKE ? OR phone LIKE ? OR car LIKE ? OR service LIKE ?)"
                args += [f"%{query}%"] * 4
            sql += " ORDER BY id DESC LIMIT 500"
            conn = get_db()
            rows = [dict(r) for r in conn.execute(sql, args)]
            stats = {
                "total": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
                "new": conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0],
                "today": conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE date(created_at)=date('now','localtime')").fetchone()[0],
            }
            conn.close()
            return self.json_out({"leads": rows, "stats": stats})
        if path == "/api/admin/services":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            conn = get_db()
            rows = [dict(r) for r in conn.execute("SELECT * FROM services ORDER BY sort, id")]
            conn.close()
            return self.json_out(rows)
        if path == "/api/admin/calendar":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            start = parse_day((qs.get("start") or [""])[0]) or datetime.date.today()
            days = max(1, min(31, int((qs.get("days") or ["7"])[0] or 7)))
            conn = get_db()
            capacity = slot_capacity(conn)
            times = slot_times(conn)
            booked = booked_map(conn, start, start + datetime.timedelta(days=days - 1))
            leads = [dict(r) for r in conn.execute(
                "SELECT id, name, phone, service, car, slot_date, slot_time, status FROM leads "
                "WHERE slot_date BETWEEN ? AND ? ORDER BY slot_date, slot_time",
                (start.isoformat(), (start + datetime.timedelta(days=days - 1)).isoformat()))]
            conn.close()
            grid = []
            for i in range(days):
                d = start + datetime.timedelta(days=i)
                grid.append({
                    "date": d.isoformat(), "weekday": WEEKDAYS_UK[d.weekday()], "day": d.day,
                    "closed": d.weekday() == 6,
                    "slots": [{"time": t, "booked": booked.get((d.isoformat(), t), 0)}
                              for t in times if d.weekday() != 6],
                })
            return self.json_out({"start": start.isoformat(), "days": days,
                                  "capacity": capacity, "times": times, "grid": grid,
                                  "leads": leads})
        if path == "/api/admin/analytics":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            return self.json_out(self.analytics())
        if path == "/api/admin/settings":
            if not self.session_ok():
                return self.json_out({"error": "auth"}, 401)
            conn = get_db()
            token = get_setting(conn, "tg_token")
            data = {"tg_enabled": get_setting(conn, "tg_enabled", "0"),
                    "tg_chat": get_setting(conn, "tg_chat"),
                    "tg_token_set": "1" if token else "0",
                    "tg_token_tail": token[-6:] if token else "",
                    "slot_capacity": str(slot_capacity(conn)),
                    "slot_times": ",".join(slot_times(conn)),
                    "contacts": contact_settings(conn)}
            conn.close()
            return self.json_out(data)
        if path == "/admin/export.csv":
            if not self.session_ok():
                return self.redirect("/admin/login")
            conn = get_db()
            rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
            conn.close()
            out = io.StringIO()
            w = csv.writer(out, delimiter=";")
            w.writerow(["Дата", "Ім'я", "Телефон", "Послуга", "Авто", "Бажана дата",
                        "Орієнтовно", "Коментар", "Нотатка", "Статус", "Джерело"])
            for r in rows:
                w.writerow([r["created_at"], r["name"], r["phone"], r["service"], r["car"],
                            r["when_at"], r["estimate"], r["comment"], r["note"],
                            "нова" if r["status"] == "new" else "опрацьовано", r["source"]])
            name = "leads-" + datetime.date.today().isoformat() + ".csv"
            return self.send(200, ("\ufeff" + out.getvalue()).encode("utf-8"),
                             "text/csv; charset=utf-8",
                             {"Content-Disposition": f'attachment; filename="{name}"'}, cache="no-store")
        if path.startswith("/static/"):
            return self.static_file(path.lstrip("/"))
        return self.not_found()

    def not_found(self):
        page = (tpl("404.html")
                .replace("{{YEAR}}", str(datetime.date.today().year)))
        return self.send(404, page)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        path = urlparse(self.path).path
        data = self.body()

        if path == "/api/hit":                                   # аналитика (sendBeacon)
            if not rate_ok(HIT_HITS, self.ip(), 120, 60):
                return self.json_out({"ok": False}, 429)
            name = re.sub(r"[^a-z_]", "", (data.get("name") or ""))[:32]
            if name:
                conn = get_db()
                conn.execute("INSERT INTO events (name, path, session) VALUES (?,?,?)",
                             (name, (data.get("path") or "")[:120], (data.get("sid") or "")[:32]))
                conn.commit()
                conn.close()
            return self.json_out({"ok": True})

        if path.startswith("/r/") and (path.endswith("/confirm") or path.endswith("/cancel")):
            parts = path.strip("/").split("/")
            if len(parts) != 3:
                return self.not_found()
            token, action = parts[1], parts[2]
            conn = get_db()
            try:
                lead = lead_by_token(conn, token)
                if not lead:
                    return self.not_found()
                if action == "confirm":
                    conn.execute("UPDATE leads SET confirmed='confirmed' WHERE id=?", (lead["id"],))
                    conn.commit()
                    notify_async(f"✅ <b>Клієнт підтвердив запис</b>\n"
                                 f"{esc(lead['name'] or '')} · {esc(lead['phone'] or '')}\n"
                                 f"{esc(lead['when_at'] or '')} · {esc(lead['service'] or '')}")
                    state = "confirmed"
                else:
                    conn.execute("UPDATE leads SET confirmed='cancelled', status='cancelled' "
                                 "WHERE id=?", (lead["id"],))
                    conn.commit()
                    notify_async(f"❌ <b>Клієнт скасував запис</b>\n"
                                 f"{esc(lead['name'] or '')} · {esc(lead['phone'] or '')}\n"
                                 f"{esc(lead['when_at'] or '')} · час звільнився")
                    state = "cancelled"
                page = render_reminder(conn, lead, state)
            finally:
                conn.close()
            return self.send(200, page, cache="no-store")

        if path == "/api/leads":
            if not rate_ok(ATTEMPT_HITS, self.ip(), ATTEMPT_LIMIT, LEAD_WINDOW_S):
                return self.json_out({"ok": False, "error": "Забагато запитів"}, 429)
            if (data.get("company") or "").strip():              # honeypot против ботов
                return self.json_out({"ok": True})
            kind = "callback" if str(data.get("kind")) == "callback" else "book"
            name = (data.get("name") or "").strip()
            phone = (data.get("phone") or "").strip()
            consent = str(data.get("consent") or "")
            if kind == "callback":
                name = name or "Зворотний дзвінок"
            if len(name) < 2:
                return self.json_out({"ok": False, "error": "Вкажіть ім'я"}, 400)
            if sum(ch.isdigit() for ch in phone) < 9:
                return self.json_out({"ok": False, "error": "Вкажіть коректний телефон"}, 400)
            if consent not in ("1", "on", "true"):
                return self.json_out({"ok": False,
                                      "error": "Потрібна згода на обробку даних"}, 400)

            slot_date = (data.get("slot_date") or "").strip()
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
            lead_token = secrets.token_urlsafe(9)
            conn.execute("""INSERT INTO leads (name, phone, service, car, when_at, comment, estimate,
                                              source, slot_date, slot_time,
                                              utm_source, utm_medium, utm_campaign, kind, token)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (name[:80], phone[:30], (data.get("service") or "Зворотний дзвінок" if kind == "callback" else data.get("service") or "")[:80],
                          (data.get("car") or "")[:80], when_at,
                          (data.get("comment") or "")[:800],
                          (data.get("estimate") or "")[:40], source[:80],
                          slot_date if slot_date else "", slot_time if slot_time else "",
                          utm_source, utm_medium, utm_campaign, kind, lead_token))
            lead_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO events (name, path, session) VALUES ('lead', '/', ?)",
                         ((data.get("sid") or "")[:32],))
            conn.commit()
            conn.close()

            if kind == "callback":
                notify_async(
                    "📞 <b>Прохання передзвонити</b>\n\n"
                    f"👤 {esc(name)}\n📞 {esc(phone)}\n"
                    f"🔗 Джерело: {esc(source)}\n\n"
                    f"Заявка №{lead_id} у адмінці: {SITE_URL}/admin")
            else:
                notify_async(
                    "🚗 <b>Нова заявка з сайту</b>\n\n"
                    f"👤 {esc(name)}\n📞 {esc(phone)}\n"
                    f"🔧 {esc(data.get('service') or '—')}\n"
                    f"🚙 {esc(data.get('car') or '—')}\n"
                    f"📅 {esc(when_at or '—')}\n"
                    f"💰 {esc(data.get('estimate') or '—')}\n"
                    f"💬 {esc((data.get('comment') or '—')[:300])}\n"
                    f"🔗 {esc(source)}\n\n"
                    f"Заявка №{lead_id} у адмінці: {SITE_URL}/admin")
            return self.json_out({"ok": True, "id": lead_id})

        if path == "/admin/login":
            ip = self.ip()
            not_long_ago = datetime.datetime.now() - datetime.timedelta(minutes=5)
            recent_fails = [t for t in LOGIN_TRIES.get(ip, []) if t > not_long_ago]
            if len(recent_fails) >= 10:
                return self.send(429, tpl("login.html").replace(
                    "{{ERROR}}", '<p class="err">Забагато спроб. Зачекайте 5 хвилин.</p>'))
            if verify_password(data.get("password")):
                LOGIN_TRIES.pop(ip, None)
                token = secrets.token_urlsafe(24)
                SESSIONS[token] = datetime.datetime.now() + datetime.timedelta(hours=8)
                conn = get_db()
                try:
                    ops.audit(conn, "вхід в адмінку", ip)
                finally:
                    conn.close()
                return self.redirect("/admin", cookie=(
                    f"sid={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=28800"))
            LOGIN_TRIES[ip] = recent_fails + [datetime.datetime.now()]
            conn = get_db()
            try:
                ops.audit(conn, "невдалий вхід", ip)
            finally:
                conn.close()
            time.sleep(0.4)                                    # замедляем перебор
            return self.send(200, tpl("login.html").replace(
                "{{ERROR}}", '<p class="err">Невірний пароль</p>'))

        if path == "/admin/logout":
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "sid":
                    SESSIONS.pop(v, None)
            return self.redirect("/admin/login", cookie="sid=; Max-Age=0; Path=/")

        if not self.session_ok():
            return self.json_out({"error": "auth"}, 401)
        if not self.same_origin():
            return self.json_out({"error": "origin"}, 403)

        if path == "/admin/lead":
            conn = get_db()
            if data.get("action") == "delete":
                conn.execute("DELETE FROM leads WHERE id=?", (int(data.get("id") or 0),))
                ops.audit(conn, "заявку видалено", f"#{data.get('id')}")
            else:
                conn.execute("UPDATE leads SET status=?, note=? WHERE id=?",
                             ((data.get("status") or "new")[:20],
                              (data.get("note") or "")[:800], int(data.get("id") or 0)))
                st_map = {"new": "нова", "done": "опрацьовано", "cancelled": "скасована"}
                ops.audit(conn, "заявку оновлено", f"#{data.get('id')}",
                          f"статус: {st_map.get(data.get('status') or 'new', data.get('status'))}")
            conn.commit()
            conn.close()
            return self.json_out({"ok": True})

        if path == "/admin/service":
            conn = get_db()
            action, sid = data.get("action"), int(data.get("id") or 0)
            ops.audit(conn, {"update": "послугу змінено", "add": "послугу додано",
                             "delete": "послугу видалено"}.get(action, "послуги: " + str(action)),
                      f"#{sid}")
            if action == "update":
                conn.execute("""UPDATE services SET title=?, price=?, note=?, base=?, active=?, photo=? WHERE id=?""",
                             ((data.get("title") or "").strip()[:120],
                              (data.get("price") or "").strip()[:40],
                              (data.get("note") or "").strip()[:300],
                              int(data.get("base") or 0),
                              1 if str(data.get("active", "1")) in ("1", "true", "on") else 0,
                              (data.get("photo") or "").strip()[:60], sid))
            elif action == "add":
                nxt = conn.execute("SELECT COALESCE(MAX(sort),0)+1 FROM services").fetchone()[0]
                conn.execute("INSERT INTO services (title, price, note, base, icon, sort) VALUES (?,?,?,?,?,?)",
                             ((data.get("title") or "Нова послуга").strip()[:120],
                              (data.get("price") or "0 ₴").strip()[:40],
                              (data.get("note") or "").strip()[:300],
                              int(data.get("base") or 0), "wrench", nxt))
            elif action == "delete":
                conn.execute("DELETE FROM services WHERE id=?", (sid,))
            elif action == "move":
                row = conn.execute("SELECT sort FROM services WHERE id=?", (sid,)).fetchone()
                if row:
                    step = -2 if data.get("dir") == "up" else 2
                    conn.execute("UPDATE services SET sort=? WHERE id=?", (row["sort"] + step, sid))
            conn.commit()
            conn.close()
            return self.json_out({"ok": True})

        if path == "/admin/settings":
            conn = get_db()
            token = (data.get("tg_token") or "").strip()
            if token:
                if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,50}", token):
                    conn.close()
                    return self.json_out({"ok": False, "error": "Токен не схожий на справжній"}, 400)
                put_setting(conn, "tg_token", token)
            put_setting(conn, "tg_chat", (data.get("tg_chat") or "").strip()[:40])
            put_setting(conn, "tg_enabled", "1" if str(data.get("tg_enabled")) in ("1", "on", "true") else "0")
            if "slot_capacity" in data:
                try:
                    cap = int(data.get("slot_capacity") or DEFAULT_CAPACITY)
                except ValueError:
                    cap = DEFAULT_CAPACITY
                put_setting(conn, "slot_capacity", str(max(1, min(20, cap))))
            if "slot_times" in data:
                times = [t.strip() for t in str(data.get("slot_times") or "").split(",")
                         if re.fullmatch(r"\d{1,2}:\d{2}", t.strip())]
                if times:
                    put_setting(conn, "slot_times", ",".join(times))
            contacts = data.get("contacts") or {}
            if isinstance(contacts, dict):
                for key in CONTACT_DEFAULTS:
                    if key in contacts:
                        put_setting(conn, "c_" + key, str(contacts[key]).strip()[:200])
            for key in CONTACT_DEFAULTS:                     # плоские ключи из формы админки
                if "c_" + key in data:
                    put_setting(conn, "c_" + key, str(data["c_" + key]).strip()[:200])
            ops.audit(conn, "налаштування збережено")
            conn.commit()
            conn.close()
            return self.json_out({"ok": True})

        if path == "/admin/settings/test":
            ok, info = send_telegram("🔔 Тестове повідомлення з адмінки «АвтоТочка». "
                                     "Якщо ви це бачите — заявки будуть приходити сюди.")
            return self.json_out({"ok": ok, "info": info})

        if path == "/admin/password":
            old = data.get("old") or ""
            new = data.get("new") or ""
            if not verify_password(old):
                return self.json_out({"ok": False, "error": "Поточний пароль невірний"}, 400)
            problem = password_problem(new)
            if problem:
                return self.json_out({"ok": False, "error": problem}, 400)
            set_password(new)
            conn = get_db()
            try:
                ops.audit(conn, "пароль змінено")
            finally:
                conn.close()
            return self.json_out({"ok": True})

        return self.send(404, "Не знайдено")

    # ------------------------------------------------------------ аналитика
    def analytics(self):
        conn = get_db()
        def scalar(sql, args=()):
            row = conn.execute(sql, args).fetchone()
            return row[0] if row else 0
        since = "(datetime('now','localtime','-30 days'))"
        def sessions(event):
            """Сколько разных посетителей (сессий) сделали шаг воронки."""
            return scalar(f"SELECT COUNT(DISTINCT session) FROM events "
                          f"WHERE name=? AND session != '' AND created_at > {since}", (event,))
        views = sessions("view")
        calc = sessions("calc_used")
        form = sessions("form_start")
        leads = sessions("lead_sent")
        days = [dict(r) for r in conn.execute(
            "SELECT date(created_at) d, COUNT(*) c FROM leads "
            f"WHERE created_at > {since} GROUP BY d ORDER BY d")]
        top = [dict(r) for r in conn.execute(
            "SELECT service, COUNT(*) c FROM leads WHERE service != '' "
            "GROUP BY service ORDER BY c DESC LIMIT 6")]
        sources = [dict(r) for r in conn.execute(
            "SELECT source, COUNT(*) c FROM leads GROUP BY source ORDER BY c DESC")]
        conn.close()
        # конверсия сайта: сколько посетителей дошли до отправки заявки
        conv = round(min(leads, views) * 100 / views, 1) if views else 0
        return {"views": views, "calc": calc, "form": form, "leads": leads,
                "conversion": conv, "days": days, "top": top, "sources": sources}

    # ------------------------------------------------------------ главная
    def render_index(self):
        conn = get_db()
        services = [dict(r) for r in conn.execute(
            "SELECT * FROM services WHERE active=1 ORDER BY sort, id")]
        conn.close()

        icons = {
            "diag": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 12h4l2-5 3 10 2-5h7"/></svg>',
            "wrench": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M14 6a4 4 0 1 0 5 5L10 20l-3 1 1-3 9-9"/></svg>',
            "wheel": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg>',
            "spray": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 9h6v11H8z"/><path d="M11 9V6h4V3"/><path d="M17 8h3M17 11h3"/></svg>',
            "shine": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/></svg>',
            "seat": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 19v-8a3 3 0 0 1 3-3h5l3 4h3v7"/><path d="M5 19h14"/></svg>',
        }

        cards = "\n".join(f"""<article class="card" data-reveal>
          <span class="card-ico">{icons.get(s['icon'], icons['wrench'])}</span>
          <h3>{esc(s['title'])}</h3>
          <p class="price">{esc(s['price'])}</p>
          <p class="note">{esc(s['note'])}</p>
          <button class="card-link" type="button" data-service="{esc(s['title'])}">Записатись →</button>
          {('<a class="card-more" href="/services/' + SERVICE_SLUG_BY_TITLE[s['title']] + '">Детальніше →</a>') if s['title'] in SERVICE_SLUG_BY_TITLE else ''}
        </article>""" for s in services)

        rows = "\n".join(
            f"<tr><td>{esc(s['title'])}</td><td class='muted'>{esc(s['note'])}</td>"
            f"<td class='price-cell'>{esc(s['price'])}</td></tr>" for s in services)

        options = "\n".join(
            f'<option value="{esc(s["title"])}" data-base="{s["base"]}">{esc(s["title"])}</option>'
            for s in services)

        checks = "\n".join(
            f'<label class="chk"><input type="checkbox" name="svc" value="{esc(s["title"])}" '
            f'data-base="{s["base"]}"><span>{esc(s["title"])}</span></label>' for s in services)

        class_cards = "\n".join(
            f'<label class="cls"><input type="radio" name="car_class" value="{k}" '
            f'data-mult="{m}"{" checked" if i == 0 else ""}>'
            f'<span class="cls-name">{esc(t)}</span>'
            f'<span class="cls-mult">×{m:g}</span></label>'
            for i, (k, (t, m)) in enumerate(CLASSES.items()))

        # галерея работ
        gallery = [
            ("polish", "Полірування кузова", "Абразивна поліровка + захисне покриття"),
            ("paint", "Кузовний ремонт і фарбування", "Підбір кольору, робота в камері"),
            ("tires", "Шиномонтаж", "Балансування, сезонне зберігання"),
            ("engine", "Технічне обслуговування", "Регламентне ТО з фото-звітом"),
            ("seatclean", "Хімчистка салону", "Екстракторна чистка, сушіння 4 години"),
            ("foam", "Детейлінг-мийка", "Безконтактна піна, сушка турбіною"),
        ]
        photos = "\n".join(f"""<figure class="shot" data-reveal>
          <img src="/static/img/{name}-sm.webp" data-full="/static/img/{name}.webp"
               width="760" height="570" loading="lazy" decoding="async"
               alt="{esc(cap)} — АвтоТочка, Київ">
          <figcaption><b>{esc(cap)}</b><span>{esc(sub)}</span></figcaption>
        </figure>""" for name, cap, sub in gallery)

        reviews = "\n".join(f"""<article class="review" data-reveal>
          <div class="stars" aria-label="Оцінка {n} з 5">{'★' * n}</div>
          <p>«{esc(text)}»</p>
          <footer>{esc(who)} · <span>{esc(car)}</span></footer>
        </article>""" for who, car, n, text in REVIEWS)

        faq = "\n".join(f"""<details class="faq-item">
          <summary>{esc(q)}</summary><div class="faq-body"><p>{esc(a)}</p></div>
        </details>""" for q, a in FAQ)

        jsonld = {
            "@context": "https://schema.org",
            "@type": "AutoRepair",
            "name": "АвтоТочка",
            "description": "СТО та детейлінг у Києві: ремонт, ТО, шиномонтаж, кузовний ремонт, полірування.",
            "url": SITE_URL,
            "telephone": "+380440000000",
            "priceRange": "450–25000 ₴",
            "image": f"{SITE_URL}/static/img/hero.webp",
            "address": {"@type": "PostalAddress", "streetAddress": "вул. Автосервісна, 12",
                        "addressLocality": "Київ", "postalCode": "02000", "addressCountry": "UA"},
            "geo": {"@type": "GeoCoordinates", "latitude": 50.4501, "longitude": 30.5234},
            "openingHoursSpecification": [{
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                "opens": "09:00", "closes": "19:00"}],
            "makesOffer": [{
                "@type": "Offer",
                "itemOffered": {"@type": "Service", "name": s["title"]},
                "priceCurrency": "UAH", "price": str(s["base"])} for s in services],
        }
        faqld = {
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ],
        }

        conn2 = get_db()
        contacts = contact_settings(conn2)
        cal = slots_overview(conn2)
        capacity = slot_capacity(conn2)
        conn2.close()

        html = (tpl("index.html")
                .replace("{{SERVICE_CARDS}}", cards)
                .replace("{{PRICE_ROWS}}", rows)
                .replace("{{SERVICE_OPTIONS}}", options)
                .replace("{{SERVICE_CHECKBOXES}}", checks)
                .replace("{{CLASS_CARDS}}", class_cards)
                .replace("{{GALLERY}}", photos)
                .replace("{{REVIEWS}}", reviews)
                .replace("{{FAQ}}", faq)
                .replace("{{JSONLD}}", json.dumps(jsonld, ensure_ascii=False))
                .replace("{{JSONLD_FAQ}}", json.dumps(faqld, ensure_ascii=False))
                .replace("{{SITE_URL}}", SITE_URL)
                .replace("{{SLOT_DAYS}}", json.dumps(cal, ensure_ascii=False))
                .replace("{{SLOT_CAPACITY}}", str(capacity))
                .replace("{{C_PHONE}}", esc(contacts["phone"]))
                .replace("{{C_PHONE_RAW}}", esc(contacts["phone_raw"]))
                .replace("{{C_ADDRESS}}", esc(contacts["address"]))
                .replace("{{C_HOURS}}", esc(contacts["hours"]))
                .replace("{{C_TELEGRAM}}", esc(contacts["telegram"]))
                .replace("{{C_VIBER}}", esc(contacts["viber"]))
                .replace("{{C_WHATSAPP}}", esc(contacts["whatsapp"]))
                .replace("{{C_REVIEWS_URL}}", esc(contacts["reviews_url"]))
                .replace("{{C_REVIEWS_NOTE}}", esc(contacts["reviews_note"]))
                .replace("{{YEAR}}", str(datetime.date.today().year)))
        self.send(200, html, cache="no-store")

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


class Server(ThreadingHTTPServer):
    """На Windows allow_reuse_address разрешает ДВУМ процессам сесть на один порт —
    тогда часть запросов уходит старой копии кода. Отключаем, чтобы дубль падал сразу."""
    allow_reuse_address = os.name != "nt"


if __name__ == "__main__":
    seed()
    load_auth()
    if "--backup" in sys.argv:
        path = ops.backup_db(DB_PATH, BACKUPS_DIR)
        print(f"Копія бази: {path}")
        raise SystemExit(0)
    print(f"Сайт:    {SITE_URL}/")
    print(f"Адмінка: http://127.0.0.1:{PORT}/admin")
    print(f"Пароль адмінки: {INITIAL_PASSWORD} (змінюється в адмінці, зберігається хешем)")
    if is_default_password():
        print("УВАГА: стоїть демо-пароль. Змініть його в адмінці до показу клієнту.")
    threading.Thread(target=reminder_loop, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    try:
        Server((HOST, PORT), Handler).serve_forever()
    except OSError as e:
        print(f"Порт {PORT} уже занят другим процессом — закройте его и запустите снова. ({e})")
        raise SystemExit(1)
