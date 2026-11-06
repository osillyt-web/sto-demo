# -*- coding: utf-8 -*-
"""
Генераторы SEO-страниц: /services, /services/<slug>, /brands, /brands/<slug>.
Зависимости (esc, tpl, SITE_URL, contact_settings) передаются из server.py
через configure(), чтобы не было циклического импорта.
"""

import re
import json
import datetime

from content import SERVICES, BRANDS

_esc = str
_site = ""
_tpl = None
_contacts = None


def configure(esc, site_url, tpl, contact_settings):
    global _esc, _site, _tpl, _contacts
    _esc, _site, _tpl, _contacts = esc, site_url, tpl, contact_settings


PG_CLASSES = [("Стандарт", "легкові до 2,0 л"), ("Комфорт", "кросовери, 2,0–3,0 л"),
              ("Преміум", "преміум-марки, позашляховики")]


def render_page(conn, title, desc, path, body, jsonld, og_image="hero"):
    contacts = _contacts(conn)
    return (_tpl("page.html")
            .replace("{{HEAD_TITLE}}", _esc(title))
            .replace("{{HEAD_DESC}}", _esc(desc))
            .replace("{{CANONICAL}}", _esc(_site + path))
            .replace("{{SITE_URL}}", _esc(_site))
            .replace("{{OG_IMAGE}}", _esc(og_image))
            .replace("{{BODY}}", body)
            .replace("{{JSONLD}}", json.dumps(jsonld, ensure_ascii=False))
            .replace("{{YEAR}}", str(datetime.date.today().year))
            .replace("{{C_PHONE}}", _esc(contacts["phone"]))
            .replace("{{C_PHONE_RAW}}", _esc(contacts["phone_raw"]))
            .replace("{{C_ADDRESS}}", _esc(contacts["address"]))
            .replace("{{C_HOURS}}", _esc(contacts["hours"])))


def crumbs(items):
    parts = []
    for i, (label, href) in enumerate(items):
        if href and i < len(items) - 1:
            parts.append('<a href="%s">%s</a>' % (_esc(href), _esc(label)))
        else:
            parts.append('<span aria-current="page">%s</span>' % _esc(label))
    return ('<nav class="crumbs" aria-label="Навігаційний ланцюжок">'
            + '<span class="sep">/</span>'.join(parts) + '</nav>')


def _phone_raw(conn):
    return _esc(_contacts(conn)["phone_raw"])


# ------------------------------------------------------------------ /services

def build_services_index(conn):
    cards = []
    for slug, sv in SERVICES.items():
        cards.append('''<a class="svc-card" href="/services/%s">
          <span class="svc-name">%s</span>
          <span class="svc-short">%s</span>
          <span class="svc-meta">%s · від %s</span>
          <span class="svc-go">Детальніше →</span></a>''' % (
            slug, _esc(sv["title"]), _esc(sv["short"]),
            _esc(sv["duration"]), _esc(sv["price_rows"][0][1])))

    body = '''
<section class="sec"><div class="wrap">
  %s
  <h1 class="page-h1">Послуги сервісу</h1>
  <p class="page-lead">Шість напрямків, кожен — з цінами за класом авто і відповіддю на питання,
  які виникають до запису. Не знаєте, що потрібно — почніть з діагностики.</p>
  <div class="svc-grid">%s</div>
  <div class="cta-band">
    <div><b>Не впевнені, яка послуга потрібна?</b>
      <p class="mini">Опишіть симптом — підкажемо, з чого почати, без візиту.</p></div>
    <div class="cta-actions">
      <a class="btn btn-accent" href="/#book">Записатись</a>
      <a class="btn btn-ghost" href="tel:%s">Подзвонити</a>
    </div>
  </div>
</div></section>''' % (crumbs([("Головна", "/"), ("Послуги", None)]), "".join(cards), _phone_raw(conn))

    jsonld = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": "Послуги СТО АвтоТочка", "url": _site + "/services"}
    return ("Послуги СТО у Києві — діагностика, ТО, шиномонтаж, кузовний ремонт, полірування, хімчистка",
            "Шість послуг автосервісу з цінами за класом авто: діагностика, технічне обслуговування, "
            "шиномонтаж, кузовний ремонт, полірування кузова, хімчистка салону. Онлайн-запис.",
            "/services", body, jsonld, "engine")


def build_service_page(conn, slug):
    sv = SERVICES[slug]
    price_rows = "".join(
        "<tr><td>%s</td>%s</tr>" % (_esc(name), "".join('<td class="num">%s</td>' % _esc(v) for v in vals))
        for name, *vals in sv["price_rows"])
    includes = "".join("<li>%s</li>" % _esc(x) for x in sv["includes"])
    not_included = "".join("<li>%s</li>" % _esc(x) for x in sv["not_included"])
    faq_html = "".join(
        '<details class="faq-item"><summary>%s</summary><div class="faq-a">%s</div></details>'
        % (_esc(q), _esc(a)) for q, a in sv["faq"])
    others = "".join(
        '<a class="svc-mini" href="/services/%s"><b>%s</b><span>%s</span></a>'
        % (k, _esc(v["title"]), _esc(v["duration"]))
        for k, v in SERVICES.items() if k != slug)
    head_cells = "".join('<th class="num">%s<small>%s</small></th>' % (c[0], c[1]) for c in PG_CLASSES)

    body = '''
<section class="sec"><div class="wrap">
  %s
  <div class="svc-top">
    <div class="svc-main">
      <h1 class="page-h1">%s</h1>
      <p class="page-lead">%s</p>
      <div class="svc-chips">
        <span class="chip-t">%s</span>
        <span class="chip-t">Гарантія 12 місяців</span>
        <span class="chip-t">Ціна фіксується до робіт</span>
      </div>
      <div class="cta-actions svc-actions">
        <a class="btn btn-accent" href="/#book">Записатись</a>
        <a class="btn btn-ghost" href="tel:%s">Подзвонити</a>
      </div>
    </div>
    <figure class="svc-photo">
      <img src="/static/img/%s.webp" width="560" height="420"
           alt="%s — майстерня АвтоТочка" loading="lazy">
    </figure>
  </div>

  <h2 class="h2">Ціни</h2>
  <div class="table-wrap" role="region" aria-label="Тарифи" tabindex="0">
    <table class="ptable">
      <thead><tr><th>Робота</th>%s</tr></thead>
      <tbody>%s</tbody>
    </table>
  </div>
  <p class="mini">Ціна за роботу без вартості запчастин і розхідників. Точну суму називаємо після
  огляду — до початку робіт, письмово в чат.</p>

  <div class="two-col svc-cols">
    <div class="col">
      <h2 class="h2">Що входить</h2>
      <ul class="ticks">%s</ul>
    </div>
    <div class="col">
      <h2 class="h2">Що не входить</h2>
      <ul class="crosses">%s</ul>
      <div class="why"><b>Чому так</b><p>%s</p></div>
    </div>
  </div>

  <h2 class="h2">Часті питання</h2>
  <div class="faq">%s</div>

  <h2 class="h2">Інші послуги</h2>
  <div class="svc-mini-grid">%s</div>
</div></section>''' % (
        crumbs([("Головна", "/"), ("Послуги", "/services"), (sv["title"], None)]),
        _esc(sv["title"]), _esc(sv["lead"]), _esc(sv["duration"]), _phone_raw(conn),
        _esc(sv["photo"]), _esc(sv["title"]), head_cells, price_rows,
        includes, not_included, _esc(sv["why"]), faq_html, others)

    price_digits = re.sub(r"\D", "", sv["price_rows"][0][1]) or "0"
    ld = [
        {"@context": "https://schema.org", "@type": "Service", "name": sv["title"],
         "description": sv["short"], "serviceType": sv["title"],
         "url": "%s/services/%s" % (_site, slug),
         "provider": {"@type": "AutoRepair", "name": "АвтоТочка",
                      "telephone": _contacts(conn)["phone_raw"]},
         "areaServed": {"@type": "City", "name": "Київ"},
         "offers": {"@type": "Offer", "priceCurrency": "UAH", "price": price_digits}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Головна", "item": _site + "/"},
             {"@type": "ListItem", "position": 2, "name": "Послуги", "item": _site + "/services"},
             {"@type": "ListItem", "position": 3, "name": sv["title"],
              "item": "%s/services/%s" % (_site, slug)}]},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in sv["faq"]]},
    ]
    title = "%s у Києві — ціни, що входить, онлайн-запис | АвтоТочка" % sv["title"]
    desc = "%s. %s. Ціна фіксується до початку робіт, гарантія 12 місяців. Запис онлайн на сайті." % (
        sv["short"], sv["duration"])
    return title, desc, "/services/" + slug, body, ld, sv["photo"]


# -------------------------------------------------------------------- /brands

def build_brands_index(conn):
    cards = "".join(
        '<a class="svc-card" href="/brands/%s"><span class="svc-name">%s</span>'
        '<span class="svc-short">%s</span><span class="svc-go">Детальніше →</span></a>'
        % (slug, _esc(b["title"]), _esc(", ".join(b["models"][:4]))) for slug, b in BRANDS.items())
    body = '''
<section class="sec"><div class="wrap">
  %s
  <h1 class="page-h1">Марки авто, з якими працюємо</h1>
  <p class="page-lead">Обслуговуємо європейські, японські та корейські марки. Нижче — те, що
  питають найчастіше: чи знайомий сервіс з вашою моделлю і на що дивитись у першу чергу.</p>
  <div class="svc-grid">%s</div>
  <p class="mini">Немає вашої марки у списку? Зателефонуйте — у 9 з 10 випадків беремось.</p>
</div></section>''' % (crumbs([("Головна", "/"), ("Марки", None)]), cards)
    return ("Марки авто, з якими працюємо — ремонт і обслуговування у Києві | АвтоТочка",
            "Volkswagen, Toyota, Skoda, BMW, Renault, Nissan — обслуговування і ремонт у Києві. "
            "Онлайн-запис, фіксована ціна до робіт, гарантія 12 місяців.",
            "/brands", body,
            {"@context": "https://schema.org", "@type": "CollectionPage",
             "name": "Марки авто", "url": _site + "/brands"}, "hero")


def build_brand_page(conn, slug):
    b = BRANDS[slug]
    models = "".join('<span class="model-chip">%s</span>' % _esc(x) for x in b["models"])
    svc_links = "".join(
        '<a class="svc-mini" href="/services/%s"><b>%s</b><span>від %s</span></a>'
        % (k, _esc(v["title"]), _esc(v["price_rows"][0][1])) for k, v in SERVICES.items())
    body = '''
<section class="sec"><div class="wrap">
  %s
  <div class="svc-top">
    <div class="svc-main">
      <h1 class="page-h1">%s — ремонт і обслуговування у Києві</h1>
      <p class="page-lead">%s</p>
      <div class="brand-models">%s</div>
      <div class="cta-actions svc-actions">
        <a class="btn btn-accent" href="/#book">Записатись на сервіс</a>
        <a class="btn btn-ghost" href="tel:%s">Подзвонити</a>
      </div>
    </div>
    <figure class="svc-photo">
      <img src="/static/img/%s.webp" width="560" height="420"
           alt="%s у сервісі АвтоТочка" loading="lazy">
    </figure>
  </div>
  <h2 class="h2">Що робимо з %s</h2>
  <div class="svc-mini-grid">%s</div>
  <div class="why"><b>Гарантія і чесність</b><p>Працюємо за регламентом виробника, ставимо відмітку
  в сервісній книжці, зняті деталі показуємо. Гарантія на роботи — 12 місяців. Якщо ремонт
  не потрібен — так і скажемо.</p></div>
</div></section>''' % (
        crumbs([("Головна", "/"), ("Марки", "/brands"), (b["title"], None)]),
        _esc(b["title"]), _esc(b["note"]), models, _phone_raw(conn),
        _esc(b["photo"]), _esc(b["title"]), _esc(b["title"]), svc_links)

    ld = [
        {"@context": "https://schema.org", "@type": "Service",
         "name": "Ремонт %s у Києві" % b["title"], "description": b["note"],
         "serviceType": "Автосервіс", "url": "%s/brands/%s" % (_site, slug),
         "provider": {"@type": "AutoRepair", "name": "АвтоТочка"},
         "areaServed": {"@type": "City", "name": "Київ"}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Головна", "item": _site + "/"},
             {"@type": "ListItem", "position": 2, "name": "Марки", "item": _site + "/brands"},
             {"@type": "ListItem", "position": 3, "name": b["title"],
              "item": "%s/brands/%s" % (_site, slug)}]},
    ]
    title = "Ремонт %s у Києві — діагностика, ТО, кузовний ремонт | АвтоТочка" % b["title"]
    desc = "%s: %s. Діагностика, ТО, шиномонтаж, кузовний ремонт, полірування. " \
           "Фіксована ціна до робіт, гарантія 12 місяців, онлайн-запис." % (
               b["title"], ", ".join(b["models"][:5]))
    return title, desc, "/brands/" + slug, body, ld, b["photo"]
