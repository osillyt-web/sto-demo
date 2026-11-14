/* АвтоКрапка — интерактив главной страницы (без зависимостей) */
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const money = (n) => Math.round(n / 10) * 10;

  /* ---------- источник заявки (UTM / переход) ---------- */
  const src = (() => {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem("at_src") || "null"); } catch (e) {}
    if (saved && typeof saved === "object") return saved;
    const q = new URLSearchParams(location.search);
    const get = k => (q.get(k) || "").slice(0, 60);
    let ref = "";
    try { ref = document.referrer ? new URL(document.referrer).hostname.replace(/^www\./, "") : ""; } catch (e) {}
    if (ref === location.hostname) ref = "";
    const data = { utm_source: get("utm_source"), utm_medium: get("utm_medium"),
                   utm_campaign: get("utm_campaign"), referrer: ref };
    try { sessionStorage.setItem("at_src", JSON.stringify(data)); } catch (e) {}
    return data;
  })();
  const srcFields = () => ({ utm_source: src.utm_source, utm_medium: src.utm_medium,
                             utm_campaign: src.utm_campaign, referrer: src.referrer });

  /* маска телефона: последние 9 цифр как национальный номер */
  function maskPhone(input) {
    let d = input.value.replace(/\D/g, "");
    if (d.length > 12) d = d.slice(-12);
    let out = d;
    if (d.length >= 9) {
      const nat = d.slice(-9);
      out = `+380 ${nat.slice(0, 2)} ${nat.slice(2, 5)} ${nat.slice(5, 7)} ${nat.slice(7, 9)}`;
    }
    if (input.value !== out) {
      input.value = out;
      try { input.setSelectionRange(out.length, out.length); } catch (e) {}
    }
  }

  /* ---------- мобильное меню ---------- */
  const burger = $("#burger");
  const menu = $("#mobile-menu");
  if (burger && menu) {
    burger.addEventListener("click", () => {
      const open = menu.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });
    $$("a", menu).forEach(a => a.addEventListener("click", () => {
      menu.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
    }));
  }

  /* ---------- появление блоков ---------- */
  const items = $$("[data-reveal]");
  if ("IntersectionObserver" in window && items.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add("shown"); io.unobserve(e.target); }
      });
    }, { threshold: 0, rootMargin: "0px 0px 240px 0px" });
    items.forEach((el, i) => { el.style.transitionDelay = `${Math.min(i, 6) * 45}ms`; io.observe(el); });

    // Страховка. При быстрой прокрутке пальцем (флик) наблюдатель может пропустить
    // блок: он пролетает мимо зоны срабатывания и остаётся прозрачным — человек
    // видит заголовок и пустое место. Поэтому на каждый кадр прокрутки показываем
    // всё, что уже поднялось выше нижней границы окна.
    let raf = 0;
    const sweep = () => {
      raf = 0;
      items.forEach(el => {
        if (!el.classList.contains("shown") && el.getBoundingClientRect().top < window.innerHeight) {
          el.classList.add("shown");
          io.unobserve(el);
        }
      });
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(sweep); };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    window.addEventListener("load", () => setTimeout(sweep, 300));
    setTimeout(sweep, 900);
  } else {
    items.forEach(el => el.classList.add("shown"));
  }

  /* ---------- калькулятор ---------- */
  const calcForm = $("#calc-form");
  const classRadios = $$('input[name="car_class"]');
  const priceEl = $("#calc-price");
  const hintEl = $("#calc-hint");
  const estimateField = $("#estimate-field");
  const formService = $("#form-service");
  let calcData = null;

  function currentClassMult() {
    const picked = document.querySelector('input[name="car_class"]:checked');
    return picked ? parseFloat(picked.dataset.mult || "1") : 1;
  }

  function plural(n) {
    const ten = n % 10, hundred = n % 100;
    if (ten === 1 && hundred !== 11) return `${n} послуга`;
    if (ten >= 2 && ten <= 4 && (hundred < 12 || hundred > 14)) return `${n} послуги`;
    return `${n} послуг`;
  }

  function recalc() {
    const checked = $$('input[name="svc"]:checked', calcForm || document);
    if (!checked.length) {
      priceEl.textContent = "—";
      hintEl.textContent = "Оберіть хоча б одну послугу";
      if (estimateField) estimateField.value = "";
      const estLine0 = $("#est-line");
      if (estLine0) estLine0.hidden = true;
      return;
    }
    const mult = currentClassMult();
    const sum = checked.reduce((acc, el) => acc + (parseInt(el.dataset.base, 10) || 0), 0);
    const from = money(sum * mult * 0.9);
    const to = money(sum * mult * 1.15);
    priceEl.textContent = `від ${from.toLocaleString("uk-UA")} до ${to.toLocaleString("uk-UA")} ₴`;
    hintEl.textContent = `${plural(checked.length)} · коефіцієнт класу ${mult.toFixed(2)}`;
    if (estimateField) estimateField.value = `${from}–${to} ₴`;
    const estLine = $("#est-line"), estSum = $("#est-sum");
    if (estLine && estSum) {
      estSum.textContent = `від ${from.toLocaleString("uk-UA")} до ${to.toLocaleString("uk-UA")} ₴`;
      estLine.hidden = false;
    }
  }

  if (calcForm) {
    fetch("/api/calc").then(r => r.json()).then(data => {
      calcData = data;
      recalc();
    }).catch(() => { hintEl.textContent = "Калькулятор тимчасово недоступний — напишіть у формі"; });

    calcForm.addEventListener("change", recalc);
    calcForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const checked = $$('input[name="svc"]:checked', calcForm);
      if (!checked.length) { hintEl.textContent = "Спочатку оберіть послугу"; return; }
      if (formService && !formService.value) formService.value = checked[0].value;
      const bookEl = document.getElementById("book");
      if (bookEl) smoothTo(bookEl.getBoundingClientRect().top + window.scrollY - headerOffset());
      setTimeout(() => $("#lead-form input[name=name]")?.focus({ preventScroll: true }), 500);
    });
  }

  /* ---------- плавная прокрутка: своя анимация, системная настройка её не отключает ---------- */
  const topBar = document.querySelector(".top");
  function headerOffset() { return (topBar ? topBar.offsetHeight : 0) + 6; }

  let scrollAnim = null;
  let scrollRestore = null;
  function cancelScrollAnim() {
    if (scrollAnim !== null) { cancelAnimationFrame(scrollAnim); scrollAnim = null; }
    if (scrollRestore) { scrollRestore(); scrollRestore = null; }
  }

  function smoothTo(targetY, duration = 520) {
    cancelScrollAnim();
    // CSS scroll-behavior:smooth конфликтует с покадровой анимацией —
    // на время анимации отключаем его, иначе прокрутка ползёт рывками
    const html = document.documentElement;
    const prevBehavior = html.style.scrollBehavior;
    html.style.scrollBehavior = "auto";
    scrollRestore = () => { html.style.scrollBehavior = prevBehavior; };
    const startY = window.scrollY;
    const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    const endY = Math.min(Math.max(0, targetY), maxY);
    const dist = endY - startY;
    if (Math.abs(dist) < 2) { if (scrollRestore) { scrollRestore(); scrollRestore = null; } return; }
    const t0 = performance.now();
    const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    function step(now) {
      const p = Math.min(1, (now - t0) / duration);
      window.scrollTo(0, startY + dist * ease(p));
      if (p < 1) { scrollAnim = requestAnimationFrame(step); }
      else { scrollAnim = null; if (scrollRestore) { scrollRestore(); scrollRestore = null; } }
    }
    scrollAnim = requestAnimationFrame(step);
  }

  // если человек сам начал крутить — анимация уступает
  ["wheel", "touchstart", "keydown"].forEach(ev =>
    window.addEventListener(ev, cancelScrollAnim, { passive: true }));

  document.addEventListener("click", (e) => {
    const a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (!a) return;
    const id = a.getAttribute("href").slice(1);
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    e.preventDefault();
    // #top — это фиксированная шапка: её rect.top считается от экрана, не от начала документа
    smoothTo(id === "top" ? 0 : target.getBoundingClientRect().top + window.scrollY - headerOffset());
    history.pushState(null, "", "#" + id);
  });

  /* ---------- кнопки «Записатись» в карточках ---------- */
  $$(".card-link").forEach(btn => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.service;
      if (formService && name) formService.value = name;
      const bookEl = document.getElementById("book");
      if (bookEl) smoothTo(bookEl.getBoundingClientRect().top + window.scrollY - headerOffset());
      setTimeout(() => $("#lead-form input[name=name]")?.focus({ preventScroll: true }), 500);
    });
  });

  /* ---------- сравнение «до / після» ---------- */
  $$(".ba-block").forEach(fig => {
    const frame = $(".ba-frame", fig);
    const before = $(".ba-before", fig);
    const handle = $(".ba-handle", fig);
    if (!frame || !before || !handle) return;

    const setPct = (pct) => {
      const v = Math.max(6, Math.min(94, pct));
      before.style.clipPath = `inset(0 ${100 - v}% 0 0)`;
      handle.style.left = v + "%";
      handle.setAttribute("aria-valuenow", String(Math.round(v)));
    };
    const pctFromEvent = (e) => {
      const r = frame.getBoundingClientRect();
      const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
      return (x / r.width) * 100;
    };
    let dragging = false;
    const start = (e) => { dragging = true; setPct(pctFromEvent(e)); e.preventDefault(); };
    const move = (e) => { if (dragging) setPct(pctFromEvent(e)); };
    const end = () => { dragging = false; };

    frame.addEventListener("pointerdown", start);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    handle.addEventListener("keydown", (e) => {
      const cur = parseFloat(handle.getAttribute("aria-valuenow") || "50");
      if (e.key === "ArrowLeft") { setPct(cur - 4); e.preventDefault(); }
      if (e.key === "ArrowRight") { setPct(cur + 4); e.preventDefault(); }
    });
  });

  /* ---------- выбор даты и времени (живые слоты) ---------- */
  const slotUI = (() => {
    const box = $("#days"), times = $("#times"), hidDate = $("#slot-date"),
          hidTime = $("#slot-time"), empty = $("#slot-empty"), legend = $("#slot-legend");
    if (!box || !times || !hidDate) return null;
    const dataEl = document.getElementById("slot-data");
    let days = [];
    try { days = JSON.parse(dataEl ? dataEl.textContent : "[]"); } catch (e) { days = []; }
    let active = "";

    const note = d => d.closed ? "зачинено" : (d.free ? d.free + " вільно" : "зайнято");

    function renderDays() {
      box.innerHTML = days.map(d => {
        const off = d.closed || !d.free;
        return `<button class="day${d.date === active ? " is-active" : ""}" type="button" data-date="${d.date}"
                 ${off ? "disabled" : ""} aria-pressed="${d.date === active}">
                 <b>${d.label}</b><span>${d.day}.${d.month}</span><small>${note(d)}</small></button>`;
      }).join("");
    }

    function renderTimes(slots) {
      const free = slots.filter(x => x.state === "free");
      empty.hidden = free.length > 0;
      if (!free.length) empty.textContent = "На цей день вільних годин немає — оберіть інший день.";
      times.innerHTML = slots.filter(x => x.state !== "closed").map(x => {
        const dis = x.state !== "free";
        const label = x.state === "past" ? "минуло"
                    : x.state === "full" ? "зайнято"
                    : x.free === 1 ? "1 місце" : x.free + " місця";
        return `<button class="time${hidTime.value === x.time ? " is-active" : ""}" type="button"
                 data-time="${x.time}" ${dis ? "disabled" : ""}>${x.time}<small>${label}</small></button>`;
      }).join("");
    }

    async function openDay(date, keepTime) {
      active = date;
      hidDate.value = date;
      if (!keepTime) hidTime.value = "";
      renderDays();
      times.innerHTML = '<span class="slot-legend">Завантажуємо вільні години…</span>';
      try {
        const j = await (await fetch("/api/slots?date=" + encodeURIComponent(date))).json();
        renderTimes(j.slots || []);
      } catch (e) {
        times.innerHTML = "";
        empty.hidden = false;
        empty.textContent = "Не вдалося завантажити час — оновіть сторінку.";
      }
    }

    box.addEventListener("click", (e) => {
      const b = e.target.closest(".day");
      if (b && !b.disabled) openDay(b.dataset.date);
    });

    times.addEventListener("click", (e) => {
      const b = e.target.closest(".time");
      if (!b || b.disabled) return;
      [...times.querySelectorAll(".time")].forEach(x => x.classList.remove("is-active"));
      b.classList.add("is-active");
      hidTime.value = b.dataset.time;
      if (legend) legend.textContent = "Час обрано — натисніть «Записатись»";
    });

    async function refresh() {
      try {
        const j = await (await fetch("/api/slots/days")).json();
        days = j.days || days;
      } catch (e) {}
      const keep = active;
      hidDate.value = "";
      hidTime.value = "";
      active = "";
      renderDays();
      if (keep) openDay(keep);
    }

    renderDays();
    const first = days.find(d => !d.closed && d.free);
    if (first) openDay(first.date);
    return { refresh, get date() { return hidDate.value; }, get time() { return hidTime.value; } };
  })();

  /* ---------- ближайшее окно в hero-карточке ---------- */
  const nextSlotEl = $("#next-slot");
  if (nextSlotEl) {
    (async () => {
      try {
        const j = await (await fetch("/api/slots/days")).json();
        for (const d of (j.days || [])) {
          if (d.closed || !d.free) continue;
          const s = await (await fetch("/api/slots?date=" + encodeURIComponent(d.date))).json();
          const free = (s.slots || []).find(x => x.state === "free");
          if (free) { nextSlotEl.textContent = `${d.label}, ${free.time}`; return; }
        }
        nextSlotEl.textContent = "Зателефонуйте — підберемо час";
      } catch (e) { nextSlotEl.textContent = "Зателефонуйте — підберемо час"; }
    })();
  }

  /* ---------- обратный звонок ---------- */
  const cbForm = $("#callback-form");
  if (cbForm) {
    const cbMsg = $("#callback-msg");
    const cbPhone = cbForm.querySelector('input[name="phone"]');
    cbPhone?.addEventListener("input", () => maskPhone(cbPhone));
    cbForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      cbMsg.className = "callback-msg";
      if (cbPhone.value.replace(/\D/g, "").length !== 12) {
        cbMsg.textContent = "Вкажіть номер у форматі +380 XX XXX XX XX";
        cbMsg.classList.add("err");
        cbPhone.focus();
        return;
      }
      const btn = cbForm.querySelector("button");
      btn.disabled = true;
      try {
        const body = new URLSearchParams(Object.assign({ kind: "callback", phone: cbPhone.value, consent: "1" }, srcFields()));
        const r = await (await fetch("/api/leads", { method: "POST", body })).json();
        if (r.ok) {
          cbMsg.textContent = "Прийнято — передзвонимо протягом 15 хвилин.";
          cbForm.reset();
          window.hit && window.hit("lead_sent");
        } else {
          cbMsg.textContent = r.error || "Не вдалося — зателефонуйте нам";
          cbMsg.classList.add("err");
        }
      } catch (err) {
        cbMsg.textContent = "Немає зв'язку з сервером";
        cbMsg.classList.add("err");
      } finally { btn.disabled = false; }
    });
  }

  /* ---------- форма записи ---------- */
  const form = $("#lead-form");
  const msg = $("#form-msg");
  /* выбор даты и времени теперь в блоке слотов — см. модуль ниже */

  if (form) {
    const phone = form.querySelector('input[name="phone"]');
    phone?.addEventListener("input", () => maskPhone(phone));

    // режим заявки: «записатися» требует слот, «тільки дізнатися ціну» — нет
    const modeRadios = form.querySelectorAll('input[name="mode"]');
    const askMode = () => form.querySelector('input[name="mode"]:checked')?.value === "ask";
    function applyMode() {
      const ask = askMode();
      form.classList.toggle("mode-ask", ask);
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.textContent = ask ? "Надіслати питання" : "Записатись";
      if (ask) {
        ["#slot-date", "#slot-time"].forEach(sel => {
          const el = form.querySelector(sel);
          if (el) el.value = "";
        });
      }
    }
    modeRadios.forEach(r => r.addEventListener("change", applyMode));
    applyMode();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      msg.className = "form-msg";
      const name = form.name.value.trim();
      const ph = form.phone.value.trim();
      if (name.length < 2) { msg.textContent = "Вкажіть ім'я"; msg.classList.add("err"); form.name.focus(); return; }
      if (ph.replace(/\D/g, "").length !== 12) { msg.textContent = "Вкажіть телефон у форматі +380 XX XXX XX XX"; msg.classList.add("err"); form.phone.focus(); return; }
      const consent = form.querySelector('input[name="consent"]');
      if (consent && !consent.checked) {
        msg.textContent = "Позначте згоду на обробку даних — без неї не можемо прийняти заявку";
        msg.classList.add("err");
        consent.focus();
        return;
      }

      // услуги могли выбрать в калькуляторе — переносим их в заявку
      const svcSel = form.querySelector('select[name="service"]');
      const picked = $$('input[name="svc"]:checked').map(i => i.value);
      if (svcSel && !svcSel.value && picked.length) {
        if ([...svcSel.options].some(o => o.value === picked[0])) svcSel.value = picked[0];
        if (picked.length > 1) {
          const c = form.querySelector('[name="comment"]');
          const line = "Послуги: " + picked.join(", ");
          if (c && !c.value.includes(line)) c.value = (c.value ? c.value + "\n" : "") + line;
        }
      }

      if (!askMode() && slotUI && (!slotUI.date || !slotUI.time)) {
        msg.textContent = "Оберіть день і час — інакше не забронюємо місце";
        msg.classList.add("err");
        document.getElementById("days")?.scrollIntoView({ block: "center" });
        return;
      }

      const btn = form.querySelector('button[type="submit"]');
      const label = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Надсилаємо…";
      msg.textContent = "";

      try {
        const payload = Object.assign(Object.fromEntries(new FormData(form)), srcFields());
        const res = await fetch("/api/leads", { method: "POST", body: new URLSearchParams(payload) });
        const data = await res.json();
        if (data.ok) {
          msg.textContent = askMode()
            ? "Дякуємо! Питання прийнято — відповімо в робочий час."
            : "Дякуємо! Заявку прийнято — передзвонимо протягом 15 хвилин.";
          window.hit && window.hit("lead_sent");
          msg.classList.add("ok");
          form.reset();
          applyMode();
          if (estimateField) estimateField.value = "";
          const estLine1 = $("#est-line");
          if (estLine1) estLine1.hidden = true;
          if (slotUI) slotUI.refresh();
          if (calcData) recalc();
        } else {
          msg.textContent = data.error || "Не вдалося надіслати заявку";
          msg.classList.add("err");
        }
      } catch (err) {
        msg.textContent = "Немає зв’язку з сервером. Зателефонуйте: +380 44 000-00-00";
        msg.classList.add("err");
      } finally {
        btn.disabled = false;
        btn.textContent = label;
      }
    });
  }


  /* ---------- аналитика (свой счётчик, без внешних трекеров) ---------- */
  const sid = (() => {
    let s = sessionStorage.getItem("at_sid");
    if (!s) { s = Math.random().toString(36).slice(2, 12); sessionStorage.setItem("at_sid", s); }
    return s;
  })();
  /* источник перехода: запоминаем utm_source из адреса на всю сессию,
     чтобы заход по ссылке из письма был виден и на внутренних страницах */
  const utmSrc = (() => {
    const q = new URLSearchParams(location.search).get("utm_source") || "";
    const clean = q.replace(/[^A-Za-z0-9_.-]/g, "").slice(0, 32);
    if (clean) sessionStorage.setItem("at_src", clean);
    return sessionStorage.getItem("at_src") || "";
  })();
  function hit(name) {
    const payload = JSON.stringify({ name, path: location.pathname, sid, src: utmSrc });
    // важно: Blob с типом application/json — иначе сервер не разберёт тело beacon-запроса
    try {
      const blob = new Blob([payload], { type: "application/json" });
      const ok = navigator.sendBeacon("/api/hit", blob);
      if (!ok) throw new Error("beacon rejected");
    } catch (e) {
      fetch("/api/hit", { method: "POST", body: payload, keepalive: true,
                          headers: { "Content-Type": "application/json" } }).catch(() => {});
    }
  }
  window.hit = hit;
  hit("view");
  let calcTracked = false;
  if (calcForm) {
    calcForm.addEventListener("change", () => {
      if (!calcTracked && document.querySelector('input[name="svc"]:checked')) {
        calcTracked = true; hit("calc_used");
      }
    });
  }
  const leadFormEl = $("#lead-form");
  if (leadFormEl) {
    let formTracked = false;
    leadFormEl.addEventListener("focusin", () => {
      if (!formTracked) { formTracked = true; hit("form_start"); }
    }, { once: false });
  }

  /* ---------- лайтбокс для галереи ---------- */
  const lb = $("#lightbox");
  const lbImg = $("#lb-img");
  if (lb && lbImg) {
    const close = () => { lb.hidden = true; lbImg.src = ""; document.body.style.overflow = ""; };
    $$(".shot").forEach(fig => {
      fig.addEventListener("click", () => {
        const img = fig.querySelector("img");
        if (!img) return;
        lbImg.src = img.dataset.full || img.src;
        lbImg.alt = img.alt;
        lb.hidden = false;
        document.body.style.overflow = "hidden";
      });
    });
    lb.addEventListener("click", (e) => { if (e.target === lb || e.target.closest(".lb-close")) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !lb.hidden) close(); });
  }

  /* ---------- нижняя панель: скрываем, когда форма записи уже на экране ---------- */
  const floatCta = $("#float-cta");
  const bookSection = document.getElementById("book");
  if (floatCta && bookSection) {
    const syncBar = () => {
      const r = bookSection.getBoundingClientRect();
      // прячем, когда форма записи уже на экране — кнопка внизу становится дублем
      const formOnScreen = r.top < window.innerHeight * 0.65 && r.bottom > 140;
      // и пока не прокрутили первый экран: там та же кнопка есть в шапке
      const pastHero = window.scrollY > window.innerHeight * 0.6;
      floatCta.classList.toggle("hide", formOnScreen || !pastHero);
    };
    window.addEventListener("scroll", syncBar, { passive: true });
    window.addEventListener("resize", syncBar, { passive: true });
    syncBar();
  }

  /* старый обработчик со window.scrollTo({behavior:"smooth"}) удалён:
     встроенная плавность зависит от системной настройки и на ней прыгает.
     Теперь якоря обрабатывает smoothTo() выше — своя покадровая анимация. */
})();
