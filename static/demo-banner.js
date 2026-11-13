(() => {
  "use strict";

  const banner = document.querySelector(".demo-bar");
  const close = banner?.querySelector(".demo-bar-close");
  if (!banner || !close) return;

  try {
    if (sessionStorage.getItem("demo-banner-dismissed") === "1") {
      banner.hidden = true;
    }
  } catch (_) {
    // If storage is unavailable, keep the banner visible and still allow closing it.
  }

  close.addEventListener("click", () => {
    banner.hidden = true;
    try {
      sessionStorage.setItem("demo-banner-dismissed", "1");
    } catch (_) {
      // Closing still works for the current page if storage is unavailable.
    }
  });
})();
