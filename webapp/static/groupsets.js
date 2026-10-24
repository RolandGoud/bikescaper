// Groupsets page.
// Lines: every system (the groupsets that share parts) is a coloured line through its tiles, like a metro map,
// yours drawn bold. Each tile's main line goes to the closest in age in the next step up; its other links on the
// same system there are dotted, as are the links between generations of one series on the same line. A tile
// gets a bullet only where a line comes in, and clicking a line picks the tile it leads to. With "Easiest route" on, an
// accent-coloured line runs from yours through the route's tiles.
// Navigation: picking a groupset, brand, type or view fetches the new page and morphs into it (View
// Transitions where the browser has them), keeping the tile you clicked where it was. Without JavaScript the
// links and form just load the page.
(() => {
  const main = document.querySelector("main.page");
  if (!main) return;
  // Line colours that stay clear of the emerald accent, which is kept for the route.
  const METRO = ["#FF8A5C", "#7C8CFF", "#F2C27A", "#C792EA", "#FF8F86", "#6CC4FF", "#E6A1C8", "#9A9CA6"];
  const css = getComputedStyle(document.documentElement);
  const ROUTE = css.getPropertyValue("--accent").trim() || "#34D399";
  const DOT = css.getPropertyValue("--card").trim() || "#fff";
  const NS = "http://www.w3.org/2000/svg";
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  const tiles = (section) => [...section.querySelectorAll(".ladder")].flatMap((ladder, l) =>
    [...ladder.querySelectorAll(".step")].flatMap((step, s) =>
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

  // Down the left edge from one generation to a newer one of the same series on the same line.
  const bracket = (a, b) => `M${a.l},${a.y} C${a.l - 18},${a.y} ${b.l - 18},${b.y} ${b.l},${b.y}`;

  const path = (svg, d, color, width, opacity, cls, dotted) => {
    const p = document.createElementNS(NS, "path");
    Object.entries({ d, fill: "none", stroke: color, "stroke-width": width, "stroke-linecap": "round",
                     "stroke-opacity": opacity }).forEach(([k, v]) => p.setAttribute(k, v));
    if (dotted) p.setAttribute("stroke-dasharray", `0 ${width * 2.4}`);
    if (cls) p.classList.add(cls);
    svg.append(p);
    return p;
  };

  // A wide invisible stroke over a line, so clicking the line picks the tile it leads to.
  const hit = (svg, d, to) => {
    const p = document.createElementNS(NS, "path");
    Object.entries({ d, fill: "none", stroke: "transparent", "stroke-width": 12 }).forEach(([k, v]) => p.setAttribute(k, v));
    p.classList.add("line-hit");
    p.dataset.href = to.el.href;
    p.dataset.key = to.el.dataset.key;
    p.append(Object.assign(document.createElementNS(NS, "title"), { textContent: to.el.querySelector(".gen-name").textContent }));
    svg.append(p);
  };

  const dot = (svg, x, y, color) => {
    const c = document.createElementNS(NS, "circle");
    Object.entries({ cx: x, cy: y, r: 4, fill: DOT, stroke: color, "stroke-width": 2.5 })
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
        // Each tile links to the one in the next step up on the same line that's closest in age (the main line)
        // and, dotted, to the others on that line in the same step.
        const fed = new Set();
        on.forEach((t) => {
          const next = on.filter((n) => n.ladder === t.ladder && n.step > t.step);
          if (!next.length) return;
          const step = Math.min(...next.map((n) => n.step));
          const there = next.filter((n) => n.step === step);
          const closest = there.reduce((best, n) => (Math.abs(n.year - t.year) < Math.abs(best.year - t.year) ? n : best));
          there.filter((n) => n !== closest).forEach((n) => {
            const d = curve(box(t, origin), box(n, origin));
            path(svg, d, color, 2, opacity * 0.8, null, true);
            hit(svg, d, n);
            fed.add(n);
          });
          const d = curve(box(t, origin), box(closest, origin));
          path(svg, d, color, mine && !routeOn ? 5 : 2.5, opacity);
          hit(svg, d, closest);
          fed.add(closest);
        });
        // Generations of one series on the same line: each to the next one down the column, dotted.
        on.forEach((t, k) => {
          const below = on.slice(k + 1).find((n) => n.ladder === t.ladder && n.step === t.step);
          if (!below) return;
          const d = bracket(box(t, origin), box(below, origin));
          path(svg, d, color, 2, opacity * 0.8, null, true);
          hit(svg, d, below);
          fed.add(below);
        });
        on.forEach((t) => {
          if (fed.has(t)) {
            const b = box(t, origin);
            dot(svg, b.l, b.y, color);
          }
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
    const line = e.target.closest(".line-hit");
    if (line && plain(e)) {
      show(line.dataset.href.split("#")[0], true, line.dataset.key);
      return;
    }
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
