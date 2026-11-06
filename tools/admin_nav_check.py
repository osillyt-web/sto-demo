"""Проверка навигации в админ-панели — на временном пароле.

Пароль владельца не трогаем: файл auth.json копируется, на время проверки
ставится admin123 (его ждут и автотесты), в конце файл возвращается байт-в-байт.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = r"C:\Users\Alex\sto_demo"
AUTH = os.path.join(REPO, "data", "auth.json")
BACKUP = AUTH + ".owner-backup"
sys.path.insert(0, REPO)

from playwright.sync_api import sync_playwright  # noqa: E402

SECTIONS = ["leads", "load", "contacts", "services", "analytics", "tg", "ops", "security"]
problems = []


def check(label, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {label}" + (f" :: {detail}" if detail else ""))
    if not ok:
        problems.append(f"{label} :: {detail}")


def run_engine(name, browser_type, width, height, mobile=False):
    browser = browser_type.launch()
    # bypass_csp: сайт отдаёт строгий CSP script-src 'self'; axe подключаем только на время проверки
    ctx = browser.new_context(viewport={"width": width, "height": height}, bypass_csp=True,
                             is_mobile=mobile, has_touch=mobile,
                             device_scale_factor=2 if mobile else 1)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:120]))
    page.goto("http://127.0.0.1:8000/admin/login", wait_until="load")
    page.fill("input[name=password]", "admin123")
    page.click("button[type=submit]")
    page.wait_for_url("**/admin", timeout=15000)
    page.wait_for_timeout(1800)

    # доступность самой панели: тот же движок axe, что внутри Lighthouse
    axe_path = os.path.join(REPO, "tools", "axe.min.js")
    if os.path.exists(axe_path):
        page.add_script_tag(content=open(axe_path, encoding="utf-8").read())
        axe_res = page.evaluate("""async () => {
            const r = await axe.run(document, {runOnly: {type: 'tag',
                values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']}});
            return r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length,
                                           target: v.nodes[0] ? v.nodes[0].target : null}));
        }""")
        tag0 = f"[{name} {width}px]"
        check(f"{tag0} панель: нарушений доступности нет (axe)", not axe_res, axe_res[:3])

    info = page.evaluate("""() => {
        const links = [...document.querySelectorAll('.adm-nav-list a')];
        return {
            count: links.length,
            hrefs: links.map(a => a.getAttribute('href')),
            current: (document.querySelector('.adm-nav-list a[aria-current]') || {}).textContent?.trim() || null,
            overflow: document.documentElement.scrollWidth - window.innerWidth,
            pageH: document.documentElement.scrollHeight,
            navTop: Math.round(document.querySelector('.adm-nav').getBoundingClientRect().top),
            navW: Math.round(document.querySelector('.adm-nav').getBoundingClientRect().width),
        };
    }""")
    page.screenshot(path=os.path.join(REPO, "shots", f"95_admin_nav_top_{name}_{width}.png"))
    tag = f"[{name} {width}px]"
    check(f"{tag} ссылок в навигации 8", info["count"] == 8, info["count"])
    check(f"{tag} все ссылки ведут на существующие разделы",
          all(h == "#" + s for h, s in zip(info["hrefs"], SECTIONS)), info["hrefs"])
    check(f"{tag} нет горизонтальной прокрутки", info["overflow"] <= 1, info["overflow"])
    check(f"{tag} активный раздел отмечен сразу", bool(info["current"]), info["current"])
    if not mobile:
        check(f"{tag} навигация слева от контента", info["navTop"] < 400 and 180 <= info["navW"] <= 300,
              f"top {info['navTop']}, ширина {info['navW']}")

    for hid in SECTIONS:
        page.click(f'.adm-nav-list a[href="#{hid}"]')
        page.wait_for_timeout(650)
        st = page.evaluate("""(id) => {
            const el = document.getElementById(id), h = el.querySelector('h2');
            const r = el.getBoundingClientRect();
            const nav = document.querySelector('.adm-nav');
            return {
                top: Math.round(r.top),
                focused: document.activeElement === h,
                current: (document.querySelector('.adm-nav-list a[aria-current]')||{}).getAttribute?.('href') || null,
                hash: location.hash,
                docW: document.documentElement.scrollWidth,
                winW: window.innerWidth,
                atBottom: window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4,
            };
        }""", hid)
        # последний раздел физически не может встать к верху окна — там уже край страницы
        top_ok = (0 <= st["top"] <= 200) or (st["atBottom"] and 0 <= st["top"] <= 600)
        ok = (top_ok and st["current"] == "#" + hid
              and st["hash"] == "#" + hid and st["docW"] - st["winW"] <= 1)
        check(f"{tag} переход к «{hid}»", ok, f"top={st['top']} current={st['current']} hash={st['hash']}")

    # клавиатура: Tab по навигации и Enter
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(300)
    page.focus('.adm-nav-list a[href="#security"]')
    page.keyboard.press("Enter")
    page.wait_for_timeout(700)
    kb = page.evaluate("""() => ({hash: location.hash,
        focusedTag: document.activeElement.tagName,
        focusedText: (document.activeElement.textContent||'').trim().slice(0,30),
        top: Math.round(document.getElementById('security').getBoundingClientRect().top)})""")
    kb_ok = kb["hash"] == "#security" and kb["focusedTag"] == "H2" and 0 <= kb["top"] <= 600
    check(f"{tag} Enter на ссылке переводит в раздел и ставит фокус", kb_ok, kb)

    check(f"{tag} ошибок JS нет", not errors, "; ".join(errors[:2]))
    page.screenshot(path=os.path.join(REPO, "shots", f"95_admin_nav_{name}_{width}.png"), full_page=False)
    ctx.close()
    browser.close()


def main():
    shutil.copy2(AUTH, BACKUP)
    owner_hash = open(BACKUP, "rb").read()
    try:
        import server
        server.set_password("admin123")

        with sync_playwright() as p:
            run_engine("chromium", p.chromium, 1440, 900)
            run_engine("firefox", p.firefox, 1440, 900)
            run_engine("webkit", p.webkit, 1440, 900)
            run_engine("mobile", p.chromium, 390, 844, mobile=True)

        print("\n--- основные автотесты ---")
        r = subprocess.run([sys.executable, "test_flow.py"], cwd=REPO, capture_output=True, text=True)
        tail = [ln for ln in r.stdout.splitlines() if ln.startswith("ИТОГ") or ln.startswith("FAIL")]
        check("автотесты проекта зелёные", r.returncode == 0, tail[-1] if tail else r.stdout[-200:])
    finally:
        shutil.copy2(BACKUP, AUTH)
        os.remove(BACKUP)
        restored = open(AUTH, "rb").read()
        same = hashlib.sha256(restored).hexdigest() == hashlib.sha256(owner_hash).hexdigest()
        print(f"\nпароль владельца восстановлен байт-в-байт: {'да' if same else 'НЕТ!'}")
        if not same:
            problems.append("пароль владельца не восстановился")

    print("\n================ ИТОГ ================")
    print(f"проверок с проблемой: {len(problems)}")
    for p in problems:
        print("  ", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
