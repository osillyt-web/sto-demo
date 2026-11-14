"""WSGI-обёртка для server.py.

server.py написан как самостоятельный HTTP-сервер на BaseHTTPRequestHandler
(ThreadingHTTPServer). Хостинг alwaysdata отдаёт Python-сайты только через WSGI,
поэтому здесь создаётся тонкая прослойка: WSGI-запрос превращается в вызов
того же обработчика Handler, а его вывод — обратно в WSGI-ответ.

Ничего из бизнес-логики не дублируется: вся маршрутизация остаётся в server.py.
"""
import io
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import server as srv  # noqa: E402

_ready = False


def _prepare():
    """Однократная инициализация базы и пароля (в server.py это делает __main__)."""
    global _ready
    if _ready:
        return
    srv.seed()
    srv.load_auth()
    _ready = True


class _Bridge(srv.Handler):
    """Обработчик, у которого ввод-вывод ведёт не сокет, а WSGI."""

    def __init__(self, environ):
        self.environ = environ
        self.command = (environ.get("REQUEST_METHOD") or "GET").upper()
        query = environ.get("QUERY_STRING") or ""
        self.path = (environ.get("PATH_INFO") or "/") + (("?" + query) if query else "")
        self.request_version = environ.get("SERVER_PROTOCOL") or "HTTP/1.1"
        self.requestline = "%s %s %s" % (self.command, self.path, self.request_version)

        self.headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                self.headers[key[5:].replace("_", "-")] = value
        if environ.get("CONTENT_TYPE"):
            self.headers["Content-Type"] = environ["CONTENT_TYPE"]
        if environ.get("CONTENT_LENGTH"):
            self.headers["Content-Length"] = environ["CONTENT_LENGTH"]

        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        body = environ["wsgi.input"].read(length) if length > 0 else b""
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.client_address = (environ.get("REMOTE_ADDR") or "127.0.0.1", 0)
        self.server = srv.Server
        self.status = 200
        self.out_headers = []

    # --- интерфейс BaseHTTPRequestHandler, который вызывает Handler.send()
    def send_response(self, code, message=None):
        self.status = code
        self.out_headers = []

    def send_response_only(self, code, message=None):
        self.status = code

    def send_header(self, keyword, value):
        self.out_headers.append((keyword, str(value)))

    def end_headers(self):
        pass

    def log_message(self, fmt, *args):
        pass

    def log_error(self, fmt, *args):
        pass


def application(environ, start_response):
    """Точка входа WSGI: alwaysdata → это приложение."""
    _prepare()
    bridge = _Bridge(environ)
    method = getattr(bridge, "do_" + bridge.command, None)
    try:
        if method is not None:
            method()
        else:
            bridge.send(405, "Method Not Allowed")
    except Exception:
        traceback.print_exc()
        try:
            bridge.send(500, "Internal Server Error")
        except Exception:
            bridge.wfile = io.BytesIO()
            bridge.status = 500
            bridge.out_headers = [("Content-Type", "text/plain; charset=utf-8")]

    phrase = BaseHTTPRequestHandler.responses.get(bridge.status, ("OK",))[0]
    headers = [(k, v) for (k, v) in bridge.out_headers
               if k.lower() not in ("connection", "transfer-encoding", "content-length")]
    body = bridge.wfile.getvalue()
    headers.append(("Content-Length", str(len(body))))
    start_response("%d %s" % (bridge.status, phrase), headers)
    return [body]