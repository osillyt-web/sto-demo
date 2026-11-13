/* Форма заявки на сторінці /order.
   Валідація на місці, відправка без перезавантаження, повідомлення під формою. */
(function () {
  // Форма заявки скрыта по умолчанию и открывается кнопкой «Написати на email»
  const toggle = document.getElementById("order-form-toggle");
  const wrap = document.getElementById("order-form-wrap");
  if (toggle && wrap) {
    toggle.addEventListener("click", function () {
      const willOpen = wrap.hidden;
      wrap.hidden = !willOpen;
      toggle.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) {
        const first = document.getElementById("of-name");
        if (first) first.focus();
        wrap.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  const form = document.getElementById("order-form");
  if (!form) return;

  const msg = document.getElementById("order-msg");
  const btn = form.querySelector('button[type="submit"]');
  const btnLabel = btn ? btn.textContent : "";
  const nameEl = form.querySelector('[name="name"]');
  const contactEl = form.querySelector('[name="contact"]');
  const nameErr = document.getElementById("of-name-err");
  const contactErr = document.getElementById("of-contact-err");
  const consentEl = form.querySelector('[name="consent"]');

  const EMAIL_RE = /^[^@\s]{1,64}@[^@\s.]{1,63}(\.[^@\s.]{2,})+$/;

  function contactOk(value) {
    const v = (value || "").trim();
    if (!v) return false;
    if (v.indexOf("@") !== -1) return EMAIL_RE.test(v);
    const digits = (v.match(/\d/g) || []).length;
    return digits >= 9 && digits <= 15 && v.length <= 40;
  }

  function setError(el, errEl, text) {
    if (errEl) errEl.textContent = text || "";
    el.classList.toggle("is-bad", !!text);
    el.setAttribute("aria-invalid", text ? "true" : "false");
  }

  nameEl.addEventListener("blur", function () {
    const v = nameEl.value.trim();
    setError(nameEl, nameErr, v && v.length < 2 ? "Вкажіть ім’я" : "");
  });
  contactEl.addEventListener("blur", function () {
    const v = contactEl.value.trim();
    setError(contactEl, contactErr, v && !contactOk(v) ? "Вкажіть email або телефон" : "");
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    msg.className = "form-msg";
    msg.textContent = "";

    const nameValue = nameEl.value.trim();
    const contactValue = contactEl.value.trim();
    let firstBad = null;

    if (nameValue.length < 2) {
      setError(nameEl, nameErr, "Вкажіть ім’я");
      firstBad = firstBad || nameEl;
    } else {
      setError(nameEl, nameErr, "");
    }

    if (!contactOk(contactValue)) {
      setError(contactEl, contactErr, "Вкажіть email або телефон");
      firstBad = firstBad || contactEl;
    } else {
      setError(contactEl, contactErr, "");
    }

    if (!consentEl.checked) {
      msg.textContent = "Позначте згоду на обробку даних — без неї не можемо прийняти заявку";
      msg.classList.add("err");
      firstBad = firstBad || consentEl;
    }

    if (firstBad) {
      firstBad.focus();
      return;
    }

    btn.disabled = true;
    btn.textContent = "Надсилаємо…";

    try {
      const res = await fetch("/api/order", {
        method: "POST",
        body: new URLSearchParams(Object.fromEntries(new FormData(form)))
      });
      const json = await res.json();
      if (json.ok) {
        msg.textContent = "Дякую! Заявку прийнято — відповім на вказаний контакт.";
        msg.classList.add("ok");
        form.reset();
        setError(nameEl, nameErr, "");
        setError(contactEl, contactErr, "");
      } else {
        msg.textContent = json.error || "Не вдалося надіслати заявку";
        msg.classList.add("err");
      }
    } catch (err) {
      msg.textContent = "Немає зв’язку з сервером. Спробуйте ще раз або напишіть у месенджер.";
      msg.classList.add("err");
    } finally {
      btn.disabled = false;
      btn.textContent = btnLabel;
    }
  });
})();
