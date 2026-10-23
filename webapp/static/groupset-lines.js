// Groupsets page: lines between the generation tiles, drawn in an SVG over each brand's ladders.
// Prototype with three styles, picked by ?lines=a|b|c:
//   a  spokes: from your groupset to every upgrade, coloured by how much has to change
//   b  route:  one line through the easiest upgrade in each step up from yours
//   c  metro:  every system as its own line through the groupsets it shares parts with
(() => {
  const style = new URLSearchParams(location.search).get("lines") || "c";
  const COLORS = { 1: "#1E8A4C", 2: "#2B3BFF", 3: "#1A24B3", 4: "#D9822B", no: "#A3241B" };
  const METRO = ["#FF5A1F", "#2B3BFF", "#1E8A4C", "#9B3BD1", "#D9822B", "#0E9AA7", "#C2185B", "#6D6D7A"];
  const NS = "http://www.w3.org/2000/svg";

  const tiles = (section) => [...section.querySelectorAll(".ladder")].flatMap((ladder, l) =>
    [...ladder.children].flatMap((step, s) =>
      [...step.querySelectorAll(".gen")].map((el) => ({ el, ladder: l, step: s, system: el.dataset.system,
        effort: el.dataset.effort, fit: el.dataset.fit, year: +el.dataset.year, here: el.classList.contains("here") }))));

  const box = (t, origin) => {
    const r = t.el.getBoundingClientRect();
    return { l: r.left - origin.left, r: r.right - origin.left, y: r.top - origin.top + r.height / 2,
             t: r.top - origin.top, b: r.bottom - origin.top, cx: r.left - origin.left + r.width / 2 };
  };

  // A smooth line from the right edge of one tile to the left edge of the next; down and round when stacked.
  const curve = (a, b) => {
    if (b.l > a.r - 4) {
      const dx = Math.max(24, (b.l - a.r) / 2);
      return `M${a.r},${a.y} C${a.r + dx},${a.y} ${b.l - dx},${b.y} ${b.l},${b.y}`;
    }
    const x = Math.max(a.r, b.r) + 10;  // same column or to the left: loop out to the right
    return `M${a.r},${a.y} C${x + 20},${a.y} ${x + 20},${b.y} ${b.r},${b.y}`;
  };

  const line = (svg, d, color, width, opts = {}) => {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d);
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", color);
    p.setAttribute("stroke-width", width);
    p.setAttribute("stroke-linecap", "round");
    if (opts.dash) p.setAttribute("stroke-dasharray", opts.dash);
    if (opts.opacity) p.setAttribute("stroke-opacity", opts.opacity);
    svg.append(p);
  };

  const dot = (svg, x, y, color) => {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", 4);
    c.setAttribute("fill", "#fff"); c.setAttribute("stroke", color); c.setAttribute("stroke-width", 2.5);
    svg.append(c);
  };

  const draw = () => {
    document.querySelectorAll(".path-lines").forEach((s) => s.remove());
    if (matchMedia("(max-width: 640px)").matches) return;  // the ladders stack on phones
    document.querySelectorAll(".brand-ladders").forEach((section) => {
      const origin = section.getBoundingClientRect();
      const svg = document.createElementNS(NS, "svg");
      svg.classList.add("path-lines");
      svg.setAttribute("width", origin.width);
      svg.setAttribute("height", origin.height);
      svg.setAttribute("aria-hidden", "true");
      const all = tiles(section), here = all.find((t) => t.here);

      if (style === "a" && here) {
        const a = box(here, origin);
        all.filter((t) => t.effort && t.ladder === here.ladder).forEach((t) => {
          const b = box(t, origin);
          line(svg, curve(a, b), COLORS[t.fit === "no" ? "no" : t.effort], t.fit === "no" ? 1.5 : 2.5,
               { dash: t.fit === "no" ? "4 5" : t.fit === "check" ? "8 4" : null, opacity: t.fit === "no" ? 0.6 : 0.9 });
        });
      }

      if (style === "b" && here) {
        // In each step up, the upgrade that fits with the least work (the newest on a tie).
        let prev = here;
        const steps = [...new Set(all.filter((t) => t.ladder === here.ladder && t.step > here.step).map((t) => t.step))];
        steps.sort((x, y) => x - y).forEach((s) => {
          const pick = all.filter((t) => t.ladder === here.ladder && t.step === s && t.effort && t.fit !== "no")
            .sort((x, y) => x.effort - y.effort || (x.fit === "check") - (y.fit === "check"))
            .reduce((best, t) => (!best || t.effort < best.effort ? t : best), null);
          if (!pick) return;
          line(svg, curve(box(prev, origin), box(pick, origin)), "#FF5A1F", 4);
          pick.el.classList.add("on-route");
          prev = pick;
        });
        here.el.classList.add("on-route");
      }

      if (style === "c") {
        // Every system as a line, left to right through the groupsets it runs on: yours bold, the rest thin.
        const systems = [...new Set(all.map((t) => t.system))];
        systems.forEach((system, i) => {
          const on = all.filter((t) => t.system === system);
          const mine = here && here.system === system;
          const color = METRO[i % METRO.length];
          // Each tile links to the one in the next step up on the same line that's closest in age.
          on.forEach((t) => {
            const next = on.filter((n) => n.ladder === t.ladder && n.step > t.step);
            if (!next.length) return;
            const step = Math.min(...next.map((n) => n.step));
            const to = next.filter((n) => n.step === step)
              .reduce((best, n) => (Math.abs(n.year - t.year) < Math.abs(best.year - t.year) ? n : best));
            line(svg, curve(box(t, origin), box(to, origin)), color, mine ? 5 : 2.5,
                 { opacity: here && !mine ? 0.35 : 0.9 });
          });
          on.forEach((t) => { const b = box(t, origin); dot(svg, b.l, b.y, color); t.el.style.setProperty("--line", color); });
        });
      }
      section.append(svg);
    });
  };

  addEventListener("load", draw);
  addEventListener("resize", () => requestAnimationFrame(draw));
  document.querySelectorAll(".ladder").forEach((l) => l.addEventListener("scroll", draw, { passive: true }));
})();
