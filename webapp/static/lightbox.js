// Ad photos on the report: a click opens them full size; arrows, keys or a swipe flip through them.
(() => {
  const box = document.querySelector("dialog.lightbox");
  if (!box || !box.showModal) return;  // no <dialog>: the links just open the photo
  const photos = JSON.parse(box.dataset.photos);
  const img = box.querySelector("img"), count = box.querySelector(".lb-count");
  let at = 0;

  const show = (i) => {
    at = (i + photos.length) % photos.length;
    img.src = photos[at];
    img.alt = count.textContent = box.dataset.label.replace("{n}", at + 1).replace("{total}", photos.length);
    // warm up the neighbours so flipping feels instant
    [at + 1, at - 1].forEach((j) => { new Image().src = photos[(j + photos.length) % photos.length]; });
  };

  document.querySelectorAll(".ad-photos [data-photo]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      show(Number(link.dataset.photo));
      box.showModal();
    });
  });
  box.querySelector(".lb-prev").addEventListener("click", () => show(at - 1));
  box.querySelector(".lb-next").addEventListener("click", () => show(at + 1));
  box.querySelector(".lb-close").addEventListener("click", () => box.close());
  if (photos.length < 2) box.querySelectorAll(".lb-prev, .lb-next").forEach((b) => (b.hidden = true));

  box.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") show(at - 1);
    else if (e.key === "ArrowRight") show(at + 1);
  });  // Esc closes a <dialog> by itself
  box.addEventListener("click", (e) => { if (e.target === box) box.close(); });  // click beside the photo

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
