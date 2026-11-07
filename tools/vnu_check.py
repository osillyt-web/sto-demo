"""Проверка HTML официальным валидатором W3C (Nu HTML Checker) БЕЗ сети.

Используется локальная копия того же движка, что стоит на validator.w3.org:
файл vnu.jar (сборка из github.com/validator/validator) + любая Java 17+.
Плюс: нет лимита частоты и работает без интернета.

Запуск:
    python tools/vnu_check.py
Переменные:
    JAVA     путь к java.exe (по умолчанию берётся JBR от Android Studio)
    VNU_JAR  путь к vnu.jar (по умолчанию %LOCALAPPDATA%/hermes/cache/scratch/vnu.jar)
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
JAVA = os.environ.get("JAVA") or r"C:\Program Files\Android\Android Studio\jbr\bin\java.exe"
# сначала свой vnu.jar рядом со скриптом (он не чистится), потом временная папка
_LOCAL_JAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vnu.jar")
VNU_JAR = os.environ.get("VNU_JAR") or (
    _LOCAL_JAR if os.path.exists(_LOCAL_JAR)
    else os.path.expandvars(r"%LOCALAPPDATA%\hermes\cache\scratch\vnu.jar"))


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "check"}), timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace")


def main():
    if not os.path.exists(JAVA):
        sys.exit(f"не найдена Java: {JAVA} (укажите переменную JAVA)")
    if not os.path.exists(VNU_JAR):
        sys.exit(f"не найден vnu.jar: {VNU_JAR}")

    sm = fetch(BASE + "/sitemap.xml")
    paths = [(u.split(BASE)[-1] or "/") for u in re.findall(r"<loc>(.*?)</loc>", sm)]
    paths += ["/admin/login", "/nope"]

    tmp = tempfile.mkdtemp(prefix="vnu_")
    files = {}
    for i, p in enumerate(paths):
        name = os.path.join(tmp, f"{i:02d}" + (p.strip("/").replace("/", "_") or "home") + ".html")
        open(name, "w", encoding="utf-8").write(fetch(BASE + p))
        files[name] = p

    r = subprocess.run([JAVA, "-jar", VNU_JAR, "--format", "json", "--also-check-svg", *files.keys()],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        msgs = json.loads(r.stdout or "{}").get("messages", [])
    except json.JSONDecodeError:
        print(r.stdout[:2000]); print(r.stderr[:2000]); return 2

    by_file = {}
    for m in msgs:
        f = (m.get("url") or "").replace("file:///", "").replace("/", "\\")
        page = next((p for path, p in files.items() if os.path.normpath(path) == os.path.normpath(f)), f)
        by_file.setdefault(page, []).append(m)

    errors = warns = 0
    for p in files.values():
        ms = by_file.get(p, [])
        e = [m for m in ms if m.get("type") == "error"]
        w = [m for m in ms if m.get("subType") == "warning"]
        errors += len(e); warns += len(w)
        mark = "OK " if not e and not w else "ЕСТЬ"
        print(f"{mark} {p:26} ошибок {len(e)} | предупреждений {len(w)}")
        for m in (e + w)[:6]:
            print(f"      · {m.get('message','')[:150]}")

    out = os.path.join("tools", "vnu_report.json")
    open(out, "w", encoding="utf-8").write(json.dumps(
        {p: [{"type": m.get("type"), "message": m.get("message"), "line": m.get("lastLine")} for m in v]
         for p, v in by_file.items()}, ensure_ascii=False, indent=1))
    print(f"\nИТОГ: страниц {len(files)}, ошибок {errors}, предупреждений {warns}")
    print("отчёт:", out)
    return 0 if errors == 0 and warns == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
