"""Проверка HTML по официальному валидатору W3C (Nu HTML Checker) через его API.

Зачем: W3C Nu проверяет разметку на соответствие стандарту HTML (WHATWG Living Standard).
Валидатор доступен только по сети и ограничивает частоту запросов, поэтому здесь
есть пауза между запросами и повтор при ответе 429.

Запуск (сервер сайта должен быть поднят):
    python tools/w3c_check.py                # все адреса из sitemap.xml + вход в админку
    python tools/w3c_check.py --public URL   # проверять живой адрес, а не локальный
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

LOCAL = "http://127.0.0.1:8000"
API = "https://validator.w3.org/nu/?out=json"
PAUSE = 8          # секунд между запросами: у сервиса жёсткий лимит частоты
RETRIES = 4


def fetch(url, timeout=40):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace")


def check(html):
    """Отдаём страницу валидатору как есть (POST) и ждём вердикт."""
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(API, data=html.encode("utf-8"),
                                        headers={"Content-Type": "text/html; charset=utf-8",
                                                 "User-Agent": "sto-demo-check"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8")).get("messages", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(5)
    raise RuntimeError("валидатор не ответил после повторов")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", help="публичный адрес сайта (например, туннель)")
    args = ap.parse_args()
    base = (args.public or LOCAL).rstrip("/")
    src = args.public or LOCAL

    paths = [(u.split(base)[-1] or "/") for u in re.findall(r"<loc>(.*?)</loc>", fetch(src + "/sitemap.xml"))]
    paths += ["/admin/login", "/nope"]

    report, errors_total, warns_total = [], 0, 0
    for i, p in enumerate(paths, 1):
        html = fetch(base + p)
        msgs = check(html)
        errs = [m for m in msgs if m.get("type") == "error"]
        warns = [m for m in msgs if m.get("subType") == "warning"]
        errors_total += len(errs)
        warns_total += len(warns)
        report.append({"page": p, "errors": [m.get("message") for m in errs],
                       "warnings": [m.get("message") for m in warns]})
        mark = "OK " if not errs and not warns else "ЕСТЬ"
        print(f"{mark} [{i:2}/{len(paths)}] {p:26} ошибок {len(errs)} | предупреждений {len(warns)}", flush=True)
        for m in (errs + warns)[:6]:
            print(f"        · {m.get('message','')[:150]}", flush=True)
        if i < len(paths):
            time.sleep(PAUSE)

    out = "tools/w3c_report.json"
    open(out, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nИТОГ: страниц {len(paths)}, ошибок {errors_total}, предупреждений {warns_total}")
    print("отчёт:", out)
    return 0 if errors_total == 0 and warns_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
