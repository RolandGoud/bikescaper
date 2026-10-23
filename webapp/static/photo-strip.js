// The ad's photo strip on the report: arrows page through it instead of a scrollbar,
// with dots and a "3–8 / 8" counter below. Without JS the strip just scrolls.
document.querySelectorAll(".ad-strip").forEach((wrap) => {
  const strip = wrap.querySelector(".ad-photos");
  const prev = wrap.querySelector(".strip-prev"), next = wrap.querySelector(".strip-next");
  const dots = wrap.querySelector(".strip-dots");
  const items = [...strip.children];

  const update = () => {
    const width = strip.clientWidth, max = strip.scrollWidth - width, at = strip.scrollLeft;
    const paged = max > 2;  // everything fits: no arrows, no dots
    wrap.classList.toggle("paged", paged);
    prev.hidden = next.hidden = dots.hidden = !paged;
    if (!paged) return;
    prev.disabled = at < 2;
    next.disabled = at > max - 2;
    const pages = Math.ceil(strip.scrollWidth / width);
    const page = next.disabled ? pages - 1 : Math.round(at / width);
    // the photos wholly in view, counted from 1
    const left = strip.getBoundingClientRect().left;
    const seen = items.map((a, i) => [i + 1, a.getBoundingClientRect()])
      .filter(([, r]) => r.left >= left - 4 && r.right <= left + width + 4).map(([n]) => n);
    const range = seen.length ? `${seen[0]}–${seen[seen.length - 1]}` : "";
    dots.innerHTML = Array.from({ length: pages }, (_, i) => `<i${i === page ? ' class="on"' : ""}></i>`).join("") +
      `<span>${range} / ${items.length}</span>`;
  };

  // a page is most of the strip, so the last photo of one page shows again at the start of the next
  const step = () => strip.clientWidth * 0.8;
  prev.addEventListener("click", () => strip.scrollBy({ left: -step() }));
  next.addEventListener("click", () => strip.scrollBy({ left: step() }));
  strip.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
  strip.querySelectorAll("img").forEach((img) => img.addEventListener("load", update));  // widths settle as photos load
  update();
});
