"""Локальная проверка WSGI-обёртки через wsgiref (как на хостинге)."""
import os
import sys
import threading
import time
import urllib.request
import urllib.error
from wsgiref.simple_server import make_server, WSGIRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import wsgi  # noqa: E402


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


def run():
    srv = make_server("127.0.0.1", 8765, wsgi.application, handler_class=Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def get(path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765" + path, timeout=15) as r:
            return r.status, r.read(400)
    except urllib.error.HTTPError as e:
        return e.code, e.read(200)
    except Exception as e:
        return None, str(e).encode()


def post(path, payload):
    data = payload.encode()
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(400)
    except urllib.error.HTTPError as e:
        return e.code, e.read(300)
    except Exception as e:
        return None, str(e).encode()


srv = run()
time.sleep(1.5)
ok = 0
fail = 0
for path in ["/", "/order", "/pricing", "/api/health", "/cases", "/privacy", "/sitemap.xml"]:
    code, body = get(path)
    mark = "OK " if code == 200 else "FAIL"
    if code == 200:
        ok += 1
    else:
        fail += 1
    print(f"{mark} GET {path} -> {code} {body[:80]!r}")

code, body = post("/api/order", '{"name":"Тест WSGI","contact":"+380501112233","topic":"Сайт для СТО","text":"проверка обёртки","consent":"1"}')
mark = "OK " if code == 200 else "FAIL"
if code == 200:
    ok += 1
else:
    fail += 1
print(f"{mark} POST /api/order -> {code} {body[:160]!r}")

code, body = get("/admin")
print(f"{'OK ' if code in (200, 302) else 'FAIL'} GET /admin -> {code}")

srv.shutdown()
print(f"\nИТОГ: ok={ok} fail={fail}")
sys.exit(0 if fail == 0 else 1)