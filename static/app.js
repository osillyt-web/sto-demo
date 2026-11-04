/* АвтоТочка — интерактив главной страницы (без зависимостей) */
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const money = (n) => Math.round(n / 10) * 10;

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
    }, { threshold: 0.12 });
    items.forEach((el, i) => { el.style.transitionDelay = `${Math.min(i, 6) * 45}ms`; io.observe(el); });
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
      return;
    }
    const mult = currentClassMult();
    const sum = checked.reduce((acc, el) => acc + (parseInt(el.dataset.base, 10) || 0), 0);
    const from = money(sum * mult * 0.9);
    const to = money(sum * mult * 1.15);
    priceEl.textContent = `від ${from.toLocaleString("uk-UA")} до ${to.toLocaleString("uk-UA")} ₴`;
    hintEl.textContent = `${plural(checked.length)} · коефіцієнт класу ${mult.toFixed(2)}`;
    if (estimateField) estimateField.value = `${from}–${to} ₴`;
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
  function cancelScrollAnim() {
    if (scrollAnim !== null) { cancelAnimationFrame(scrollAnim); scrollAnim = null; }
  }

  function smoothTo(targetY, duration = 520) {
    cancelScrollAnim();
    const startY = window.scrollY;
    const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    const endY = Math.min(Math.max(0, targetY), maxY);
    const dist = endY - startY;
    if (Math.abs(dist) < 2) return;
    const t0 = performance.now();
    const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    function step(now) {
      const p = Math.min(1, (now - t0) / duration);
      window.scrollTo(0, startY + dist * ease(p));
      scrollAnim = p < 1 ? requestAnimationFrame(step) : null;
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
    smoothTo(target.getBoundingClientRect().top + window.scrollY - headerOffset());
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

  /* ---------- форма записи ---------- */
  const form = $("#lead-form");
  const msg = $("#form-msg");
  const whenInput = $("#when-at");

  if (whenInput) whenInput.min = new Date().toISOString().slice(0, 10);

  if (form) {
    const phone = form.querySelector('input[name="phone"]');
    phone?.addEventListener("input", () => {
      // берём последние 9 цифр как национальный номер — так маска не ломается,
      // когда человек набирает 0..., 380... или вставляет готовый номер
      let d = phone.value.replace(/\D/g, "");
      if (d.length > 12) d = d.slice(-12);
      let out = d;
      if (d.length >= 9) {
        const nat = d.slice(-9);
        out = `+380 ${nat.slice(0, 2)} ${nat.slice(2, 5)} ${nat.slice(5, 7)} ${nat.slice(7, 9)}`;
      }
      if (phone.value !== out) {
        phone.value = out;
        try { phone.setSelectionRange(out.length, out.length); } catch (e) {}
      }
    });

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

      const btn = form.querySelector('button[type="submit"]');
      const label = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Надсилаємо…";
      msg.textContent = "";

      try {
        const res = await fetch("/api/leads", { method: "POST", body: new URLSearchParams(new FormData(form)) });
        const data = await res.json();
        if (data.ok) {
          msg.textContent = "Дякуємо! Заявку прийнято — передзвонимо протягом 15 хвилин.";
          window.hit && window.hit("lead_sent");
          msg.classList.add("ok");
          form.reset();
          if (estimateField) estimateField.value = "";
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
  function hit(name) {
    const payload = JSON.stringify({ name, path: location.pathname, sid });
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
