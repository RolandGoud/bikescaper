// Groupsets page.
// Lines: every system (the groupsets that share parts) is a coloured line through its tiles, like a metro map,
// yours drawn bold. With "Easiest route" on, an orange line runs from yours through the route's tiles.
// Navigation: picking a groupset, brand, type or view fetches the new page and morphs into it (View
// Transitions where the browser has them), keeping the tile you clicked where it was. Without JavaScript the
// links and form just load the page.
(() => {
  const main = document.querySelector("main.page");
  if (!main) return;
  const METRO = ["#FF5A1F", "#2B3BFF", "#1E8A4C", "#9B3BD1", "#D9822B", "#0E9AA7", "#C2185B", "#6D6D7A"];
  const ROUTE = "#FF5A1F";
  const NS = "http://www.w3.org/2000/svg";
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  const tiles = (section) => [...section.querySelectorAll(".ladder")].flatMap((ladder, l) =>
    [...ladder.children].flatMap((step, s) =>
      [...step.querySelectorAll(".gen")].map((el) => ({ el, ladder: l, step: s, system: el.dataset.system,
        year: +el.dataset.year, route: el.dataset.route, here: el.classList.contains("here") }))));

  const box = (t, origin) => {
    const r = t.el.getBoundingClientRect();
    return { l: r.left - origin.left, r: r.right - origin.left, y: r.top - origin.top + r.height / 2 };
  };

  // From the right edge of one tile to the left edge of the next step's tile.
  const curve = (a, b) => {
    const dx = Math.max(18, (b.l - a.r) / 2);
    return `M${a.r},${a.y} C${a.r + dx},${a.y} ${b.l - dx},${b.y} ${b.l},${b.y}`;
  };

  const path = (svg, d, color, width, opacity, cls) => {
    const p = document.createElementNS(NS, "path");
    Object.entries({ d, fill: "none", stroke: color, "stroke-width": width, "stroke-linecap": "round",
                     "stroke-opacity": opacity }).forEach(([k, v]) => p.setAttribute(k, v));
    if (cls) p.classList.add(cls);
    svg.append(p);
    return p;
  };

  const dot = (svg, x, y, color) => {
    const c = document.createElementNS(NS, "circle");
    Object.entries({ cx: x, cy: y, r: 4, fill: "#fff", stroke: color, "stroke-width": 2.5 })
      .forEach(([k, v]) => c.setAttribute(k, v));
    svg.append(c);
  };

  const draw = (animate) => {
    main.querySelectorAll(".path-lines").forEach((s) => s.remove());
    if (matchMedia("(max-width: 640px)").matches) return;  // the ladders stack on phones
    const routeOn = !!main.querySelector(".segmented a.on[href*='show=route']");
    main.querySelectorAll(".brand-ladders").forEach((section) => {
      const origin = section.getBoundingClientRect();
      const svg = document.createElementNS(NS, "svg");
      svg.classList.add("path-lines");
      svg.setAttribute("width", origin.width);
      svg.setAttribute("height", origin.height);
      svg.setAttribute("aria-hidden", "true");
      const all = tiles(section), here = all.find((t) => t.here);

      [...new Set(all.map((t) => t.system))].forEach((system, i) => {
        const on = all.filter((t) => t.system === system);
        const mine = here && here.system === system;
        const color = METRO[i % METRO.length];
        const opacity = routeOn ? 0.2 : here && !mine ? 0.35 : 0.9;
        // Each tile links to the one in the next step up on the same line that's closest in age.
        on.forEach((t) => {
          const next = on.filter((n) => n.ladder === t.ladder && n.step > t.step);
          if (!next.length) return;
          const step = Math.min(...next.map((n) => n.step));
          const to = next.filter((n) => n.step === step)
            .reduce((best, n) => (Math.abs(n.year - t.year) < Math.abs(best.year - t.year) ? n : best));
          path(svg, curve(box(t, origin), box(to, origin)), color, mine && !routeOn ? 5 : 2.5, opacity);
        });
        on.forEach((t) => {
          const b = box(t, origin);
          dot(svg, b.l, b.y, color);
          t.el.style.setProperty("--line", routeOn ? "" : color);
        });
      });

      if (routeOn && here) {
        const stops = [here, ...all.filter((t) => t.route !== undefined).sort((a, b) => a.route - b.route)];
        stops.slice(1).forEach((t, k) => {
          const p = path(svg, curve(box(stops[k], origin), box(t, origin)), ROUTE, 5, 1, "route-line");
          if (animate && !still.matches) {  // draw the route out from yours, one step after the other
            const len = p.getTotalLength();
            p.style.strokeDasharray = len;
            p.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
                      { duration: 380, delay: 200 + k * 300, easing: "ease-out", fill: "backwards" });
          }
        });
      }
      section.prepend(svg);
    });
  };

  // In-place navigation.
  let latest = 0;
  const show = async (url, push, anchorKey) => {
    const ticket = ++latest;
    let next;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.status);
      next = new DOMParser().parseFromString(await res.text(), "text/html");
      if (!next.querySelector("main.page")) throw new Error("no page");
    } catch {
      if (ticket === latest) location.href = url;
      return;
    }
    if (ticket !== latest) return;
    // Keep the clicked tile (or the results card) where it was on screen.
    const anchorOf = (root) => (anchorKey && root.querySelector(`.gen[data-key="${anchorKey}"]`)) || root.querySelector("#paths");
    const before = anchorOf(main)?.getBoundingClientRect().top;
    const swap = () => {
      main.replaceChildren(...next.querySelector("main.page").childNodes);
      const langs = document.querySelector(".lang-switch"), newLangs = next.querySelector(".lang-switch");
      if (langs && newLangs) langs.replaceWith(newLangs);
      document.title = next.title;
      if (push) history.pushState(null, "", url);
      const after = anchorOf(main)?.getBoundingClientRect().top;
      if (before !== undefined && after !== undefined) scrollBy(0, after - before);
      else if (!anchorKey && main.querySelector("#paths")) main.querySelector("#paths").scrollIntoView({ block: "start" });
      draw(true);
    };
    if (document.startViewTransition && !still.matches) document.startViewTransition(swap);
    else swap();
  };

  const plain = (e) => !(e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey);
  main.addEventListener("click", (e) => {
    const link = e.target.closest("a.gen, .logo-pills a, .segmented a, .path-card > a, .filter-row > a, .route + p a");
    if (!link || !plain(e)) return;
    e.preventDefault();
    const key = link.matches("a.gen") ? new URL(link.href).searchParams.get("have") : null;
    show(link.href.split("#")[0], true, key);
  });
  main.addEventListener("submit", (e) => {
    const form = e.target.closest("form.filter-row");
    if (!form) return;
    e.preventDefault();
    show(location.pathname + "?" + new URLSearchParams(new FormData(form)), true);
  });
  addEventListener("popstate", () => show(location.href, false));

  addEventListener("load", () => draw(true));
  addEventListener("resize", () => requestAnimationFrame(() => draw(false)));
  document.fonts?.ready.then(() => draw(false));
})();
