// Models page: a filter change fetches the new list and swaps it in without a page reload.
// Cards that stay glide to their new spot, cards that drop out fade where they were, new ones
// fade in (FLIP). Only cards on screen animate. The address still updates, so back and sharing
// work; with reduced motion the list just swaps; without JavaScript the filters reload the page.
(() => {
  const main = document.querySelector("main.page");
  if (!main || !window.fetch || !Element.prototype.animate) return;
  const still = matchMedia("(prefers-reduced-motion: reduce)");
  const ease = "cubic-bezier(.2, .7, .2, 1)";
  let latest = 0;

  const cards = () => [...main.querySelectorAll(".model-card")];
  const onScreen = (r) => r.bottom > 0 && r.top < innerHeight;

  // Which control had focus, so the same one has it again after the swap.
  const focusKey = () => {
    const el = document.activeElement;
    if (!main.contains(el)) return null;
    const pill = [...main.querySelectorAll(".logo-pills a")].indexOf(el);
    if (pill >= 0) return () => main.querySelectorAll(".logo-pills a")[pill];
    return el.name ? () => main.querySelector(`[name="${el.name}"]`) : null;
  };

  const swap = (next) => {
    document.querySelectorAll(".model-card.leaving").forEach((g) => g.remove());
    const refocus = focusKey(), y = scrollY;
    main.replaceChildren(...next.childNodes);
    scrollTo(0, y);  // keep the reader where they were; scroll anchoring would jump otherwise
    refocus?.()?.focus({ preventScroll: true });
  };

  const animateSwap = (next) => {
    const before = new Map(cards().map((c) => [c.getAttribute("href"), c.getBoundingClientRect()]));
    const ghosts = cards().filter((c) => onScreen(before.get(c.getAttribute("href")))).map((c) => {
      const r = before.get(c.getAttribute("href")), g = c.cloneNode(true);
      g.classList.add("leaving");
      g.setAttribute("aria-hidden", "true");
      Object.assign(g.style, { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
      return g;
    });
    swap(next);
    const staying = new Set(cards().map((c) => c.getAttribute("href")));
    ghosts.filter((g) => !staying.has(g.getAttribute("href"))).forEach((g) => {
      document.body.append(g);
      g.animate([{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(.85)" }],
        { duration: 220, easing: "ease-in", fill: "forwards" }).finished.then(() => g.remove(), () => g.remove());
    });
    cards().forEach((c) => {
      const old = before.get(c.getAttribute("href")), now = c.getBoundingClientRect();
      if (old && (onScreen(old) || onScreen(now))) {
        c.animate([{ transform: `translate(${old.left - now.left}px, ${old.top - now.top}px)` }, { transform: "none" }],
          { duration: 420, easing: ease });
      } else if (!old && onScreen(now)) {
        c.animate([{ opacity: 0, transform: "scale(.9)" }, { opacity: 1, transform: "none" }],
          { duration: 300, delay: 160, easing: ease, fill: "backwards" });
      }
    });
  };

  const show = async (url, push) => {
    const ticket = ++latest;
    let next;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.status);
      next = new DOMParser().parseFromString(await res.text(), "text/html").querySelector("main.page");
      if (!next) throw new Error("no list");
    } catch {
      location.href = url;  // fall back to a normal page load
      return;
    }
    if (ticket !== latest) return;  // a newer filter click won
    if (push) history.pushState(null, "", url);
    (still.matches ? swap : animateSwap)(next);
  };

  // Listen on <main>, which stays put, so the swapped-in pills and form need no rebinding.
  main.addEventListener("click", (e) => {
    const pill = e.target.closest(".logo-pills a");
    if (!pill || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    show(pill.href, true);
  });
  main.addEventListener("submit", (e) => {
    const form = e.target.closest("form.filter-row");
    if (!form) return;
    e.preventDefault();
    show(location.pathname + "?" + new URLSearchParams(new FormData(form)), true);
  });
  addEventListener("popstate", () => show(location.href, false));
})();
