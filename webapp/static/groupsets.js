// Groupsets page.
// Lines: every system (the groupsets that share parts) is a coloured line through its tiles, like a metro map: each
// tile links to every tile on its line in the next column, and down its column to the next generation of its series.
// Lines are dotted, except at most one bold line per gap between two columns: the connection you picked by clicking
// a line (click it again to drop it), or else the one on your groupset's way up, to the closest in age. A tile gets
// a bullet on each side where a line meets it. With "Easiest route" on, an accent-coloured line runs from yours
// through the route's tiles.
// Navigation: picking a groupset (a tile), brand or type fetches the new page and morphs into it (View
// Transitions where the browser has them), keeping the tile you clicked where it was. Without JavaScript the
// links just load the page.
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

  // A wide invisible stroke over a line, so it can be clicked.
  const hit = (svg, link, bold) => {
    const p = document.createElementNS(NS, "path");
    Object.entries({ d: link.d, fill: "none", stroke: "transparent", "stroke-width": 12 })
      .forEach(([k, v]) => p.setAttribute(k, v));
    p.classList.add("line-hit");
    p.dataset.gap = link.gap;
    p.dataset.id = link.id;
    p.dataset.bold = bold ? "1" : "";
    const name = (t) => t.el.querySelector(".gen-name").textContent;
    p.append(Object.assign(document.createElementNS(NS, "title"), { textContent: `${name(link.from)} → ${name(link.to)}` }));
    svg.append(p);
  };

  // The connection picked in each gap between columns (or down a column): gap -> link id, or null for none.
  // Picks last until the page changes.
  let picked = new Map();

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

      const colors = new Map([...new Set(all.map((t) => t.system))].map((system, i) => [system, METRO[i % METRO.length]]));
      const links = [];
      const link = (from, to, d, gap) => links.push({ from, to, d, gap, id: `${from.el.dataset.key}>${to.el.dataset.key}` });
      all.forEach((t, k) => {
        const on = all.filter((n) => n.system === t.system && n.ladder === t.ladder);
        const next = on.filter((n) => n.step > t.step);
        if (next.length) {
          const step = Math.min(...next.map((n) => n.step));
          next.filter((n) => n.step === step)
            .forEach((n) => link(t, n, curve(box(t, origin), box(n, origin)), `${t.ladder}:${t.step}>${step}`));
        }
        const below = all.slice(k + 1).find((n) => n.system === t.system && n.ladder === t.ladder && n.step === t.step);
        if (below) link(t, below, bracket(box(t, origin), box(below, origin)), `${t.ladder}:${t.step}`);
      });

      // The bold lines run up from yours: in each gap the line you picked, or else the one to the closest in age,
      // and on from wherever that line lands. In a gap off that way only a picked line is bold.
      const way = new Map();
      for (let t = here; t;) {
        const out = links.filter((l) => l.from === t && l.gap.includes(">"));
        if (!out.length) break;
        const gap = out[0].gap;
        const best = picked.has(gap)
          ? links.find((l) => l.id === picked.get(gap))
          : out.reduce((a, b) => (Math.abs(b.to.year - t.year) < Math.abs(a.to.year - t.year) ? b : a));
        way.set(gap, best ? best.id : null);
        t = best && best.to;
      }
      const bold = (l) => (way.has(l.gap) ? way.get(l.gap) : picked.get(l.gap)) === l.id;

      const ends = new Map();  // dots: "key:side" -> [x, y, colour]
      [...links.filter((l) => !bold(l)), ...links.filter(bold)].forEach((l) => {
        const color = colors.get(l.from.system), b = bold(l);
        path(svg, l.d, color, b ? 5 : 2, routeOn ? 0.2 : b ? 0.95 : 0.7, null, !b);
        const from = box(l.from, origin), to = box(l.to, origin), down = !l.gap.includes(">");
        ends.set(`${l.from.el.dataset.key}:${down ? "l" : "r"}`, [down ? from.l : from.r, from.y, color]);
        ends.set(`${l.to.el.dataset.key}:l`, [to.l, to.y, color]);
      });
      links.forEach((l) => hit(svg, l, bold(l)));
      ends.forEach(([x, y, color]) => dot(svg, x, y, color));
      all.forEach((t) => t.el.style.setProperty("--line", routeOn ? "" : colors.get(t.system)));

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
      picked = new Map();
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
    if (line) {  // make this the bold line in its gap, or drop it when it already is
      picked.set(line.dataset.gap, line.dataset.bold === "1" ? null : line.dataset.id);
      draw(false);
      return;
    }
    const link = e.target.closest("a.gen, .logo-pills a, .segmented a, .path-card > a, .clear-pick, .route + p a");
    if (!link || !plain(e)) return;
    e.preventDefault();
    const key = link.matches("a.gen") ? new URL(link.href).searchParams.get("have") : null;
    show(link.href.split("#")[0], true, key);
  });
  addEventListener("popstate", () => show(location.href, false));

  addEventListener("load", () => draw(true));
  addEventListener("resize", () => requestAnimationFrame(() => draw(false)));
  document.fonts?.ready.then(() => draw(false));
})();
