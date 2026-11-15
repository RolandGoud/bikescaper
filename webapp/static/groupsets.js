// Groupsets page.
// Lines: every system (the groupsets that share parts) is a coloured line through its tiles, like a metro map: each
// tile links to every tile on its line in the next column, and down its column to the next generation of its series.
// A tile at the end of its line links on to its upgrades on other systems in the nearest column that has any.
// Lines are dotted, except one connected bold path with at most one line per gap between two columns: by default
// your groupset's way up, to the closest in age column by column. Clicking a line keeps that line bold and re-picks
// the bold lines either side of it so the path runs through its tiles (to and from yours where it can); clicking a
// bold line clears the path. Lines down a column turn bold on their own when clicked. A tile gets
// a bullet on each side where a line meets it, and only the tiles on the bold path, up to a red X, take their line's colour; the
// other tiles and lines turn grey. A bold line to a groupset we advise against going to from the tile it starts
// at (a new freehub body on top of a whole new drivetrain) gets a red X halfway.
// Navigation: picking a groupset (a tile), brand or type fetches the new page and morphs into it (View
// Transitions where the browser has them), keeping the tile you clicked where it was. Without JavaScript the
// links just load the page.
(() => {
  const main = document.querySelector("main.page");
  if (!main) return;
  // Line colours that stay clear of the emerald accent, which marks yours.
  const METRO = ["#FF8A5C", "#7C8CFF", "#F2C27A", "#C792EA", "#FF8F86", "#6CC4FF", "#E6A1C8", "#9A9CA6"];
  const css = getComputedStyle(document.documentElement);
  const DOT = css.getPropertyValue("--card").trim() || "#fff";
  const RED = "#FF3B30";
  const GREY = "#4A4E58";  // lines off the bold path  // a true red, apart from the coral line colour and --bad
  const NS = "http://www.w3.org/2000/svg";
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  const tiles = (section) => [...section.querySelectorAll(".ladder")].flatMap((ladder, l) =>
    [...ladder.querySelectorAll(".step")].flatMap((step) =>
      [...step.querySelectorAll(".gen")].map((el) => ({ el, ladder: l, step: +step.dataset.col, system: el.dataset.system,
        year: +el.dataset.year, up: (el.dataset.up || "").split(" ").filter(Boolean),
        against: (el.dataset.against || "").split(" ").filter(Boolean), here: el.classList.contains("here") }))));

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
    const note = link.against ? ` · ${main.dataset.notAdvised || "Not advised"}` : "";
    p.append(Object.assign(document.createElementNS(NS, "title"), { textContent: `${name(link.from)} → ${name(link.to)}${note}` }));
    svg.append(p);
  };

  // The line the bold path was last built around (null: no path), and the lines picked down a column (gap -> id).
  // Both last until the page changes.
  let chosen, picked = new Map();

  const dot = (svg, x, y, color) => {
    const c = document.createElementNS(NS, "circle");
    Object.entries({ cx: x, cy: y, r: 4, fill: DOT, stroke: color, "stroke-width": 2.5 })
      .forEach(([k, v]) => c.setAttribute(k, v));
    svg.append(c);
  };

  // A red X on a card-coloured disc halfway along a line we advise against.
  const cross = (svg, d) => {
    const probe = document.createElementNS(NS, "path");
    probe.setAttribute("d", d);
    svg.append(probe);
    const { x, y } = probe.getPointAtLength(probe.getTotalLength() / 2);
    probe.remove();
    const g = document.createElementNS(NS, "g");
    g.classList.add("advise-x");
    const c = document.createElementNS(NS, "circle");
    Object.entries({ cx: x, cy: y, r: 10, fill: DOT, stroke: RED, "stroke-width": 1.5 }).forEach(([k, v]) => c.setAttribute(k, v));
    const s = 4.5;
    const x_ = document.createElementNS(NS, "path");
    Object.entries({ d: `M${x - s},${y - s} L${x + s},${y + s} M${x + s},${y - s} L${x - s},${y + s}`, stroke: RED,
                     "stroke-width": 3, "stroke-linecap": "round", fill: "none" }).forEach(([k, v]) => x_.setAttribute(k, v));
    g.append(c, x_);
    svg.append(g);
  };

  const draw = (animate) => {
    main.querySelectorAll(".path-lines").forEach((s) => s.remove());
    if (matchMedia("(max-width: 640px)").matches) {  // the ladders stack on phones: no lines, nothing greyed
      main.querySelectorAll(".gen.off-path").forEach((el) => el.classList.remove("off-path"));
      return;
    }
    main.querySelectorAll(".brand-ladders").forEach((section) => {
      const origin = section.getBoundingClientRect();
      const svg = document.createElementNS(NS, "svg");
      svg.classList.add("path-lines");
      svg.setAttribute("width", origin.width);
      svg.setAttribute("height", origin.height);
      svg.setAttribute("aria-hidden", "true");
      const all = tiles(section), here = all.find((t) => t.here);
      // A shaded band behind each tier column, from its tier label down to the bottom of the ladder.
      section.querySelectorAll(".ladder").forEach((ladder) => {
        const bottom = ladder.getBoundingClientRect().bottom - origin.top;
        ladder.querySelectorAll(":scope > .tier-span").forEach((t, i) => {
          const r = t.getBoundingClientRect(), band = document.createElementNS(NS, "rect");
          Object.entries({ x: r.left - origin.left - 16, y: r.top - origin.top - 10, width: r.width + 32,
                           height: bottom - r.top + origin.top + 16, rx: 16, class: `col-band${i % 2 ? " even" : ""}` })
            .forEach(([k, v]) => band.setAttribute(k, v));
          svg.append(band);
        });
      });
      // Between the shifting rows (mechanical, wired, wireless), level with each side label: the same thin line as
      // under the series logos, one per tier column.
      section.querySelectorAll(".ladder").forEach((ladder) => {
        const cols = [...ladder.querySelectorAll(":scope > .tier-span")].map((t) => t.getBoundingClientRect());
        ladder.querySelectorAll(".row-label:not(.row-0)").forEach((label) => {
          const y = label.getBoundingClientRect().top - origin.top - 8;
          cols.forEach((c) => {
            const rule = document.createElementNS(NS, "rect");
            Object.entries({ x: c.left - origin.left, y, width: c.width, height: 1, class: "row-rule" })
              .forEach(([k, v]) => rule.setAttribute(k, v));
            svg.append(rule);
          });
        });
      });

      const colors = new Map([...new Set(all.map((t) => t.system))].map((system, i) => [system, METRO[i % METRO.length]]));
      const links = [];
      const link = (from, to, d, gap) => links.push({ from, to, d, gap, id: `${from.el.dataset.key}>${to.el.dataset.key}`,
                                                      against: from.against.includes(to.el.dataset.key) });
      all.forEach((t, k) => {
        const on = all.filter((n) => n.system === t.system && n.ladder === t.ladder);
        const next = on.filter((n) => n.step > t.step);
        if (next.length) {
          const step = Math.min(...next.map((n) => n.step));
          next.filter((n) => n.step === step)
            .forEach((n) => link(t, n, curve(box(t, origin), box(n, origin)), `${t.ladder}:${t.step}>${step}`));
        } else if (t.up.length) {
          // The end of its own line: on to the nearest column's upgrades on other systems (R7100 to Ultegra Di2).
          const ups = all.filter((n) => n.ladder === t.ladder && n.step > t.step && t.up.includes(n.el.dataset.key));
          const step = Math.min(...ups.map((n) => n.step));
          ups.filter((n) => n.step === step)
            .forEach((n) => link(t, n, curve(box(t, origin), box(n, origin)), `${t.ladder}:${t.step}>${step}`));
        }
        const below = all.slice(k + 1).find((n) => n.system === t.system && n.ladder === t.ladder && n.step === t.step);
        if (below) link(t, below, bracket(box(t, origin), box(below, origin)), `${t.ladder}:${t.step}`);
      });

      // The bold path: out from the chosen line both ways (or up from yours), each step to the tile closest in age,
      // and back through yours when it can.
      // With a groupset picked, lines starting below it lead down, not up: they never join the bold path.
      const down = (l) => here && l.from.ladder === here.ladder && l.from.step < here.step;
      const across = links.filter((l) => l.gap.includes(">") && !down(l));
      const nearest = (ls, year, side) => ls.find((l) => l[side] === here)
        || ls.reduce((a, b) => (Math.abs(b[side].year - year) < Math.abs(a[side].year - year) ? b : a));
      const path_ = [];
      const start = chosen === undefined ? null : across.find((l) => l.id === chosen);
      if (start) {
        path_.push(start);
        for (let t = start.from, ins; (ins = across.filter((l) => l.to === t)).length; t = path_[0].from) {
          path_.unshift(nearest(ins, t.year, "from"));
        }
      }
      if (chosen === undefined || start) {
        for (let t = start ? start.to : here, outs; t && (outs = across.filter((l) => l.from === t)).length;
             t = path_[path_.length - 1].to) {
          path_.push(nearest(outs, t.year, "to"));
        }
      }
      const way = new Set(path_.map((l) => l.id));
      const bold = (l) => !down(l) && (l.gap.includes(">") ? way.has(l.id) : picked.get(l.gap) === l.id);

      const boldLinks = links.filter(bold);
      const ends = new Map();  // dots: "key:side" -> [x, y, colour]
      [...links.filter((l) => !bold(l)), ...links.filter(bold)].forEach((l) => {
        const b = bold(l), color = b || !boldLinks.length ? colors.get(l.from.system) : GREY;
        path(svg, l.d, color, b ? 5 : 2, b ? 0.95 : 0.7, null, !b);
        const from = box(l.from, origin), to = box(l.to, origin), down = !l.gap.includes(">");
        ends.set(`${l.from.el.dataset.key}:${down ? "l" : "r"}`, [down ? from.l : from.r, from.y, color]);
        ends.set(`${l.to.el.dataset.key}:l`, [to.l, to.y, color]);
      });
      links.filter((l) => !down(l)).forEach((l) => hit(svg, l, bold(l)));  // lines down aren't clickable
      ends.forEach(([x, y, color]) => dot(svg, x, y, color));
      links.filter((l) => l.against && bold(l)).forEach((l) => cross(svg, l.d));
      // Tiles take their line's colour only on the bold path (all of them while there is none), and only up to a
      // red X: the tiles past one are not a way we advise.
      // Up from yours when the path runs through it (not back down to the groupsets below it), else from its start.
      const throughYours = here && boldLinks.some((l) => l.from === here || l.to === here);
      const onPath = new Set(throughYours ? [here]
        : boldLinks.map((l) => l.from).filter((t) => !boldLinks.some((l) => l.to === t)));
      for (let grew = true; grew;) {
        grew = false;
        boldLinks.forEach((l) => {
          if (!l.against && onPath.has(l.from) && !onPath.has(l.to)) onPath.add(l.to), (grew = true);
        });
      }
      all.forEach((t) => (onPath.size && !onPath.has(t) ? t.el.style.removeProperty("--line")
        : t.el.style.setProperty("--line", colors.get(t.system))));
      // Everything off the bold path is greyed out, so the path stands out.
      const anyPath = new Set(boldLinks.flatMap((l) => [l.from, l.to]));
      all.forEach((t) => t.el.classList.toggle("off-path", anyPath.size > 0 && !anyPath.has(t) && !t.here));

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
      chosen = undefined;
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
      const on = line.dataset.bold === "1";
      if (line.dataset.gap.includes(">")) chosen = on ? null : line.dataset.id;
      else picked.set(line.dataset.gap, on ? null : line.dataset.id);
      draw(false);
      return;
    }
    const link = e.target.closest("a.gen, .brand-cards a, .bike-types a, .clear-pick");
    if (!link || !plain(e)) return;
    e.preventDefault();
    const key = link.matches("a.gen") ? link.dataset.key : null;  // keep the clicked tile in place, also when it clears
    show(link.href.split("#")[0], true, key);
  });
  addEventListener("popstate", () => show(location.href, false));

  addEventListener("load", () => draw(true));
  addEventListener("resize", () => requestAnimationFrame(() => draw(false)));
  document.fonts?.ready.then(() => draw(false));
})();
