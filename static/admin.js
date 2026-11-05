/* админ-панель: заявки, поиск, фильтры, редактор услуг */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => (v ?? "").toString().replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const state = { filter: "all", q: "" };
  let toastTimer = null;

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      document.body.removeChild(ta);
      return ok;
    }
  }

  function toast(text) {
    const t = $("#toast");
    if (!t) return;
    t.textContent = text;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2000);
  }

  async function api(url, body) {
    const opts = body ? { method: "POST", body: new URLSearchParams(body) } : {};
    const res = await fetch(url, opts);
    if (res.status === 401) { location.href = "/admin/login"; throw new Error("auth"); }
    return res.json();
  }

  /* ------------------------------ заявки ------------------------------ */
  async function loadLeads() {
    const params = new URLSearchParams({ status: state.filter, q: state.q });
    let data;
    try { data = await api("/api/admin/leads?" + params); } catch (e) { return; }

    const { leads, stats } = data;
    $("#st-total").textContent = stats.total;
    $("#st-new").textContent = stats.new;
    $("#st-today").textContent = stats.today;
    $("#st-conv").textContent = stats.total
      ? Math.round((stats.new / stats.total) * 100) + "%"
      : "—";

    if (!leads.length) {
      $("#leads-box").innerHTML = `<div class="empty">${
        state.q || state.filter !== "all"
          ? "За цим фільтром нічого не знайдено."
          : "Поки що заявок немає. Відправте тестову з форми на сайті."}</div>`;
      return;
    }

    const rows = leads.map(l => `
      <tr>
        <td class="hide-sm"><span class="sub-line">${esc(l.created_at)}</span></td>
        <td>
          <b>${esc(l.name)}</b>${l.kind === "callback" ? ' <span class="badge cb">дзвінок</span>' : ""}
          <span class="sub-line"><a href="tel:${esc(l.phone)}">${esc(l.phone)}</a></span>
        </td>
        <td class="hide-sm">${esc(l.service) || '<span class="muted">—</span>'}
          <span class="sub-line">${esc(l.car) || "авто не вказано"}</span></td>
        <td class="hide-sm">
          ${l.slot_date && l.slot_time
              ? `<b class="slot-cell">${esc(l.slot_date)} · ${esc(l.slot_time)}</b>`
              : (esc(l.when_at) || "дата не обрана")}
          ${l.source ? `<span class="sub-line">Джерело: ${esc(l.source)}${
              l.utm_campaign ? " · " + esc(l.utm_campaign) : ""}</span>` : ""}
          ${l.estimate ? `<span class="sub-line">Кошторис: ${esc(l.estimate)}</span>` : ""}
          ${l.comment ? `<span class="sub-line">«${esc(l.comment)}»</span>` : ""}
        </td>
        <td>
          <input class="note-input" data-note="${l.id}" value="${esc(l.note)}"
                 placeholder="Нотатка менеджера" aria-label="Нотатка до заявки ${l.id}">
        </td>
        <td><span class="badge ${l.status === "new" ? "new" : "done"}">${
          l.status === "new" ? "нова" : "опрацьовано"}</span>
          ${l.confirmed === "confirmed" ? '<span class="badge ok">підтвердив</span>' : ""}
          ${l.confirmed === "cancelled" ? '<span class="badge cb">скасував</span>' : ""}</td>
        <td>
          <div class="row-actions">
            <button class="icon-btn" title="${l.status === "new" ? "Позначити опрацьованою" : "Повернути в нові"}"
                    data-status-id="${l.id}" data-status="${l.status === "new" ? "done" : "new"}">
              ${l.status === "new" ? "✓" : "↺"}
            </button>
            ${l.slot_time ? `<button class="icon-btn" title="Скопіювати нагадування клієнту"
                    data-remind="${l.id}">🔔</button>` : ""}
            ${l.status === "done" ? `<button class="icon-btn" title="Скопіювати прохання про відгук"
                    data-review="${l.id}">★</button>` : ""}
            <button class="icon-btn danger" title="Видалити заявку" data-del="${l.id}">✕</button>
          </div>
        </td>
      </tr>`).join("");

    $("#leads-box").innerHTML = `
      <table class="responsive">
        <thead><tr>
          <th class="hide-sm">Дата</th><th>Клієнт</th><th class="hide-sm">Послуга / авто</th>
          <th class="hide-sm">Деталі</th><th>Нотатка</th><th>Статус</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  /* ------------------------------ услуги ------------------------------ */
  async function loadServices() {
    let list;
    try { list = await api("/api/admin/services"); } catch (e) { return; }

    const rows = list.map(s => `
      <tr class="svc-row ${s.active ? "" : "off"}" data-id="${s.id}">
        <td><input value="${esc(s.title)}" data-f="title" aria-label="Назва"></td>
        <td style="width:150px"><input value="${esc(s.price)}" data-f="price" aria-label="Ціна"></td>
        <td style="width:120px"><input value="${s.base}" type="number" step="50" min="0" data-f="base" aria-label="База"></td>
        <td class="hide-sm"><input value="${esc(s.note)}" data-f="note" aria-label="Опис"></td>
        <td style="width:110px">
          <label class="switch"><input type="checkbox" data-f="active" ${s.active ? "checked" : ""}>на сайті</label>
        </td>
        <td style="width:150px">
          <div class="row-actions">
            <button class="btn btn-accent btn-sm" data-save="${s.id}">Зберегти</button>
            <button class="icon-btn" data-move="${s.id}" data-dir="up" title="Вище">↑</button>
            <button class="icon-btn" data-move="${s.id}" data-dir="down" title="Нижче">↓</button>
            <button class="icon-btn danger" data-svc-del="${s.id}" title="Видалити">✕</button>
          </div>
        </td>
      </tr>`).join("");

    $("#svc-box").innerHTML = `
      <table class="responsive">
        <thead><tr>
          <th>Назва</th><th>Ціна</th><th>База, ₴</th><th class="hide-sm">Опис</th><th>Активна</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }


  /* ------------------------------ завантаження тижня ------------------------------ */
  const calState = { start: null };

  async function loadCalendar(startIso) {
    const box = $("#cal-box");
    if (!box) return;
    const params = new URLSearchParams({ days: "7" });
    if (startIso) params.set("start", startIso);
    let data;
    try { data = await api("/api/admin/calendar?" + params); } catch (e) { return; }
    calState.start = data.start;
    const grid = data.grid || [];
    const head = grid.map(d => `<th>${d.weekday}<span class="sub-line">${d.day}</span></th>`).join("");
    const rows = (data.times || []).map(t => {
      const cells = grid.map(d => {
        if (d.closed) return `<td class="cal-closed">—</td>`;
        const cell = (d.slots || []).find(x => x.time === t);
        const b = cell ? cell.booked : 0;
        const cls = b >= data.capacity ? "cal-full" : (b ? "cal-busy" : "cal-free");
        return `<td class="${cls}">${b ? b + "/" + data.capacity : "•"}</td>`;
      }).join("");
      return `<tr><th class="cal-time">${t}</th>${cells}</tr>`;
    }).join("");

    const list = (data.leads || []).length
      ? `<div class="cal-leads">${data.leads.map(l => `
          <div class="cal-lead">
            <b>${esc(l.slot_date)} ${esc(l.slot_time)}</b>
            <span>${esc(l.name)} · <a href="tel:${esc(l.phone)}">${esc(l.phone)}</a></span>
            <span class="sub-line">${esc(l.service) || "послуга не вказана"}</span>
          </div>`).join("")}</div>`
      : `<p class="hint">На цей тиждень записів ще немає.</p>`;

    box.innerHTML = `
      <table class="cal-table">
        <thead><tr><th></th>${head}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="hint">Клітинка — скільки авто зайнято з ${data.capacity} можливих на цю годину.</p>
      ${list}`;
  }

  $("#cal-prev")?.addEventListener("click", () => {
    const d = new Date(calState.start || new Date());
    d.setDate(d.getDate() - 7);
    loadCalendar(d.toISOString().slice(0, 10));
  });
  $("#cal-next")?.addEventListener("click", () => {
    const d = new Date(calState.start || new Date());
    d.setDate(d.getDate() + 7);
    loadCalendar(d.toISOString().slice(0, 10));
  });
  $("#cal-today")?.addEventListener("click", () => loadCalendar(null));

  /* ------------------------------ контакты и слоты ------------------------------ */
  const contactFields = ["c_phone", "c_phone_raw", "c_address", "c_hours", "c_telegram",
                         "c_viber", "c_whatsapp", "c_reviews_url", "c_reviews_note"];

  async function loadContacts() {
    let data;
    try { data = await api("/api/admin/settings"); } catch (e) { return; }
    const form = $("#contacts-form");
    if (!data.contacts) return;
    window.__reviewsUrl = data.contacts.reviews_url || "";
    if (!form) return;
    contactFields.forEach(f => {
      const input = form.querySelector(`[name="${f}"]`);
      if (input) input.value = data.contacts[f.slice(2)] ?? "";
    });
    const cap = form.querySelector('[name="slot_capacity"]');
    if (cap) cap.value = data.slot_capacity || "2";
    const times = form.querySelector('[name="slot_times"]');
    if (times) times.value = data.slot_times || "";
  }

  $("#contacts-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const body = { slot_capacity: form.querySelector('[name="slot_capacity"]').value,
                   slot_times: form.querySelector('[name="slot_times"]').value };
    contactFields.forEach(f => { body[f] = form.querySelector(`[name="${f}"]`).value; });
    try {
      const r = await fetch("/admin/settings", { method: "POST", body: new URLSearchParams(body) });
      const j = await r.json();
      if (j.ok) { toast("Контакти збережено — оновіть сайт"); loadContacts(); }
      else toast(j.error || "Не збережено");
    } catch (err) { toast("Помилка збереження"); }
  });


  /* ------------------------------ состояние системы и журнал ------------------------------ */
  async function loadOps() {
    let st;
    try { st = await api("/api/admin/state"); } catch (e) { return; }
    if (st.ok === false) return;
    const alert = $("#pwd-alert");
    if (alert) alert.hidden = !st.default_password;

    const fmtUp = (sec) => {
      if (sec == null) return "—";
      const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600);
      return d ? `${d} дн ${h} год` : `${h} год`;
    };
    const backupOk = st.backup_age_h != null && st.backup_age_h < 26;
    $("#ops-box").innerHTML = `
      <div class="ops-cell ${backupOk ? "ok" : "warn"}">
        <span class="ops-k">Резервна копія</span>
        <b>${st.last_backup ? esc(st.last_backup) : "немає"}</b>
        <span class="ops-sub">${st.backup_age_h != null ? st.backup_age_h + " год тому" : "зробіть копію"}</span>
      </div>
      <div class="ops-cell">
        <span class="ops-k">Розмір бази</span><b>${st.db_size_kb} КБ</b>
        <span class="ops-sub">заявки, налаштування, аналітика</span>
      </div>
      <div class="ops-cell">
        <span class="ops-k">Працює без перезапуску</span><b>${fmtUp(st.uptime_s)}</b>
        <span class="ops-sub">версія ${esc(st.version)}</span>
      </div>
      <div class="ops-cell ${st.errors_log_kb > 0 ? "warn" : "ok"}">
        <span class="ops-k">Журнал помилок</span>
        <b>${st.errors_log_kb} КБ</b>
        <span class="ops-sub">${st.errors_log_kb > 0 ? "перевірте data/errors.log" : "помилок немає"}</span>
      </div>`;

    let data;
    try { data = await api("/api/admin/audit?limit=30"); } catch (e) { return; }
    if (!data.rows || !data.rows.length) {
      $("#audit-box").innerHTML = `<div class="empty">Журнал порожній.</div>`;
      return;
    }
    $("#audit-box").innerHTML = `<table class="audit-table">
      <thead><tr><th>Коли</th><th>Дія</th><th>Обʼєкт</th><th>Деталі</th></tr></thead>
      <tbody>${data.rows.map(r => `<tr>
        <td class="muted">${esc(r.at)}</td>
        <td>${esc(r.action)}</td>
        <td class="muted">${esc(r.target) || "—"}</td>
        <td class="muted">${esc(r.detail) || "—"}</td></tr>`).join("")}</tbody></table>`;
  }

  $("#ops-refresh")?.addEventListener("click", loadOps);

  /* ------------------------------ события ------------------------------ */
  document.addEventListener("click", async (e) => {
    const statusBtn = e.target.closest("[data-status-id]");
    if (statusBtn) {
      await api("/admin/lead", { id: statusBtn.dataset.statusId, status: statusBtn.dataset.status });
      toast("Статус оновлено");
      loadLeads();
      return;
    }

    const remindBtn = e.target.closest("[data-remind]");
    if (remindBtn) {
      try {
        const r = await api("/api/admin/remind?id=" + encodeURIComponent(remindBtn.dataset.remind));
        if (!r.ok) { toast(r.error || "Не вдалося"); return; }
        const copied = await copyText(r.text);
        toast(copied ? "Текст нагадування скопійовано" : r.url);
      } catch (err) { toast("Помилка"); }
      return;
    }

    const reviewBtn = e.target.closest("[data-review]");
    if (reviewBtn) {
      const link = document.querySelector('meta[name="reviews-url"]')?.content ||
                   "https://maps.google.com/";
      const text = "Дякуємо, що обрали АвтоТочку! Якщо все сподобалось — залиште, будь ласка, " +
                   "відгук, це допомагає нам: " + link;
      const copied = await copyText(text);
      toast(copied ? "Прохання про відгук скопійовано" : text);
      return;
    }

    const delLead = e.target.closest("[data-del]");
    if (delLead) {
      if (!confirm("Видалити заявку назавжди?")) return;
      await api("/admin/lead", { action: "delete", id: delLead.dataset.del });
      toast("Заявку видалено");
      loadLeads();
      return;
    }

    const saveSvc = e.target.closest("[data-save]");
    if (saveSvc) {
      const row = saveSvc.closest("tr");
      const body = { action: "update", id: saveSvc.dataset.save };
      $$("input", row).forEach(i => {
        body[i.dataset.f] = i.type === "checkbox" ? (i.checked ? "1" : "0") : i.value;
      });
      await api("/admin/service", body);
      toast("Збережено — на сайті вже оновлено");
      loadServices();
      return;
    }

    const moveBtn = e.target.closest("[data-move]");
    if (moveBtn) {
      await api("/admin/service", { action: "move", id: moveBtn.dataset.move, dir: moveBtn.dataset.dir });
      loadServices();
      return;
    }

    const delSvc = e.target.closest("[data-svc-del]");
    if (delSvc) {
      if (!confirm("Видалити послугу? Вона зникне з сайту й калькулятора.")) return;
      await api("/admin/service", { action: "delete", id: delSvc.dataset.svcDel });
      toast("Послугу видалено");
      loadServices();
      return;
    }

    const filterBtn = e.target.closest(".seg-btn");
    if (filterBtn) {
      $$(".seg-btn").forEach(b => b.classList.toggle("active", b === filterBtn));
      state.filter = filterBtn.dataset.filter;
      loadLeads();
    }
  });

  /* автосохранение заметки при уходе из поля */
  document.addEventListener("blur", async (e) => {
    const input = e.target.closest?.("[data-note]");
    if (!input) return;
    const row = input.closest("tr");
    const badge = row.querySelector(".badge");
    const status = badge.classList.contains("new") ? "new" : "done";
    await api("/admin/lead", { id: input.dataset.note, status, note: input.value });
    toast("Нотатку збережено");
  }, true);

  /* поиск с задержкой */
  let searchTimer = null;
  $("#search")?.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value.trim(); loadLeads(); }, 300);
  });

  $("#reload")?.addEventListener("click", () => { loadLeads(); loadServices(); toast("Оновлено"); });

  /* добавление услуги */
  const addForm = $("#add-form");
  $("#toggle-add")?.addEventListener("click", () => {
    addForm.hidden = !addForm.hidden;
    if (!addForm.hidden) addForm.querySelector("input").focus();
  });
  $("#cancel-add")?.addEventListener("click", () => { addForm.hidden = true; addForm.reset(); });
  addForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await api("/admin/service", { action: "add", ...Object.fromEntries(new FormData(addForm)) });
    addForm.reset();
    addForm.hidden = true;
    toast("Послугу додано");
    loadServices();
  });

  loadLeads();
  loadOps();
  loadServices();
  loadCalendar();
  loadContacts();

  /* ------------------------------ аналитика ------------------------------ */
  async function loadAnalytics() {
    let d;
    try { d = await api("/api/admin/analytics"); } catch (e) { return; }
    $("#an-views").textContent = d.views;
    $("#an-calc").textContent = d.calc;
    $("#an-form").textContent = d.form;
    $("#an-leads").textContent = d.leads;
    $("#an-conv").textContent = d.conversion + "%";
    $("#an-top").textContent = d.top.length
      ? d.top.map(t => `${t.service} (${t.c})`).join(", ")
      : "поки немає даних";

    const chart = $("#an-chart");
    const days = d.days.slice(-14);
    if (!days.length) { chart.innerHTML = '<p class="empty">Заявок за період ще немає.</p>'; return; }
    const max = Math.max(...days.map(x => x.c));
    chart.innerHTML = days.map(x => {
      const h = Math.max(6, Math.round((x.c / max) * 110));
      return `<div class="bar"><span style="height:${h}px" title="${x.d}: ${x.c}"></span>
              <small>${x.d.slice(8)}.${x.d.slice(5, 7)}</small></div>`;
    }).join("");
  }

  /* ------------------------------ telegram ------------------------------ */
  async function loadSettings() {
    let d;
    try { d = await api("/api/admin/settings"); } catch (e) { return; }
    $("#tg-chat").value = d.tg_chat || "";
    $("#tg-enabled").checked = d.tg_enabled === "1";
    $("#tg-token").placeholder = d.tg_token_set === "1"
      ? `збережено (…${d.tg_token_tail}) — введіть новий, щоб замінити`
      : "123456789:AA... (токен від @BotFather)";
    const state = $("#tg-state");
    const on = d.tg_enabled === "1" && d.tg_token_set === "1";
    state.textContent = on ? "увімкнено" : "вимкнено";
    state.className = "badge " + (on ? "badge-ok" : "badge-off");
  }

  $("#tg-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const res = await api("/admin/settings", {
      tg_token: f.tg_token.value.trim(),
      tg_chat: f.tg_chat.value.trim(),
      tg_enabled: f.tg_enabled.checked ? "1" : "0",
    });
    if (res.ok) { toast("Налаштування збережено"); f.tg_token.value = ""; loadSettings(); }
    else toast(res.error || "Не збережено");
  });

  $("#tg-test")?.addEventListener("click", async () => {
    toast("Надсилаємо…");
    const res = await api("/admin/settings/test", {});
    toast(res.ok ? "Тестове повідомлення надіслано — перевірте Telegram"
                 : "Не вдалося: " + (res.info || "перевірте токен і chat_id"));
  });

  /* ------------------------------ пароль ------------------------------ */
  $("#pw-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const res = await api("/admin/password", { old: f.old.value, new: f.new.value });
    if (res.ok) { toast("Пароль змінено — увійдіть заново"); setTimeout(() => location.href = "/admin/login", 1200); }
    else toast(res.error || "Не змінено");
  });

  $("#reload-stats")?.addEventListener("click", () => { loadAnalytics(); toast("Оновлено"); });
  loadAnalytics();
  loadSettings();
})();
