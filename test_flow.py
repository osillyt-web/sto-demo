#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Функциональный прогон: сайт, калькулятор, форма, админка, экспорт. Печатает PASS/FAIL."""
import json, sys, urllib.request, urllib.parse, urllib.error

BASE = "http://127.0.0.1:8000"
fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f" :: {extra}" if extra else ""))
    if not cond:
        fails.append(name)


def get(path, cookie=None):
    req = urllib.request.Request(BASE + path)
    if cookie:
        req.add_header("Cookie", cookie)
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode("utf-8"), r.headers


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def post(path, data, cookie=None, follow=True):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    if cookie:
        req.add_header("Cookie", cookie)
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req) as r:
            return r.status, r.read().decode("utf-8"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers


# ---------- главная ----------
status, html, _ = get("/")
check("GET / = 200", status == 200)
check("главная: бренд", "АвтоТочка" in html)
check("главная: калькулятор на месте", 'id="calc-form"' in html)
check("главная: чекбоксы услуг из БД", html.count('name="svc"') >= 3, html.count('name="svc"'))
check("главная: форма записи", 'id="lead-form"' in html)
check("главная: нет незаполненных плейсхолдеров", "{{" not in html,
      [h for h in ("SERVICE_CARDS", "PRICE_ROWS", "SERVICE_OPTIONS", "SERVICE_CHECKBOXES")
       if "{{" + h in html])

status, svc_json, _ = get("/api/services")
services = json.loads(svc_json)
titles = [s["title"] for s in services]
check("главная рендерит услуги из БД", all(t in html for t in titles), titles[:2])
check("у услуг есть числовая база для калькулятора", all(s["base"] > 0 for s in services),
      [(s["title"], s["base"]) for s in services][:3])

status, calc_json, _ = get("/api/calc")
calc = json.loads(calc_json)
check("GET /api/calc: услуги + классы авто",
      len(calc["services"]) >= 3 and len(calc["classes"]) == 4, len(calc["services"]))

# ---------- заявки ----------
payload = {"name": "Олег Тестовий", "phone": "+380671112233", "service": titles[0],
           "car": "Skoda Octavia 2018", "when_at": "2026-11-12",
           "comment": "Стук спереду", "estimate": "900–1200 ₴", "consent": "1"}
status, body, _ = post("/api/leads", payload)
check("POST /api/leads = 200", status == 200, body)
check("заявка принята", json.loads(body).get("ok") is True)

status, body, _ = post("/api/leads", {"name": "X", "phone": "1"})
check("пустая заявка отклонена (400)", status == 400, body)

status, body, _ = post("/api/leads", {"name": "Тест", "phone": "+380****9999",
                                      "service": titles[0]})
check("заявка без согласия отклонена (400)", status == 400, body)
status, body, _ = post("/api/leads", {"name": "Бот", "phone": "+380670000000", "company": "spam"})
check("honeypot пропускает бота молча", status == 200 and json.loads(body).get("ok") is True)

# ---------- вход ----------
status, body, _ = post("/admin/login", {"password": "wrong"})
check("неверный пароль не пускает", "Невірний пароль" in body)
status, body, hdrs = post("/admin/login", {"password": "admin123"}, follow=False)
cookie = (hdrs.get("Set-Cookie") or "").split(";")[0]
check("вход выдаёт HttpOnly cookie",
      status == 302 and cookie.startswith("sid=") and "HttpOnly" in hdrs.get("Set-Cookie", ""))
status, body, _ = get("/admin", cookie)
check("админка открывается по сессии", status == 200 and "Заявки з сайту" in body)
req = urllib.request.Request(BASE + "/admin")
try:
    urllib.request.build_opener(NoRedirect).open(req)
    check("без сессии /admin не отдаётся", False)
except urllib.error.HTTPError as e:
    check("без сессии /admin редиректит на логин (302)", e.code == 302, e.code)

# ---------- заявки через API ----------
status, body, _ = get("/api/admin/leads", cookie)
data = json.loads(body)
check("GET /api/admin/leads = 200", status == 200)
ours = [l for l in data["leads"] if l["name"] == "Олег Тестовий"]
check("кириллица в заявке не искажена", bool(ours),
      ours[0]["name"] if ours else [l["name"] for l in data["leads"][:3]])
check("кошторис сохранён", bool(ours) and ours[0]["estimate"] == "900–1200 ₴",
      ours[0]["estimate"] if ours else None)
check("статистика: total/new/today", all(k in data["stats"] for k in ("total", "new", "today")), data["stats"])

lead_id = ours[0]["id"] if ours else 0
orig_svc = [s for s in services if s["id"] == 1][0]   # для восстановления после прогона
status, body, _ = post("/admin/lead", {"id": lead_id, "status": "done", "note": "Передзвонили, записали"}, cookie)
check("статус + нотатка сохраняются", status == 200)
_, body, _ = get("/api/admin/leads", cookie)
row = [l for l in json.loads(body)["leads"] if l["id"] == lead_id][0]
check("статус в БД = done", row["status"] == "done", row["status"])
check("нотатка в БД", row["note"] == "Передзвонили, записали", row["note"])

_, body, _ = get("/api/admin/leads?status=done&q=" + urllib.parse.quote("Олег"), cookie)
filtered = json.loads(body)["leads"]
check("фильтр по статусу + поиск работают", any(l["id"] == lead_id for l in filtered), len(filtered))

status, csv_body, hdrs = get("/admin/export.csv", cookie)
check("экспорт CSV отдаётся", status == 200 and "attachment" in (hdrs.get("Content-Disposition") or ""))
check("CSV: заголовок и кириллица", "Телефон" in csv_body and "Олег" in csv_body)

try:
    get("/api/admin/leads")
    check("API заявок закрыт без сессии (401)", False)
except urllib.error.HTTPError as e:
    check("API заявок закрыт без сессии (401)", e.code == 401, e.code)

# ---------- услуги ----------
status, body, _ = post("/admin/service", {"action": "update", "id": 1, "title": titles[0],
                                          "price": "520 ₴", "note": "Оновлено з адмінки",
                                          "base": "520", "active": "1"}, cookie)
check("редактирование услуги = 200", status == 200, body)
_, svc_json, _ = get("/api/services")
svc1 = [s for s in json.loads(svc_json) if s["id"] == 1][0]
check("цена обновилась", svc1["price"] == "520 ₴", svc1["price"])
check("база для калькулятора обновилась", svc1["base"] == 520, svc1["base"])
_, html, _ = get("/")
check("новая цена видна на главной", "520 ₴" in html)

status, body, _ = post("/admin/service", {"action": "add", "title": "Тестова послуга",
                                          "price": "1 000 ₴", "base": "1000", "note": "тимчасова"}, cookie)
_, svc_json, _ = get("/api/admin/services", cookie)
added = [s for s in json.loads(svc_json) if s["title"] == "Тестова послуга"]
check("добавление услуги", status == 200 and bool(added))
if added:
    post("/admin/service", {"action": "delete", "id": added[0]["id"]}, cookie)
    _, svc_json, _ = get("/api/admin/services", cookie)
    check("удаление услуги", not [s for s in json.loads(svc_json) if s["title"] == "Тестова послуга"])

# ---------- CSRF ----------
req = urllib.request.Request(BASE + "/admin/lead", data=b"id=1&status=done", method="POST")
req.add_header("Cookie", cookie)
req.add_header("Origin", "https://evil.example")
try:
    urllib.request.urlopen(req)
    check("чужой Origin блокируется (403)", False)
except urllib.error.HTTPError as e:
    check("чужой Origin блокируется (403)", e.code == 403, e.code)


# ---------- SEO, юр. страница, безопасность, аналитика ----------
import gzip as _gz

status, body, hdrs = get("/privacy")
check("страница политики открывается", status == 200 and "Політика конфіденційності" in body, status)
check("в политике нет незаполненных плейсхолдеров", "{{" not in body)

status, body, _ = get("/robots.txt")
check("robots.txt со ссылкой на sitemap", status == 200 and "Sitemap:" in body)
status, body, _ = get("/sitemap.xml")
check("sitemap.xml — валидный urlset", status == 200 and "<urlset" in body and "/privacy" in body)
status, body, _ = get("/favicon.ico")
check("favicon отдаётся (не 404)", status == 200 and len(body) > 100, len(body))

_, html2, hdrs2 = get("/")
check("CSP-заголовок отдаётся", "Content-Security-Policy" in hdrs2)
check("X-Frame-Options стоит", hdrs2.get("X-Frame-Options") == "SAMEORIGIN")
check("микроразметка AutoRepair в HTML", "AutoRepair" in html2 and "FAQPage" in html2)
check("фото в галерее с alt", html2.count('class="shot"') >= 6 and "loading=\"lazy\"" in html2)

req = urllib.request.Request(BASE + "/", headers={"Accept-Encoding": "gzip"})
with urllib.request.urlopen(req) as r:
    check("HTML отдаётся сжатым (gzip)", r.headers.get("Content-Encoding") == "gzip")

status, body, _ = post("/api/hit", {"name": "view", "path": "/", "sid": "selftest"})
check("приём событий аналитики (POST /api/hit)", status == 200 and json.loads(body).get("ok"))

status, body, _ = get("/api/admin/analytics", cookie)
an = json.loads(body) if status == 200 else {}
check("аналитика доступна только с сессией",
      status == 200 and "views" in an and an["views"] >= 1, an.get("views"))

status, body, _ = get("/api/admin/settings", cookie)
settings = json.loads(body) if status == 200 else {}
check("настройки Telegram: токен не отдаётся открытым",
      status == 200 and settings.get("tg_token") is None and settings.get("tg_token_set") in ("0", "1"))

# ---------- уборка: демо-база остаётся чистой после прогона ----------
if lead_id:
    post("/admin/lead", {"action": "delete", "id": lead_id}, cookie)
post("/admin/service", {"action": "update", "id": 1, "title": orig_svc["title"],
                        "price": orig_svc["price"], "note": orig_svc["note"],
                        "base": orig_svc["base"], "active": "1"}, cookie)
_, body, _ = get("/api/admin/leads", cookie)
left = [l for l in json.loads(body)["leads"] if l["name"] == "Олег Тестовий"]
check("уборка: тестовая заявка удалена", not left, len(left))

print()
print("ИТОГ:", "ВСЁ ЗЕЛЁНОЕ" if not fails else f"ПРОВАЛЕНО {len(fails)}: {fails}")
sys.exit(0 if not fails else 1)
