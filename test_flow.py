#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Функциональный прогон: сайт, калькулятор, форма, админка, экспорт. Печатает PASS/FAIL."""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error

# Пароль админки: по умолчанию демонстрационный, но после смены пароля владельцем
# тесты запускаются так:  ADMIN_PASSWORD='свій пароль' python test_flow.py
PW = os.environ.get("ADMIN_PASSWORD", "admin123")

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
check("главная: бренд", "АвтоКрапка" in html)
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
status, body, hdrs = post("/admin/login", {"password": PW}, follow=False)
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

# ---------- слоты записи, источник заявки, портфолио, 404 ----------
status, body, _ = get("/api/slots/days")
days = json.loads(body) if status == 200 else {}
check("GET /api/slots/days: 14 днів і місткість", status == 200 and len(days.get("days", [])) == 14
      and isinstance(days.get("capacity"), int), len(days.get("days", [])))

open_days = [d for d in days.get("days", []) if not d["closed"] and d["free"] > 0]
check("є відкриті дні з вільними годинами", len(open_days) >= 10, len(open_days))
check("неділя позначена як зачинена",
      any(d["closed"] for d in days.get("days", []) if d["weekday"] == "Нд"))

status, body, _ = post("/api/leads", {"kind": "callback", "phone": "".join(["+380", "93", "112", "77", "88"]), "consent": "1"})
cb_id = json.loads(body).get("id") if status == 200 else None
check("зворотний дзвінок приймається без імені", status == 200 and cb_id, status)
if cb_id:
    _, body, _ = get("/api/admin/leads", cookie)
    cb = [l for l in json.loads(body)["leads"] if l["id"] == cb_id]
    check("зворотний дзвінок позначено як callback", cb and cb[0]["kind"] == "callback")

test_day = open_days[-1] if open_days else None
status, body, _ = get("/api/slots?date=" + (test_day["date"] if test_day else ""))
slot_day = json.loads(body) if status == 200 else {}
slots = slot_day.get("slots", [])
check("GET /api/slots: години робочого дня", status == 200 and len(slots) >= 8, len(slots))
check("у слотах є статуси вільно/зайнято", all("state" in s and "free" in s for s in slots))

cap = slot_day.get("capacity", 2)
free_slot = next((s for s in slots if s["state"] == "free"), None)
slot_leads = []
if free_slot:
    lead_common = {"name": "Слот Тест", "phone": "".join(["+380", "93", "112", "44", "55"]), "consent": "1",
                   "service": titles[0], "slot_date": test_day["date"], "slot_time": free_slot["time"],
                   "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "selftest"}
    codes = []
    for _ in range(cap + 1):
        st_code, st_body, _ = post("/api/leads", dict(lead_common))
        codes.append(st_code)
        if st_code == 200:
            slot_leads.append(json.loads(st_body).get("id"))
    check(f"слот приймає рівно {cap} заявки", codes[:cap] == [200] * cap and codes[-1] == 409, codes)

    status, body, _ = post("/api/leads", dict(lead_common, slot_date="", slot_time=""))
    check("без вільного часу заявка проходить (необовʼязково)", status == 200, status)
    if status == 200:
        slot_leads.append(json.loads(body).get("id"))

    _, body, _ = get("/api/admin/leads", cookie)
    saved = [l for l in json.loads(body)["leads"] if l["name"] == "Слот Тест"]
    check("у заявці збережено дату й час слота",
          any(l["slot_date"] == test_day["date"] and l["slot_time"] == free_slot["time"] for l in saved))
    check("у заявці збережено джерело з UTM",
          any(l["utm_source"] == "google" and l["utm_campaign"] == "selftest" for l in saved))

# окно 14 дней, а не 7: тестовая заявка ставится в последний свободный день
# из выдачи /api/slots, а он в ночное время выходит за семидневное окно
status, body, _ = get("/api/admin/calendar?days=14", cookie)
cal = json.loads(body) if status == 200 else {}
check("календар завантаження: 14 днів і сітка годин",
      status == 200 and len(cal.get("grid", [])) == 14 and len(cal.get("times", [])) >= 8)
check("календар показує зайняті години",
      any(s["booked"] > 0 for d in cal.get("grid", []) for s in d["slots"]) or not slot_leads,
      sum(s["booked"] for d in cal.get("grid", []) for s in d["slots"]))

# --- якорі: у кожної цілі є id, і ціль має відступ під липку шапку ---
# Перевіряємо саме розмітку й стилі: чи не забули новий блок додати до правила
# scroll-margin-top. Положення на екрані перевіряє окремо tools/anchor_check.py
status, css_body, _ = get("/static/style.css")
# комментарии убираем: иначе в разбор селектора попадает текст пояснения
css_clean = re.sub(r"/\*.*?\*/", "", css_body, flags=re.S)
check("CSS: висота шапки задана для ПК", "--top-h:75px" in css_clean)
check("CSS: висота шапки задана для вузьких екранів", "--top-h:65px" in css_clean)
_m = re.search(r"([^{}]+)\{scroll-margin-top:var\(--top-h\)\}", css_clean)
check("CSS: правило відступу для цілей якорів на місці", bool(_m), _m.group(1).strip() if _m else "правила нет")
_offset_classes = set()
if _m:
    _offset_classes = {c.strip().lstrip(".") for c in _m.group(1).split(",") if c.strip()}

for _path in ("/", "/cases"):
    _, _html, _ = get(_path)
    _ids = {}
    for _tag in re.finditer(r"<(\w+)([^>]*?)>", _html):
        _attrs = _tag.group(2)
        _mid = re.search(r'\bid="([^"]+)"', _attrs)
        if _mid:
            _mc = re.search(r'\bclass="([^"]*)"', _attrs)
            _ids[_mid.group(1)] = set((_mc.group(1) if _mc else "").split())
    _anchors = {a for a in re.findall(r'href="#([^"]+)"', _html)}
    _missing = sorted(a for a in _anchors if a not in _ids)
    check("%s: у кожного якоря є ціль" % _path, not _missing, _missing)
    # #top — сама шапка, їй відступ не потрібен
    _no_rule = sorted(a for a in _anchors
                      if a in _ids and a != "top" and not (_ids[a] & _offset_classes))
    check("%s: у цілей якорів є відступ під шапку" % _path, not _no_rule, _no_rule)

# --- у каждой услуги своя картинка: две услуги с одним фото выглядят как ошибка ---
_svc_photos = {}
for _slug in ("diahnostyka", "to", "shynomontazh", "kuzovnyi", "poliruvannia", "khimchystka"):
    _st, _h, _ = get("/services/" + _slug)
    _mm = re.search(r'<img src="(/static/img/[^"]+)"', _h)
    _svc_photos[_slug] = _mm.group(1) if _mm else None
_repeats = {v: [k for k, x in _svc_photos.items() if x == v]
            for v in set(_svc_photos.values()) if list(_svc_photos.values()).count(v) > 1}
check("у кожного сервісу своя картинка", not _repeats, _repeats or "повторів немає")
check("усі сервісні сторінки мають картинку", all(_svc_photos.values()), _svc_photos)
check("сервісні сторінки віддають зменшені картинки (-sm)",
      all(v and v.endswith("-sm.webp") for v in _svc_photos.values()), _svc_photos)

_brand_photos = {}
for _slug in ("volkswagen", "toyota", "skoda", "bmw", "renault", "nissan"):
    _st, _h, _ = get("/brands/" + _slug)
    _mm = re.search(r'<img src="(/static/img/[^"]+)"', _h)
    _brand_photos[_slug] = _mm.group(1) if _mm else None
_repeats_b = {v: [k for k, x in _brand_photos.items() if x == v]
              for v in set(_brand_photos.values()) if list(_brand_photos.values()).count(v) > 1}
check("у кожної марки своя картинка", not _repeats_b, _repeats_b or "повторів немає")
check("усі сторінки марок мають картинку", all(_brand_photos.values()), _brand_photos)

# --- блок «до/після»: ліва половина чорно-біла, права кольорова ---
_st, _home, _ = get("/")
_blocks = re.findall(r'<figure class="ba-block">(.*?)</figure>', _home, re.S)
check("на головній є блок «До і після»", "До і після" in _home and len(_blocks) == 2, len(_blocks))
check("у кожному порівнянні свій повзунок і шар «до»",
      all('class="ba-handle"' in _b and 'class="ba-before"' in _b for _b in _blocks))
check("шар «до» — те саме фото, показане чорно-білим",
      all(re.search(r'ba-img--before', _b) for _b in _blocks))
_css = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "style.css"),
            encoding="utf-8").read()
_ms = re.search(r'\.ba-img--before\{([^}]*)\}', _css)
check("чорно-біле показує сама сторінка стилів (grayscale без часткових відтінків)",
      bool(_ms) and "grayscale(1)" in _ms.group(1).replace(" ", ""), _ms.group(1) if _ms else "правило не знайдено")

status, body, _ = get("/cases")
check("сторінка портфоліо відкривається", status == 200 and "Портфоліо" in body, status)
check("у портфоліо два кейси для автобізнесу", body.count('class="case"') == 2, body.count('class="case"'))
check("портфоліо: заголовок про СТО й запис", "Сайти для СТО та детейлінгу" in body)
check("портфоліо: кейс VoiceReader прибрано з великих", 'id="case-voice"' not in body)
check("портфоліо: блоку «Інші роботи» немає", 'id="other"' not in body and "Інші роботи" not in body)
check("портфоліо: VoiceReader на сторінці не згадується", "VoiceReader" not in body)
check("портфоліо: підпис кейсу ГСМ — автопарк і СТО", "автопарк і СТО" in body)
check("у портфоліо немає плейсхолдерів", "{{" not in body)

# --- пропозиція та живий контакт у портфоліо ---
check("портфоліо: є блок пропозиції", 'id="offer"' in body)
check("портфоліо: у пропозиції є ціна і строк", "19 900" in body and "7–10" in body)
check("портфоліо: обіцяно показати головну до оплати", "До оплати покажу" in body)
check("портфоліо: кнопки ведуть у Telegram, а не на форму запису в автосервіс",
      "t.me/" in body and "/#book" not in body)
check("портфоліо: є блок «8 пунктів» як стандарт якості",
      'id="standard"' in body and "8 пунктами" in body)
check("портфоліо: сказано про роботу текстом, без дзвінків", "дзвінки не потрібні" in body)
_imgs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img")
check("карта-прев'ю віддається webp і важить менше 150 КБ",
      os.path.exists(os.path.join(_imgs, "map-preview.webp"))
      and os.path.getsize(os.path.join(_imgs, "map-preview.webp")) < 150 * 1024,
      round(os.path.getsize(os.path.join(_imgs, "map-preview.webp")) / 1024) if os.path.exists(os.path.join(_imgs, "map-preview.webp")) else "файла нет")
check("старий PNG-файл карти видалено", not os.path.exists(os.path.join(_imgs, "map-preview.png")))
status, body, _ = get("/sitemap.xml")
check("sitemap містить /cases", "/cases" in body)

try:
    status, body, _ = get("/takoi-storinky-nema")
    check("404 віддає сторінку, а не порожнечу", False, status)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    check("404 віддає зрозумілу сторінку", e.code == 404 and "404" in body and 'href="/"' in body, e.code)

# контакты из админки меняют сайт
status, body, _ = get("/api/admin/settings", cookie)
base_contacts = json.loads(body)["contacts"] if status == 200 else {}
status, _, _ = post("/admin/settings", {"c_phone": "+380 44 777-77-77", "c_phone_raw": "+380447777777",
                                        "c_address": base_contacts.get("address", ""),
                                        "c_hours": base_contacts.get("hours", ""),
                                        "c_telegram": base_contacts.get("telegram", ""),
                                        "c_viber": base_contacts.get("viber", ""),
                                        "c_whatsapp": base_contacts.get("whatsapp", ""),
                                        "c_reviews_url": base_contacts.get("reviews_url", ""),
                                        "c_reviews_note": base_contacts.get("reviews_note", "")}, cookie)
_, html_c, _ = get("/")
check("телефон з адмінки зʼявляється на сайті", "+380 44 777-77-77" in html_c)
post("/admin/settings", {"c_phone": base_contacts.get("phone", ""),
                         "c_phone_raw": base_contacts.get("phone_raw", ""),
                         "c_address": base_contacts.get("address", ""),
                         "c_hours": base_contacts.get("hours", ""),
                         "c_telegram": base_contacts.get("telegram", ""),
                         "c_viber": base_contacts.get("viber", ""),
                         "c_whatsapp": base_contacts.get("whatsapp", ""),
                         "c_reviews_url": base_contacts.get("reviews_url", ""),
                         "c_reviews_note": base_contacts.get("reviews_note", "")}, cookie)
_, html_c2, _ = get("/")
check("демо-контакти відновлено після тесту", base_contacts.get("phone", "") in html_c2)

check("на головній є блок гарантії та месенджери",
      'id="guarantee"' in html2 and html2.count("msgr-btn") >= 3 and 'id="callback-form"' in html2)
check("на головній є вибір дати й часу", 'id="days"' in html2 and 'id="times"' in html2
      and 'id="slot-data"' in html2)

for lid in slot_leads + ([cb_id] if cb_id else []):
    if lid:
        post("/admin/lead", {"action": "delete", "id": lid}, cookie)


# ---------- SEO-страницы услуг и марок ----------
import re as _re


def get_soft(path, cookie=None):
    """GET, который не падает на 4xx — для проверок 404 и 401."""
    try:
        return get(path, cookie)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers

status, svc_list, _ = get("/services")
check("GET /services = 200", status == 200)
check("список послуг: 6 карток", svc_list.count('class="svc-card"') == 6,
      svc_list.count('class="svc-card"'))
slugs = ["diahnostyka", "to", "shynomontazh", "kuzovnyi", "poliruvannia", "khimchystka"]
bad = []
for slug in slugs:
    st, page, _ = get("/services/" + slug)
    h1 = len(_re.findall(r"<h1", page))
    if (st != 200 or h1 != 1 or "{{" in page or 'class="ptable"' not in page
            or ("/services/" + slug) not in page):
        bad.append(slug)
check("6 сторінок послуг: 200, один H1, ціни, canonical", not bad, bad)
status, _, _ = get_soft("/services/no-such-service")
check("невідома послуга = 404", status == 404)
st, page, _ = get("/services/poliruvannia")
check("сторінка послуги містить FAQ і розмітку Service",
      'class="faq-item"' in page and '"@type": "Service"' in page)

status, br_list, _ = get("/brands")
check("GET /brands = 200, 6 марок", status == 200 and br_list.count('class="svc-card"') == 6,
      br_list.count('class="svc-card"'))
st, bmw, _ = get("/brands/bmw")
check("сторінка марки: 200, моделі, ціни послуг",
      st == 200 and "X5" in bmw and 'class="model-chip"' in bmw and "від" in bmw)
status, _, _ = get_soft("/brands/no-such-brand")
check("невідома марка = 404", status == 404)

_, sm, _ = get("/sitemap.xml")
check("sitemap: 18 адрес, включно з послугами, марками й тарифами",
      sm.count("<loc>") == 18 and "/services/to" in sm and "/brands/skoda" in sm
      and "/pricing" in sm, sm.count("<loc>"))

# ---------- напоминание о записи ----------
_, days_raw, _ = get("/api/slots/days")
_cal = json.loads(days_raw)["days"]
_day = next((d for d in _cal if d["free"] > 0 and not d["closed"]), None)
check("є день із вільними слотами", bool(_day))
rem_token = ""
if _day:
    st, body, _ = post("/api/leads", {
        "name": "Тест Нагадування", "phone": "".join(["+380", "67", "123", "45", "67"]),
        "service": "Шиномонтаж", "car": "Test", "slot_date": _day["date"],
        "slot_time": _day["times"][0] if isinstance(_day.get("times"), list) else "10:00",
        "consent": "1"}, follow=True)
    book_id = json.loads(body).get("id") if body.strip().startswith("{") else None

    _, leads_raw, _ = get("/api/admin/leads", cookie)
    mine = [l for l in json.loads(leads_raw)["leads"] if l["name"] == "Тест Нагадування"]
    rem_token = mine[0]["token"] if mine else ""
    check("у заявки є токен для сторінки запису", bool(rem_token))
    book_id = mine[0]["id"] if mine else None

if rem_token:
    st, rem_page, _ = get("/r/" + rem_token)
    check("сторінка запису: 200, дата й час, кнопки",
          st == 200 and "Підтвердити запис" in rem_page and "Скасувати запис" in rem_page
          and "{{" not in rem_page)
    st, conf, _ = post("/r/" + rem_token + "/confirm", {})
    check("підтвердження запису працює", st == 200 and "Запис підтверджено" in conf)
    _, leads_raw, _ = get("/api/admin/leads", cookie)
    got = [l for l in json.loads(leads_raw)["leads"] if l.get("token") == rem_token]
    check("підтвердження збережено в базі", bool(got) and got[0]["confirmed"] == "confirmed")
    st, canc, _ = post("/r/" + rem_token + "/cancel", {})
    check("скасування запису працює", st == 200 and "Запис скасовано" in canc)
    _, leads_raw, _ = get("/api/admin/leads", cookie)
    got = [l for l in json.loads(leads_raw)["leads"] if l.get("token") == rem_token]
    check("скасування змінює статус заявки",
          bool(got) and got[0]["confirmed"] == "cancelled" and got[0]["status"] == "cancelled")

    _, rem_raw, _ = get("/api/admin/remind?id=%s" % got[0]["id"], cookie)
    rem = json.loads(rem_raw)
    check("API нагадування: текст із посиланням",
          rem.get("ok") and "/r/" in rem.get("text", "") and rem.get("url", "").endswith(rem_token))
    status, _, _ = get_soft("/api/admin/remind?id=1")
    check("API нагадування закрите без входу", status in (401, 403), status)
    if got:
        post("/admin/lead", {"action": "delete", "id": got[0]["id"]}, cookie)

status, _, _ = get_soft("/r/nesovsem-token")
check("невідомий токен запису = 404", status == 404)



# ---------- защита служебных файлов: перебор не должен ничего отдавать ----------
import glob as _glob2
_here2 = os.path.dirname(os.path.abspath(__file__))
_sensitive = [
    "/data/auth.json", "/data/sto.db", "/data/errors.log", "/data/security.log", "/backups/",
    "/server.py", "/content.py", "/ops.py", "/templates/index.html", "/tools/axe_check.py",
    "/.git/config", "/.env", "/requirements.txt", "/test_flow.py", "/server.log",
    "/static/../data/auth.json", "/static/%2e%2e/data/auth.json", "/static\\..\\data\\auth.json",
    "/static/style.css::$DATA", "/static/foo.json", "/static/x.py", "/static/.hidden",
    "/admin/../data/auth.json", "/api/../data/auth.json", "/data/",
]
_opened = []
for _p in _sensitive:
    _st = get_soft(_p)[0]
    if _st == 200:
        _opened.append(_p)
check("служебные файлы недоступны снаружи", not _opened, _opened)

# обход через кодирование и «хвосты» тоже не должен открывать файлы
_q = ["/data/auth.json?x=1", "/data/auth.json%20", "/DATA/AUTH.JSON", "/data//auth.json",
      "/%64ata/auth.json", "/static/./../data/sto.db"]
_opened2 = [p for p in _q if get_soft(p)[0] == 200]
check("обход каталогов через кодирование не работает", not _opened2, _opened2)

# ответ не должен отличаться от обычной отсутствующей страницы (никаких подсказок)
_st_b, _body_b, _ = get_soft("/data/auth.json")
check("на служебный путь ответ как на несуществующую страницу",
      _st_b == 404 and _body_b.strip() == "not found", (get_soft("/data/auth.json")[0], _body_b[:40]))

# все реальные файлы статики должны отдаваться (картинки — двоичные, поэтому только код ответа)
def _status_only(path):
    import http.client as _h
    c = _h.HTTPConnection("127.0.0.1", 8000, timeout=10)
    c.request("GET", path)
    code = c.getresponse().status
    c.close()
    return code

_missing_static = []
for _f in _glob2.glob(os.path.join(_here2, "static", "**", "*"), recursive=True):
    if os.path.isfile(_f):
        _rel = "/static/" + os.path.relpath(_f, os.path.join(_here2, "static")).replace(os.sep, "/")
        if _status_only(_rel) != 200:
            _missing_static.append(_rel)
check("вся статика отдаётся после введения ограничений", not _missing_static, _missing_static[:5])

# попытки перебора попадают в журнал
_log = os.path.join(_here2, "data", "security.log")
_seen = os.path.exists(_log) and "data/auth.json" in open(_log, encoding="utf-8").read()
check("попытки доступа к служебным файлам пишутся в журнал", _seen)

# заголовок Server не выдаёт версию Python
import http.client as _http
_c = _http.HTTPConnection("127.0.0.1", 8000, timeout=10)
_c.request("GET", "/")
_srv = _c.getresponse().getheader("Server") or ""
_c.close()
check("заголовок Server не содержит версию Python", "Python" not in _srv and "avtokrapka" in _srv, _srv)

# ---------- эксплуатация: health, бэкапы, журнал, пароль ----------
import os as _os, glob as _glob, sqlite3 as _sqlite

st, hbody, _ = get("/api/health")
h = json.loads(hbody)
check("GET /api/health = 200, база ок", st == 200 and h.get("ok") and h.get("db") == "ok", h.get("db"))
check("health віддає версію та аптайм",
      bool(h.get("version")) and isinstance(h.get("uptime_s"), int))
# кількість заявок — не публічна інформація: без входу її не видно
check("health без входу не показує кількість заявок і налаштувань",
      "leads" not in h and "settings" not in h)
check("health не світить стан пароля без входу", "default_password" not in h)
_, hbody2, _ = get("/api/health", cookie)
h2 = json.loads(hbody2)
check("health з входом показує кількість заявок", isinstance(h2.get("leads"), int))

st, _, _ = get_soft("/api/admin/state")
check("стан системи закритий без входу", st in (401, 403), st)
_, sbody, _ = get("/api/admin/state", cookie)
state = json.loads(sbody)
check("стан системи: прапор демо-пароля, розмір бази, копія",
      state.get("ok") and isinstance(state.get("default_password"), bool)
      and state.get("db_size_kb", 0) > 0 and state.get("last_backup"))

_, abody, _ = get("/api/admin/audit?limit=200", cookie)
audit_rows = json.loads(abody)["rows"]
check("журнал дій пише вхід в адмінку",
      any(r["action"] == "вхід в адмінку" for r in audit_rows), len(audit_rows))

# копия базы на диске должна открываться и содержать заявки
_here = _os.path.dirname(_os.path.abspath(__file__))
_backups = sorted(_glob.glob(_os.path.join(_here, "backups", "sto-*.db")))
check("резервна копія існує", bool(_backups), len(_backups))
if _backups:
    _bc = _sqlite.connect(_backups[-1])
    try:
        _leads_in_copy = _bc.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        _svc_in_copy = _bc.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    finally:
        _bc.close()
    check("копія цілісна: заявки й послуги на місці", _svc_in_copy >= 6 and _leads_in_copy >= 0,
          f"заявок {_leads_in_copy}, послуг {_svc_in_copy}")

# слабкий пароль не приймається
st, pbody, _ = post("/admin/password", {"old": PW, "new": "admin123"}, cookie)
check("слабкий пароль відхилено (400)", st == 400, pbody[:60])
st, pbody, _ = post("/admin/password", {"old": PW, "new": "korotkyi"}, cookie)
check("короткий пароль відхилено (400)", st == 400, pbody[:60])

# журнал фіксує зміну налаштувань
post("/admin/settings", {"c_phone": base_contacts.get("phone", ""),
                         "c_phone_raw": base_contacts.get("phone_raw", "")}, cookie)
_, abody2, _ = get("/api/admin/audit?limit=10", cookie)
check("журнал фіксує збереження налаштувань",
      any("налаштування" in r["action"] for r in json.loads(abody2)["rows"]))


# ---------- регрессия: текст кнопок не должен сливаться с фоном ----------
_css_path = _os.path.join(_here, "static", "style.css")
_css = open(_css_path, encoding="utf-8").read()
_legal_rule = [ln for ln in _css.splitlines() if ln.strip().startswith(".legal a")]
check("CSS: ссылки в юридических текстах не перебивают цвет кнопок",
      _legal_rule and all(":not(.btn)" in ln for ln in _legal_rule), _legal_rule[:2])

st, priv, _ = get("/privacy")
check("на сторінці політики кнопка повернення без 'голого' посилання",
      'class="btn btn-accent" href="/"' in priv and "Повернутися на сайт" in priv)
check("на /privacy телефон підставляється з налаштувань, без плейсхолдерів",
      "{{" not in priv and 'href="tel:' in priv)


# ---------- адреса с «хвостами» из чата не должны давать 404 ----------
for junk, expect in [("/admin%C2%BB", "/admin"), ("/privacy%22", "/privacy"),
                     ("/services/to.", "/services/to"), ("/cases;", "/cases")]:
    try:
        with urllib.request.urlopen(BASE + junk) as r:
            status, final = r.status, r.geturl()
        ok = status == 200 and (expect in final or "/admin/login" in final)
    except urllib.error.HTTPError as e:
        ok, status, final = False, e.code, BASE + junk
    check(f"адреса з хвостом {junk} веде на робочу сторінку", ok, f"{status} {final}")

# нормальные адреса после нормализации не пострадали
for p in ["/", "/admin", "/services", "/cases", "/privacy"]:
    st, _, _ = get_soft(p)
    check(f"нормальна адреса {p} не зламана", st in (200, 302), st)


# ---------- стоимость хранения пароля ----------
_auth_path = _os.path.join(_here, "data", "auth.json")
_auth = json.load(open(_auth_path, encoding="utf-8"))
check("пароль зберігається з 600 000 ітерацій PBKDF2", int(_auth.get("iter", 0)) >= 600_000,
      _auth.get("iter"))
check("у файлі пароля немає самого пароля", set(_auth) == {"salt", "hash", "iter"}, sorted(_auth))


# ---------- кнопка «показать пароль» ----------
_, lp, _ = get("/admin/login")
check("вхід: поле пароля з кнопкою показу", 'data-eye' in lp and "password-eye.js" in lp)
check("вхід: підказка про демо-пароль не світиться, коли пароль змінено",
      "Демо-пароль" not in lp or "admin123" in lp)
check("вхід: без незамінених плейсхолдерів", "{{" not in lp)
st, eye, _ = get("/static/password-eye.js")
check("скрипт кнопки віддається (200) і вміє перемикати стан",
      st == 200 and "aria-pressed" in eye and "password" in eye)
_, adm, _ = get("/admin", cookie)
check("адмінка: два поля з кнопкою показу", adm.count("data-eye") == 2, adm.count("data-eye"))
check("адмінка: вимоги до пароля узгоджені з сервером (10 символів)",
      "мінімум 10 символів" in adm and 'minlength="10"' in adm)
check("адмінка: на сторінці актуальна вартість хешування",
      "600 000 ітерацій" in adm, "600 000" in adm)


# ---------- кнопка «Догори» в адмінці ----------
check("адмінка: кнопка «Догори» є в розмітці", 'id="to-top"' in adm and ">Догори<" in adm)
_tag = adm.split('id="to-top"')[0].rsplit("<button", 1)[-1] + adm.split('id="to-top"')[1].split(">")[0]
check("адмінка: кнопка доступна (aria-label, тип button)",
      'aria-label="Догори — на початок сторінки"' in _tag and 'type="button"' in _tag, _tag.strip()[:90])
_acss = open(_os.path.join(_here, "static", "admin.css"), encoding="utf-8").read()
check("адмінка: стилі кнопки на місці (фіксована, 48 px, прихована за замовчуванням)",
      ".to-top-fab" in _acss and "position:fixed" in _acss and "visibility:hidden" in _acss)
_ajs = open(_os.path.join(_here, "static", "admin.js"), encoding="utf-8").read()
check("адмінка: кнопка реагує на прокрутку й піднімає сторінку",
      'getElementById("to-top")' in _ajs and "scrollTo(0, 0)" in _ajs and "SHOW_AFTER" in _ajs)
check("адмінка: невидима кнопка прибрана з Tab", "tabIndex = visible ? 0 : -1" in _ajs)


# ---------- вход: прощаем пробелы, объясняем причину отказа ----------
_st, _body, _hdrs = post("/admin/login", {"password": "  " + PW + "  "}, follow=False)
check("вхід не ламається через пробіли навколо пароля", _st == 302, _st)
_st, _body, _ = post("/admin/login", {"password": PW}, follow=False)
check("вхід звичайним паролем", _st == 302, _st)
_st, _body, _ = post("/admin/login", {"password": "admin124"})
check("невірний пароль: пояснення про розкладку",
      _st == 200 and "розкладка клавіатури" in _body, _st)
_st, _body, _ = post("/admin/password", {"old": PW, "new": "  korot  "}, cookie)
check("пароль із пробілами теж перевіряється на довжину", _st == 400, _body[:60])


# ---------- навигация по разделам админки ----------
import re as _re
_nav_ids = _re.findall(r'data-nav="([a-z-]+)"', adm)
check("адмінка: навігація має 8 розділів", len(_nav_ids) == 8, _nav_ids)
check("адмінка: навігація в landmark з назвою",
      'aria-label="Розділи панелі"' in adm and "<nav" in adm)
_missing = [i for i in _nav_ids if f'id="{i}"' not in adm]
check("адмінка: у кожного посилання є розділ на сторінці", not _missing, _missing)
check("адмінка: посилання ведуть на власні якорі",
      all(f'href="#{i}"' in adm for i in _nav_ids))
_acss2 = open(_os.path.join(_here, "static", "admin.css"), encoding="utf-8").read()
check("адмінка: якір не ховається під шапкою (scroll-margin-top)",
      "scroll-margin-top:92px" in _acss2)
_ajs2 = open(_os.path.join(_here, "static", "admin.js"), encoding="utf-8").read()
check("адмінка: поточний розділ позначається aria-current",
      'aria-current", "location"' in _ajs2 or "aria-current" in _ajs2)
check("адмінка: у низу сторінки активний останній розділ", "atBottom" in _ajs2)
check("адмінка: на телефоні активна вкладка підкручується у видиму зону",
      "is-scrollable" in _ajs2 and "is-scrollable" in _acss2)


# ---------- ориентиры страницы и доступность (по итогам проверок axe и W3C) ----------
_, home_html, home_hdrs = get("/")
check("головна: рівно один орієнтир main", home_html.count("<main") == 1 and 'id="main"' in home_html)
for _p in ("/cases", "/services", "/admin/login"):
    _, _b, _ = get(_p)
    check(f"{_p}: є орієнтир main", "<main" in _b)
check("головна: без aside (бокові колонки — не окремі орієнтири)", "<aside" not in home_html)
check("головна: у зірок рейтингу є роль",
      home_html.count('<div class="stars" role="img"') >= 1 and 'class="stars" aria-label' not in home_html)
check("головна: немає зображень із порожнім src", 'src=""' not in home_html)
check("головна: відгук має заголовок для скринрідера", 'class="sr-only">Відгук клієнта' in home_html)
check("головна: полоса переваг — не section без заголовка", '<section class="strip">' not in home_html)
check("головна: картки гарантій — не article без заголовка", '<article class="trust-card">' not in home_html)
_, _to, _ = get("/services/to")
check("/services/to: таблиця доступна з клавіатури",
      'class="table-wrap" role="region"' in _to and 'tabindex="0"' in _to)
_acss3 = open(_os.path.join(_here, "static", "style.css"), encoding="utf-8").read()
check("стилі: підзаголовок у шапці таблиці має достатній контраст",
      "opacity:.75" not in _acss3.split(".ptable th small")[1][:80])
check("стилі: є клас для тексту лише для скринрідера", ".sr-only{" in _acss3)


# ---------- доступность админки (по итогам проверки axe) ----------
check("адмінка: у сторінки є головний заголовок h1", "<h1" in adm)
check("адмінка: фільтр заявок — група кнопок, не вкладки",
      'class="seg" role="group"' in adm and 'role="tablist"' not in adm)
check("адмінка: у кнопок фільтра є aria-pressed",
      adm.count('aria-pressed="') >= 3)
check("адмінка: у порожніх заголовків таблиць є текст для скринрідера",
      "Дії</span>" in _ajs2 and "Час</span>" in _ajs2)
check("адмінка: посилання в тексті підкреслене (не тільки колір)",
      "text-decoration:underline" in _acss2.split(".alert-link{")[1][:60])
check("адмінка: підпис у підвалі має достатній контраст",
      "#8b96a6" in _acss2.split(".adm-foot{")[1][:40])

# ---------- реальна карта та адреса СТО (не заглушка) ----------
_, home3, home3_h = get("/")
check("головна: є блок реальної карти .map-card", 'class="map-card"' in home3)
check("головна: карта — справжній iframe Google Maps з координатами",
      "https://www.google.com/maps?q=50.4715341,30.4985365" in home3)
check("головна: у карти є підпис для скринрідера", 'title="Мапа: АвтоКрапка, Київ, вул. Кирилівська, 41"' in home3)
check("головна: карта вантажиться ліниво (не гальмує перший екран)",
      'loading="lazy"' in home3)
check("головна: адреса вказана і збігається з точкою на карті",
      "Київ, вул. Кирилівська, 41" in home3)
check("головна: є посилання «Прокласти маршрут» на ці координати",
      "maps/dir/?api=1&amp;destination=50.4715341,30.4985365" in home3 or
      "maps/dir/?api=1&destination=50.4715341,30.4985365" in home3)
check("головна: фальшивої вулиці «Автосервісна» більше немає", "Автосервісна" not in home3)
check("сторінка приватності: там само реальна адреса",
      "Автосервісна" not in get("/privacy")[1])
_m = _re.search(r'"geo": \{"@type": "GeoCoordinates", "latitude": ([0-9.]+), "longitude": ([0-9.]+)\}', home3)
check("розмітка LocalBusiness: координати збігаються з картою",
      bool(_m) and _m.group(1) == "50.4715341" and _m.group(2) == "30.4985365", _m.groups() if _m else None)
check("розмітка LocalBusiness: вулиця в адресі — Кирилівська",
      '"streetAddress": "вул. Кирилівська, 41"' in home3)
_csp = home3_h.get("Content-Security-Policy") or ""
check("CSP дозволяє вбудовувати карту Google", "frame-src" in _csp and "www.google.com" in _csp)
_css_map = get("/static/style.css")[1]
# картинка двоичная — читаем только код ответа и размер, без декодирования в текст
_ic = _http.HTTPConnection("127.0.0.1", 8000, timeout=10)
_ic.request("GET", "/static/img/map-preview.webp")
_ir = _ic.getresponse()
_st_img, _len_img = _ir.status, len(_ir.read())
_ic.close()
check("карта: є справжня підкладка-картинка місцевості (не сірий прямокутник)",
      _st_img == 200 and _len_img > 20000, f"{_st_img}, {_len_img} байт")
check("стилі: підкладка карти підключена до iframe",
      "map-preview.webp" in _css_map)
check("стилі: карта має власний блок, а не декоративну сітку",
      ".map-card{" in _css_map and ".map-grid" not in _css_map)

# ---------- страница тарифов ----------
_st_pr, pr, _ = get("/pricing")
check("тарифи: страница віддається", _st_pr == 200, _st_pr)
check("тарифи: три тарифи на сторінці", pr.count('<article class="tier') == 3, pr.count('<article class="tier'))
check("тарифи: ціни 7 900 / 19 900 / 24 900",
      all(x in pr for x in ("7 900", "19 900", "24 900")))
check("тарифи: середній тариф позначений як рекомендований", "Рекомендуємо" in pr)
check("тарифи: у кожного тарифу є кнопка дії", pr.count("Обговорити") == 3, pr.count("Обговорити"))
check("тарифи: без незамінених плейсхолдерів", "{{" not in pr)
check("тарифи: є один main і заголовок h1", pr.count("<main") == 1 and "<h1>Тарифи</h1>" in pr)
check("тарифи: блок «хто що робить» є", 'id="who-does-what"' in pr)
check("тарифи: перелічено, що клієнт змінює сам",
      "Ви — самі, у панелі" in pr and "Послуги й ціни: додати, змінити, прибрати" in pr)
check("тарифи: перелічено, що робить виконавець",
      "Я — у межах підтримки" in pr and "Нові сторінки й тексти" in pr)
check("тарифи: є порівняння з WordPress", 'id="vs-wp"' in pr and "Плагіни" in pr)
check("тарифи: у порівнянні п'ять рядків", pr.count('<th scope="row">') == 5, pr.count('<th scope="row">'))
check("тарифи: джерело даних про уразливості вказано",
      "Patchstack" in pr and "Wordfence" in pr)
_home = get("/")[1]
check("головна: посилання на портфоліо в підвалі виділене",
      'class="foot-link-accent" href="/cases"' in _home)
check("головна: у посилання на портфоліо є стрілка, прихована від скринридерів",
      'Портфоліо <span aria-hidden="true">→</span>' in _home)
check("тарифи: сторінка є в карті сайту", "/pricing" in get("/sitemap.xml")[1])
check("портфоліо: посилання на тарифи в меню", 'href="/pricing"' in get("/cases")[1])

# ---------- кэш: публичное кэшируется с перепроверкой, приватное — нет ----------
check("головна: Cache-Control дозволяє повернення назад (без no-store)",
      "no-store" not in (home_hdrs.get("Cache-Control") or ""))
_, _hh, _h = get("/admin/login")
check("вхід в адмінку: Cache-Control no-store", "no-store" in (_h.get("Cache-Control") or ""))
_, _hh2, _h2 = get("/api/slots/days")
check("публічне API слотів: без no-store",
      "no-store" not in (_h2.get("Cache-Control") or ""))

# ---------- уборка: демо-база остаётся чистой после прогона ----------
# удаляем все заявки тестового клиента: если прошлый прогон упал, за ним остались «хвосты»
if lead_id:
    post("/admin/lead", {"action": "delete", "id": lead_id}, cookie)
_, _lb, _ = get("/api/admin/leads", cookie)
for _l in json.loads(_lb)["leads"]:
    if _l["name"] == "Олег Тестовий":
        post("/admin/lead", {"action": "delete", "id": _l["id"]}, cookie)
post("/admin/service", {"action": "update", "id": 1, "title": orig_svc["title"],
                        "price": orig_svc["price"], "note": orig_svc["note"],
                        "base": orig_svc["base"], "active": "1"}, cookie)
_, body, _ = get("/api/admin/leads", cookie)
left = [l for l in json.loads(body)["leads"] if l["name"] == "Олег Тестовий"]
check("уборка: тестовая заявка удалена", not left, len(left))

print()
print("ИТОГ:", "ВСЁ ЗЕЛЁНОЕ" if not fails else f"ПРОВАЛЕНО {len(fails)}: {fails}")
sys.exit(0 if not fails else 1)
