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

// The report's gallery: the strip and the arrows pick the photo shown big (a click on it opens the lightbox,
// lightbox.js), with a "3 / 8" counter. Without JS the strip's links open the photos themselves.
document.querySelectorAll(".ad-gallery").forEach((gallery) => {
  const box = document.querySelector("dialog.lightbox");
  const links = [...gallery.querySelectorAll(".ad-photos [data-photo]")];
  const photos = box ? JSON.parse(box.dataset.photos) : links.map((a) => a.href);
  const big = gallery.querySelector(".ag-photo"), img = big.querySelector("img");
  const count = gallery.querySelector(".ag-count");
  const show = (i) => {
    const at = (i + photos.length) % photos.length;
    big.dataset.at = at;
    img.src = photos[at];
    img.alt = img.alt.replace(/\d+/, at + 1);
    count.textContent = `${at + 1} / ${photos.length}`;
    links.forEach((a, j) => {
      if (j === at) {
        a.setAttribute("aria-current", "true");
        const strip = a.parentElement, x = a.offsetLeft - strip.offsetLeft;  // bring it into view, not the page
        if (x < strip.scrollLeft || x + a.offsetWidth > strip.scrollLeft + strip.clientWidth)
          strip.scrollTo({ left: x - 8, behavior: "smooth" });
      } else a.removeAttribute("aria-current");
    });
    [at + 1, at - 1].forEach((j) => { new Image().src = photos[(j + photos.length) % photos.length]; });
  };
  links.forEach((a, j) => a.addEventListener("click", (e) => { e.preventDefault(); show(j); }));
  gallery.querySelector(".gallery-arrow.prev")?.addEventListener("click", () => show(Number(big.dataset.at) - 1));
  gallery.querySelector(".gallery-arrow.next")?.addEventListener("click", () => show(Number(big.dataset.at) + 1));
});
