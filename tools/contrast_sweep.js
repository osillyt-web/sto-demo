/* Проверка «невидимого текста» на страницах сайта.
 *
 * Зачем: CSS-каскад может сделать текст того же цвета, что и фон (так случилось
 * с кнопкой «Повернутися на сайт» на /privacy: правило `.legal a` перебивало цвет
 * кнопки, и оранжевый текст оказывался на оранжевом фоне).
 *
 * Как запустить:
 *   1) открыть страницу в браузере;
 *   2) вставить этот файл в консоль (DevTools → Console);
 *   3) получить список элементов с контрастом ниже 2.2:1.
 * Пустой массив [] — проблем нет.
 *
 * Учитывает прозрачность фона, градиенты и элементы с обводкой текста
 * (например, крупная цифра «404» нарисована обводкой, а не заливкой).
 */
(() => {
  const rgba = (s) => {
    const n = (s.match(/[\d.]+/g) || []).map(Number);
    if (n.length < 3) return null;
    return { r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1 };
  };
  const over = (t, b) => ({
    r: t.r * t.a + b.r * (1 - t.a),
    g: t.g * t.a + b.g * (1 - t.a),
    b: t.b * t.a + b.b * (1 - t.a),
    a: 1,
  });
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };

  function bgOf(el) {
    const stack = [];
    let node = el;
    while (node && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      let c = rgba(cs.backgroundColor);
      if ((!c || c.a === 0) && cs.backgroundImage && cs.backgroundImage.includes("gradient")) {
        const m = cs.backgroundImage.match(/rgba?\([^)]+\)/g);
        if (m && m.length) c = rgba(m[0]);
      }
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
      node = node.parentElement;
    }
    let acc = { r: 10, g: 12, b: 16, a: 1 };          // фон страницы по умолчанию
    for (let i = stack.length - 1; i >= 0; i--) acc = over(stack[i], acc);
    return acc;
  }

  const bad = [];
  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || parseFloat(cs.opacity) < 0.15) continue;
    if (cs.webkitTextStrokeWidth && parseFloat(cs.webkitTextStrokeWidth) > 0.5) continue;
    const txt = [...el.childNodes].filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim()).join(" ").trim();
    if (txt.length < 2) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 4 || box.height < 4) continue;
    const fg = rgba(cs.color);
    if (!fg || fg.a < 0.15) continue;
    const bg = bgOf(el);
    const fgC = over(fg, bg);
    const l1 = lum(fgC), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    if (ratio < 2.2) {
      bad.push({ text: txt.slice(0, 40), ratio: +ratio.toFixed(2),
                 color: `${Math.round(fgC.r)},${Math.round(fgC.g)},${Math.round(fgC.b)}`,
                 background: `${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)}`,
                 class: String(el.className).slice(0, 40) });
    }
  }
  console.table(bad);
  return bad;
})();
