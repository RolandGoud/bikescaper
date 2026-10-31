// Admin page: the charts switch between the overall bars and a line per week or month.
(() => {
  const data = JSON.parse(document.getElementById("admin-data").textContent);
  const COLOURS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
  const W = 520, H = 220, L = 36, R = 12, T = 12, B = 28;
  const svg = (tag, attrs) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  };

  const draw = (box, view) => {
    const kind = box.dataset.chart, unit = box.dataset.unit, periods = data[view];
    const labels = data.labels[kind], keys = data.keys[kind];
    box.replaceChildren();
    if (periods.length < 2) {
      box.textContent = periods.length ? `${periods[0].label}: ${data.ads.replace("{n}", periods[0].ads)}` : "—";
      box.className = "view-lines muted small";
      return;
    }
    box.className = "view-lines";
    const most = Math.max(...periods.flatMap((p) => keys.map((k) => p[kind][k])));
    const top = unit ? 100 : Math.max(2, Math.ceil(most / 2) * 2);  // whole numbers on the axis for counts
    const x = (i) => L + (i * (W - L - R)) / (periods.length - 1);
    const y = (v) => T + (H - T - B) * (1 - v / top);
    const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "line-chart", role: "img" });
    for (const v of [0, top / 2, top]) {
      chart.append(svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "grid" }));
      const t = svg("text", { x: L - 6, y: y(v) + 4, class: "axis", "text-anchor": "end" });
      t.textContent = `${Math.round(v)}${unit}`;
      chart.append(t);
    }
    const every = Math.ceil(periods.length / 6);
    periods.forEach((p, i) => {
      const last = i === periods.length - 1;
      if ((i % every && !last) || (!last && periods.length - 1 - i < every)) return;
      const t = svg("text", { x: x(i), y: H - 8, class: "axis", "text-anchor": last ? "end" : i ? "middle" : "start" });
      t.textContent = p.label;
      chart.append(t);
    });
    keys.forEach((k, s) => {
      const d = periods.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p[kind][k])}`).join("");
      chart.append(svg("path", { d, fill: "none", stroke: COLOURS[s], "stroke-width": 2, "stroke-linejoin": "round" }));
    });
    const cross = svg("line", { y1: T, y2: H - B, class: "cross", visibility: "hidden" });
    chart.append(cross);
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    chart.addEventListener("pointermove", (e) => {
      const r = chart.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(periods.length - 1, Math.round(((px - L) / (W - L - R)) * (periods.length - 1))));
      const p = periods[i];
      cross.setAttribute("x1", x(i));
      cross.setAttribute("x2", x(i));
      cross.setAttribute("visibility", "visible");
      tip.innerHTML = `<b>${p.label}</b> · ${data.ads.replace("{n}", p.ads)}` + keys.map((k, s) =>
        `<div><i style="background:${COLOURS[s]}"></i>${labels[k]} <span>${p[kind][k]}${unit}</span></div>`).join("");
      tip.hidden = false;
      tip.style.left = `${Math.min((x(i) / W) * r.width + 12, r.width - 200)}px`;
    });
    chart.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; });
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    legend.innerHTML = keys.map((k, s) => `<span><i style="background:${COLOURS[s]}"></i>${labels[k]}</span>`).join("");
    box.append(chart, tip, legend);
  };

  const pills = document.querySelectorAll("[data-admin-view] [data-view]");
  pills.forEach((pill) => pill.addEventListener("click", () => {
    const view = pill.dataset.view;
    pills.forEach((p) => { p.classList.toggle("on", p === pill); p.setAttribute("aria-pressed", p === pill); });
    document.querySelectorAll(".admin .view-total").forEach((el) => { el.hidden = view !== "total"; });
    document.querySelectorAll(".admin .view-lines").forEach((el) => {
      el.hidden = view === "total";
      if (view !== "total") draw(el, view);
    });
  }));
})();
