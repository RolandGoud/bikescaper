// Net gecheckt on the home page: one row of cards. The arrows next to the heading page through it,
// a page being the cards in view, and "1–4 / 12" says which ones those are. A swipe or a trackpad
// scrolls it too. Without JS the row just scrolls. A sponsored card isn't counted.
document.querySelectorAll(".recent-row").forEach((row) => {
  const nav = row.closest("section").querySelector(".row-nav");
  const prev = nav.querySelector(".row-prev"), next = nav.querySelector(".row-next");
  const count = nav.querySelector(".row-count");
  const cards = [...row.children].filter((c) => !c.classList.contains("sponsored-card"));

  const update = () => {
    const max = row.scrollWidth - row.clientWidth, at = row.scrollLeft;
    const paged = max > 2;  // everything fits: no arrows
    nav.hidden = !paged;
    row.classList.toggle("paged", paged);
    if (!paged) return;
    prev.disabled = at < 2;
    next.disabled = at > max - 2;
    const box = row.getBoundingClientRect();
    const seen = cards.map((c, i) => [i + 1, c.getBoundingClientRect()])
      .filter(([, r]) => r.left >= box.left - 4 && r.right <= box.right + 4).map(([n]) => n);
    if (!seen.length) return;
    const first = seen[0], last = seen[seen.length - 1];
    count.textContent = `${first === last ? first : `${first}–${last}`} / ${cards.length}`;
  };

  // a page is everything in view; snapping lines the next card up with the left edge
  const step = () => row.clientWidth + 16;
  prev.addEventListener("click", () => row.scrollBy({ left: -step(), behavior: "smooth" }));
  next.addEventListener("click", () => row.scrollBy({ left: step(), behavior: "smooth" }));
  row.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
  update();
});
