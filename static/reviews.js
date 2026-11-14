/* Форма отзыва на странице /reviews.
   Отправляет данные в /api/review; отзыв попадает в админку на модерацию
   и появляется на сайте только после одобрения владельцем. */
(() => {
  const form = document.getElementById('rev-form');
  if (!form) return;

  const statusEl = document.getElementById('rev-status');
  const say = (text, kind) => {
    statusEl.textContent = text;
    statusEl.className = 'rev-status' + (kind ? ' ' + kind : '');
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    const body = {
      name: (fd.get('name') || '').trim(),
      car: (fd.get('car') || '').trim(),
      stars: parseInt(fd.get('stars') || '5', 10),
      text: (fd.get('text') || '').trim(),
      website: (fd.get('website') || '').trim(),   // ловушка для ботов
      consent: fd.get('consent') ? '1' : '',
    };

    // проверяем до отправки, чтобы человек сразу видел, что не так
    if (body.name.length < 2) return say('Вкажіть ім\'я — мінімум 2 символи', 'err');
    if (body.text.length < 20) return say('Текст відгуку — мінімум 20 символів', 'err');
    if (!body.consent) return say('Потрібна згода на публікацію імені та тексту', 'err');

    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    say('Надсилаємо…');

    try {
      const res = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (data.ok) {
        form.reset();
        say('Дякуємо! Відгук з\'явиться на сайті після перевірки.', 'ok');
      } else {
        say(data.error || 'Не вдалося надіслати. Спробуйте ще раз.', 'err');
      }
    } catch (err) {
      say('Немає зв\'язку з сервером. Спробуйте ще раз.', 'err');
    } finally {
      btn.disabled = false;
    }
  });
})();
