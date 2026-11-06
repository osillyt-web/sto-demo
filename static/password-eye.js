/* Кнопка «показать пароль» для полей с атрибутом data-eye.
 *
 * Зачем: клиенты часто просят видеть, что набирают — особенно на телефоне,
 * где ошибиться в пароле легко. Кнопка не заменяет скрытый ввод, а временно
 * показывает символы и возвращает всё назад по повторному нажатию или Esc.
 *
 * Без JS поле остаётся обычным паролем — ничего не ломается.
 */
(function () {
  "use strict";

  var EYE_OPEN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">' +
    '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/>' +
    '<circle cx="12" cy="12" r="2.6"/></svg>';
  var EYE_OFF =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">' +
    '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/>' +
    '<circle cx="12" cy="12" r="2.6"/><path d="M4 20 20 4"/></svg>';

  function build(input) {
    if (input.dataset.eyeReady === "1") return;
    input.dataset.eyeReady = "1";

    var wrap = document.createElement("span");
    wrap.className = "pwd";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pwd-eye";
    btn.innerHTML = EYE_OPEN;
    btn.setAttribute("aria-label", "Показати пароль");
    btn.setAttribute("aria-pressed", "false");
    btn.title = "Показати пароль";
    btn.tabIndex = 0;
    wrap.appendChild(btn);

    function setVisible(show) {
      input.type = show ? "text" : "password";
      btn.innerHTML = show ? EYE_OFF : EYE_OPEN;
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Сховати пароль" : "Показати пароль");
      btn.title = show ? "Сховати пароль" : "Показати пароль";
      btn.classList.toggle("is-on", show);
      // курсор остаётся в поле и в конце ввода — иначе на телефоне прыгает клавиатура
      if (document.activeElement === btn) return;
      input.focus({ preventScroll: true });
      var end = input.value.length;
      try { input.setSelectionRange(end, end); } catch (e) { /* не все типы полей поддерживают */ }
    }

    btn.addEventListener("click", function () {
      setVisible(input.type === "password");
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.type === "text") {
        setVisible(false);
        e.stopPropagation();
      }
    });
  }

  function init() {
    var fields = document.querySelectorAll('input[type="password"][data-eye]');
    for (var i = 0; i < fields.length; i++) build(fields[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
