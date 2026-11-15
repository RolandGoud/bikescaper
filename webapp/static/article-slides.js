// Stolen-bike articles on the home page: one slide in view, in a row that scrolls and snaps. This adds the
// dots, the arrows (they wrap round: after the last comes the first) and the "up next" line under the slide.
// Without JS the row just scrolls.
document.querySelectorAll(".article-slides").forEach((box) => {
  const track = box.querySelector(".as-track");
  const slides = [...track.children];
  const ctrl = box.querySelector(".as-ctrl"), dots = [...ctrl.querySelectorAll(".as-dots button")];
  const upnext = box.querySelector(".as-upnext"), upnextBtn = upnext.querySelector("button");
  if (slides.length < 2) return;
  ctrl.hidden = upnext.hidden = false;
  track.classList.add("paged");

  const current = () => Math.round(track.scrollLeft / track.clientWidth);
  const go = (i) => {
    i = (i + slides.length) % slides.length;
    track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" });
  };
  let shown = 0;  // the slide in view, kept so a resize can put it back in place
  const update = () => {
    const i = shown = Math.min(current(), slides.length - 1);
    dots.forEach((d, k) => d.setAttribute("aria-current", k === i ? "true" : "false"));
    upnextBtn.textContent = slides[(i + 1) % slides.length].querySelector("h3").textContent;
  };

  dots.forEach((d, k) => d.addEventListener("click", () => go(k)));
  ctrl.querySelector(".as-prev").addEventListener("click", () => go(current() - 1));
  ctrl.querySelector(".as-next").addEventListener("click", () => go(current() + 1));
  upnextBtn.addEventListener("click", () => go(current() + 1));
  track.addEventListener("keydown", (e) => {
    if (e.target !== track) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(current() + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); go(current() - 1); }
  });
  track.addEventListener("scroll", update, { passive: true });
  // after a resize the old scroll position can sit between two slides: line the slide that was in view up again
  window.addEventListener("resize", () => { track.scrollTo({ left: shown * track.clientWidth, behavior: "instant" }); update(); });
  update();
});
