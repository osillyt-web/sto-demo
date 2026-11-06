"""Кросс-движковая проверка сайта «АвтоТочка»: Chromium, Firefox, WebKit.

Запускает один и тот же набор проверок в трёх настоящих движках и снимает экраны.
Результат: строки в консоль + report.json рядом со скриптом.
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = r"C:\Users\Alex\sto_demo\shots"
PAGES = ["/", "/services", "/services/to", "/brands", "/cases", "/privacy", "/admin/login", "/nope"]

PROBE = """
() => {
  const days = document.querySelectorAll('#days .day').length;
  const times = document.querySelectorAll('#times .time').length;
  const free = document.querySelectorAll('#times .time:not([disabled])').length;
  const closed = [...document.querySelectorAll('#days .day')].filter(d => (d.textContent||'').includes('зачинено')).length;
  const freeDays = document.querySelectorAll('#days .day:not([disabled])').length;
  return {
    title: document.title,
    h1: (document.querySelector('h1')||{}).textContent?.trim().slice(0, 80) || null,
    days, times, free, closed, freeDays,
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    headerVisible: !!document.querySelector('header'),
    bookBtn: !![...document.querySelectorAll('a,button')].find(e => /Записатись/.test(e.textContent||'')),
    cssRules: (() => { try { return document.styleSheets[0].cssRules.length; } catch (e) { return 0; } })(),
    h1Weight: (() => { const h = document.querySelector('h1'); return h ? getComputedStyle(h).fontWeight : null; })(),
  };
}
"""

results = []


def check(engine, name, ok, detail=""):
    results.append({"engine": engine, "check": name, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"{'OK ' if ok else 'FAIL'} [{engine:8}] {name}" + (f" :: {detail}" if detail else ""))


def run(engine_name, launcher, shots):
    with launcher.launch() as browser:
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True,
                                  user_agent=None)
        page = ctx.new_page()
        errors, failed, bad_status = [], [], []
        aborted = []
        page.on("pageerror", lambda e: (aborted if "access control checks" in str(e) else errors)
                .append("JS: " + str(e)[:120]))
        page.on("console", lambda m: (aborted if "access control checks" in m.text else errors)
                .append(m.text[:120]) if m.type == "error" else None)
        page.on("response", lambda r: bad_status.append(f"{r.status} {r.url[:90]}")
                if r.status >= 400 and not r.url.endswith("/nope") else None)
        ABORTS = ("ERR_ABORTED", "NS_BINDING_ABORTED", "cancelled", "Canceled")
        page.on("requestfailed", lambda r: failed.append(f"{r.url[:80]} {r.failure or ''}")
                if not any(a.lower() in str(r.failure).lower() for a in ABORTS) else None)

        for path in PAGES:
            resp = page.goto(BASE + path, wait_until="load", timeout=20000)
            code = resp.status if resp else 0
            expect = 404 if path == "/nope" else 200
            check(engine_name, f"{path} → {code}", code == expect, f"ожидали {expect}")

        # чистим шум от намеренной проверки /nope (404) — дальше проверяем главную
        errors.clear(); failed.clear(); bad_status.clear(); aborted.clear()

        page.goto(BASE + "/", wait_until="load", timeout=20000)
        page.wait_for_timeout(2500)
        try:
            page.wait_for_function(
                "() => getComputedStyle(document.body).backgroundColor !== 'rgba(0, 0, 0, 0)'",
                timeout=6000)
        except Exception:
            pass
        data = page.evaluate(PROBE)
        check(engine_name, "календарь: 14 дней", data["days"] == 14, data["days"])
        check(engine_name, "часы: 10 плиток", data["times"] == 10, data["times"])
        check(engine_name, "слоты: есть свободные часы", data["free"] > 0, data["free"])
        check(engine_name, "воскресенье закрыто", data["closed"] >= 1, data["closed"])
        check(engine_name, "нет горизонтальной прокрутки",
              data["overflow"] <= 1, f"scrollW {data['scrollW']} / innerW {data['innerW']}")
        check(engine_name, "CSS загрузился (правила + жирность заголовка)",
              data["cssRules"] > 100 and str(data["h1Weight"]) in ("700", "800", "900"),
              f"правил {data['cssRules']}, h1 вес {data['h1Weight']}")
        check(engine_name, "шапка на месте", data["headerVisible"], "")
        check(engine_name, "кнопка «Записатись» есть", data["bookBtn"], "")
        check(engine_name, "ошибок JS нет", not errors, "; ".join(errors[:2]))
        if aborted:
            print(f"     (обрывы при переходе, не ошибки: {len(aborted)})")
        check(engine_name, "нет ответов 4xx/5xx", not bad_status, "; ".join(sorted(set(bad_status))[:3]))
        check(engine_name, "нет оборванных запросов", not failed, "; ".join(failed[:2]))

        # экран главной
        page.screenshot(path=os.path.join(OUT, f"90_{engine_name}_hero.png"))
        # экран блока записи
        page.evaluate("document.getElementById('book').scrollIntoView({block:'start'})")
        page.wait_for_timeout(900)
        page.evaluate("window.scrollBy(0, 420)")
        page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(OUT, f"91_{engine_name}_booking.png"))

        # прокрутить страницу до конца — проверить, что ничего не ломается внизу
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(800)
        tail = page.evaluate("() => ({overflow: document.documentElement.scrollWidth - window.innerWidth,"
                             " toTop: !!document.querySelector('.to-top')})")
        check(engine_name, "низ страницы без прокрутки вбок", tail["overflow"] <= 1, tail["overflow"])
        page.screenshot(path=os.path.join(OUT, f"92_{engine_name}_footer.png"))

        # форма: выбрать день и час, заполнить поля, проверить валидацию (без отправки)
        page.goto(BASE + "/", wait_until="load")
        page.wait_for_timeout(2200)
        def pick_day(index):
            return page.evaluate("""(i) => {
                const days = [...document.querySelectorAll('#days .day:not([disabled])')];
                if (!days.length) return {ok:false, why:'нет доступных дней'};
                const d = days[Math.min(i, days.length - 1)];
                d.click();
                return {ok:true, text: d.textContent.trim().slice(0,20), total: days.length};
            }""", index)

        def wait_times(ms=5000):
            """Ждём появления свободных часов: список приходит запросом, движки отвечают с разной скоростью.
            А если сегодняшние часы уже прошли — день считается пустым, это не дефект сайта."""
            try:
                page.wait_for_selector("#times .time:not([disabled])", timeout=ms)
                return True
            except Exception:
                return False

        picked = pick_day(0)
        have_times = wait_times()
        if not have_times:
            # берём следующий день: у сегодняшнего все часы могли уже пройти
            picked = pick_day(1)
            have_times = wait_times()
        times = page.evaluate("""() => {
            const t = [...document.querySelectorAll('#times .time:not([disabled])')];
            if (!t.length) return {ok:false, why:'нет свободных часов'};
            t[0].click();
            return {ok:true, text: t[0].textContent.trim().slice(0,20), total: t.length};
        }""") if have_times else {"ok": False, "why": "свободные часы не появились"}
        page.wait_for_timeout(400)
        hidden = page.evaluate("() => ({date: document.getElementById('slot-date').value,"
                              " time: document.getElementById('slot-time').value})")
        check(engine_name, "день выбирается кликом", picked.get("ok"), picked)
        check(engine_name, "час выбирается кликом", times.get("ok"), times)
        check(engine_name, "выбор попал в форму", bool(hidden["date"]) and bool(hidden["time"]), hidden)
        page.screenshot(path=os.path.join(OUT, f"93_{engine_name}_slot_selected.png"))

        # валидация: отправить пустую форму — должны появиться встроенные браузерные сообщения
        before_url = page.url
        page.evaluate("""() => {
            const f = document.querySelector('#lead-form');
            const btn = f.querySelector('button[type=submit], button:not([type])');
            btn.click();
        }""")
        page.wait_for_timeout(1200)
        # собираем текст формы на стороне Python — без JS-строк с экранированием
        try:
            form_text = page.locator("#lead-form").inner_text(timeout=4000)
        except Exception as exc:
            form_text = ""
        marks = ("заповн", "вкаж", "невірн", "помилк", "обов", "потрібн")
        msg = next((ln.strip() for ln in form_text.splitlines()
                    if any(w in ln.lower() for w in marks)), None)
        after_url = page.url
        check(engine_name, "пустая форма не уходит на сервер", after_url == before_url, after_url[-40:])
        check(engine_name, "пустая форма объясняет, что не так", bool(msg), (msg or "")[:90])

        ctx.close()


def main():
    with sync_playwright() as p:
        run("chromium", p.chromium, None)
        run("firefox", p.firefox, None)
        run("webkit", p.webkit, None)

    total = len(results)
    bad = [r for r in results if not r["ok"]]
    print("\n================ ИТОГ ================")
    for eng in ("chromium", "firefox", "webkit"):
        rows = [r for r in results if r["engine"] == eng]
        print(f"{eng:9}: {sum(1 for r in rows if r['ok'])}/{len(rows)} пройдено")
    print(f"всего проверок: {total}, провалов: {len(bad)}")
    for r in bad:
        print(f"  ПРОВАЛ [{r['engine']}] {r['check']} :: {r['detail']}")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print("отчёт:", path)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
