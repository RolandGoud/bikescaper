// Ad photos on the report: a click opens them full size; arrows, keys or a swipe flip through them.
// When there's a merged slider, it comes first, big and still draggable.
(() => {
  const box = document.querySelector("dialog.lightbox");
  if (!box || !box.showModal) return;  // no <dialog>: the links just open the photo
  const photos = JSON.parse(box.dataset.photos);
  const img = box.querySelector(":scope > img"), count = box.querySelector(".lb-count");
  const duo = box.querySelector(".lb-duo");
  const slides = (duo ? [null] : []).concat(photos);  // null: the slider
  const first = duo ? 1 : 0;  // where the ad's own photos start
  let at = 0, openedAt = 0;

  const show = (i) => {
    at = (i + slides.length) % slides.length;
    const isDuo = slides[at] === null;
    img.hidden = isDuo;
    if (duo) duo.hidden = !isDuo;
    if (!isDuo) img.src = slides[at];
    img.alt = count.textContent = isDuo ? box.dataset.duoLabel
      : box.dataset.label.replace("{n}", at - first + 1).replace("{total}", photos.length);
    // warm up the neighbours so flipping feels instant
    [at + 1, at - 1].forEach((j) => { const src = slides[(j + slides.length) % slides.length]; if (src) new Image().src = src; });
  };
  const open = (i, e) => { show(i); box.showModal(); openedAt = e.timeStamp; };

  document.querySelectorAll(".ad-photos [data-photo]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      open(Number(link.dataset.photo) + first, e);
    });
  });
  // "Compare photos" in the parts table opens the slider, or the first photo without one
  document.querySelectorAll(".open-photos").forEach((link) => {
    link.addEventListener("click", (e) => { e.preventDefault(); open(0, e); });
  });
  // the slider at the top opens the big one, unless the click ends a drag (duo.js)
  document.querySelector(".head-duo")?.addEventListener("click", (e) => { if (duo && !e.defaultPrevented) open(0, e); });
  box.querySelector(".lb-prev").addEventListener("click", () => show(at - 1));
  box.querySelector(".lb-next").addEventListener("click", () => show(at + 1));
  box.querySelector(".lb-close").addEventListener("click", () => box.close());
  if (slides.length < 2) box.querySelectorAll(".lb-prev, .lb-next").forEach((b) => (b.hidden = true));

  box.addEventListener("keydown", (e) => {
    if (e.target.classList.contains("duo-range")) return;  // the arrows slide the cut there
    if (e.key === "ArrowLeft") show(at - 1);
    else if (e.key === "ArrowRight") show(at + 1);
  });  // Esc closes a <dialog> by itself
  // A click beside the photo closes it, but not the second click of a double-click that opened it.
  box.addEventListener("click", (e) => { if (e.target === box && e.timeStamp - openedAt > 400) box.close(); });

  let startX = null;
  img.addEventListener("pointerdown", (e) => { startX = e.clientX; });
  img.addEventListener("pointerup", (e) => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    startX = null;
    if (Math.abs(dx) > 40) show(dx < 0 ? at + 1 : at - 1);
  });
  img.addEventListener("dragstart", (e) => e.preventDefault());
})();
