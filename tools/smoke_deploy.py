"""Проверка развёрнутого сайта по внешнему адресу.

Использование:
    python tools/smoke_deploy.py https://sto-demo.onrender.com
    python tools/smoke_deploy.py https://... --post      (дополнительно отправить заявку)

Проверяет то, что чаще всего ломается при переносе на платформу:
кодировку UTF-8, статику, шаблоны, запись в базу и скорость холодного ответа.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
DO_POST = "--post" in sys.argv
results = []


def check(name, ok, extra=""):
    results.append((name, bool(ok), extra))


def _headers(msg):
    """Заголовки в едином виде: Name-Case, чтобы проверки не зависели от регистра."""
    return {k.title(): v for k, v in msg.items()}


def fetch(path, timeout=30, data=None):
    url = BASE + path
    req = urllib.request.Request(url, data=data)
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), round(time.time() - t0, 2), _headers(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), round(time.time() - t0, 2), _headers(e.headers)
    except Exception as exc:
        return 0, str(exc).encode(), round(time.time() - t0, 2), {}


# 1. health — самый важный: показывает, что база открылась
status, body, ms, _ = fetch("/api/health")
try:
    health = json.loads(body.decode("utf-8"))
except Exception:
    health = {}
check("health отвечает 200", status == 200, f"status={status}, {ms} c")
check("health: база доступна", health.get("db") == "ok", str(health)[:120])
check("первый ответ быстрее 30 с (холодный старт)", ms < 30, f"{ms} c")

# 2. главная и UTF-8
status, body, ms, headers = fetch("/")
html = body.decode("utf-8", "replace")
check("главная 200", status == 200, f"{ms} c")
check("кириллица не сломана", "АвтоКрапка" in html and "�" not in html)
check("кодировка в заголовке", "utf-8" in headers.get("Content-Type", "").lower(),
      headers.get("Content-Type", ""))

# 3. страницы
for path, needle in (("/order", "Зв’язатися письмово"), ("/pricing", "Тарифи"),
                     ("/cases", "Портфоліо"), ("/privacy", "Політика"), ("/services", "Послуги")):
    status, body, ms, _ = fetch(path)
    text = body.decode("utf-8", "replace")
    check(f"{path} 200 и содержит «{needle}»", status == 200 and needle in text, f"{status}, {ms} c")

# 3б. страница отзывов: сетка, форма и скрипт
status, body, ms, _ = fetch("/reviews")
rev = body.decode("utf-8", "replace")
check("/reviews 200 и содержит «Відгуки клієнтів»", status == 200 and "Відгуки клієнтів" in rev, f"{status}, {ms} c")
check("на /reviews есть форма отзыва", 'id="rev-form"' in rev and 'name="consent"' in rev)
check("скрипт формы отзывов отдаётся", "/static/reviews.js" in rev)
status, body, _, _ = fetch("/sitemap.xml")
check("sitemap содержит /reviews", b"/reviews" in body)

# 4. форма заявки на месте
status, body, _, _ = fetch("/order")
order_html = body.decode("utf-8", "replace")
check("форма /order на месте", 'id="order-form"' in order_html and 'id="order-form-toggle"' in order_html)
check("скрипт формы отдаётся", "/static/order.js" in order_html)

# 5. статика
status, body, ms, _ = fetch("/static/style.css")
check("CSS отдаётся", status == 200 and len(body) > 10000, f"{status}, {len(body)} байт, {ms} c")
status, body, _, _ = fetch("/static/order.js")
check("JS формы отдаётся", status == 200 and len(body) > 1000, f"{status}, {len(body)} байт")

# 6. sitemap и robots
status, _, _, _ = fetch("/sitemap.xml")
check("sitemap.xml 200", status == 200, str(status))

# 7. заявка (только по флагу, чтобы не мусорить в базе заказчика)
if DO_POST:
    payload = urllib.parse.urlencode({
        "name": "Smoke Deploy", "contact": "smoke@example.com",
        "topic": "Сайт для СТО", "message": "проверка после деплоя", "consent": "1"}).encode("utf-8")
    status, body, ms, _ = fetch("/api/order", data=payload)
    try:
        answer = json.loads(body.decode("utf-8"))
    except Exception:
        answer = {}
    check("заявка принимается и пишется в базу",
          status == 200 and answer.get("ok") is True and answer.get("id"), f"{status} {answer}")

failed = [r for r in results if not r[1]]
print(f"адрес: {BASE}")
print(f"проверок: {len(results)}, провалов: {len(failed)}\n")
for name, ok, extra in results:
    print(f"{'OK  ' if ok else 'FAIL'} {name}" + (f"  :: {extra}" if extra else ""))
print("\nИТОГ:", "ПРОЙДЕНО" if not failed else f"ПРОВАЛОВ {len(failed)}")
sys.exit(0 if not failed else 1)
