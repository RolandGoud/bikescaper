// Live charts in the blog articles (webapp/blog.py LIVE). The page first shows the chart drawn by
// tools/build_blog_charts.py; this redraws it with the reader's own numbers, in the same classes and sizes.
(function () {
  "use strict";
  var W = 720, NS = "http://www.w3.org/2000/svg";
  var COLOURS = ["#34D399", "#7AB8FF", "#F2C27A", "#E7A0F0"];
  var WORDS = {
    nl: {title: "Waarde van een fiets van {p} nieuw", normal: "normaal gebruik", "like-new": "als nieuw", used: "gebruikt",
         damaged: "beschadigd", axis: "jaar oud · de band is de eerlijke prijs (±10%)", newprice: "nieuwprijs",
         pick: "{n} jaar: {lo} – {hi}", pick1: "1 jaar: {lo} – {hi}", pick0: "Dit jaar: {lo} – {hi}",
         show: "Toon", keep: "Minstens één fiets blijft zichtbaar"},
    en: {title: "Value of a bike that cost {p} new", normal: "normal use", "like-new": "like new", used: "used",
         damaged: "damaged", axis: "years old · the band is the fair price (±10%)", newprice: "new price",
         pick: "{n} years: {lo} – {hi}", pick1: "1 year: {lo} – {hi}", pick0: "This year: {lo} – {hi}",
         show: "Show", keep: "At least one bike stays visible"}
  };
  // webapp/checks.py check_value: 80% this year, then 75% and 12% off each further year; condition on top;
  // a bike ten years or older is never "like new".
  var CONDITION = {"": 1, "like-new": 1.05, used: 0.92, damaged: 0.6};
  function factor(age, condition) {
    var f = age === 0 ? 0.8 : 0.75 * Math.pow(0.88, age - 1);
    if (condition === "like-new" && age >= 10) condition = "";
    return f * (CONDITION[condition] || 1);
  }

  function eur(v, lang) {
    var s = Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, lang === "nl" ? "." : ",");
    return "€" + s;
  }
  function fill(text, vars) { return text.replace(/\{(\w+)\}/g, function (_, k) { return vars[k]; }); }
  function el(name, attrs, text) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function label(x, y, text, cls, anchor) {
    return el("text", {x: x.toFixed(1), y: y.toFixed(1), "class": cls || "lbl", "text-anchor": anchor || "start"}, text);
  }
  function niceMax(v) {
    var steps = [1000, 2000, 2500, 5000, 10000];
    for (var i = 0; i < steps.length; i++) if (v / steps[i] <= 6) return {max: Math.ceil(v / steps[i]) * steps[i], step: steps[i]};
    return {max: Math.ceil(v / 10000) * 10000, step: 10000};
  }
  function canvas(h, title) {
    var svg = el("svg", {viewBox: "0 0 " + W + " " + h, role: "img", "aria-label": title});
    svg.appendChild(el("title", {}, title));
    return svg;
  }

  // The value curve: new price, age and condition from the inputs above it.
  function valueCurve(fig) {
    var lang = fig.dataset.lang === "en" ? "en" : "nl", w = WORDS[lang];
    var box = fig.querySelector(".blog-live-svg");
    var inputs = fig.querySelector(".blog-live-inputs");
    var table = fig.closest(".blog-switch") && fig.closest(".blog-switch").querySelector(".blog-switch-table table");
    function num(name, lo, hi, dflt) {
      var v = parseFloat(inputs.querySelector("[name=" + name + "]").value);
      return isFinite(v) ? Math.min(hi, Math.max(lo, v)) : dflt;
    }
    function draw() {
      var price = num("new", 100, 30000, 5000), age = Math.round(num("age", 0, 15, 4));
      var condition = inputs.querySelector("[name=condition]").value;
      var last = Math.max(10, age), x0 = 70, x1 = W - 30, y0 = 40, y1 = 300;
      var scale = niceMax(price * Math.max(1, factor(0, condition) * 1.1));
      var sx = function (a) { return x0 + (x1 - x0) * a / last; };
      var sy = function (v) { return y1 - (y1 - y0) * v / scale.max; };
      var title = fill(w.title, {p: eur(price, lang)}) + ", " + w[condition || "normal"];
      var svg = canvas(y1 + 46, title);
      svg.appendChild(label(x0, 18, title, "cap"));
      for (var v = 0; v <= scale.max; v += scale.step) {
        svg.appendChild(el("line", {x1: x0, y1: sy(v), x2: x1, y2: sy(v), "class": "grid"}));
        svg.appendChild(label(x0 - 8, sy(v) + 4, v ? eur(v, lang) : "€0", "tick", "end"));
      }
      var pts = [];
      for (var a = 0; a <= last; a++) pts.push([a, price * factor(a, condition)]);
      var band = pts.map(function (p) { return sx(p[0]).toFixed(1) + "," + sy(p[1] * 1.1).toFixed(1); })
        .concat(pts.slice().reverse().map(function (p) { return sx(p[0]).toFixed(1) + "," + sy(p[1] * 0.9).toFixed(1); }));
      svg.appendChild(el("polygon", {points: band.join(" "), "class": "band"}));
      svg.appendChild(el("line", {x1: x0, y1: sy(price), x2: x1, y2: sy(price), "class": "ref"}));
      svg.appendChild(label(x1, sy(price) - 6, w.newprice, "tick", "end"));
      svg.appendChild(el("polyline", {points: pts.map(function (p) { return sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1); }).join(" "), "class": "line"}));
      var every = last > 10 ? 3 : 2;
      pts.forEach(function (p) {
        svg.appendChild(el("circle", {cx: sx(p[0]), cy: sy(p[1]), r: 4, "class": "dot"}));
        if (p[0] % every === 0 && Math.abs(p[0] - age) > 2)
          svg.appendChild(label(sx(p[0]) + (p[0] === 0 ? -4 : 0), sy(p[1]) - 12, eur(Math.round(p[1] / 10) * 10, lang), "val", p[0] === 0 ? "start" : "middle"));
        if (last <= 10 || p[0] % 1 === 0) svg.appendChild(label(sx(p[0]), y1 + 18, String(p[0]), "tick", "middle"));
      });
      // the reader's bike: a guide line, a big dot and the fair range
      var mid = price * factor(age, condition), lo = Math.round(mid * 0.9 / 10) * 10, hi = Math.round(mid * 1.1 / 10) * 10;
      var px = sx(age), py = sy(mid);
      svg.appendChild(el("line", {x1: px, y1: py, x2: px, y2: y1, "class": "pick-line"}));
      svg.appendChild(el("line", {x1: px, y1: sy(mid * 1.1), x2: px, y2: sy(mid * 0.9), "class": "pick-range"}));
      svg.appendChild(el("circle", {cx: px, cy: py, r: 8, "class": "pick-dot"}));
      var text = fill(age === 0 ? w.pick0 : age === 1 ? w.pick1 : w.pick, {n: age, lo: eur(lo, lang), hi: eur(hi, lang)});
      var right = px > (x0 + x1) / 2, tx = right ? px - 14 : px + 14, ty = Math.max(y0 + 6, sy(mid * 1.1) - 10);
      var tag = label(tx, ty, text, "pick-val", right ? "end" : "start");
      svg.appendChild(tag);
      svg.appendChild(label((x0 + x1) / 2, y1 + 38, w.axis, "tick", "middle"));
      box.replaceChildren(svg);
      // a plate behind the label so the line doesn't run through it
      try {
        var bb = tag.getBBox();
        svg.insertBefore(el("rect", {x: bb.x - 6, y: bb.y - 3, width: bb.width + 12, height: bb.height + 6, rx: 6, "class": "pick-plate"}), tag);
      } catch (e) { /* not rendered yet */ }
      if (table) updateTable(table, price, age, condition, lang);
    }
    inputs.addEventListener("input", draw);
    inputs.addEventListener("change", draw);
    draw();
  }

  // The table next to the value curve follows the same inputs: its share and value columns, and the row of the
  // reader's age marked.
  function updateTable(table, price, age, condition, lang) {
    table.querySelectorAll("tbody tr").forEach(function (row) {
      var cells = row.children, m = cells[0].textContent.match(/\d+/), a = m ? parseInt(m[0], 10) : 0;
      var f = factor(a, condition);
      if (cells.length >= 3) {
        cells[1].textContent = Math.round(f * 100) + "%";
        cells[2].textContent = eur(Math.round(price * f / 10) * 10, lang);
      }
      row.classList.toggle("is-picked", a === age);
    });
  }

  // New price per model year, one line per bike; the reader picks which bikes show.
  function priceYears(fig) {
    var lang = fig.dataset.lang === "en" ? "en" : "nl", w = WORDS[lang];
    var box = fig.querySelector(".blog-live-svg"), source = box.querySelector("svg[data-series]");
    if (!source) return;
    var data = JSON.parse(source.getAttribute("data-series"));
    var on = data.series.map(function () { return true; });
    var picker = document.createElement("div");
    picker.className = "blog-live-picks";
    picker.setAttribute("role", "group");
    picker.setAttribute("aria-label", w.show);
    data.series.forEach(function (s, k) {
      var lab = document.createElement("label"), box_ = document.createElement("input");
      box_.type = "checkbox"; box_.checked = true;
      lab.style.setProperty("--c", COLOURS[k % COLOURS.length]);
      lab.appendChild(box_);
      if (s.html) {  // brand and groupset logos, built by tools/build_blog_charts.py from webapp/blog.py with_logos
        var name = document.createElement("span");
        name.innerHTML = s.html;
        name.setAttribute("aria-label", s.label);
        lab.appendChild(name);
      } else lab.appendChild(document.createTextNode(s.label));
      box_.addEventListener("change", function () {
        on[k] = box_.checked;
        if (!on.some(Boolean)) { on[k] = box_.checked = true; lab.title = w.keep; }
        draw();
      });
      picker.appendChild(lab);
    });
    fig.insertBefore(picker, box);
    function draw() {
      var shown = data.series.map(function (s, k) { return {s: s, k: k}; }).filter(function (o) { return on[o.k]; });
      var years = [], top = 0;
      shown.forEach(function (o) { o.s.points.forEach(function (p) { years.push(p[0]); top = Math.max(top, p[1]); }); });
      var lo = Math.min.apply(null, years), hi = Math.max.apply(null, years);
      if (hi === lo) { lo -= 1; hi += 1; }
      var scale = niceMax(top * 1.08), x0 = 70, x1 = W - 40, y0 = 50, y1 = 290;
      var sx = function (y) { return x0 + (x1 - x0) * (y - lo) / (hi - lo); };
      var sy = function (v) { return y1 - (y1 - y0) * v / scale.max; };
      var svg = canvas(y1 + 30, data.title);
      svg.appendChild(label(x0, 18, data.title, "cap"));
      for (var v = 0; v <= scale.max; v += scale.step) {
        svg.appendChild(el("line", {x1: x0, y1: sy(v), x2: x1, y2: sy(v), "class": "grid"}));
        svg.appendChild(label(x0 - 8, sy(v) + 4, v ? eur(v, lang) : "€0", "tick", "end"));
      }
      for (var y = lo; y <= hi; y++) svg.appendChild(label(sx(y), y1 + 20, String(y), "tick", "middle"));
      var few = shown.length <= 2, taken = [], labels = [];
      // a price label goes above its dot, else below it, else (when both would cover another label) not at all
      function place(x, y, text, anchor) {
        var w = text.length * 7.6 + 6, left = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
        var tries = [y - 12, y + 22];
        for (var i = 0; i < tries.length; i++) {
          var box = {l: left, r: left + w, t: tries[i] - 13, b: tries[i] + 3};
          var clash = taken.some(function (o) { return box.l < o.r && box.r > o.l && box.t < o.b && box.b > o.t; });
          if (!clash) { taken.push(box); return label(x, tries[i], text, "val", anchor); }
        }
        return null;
      }
      // every dot is taken first, so no price label covers another bike's point
      shown.forEach(function (o) { o.s.points.forEach(function (p) {
        taken.push({l: sx(p[0]) - 7, r: sx(p[0]) + 7, t: sy(p[1]) - 7, b: sy(p[1]) + 7});
      }); });
      shown.forEach(function (o) {
        var c = COLOURS[o.k % COLOURS.length], pts = o.s.points;
        svg.appendChild(el("polyline", {points: pts.map(function (p) { return sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1); }).join(" "),
          "class": "yline", style: "stroke:" + c}));
        pts.forEach(function (p, i) {
          var dot = el("circle", {cx: sx(p[0]), cy: sy(p[1]), r: 5, "class": "ydot", style: "fill:" + c});
          dot.appendChild(el("title", {}, o.s.label + ", " + p[0] + ": " + eur(p[1], lang)));
          svg.appendChild(dot);
          // with one or two bikes every price gets its label; with more only the first and the last
          if (few || i === 0 || i === pts.length - 1) {
            var anchor = sx(p[0]) < x0 + 30 ? "start" : sx(p[0]) > x1 - 30 ? "end" : "middle";
            var tag = place(sx(p[0]), sy(p[1]), eur(p[1], lang), anchor);
            if (tag) labels.push(tag);
          }
        });
      });
      labels.forEach(function (t) { svg.appendChild(t); });  // on top of every line
      box.replaceChildren(svg);
    }
    draw();
  }

  // Where an asking price lands: the reader's price as a marker on the verdict zones.
  function priceZones(fig) {
    var lang = fig.dataset.lang === "en" ? "en" : "nl";
    var svg = fig.querySelector("svg[data-series]"), input = fig.querySelector("[name=asking]");
    if (!svg || !input) return;
    var d = JSON.parse(svg.getAttribute("data-series"));
    var mark = el("g", {"class": "zone-mark"});
    svg.appendChild(mark);
    function draw() {
      var v = Math.max(0, Math.min(d.vmax, parseFloat(input.value) || 0));
      var x = d.x0 + (d.x1 - d.x0) * v / d.vmax, zone = d.zones.filter(function (z) { return v >= z[0] && v < z[1]; })[0] || d.zones[d.zones.length - 1];
      mark.replaceChildren(
        el("line", {x1: x, y1: d.y - 4, x2: x, y2: d.y + 38, "class": "pick-line"}),
        el("path", {d: "M" + (x - 8) + "," + (d.y + 46) + " L" + (x + 8) + "," + (d.y + 46) + " L" + x + "," + (d.y + 36) + "Z", "class": "pick-plate"}));
      var tag = label(Math.max(d.x0 + 4, Math.min(d.x1 - 4, x)), d.y + 100, eur(v, lang) + ": " + zone[2],
        "pick-val", x < d.x0 + 120 ? "start" : x > d.x1 - 120 ? "end" : "middle");
      mark.appendChild(tag);
      try {
        var bb = tag.getBBox();
        mark.insertBefore(el("rect", {x: bb.x - 6, y: bb.y - 3, width: bb.width + 12, height: bb.height + 6, rx: 6, "class": "pick-plate"}), tag);
      } catch (e) { /* not rendered */ }
    }
    input.addEventListener("input", draw);
    draw();
  }

  // Winter bikes: the fair range after the reader's number of years.
  function winterValues(fig) {
    var svg = fig.querySelector("svg[data-series]"), input = fig.querySelector("[name=age]");
    if (!svg || !input) return;
    var d = JSON.parse(svg.getAttribute("data-series")), lang = fig.dataset.lang === "en" ? "en" : "nl";
    var sx = function (v) { return d.x0 + (d.x1 - d.x0) * v / d.vmax; };
    function draw() {
      var age = Math.max(1, Math.min(10, Math.round(parseFloat(input.value) || 4))), f = factor(age, "");
      svg.querySelectorAll("rect.band-bar[data-new]").forEach(function (r) {
        var p = parseFloat(r.dataset.new), lo = Math.round(p * f * 0.9 / 10) * 10, hi = Math.round(p * f * 1.1 / 10) * 10;
        r.setAttribute("x", sx(lo).toFixed(1));
        r.setAttribute("width", (sx(hi) - sx(lo)).toFixed(1));
        var tip = r.querySelector("title");
        if (tip) tip.textContent = eur(lo, lang) + " – " + eur(hi, lang);
      });
      svg.querySelectorAll("line.stem[data-new]").forEach(function (l) {
        l.setAttribute("x1", sx(Math.round(parseFloat(l.dataset.new) * f * 1.1 / 10) * 10).toFixed(1));
      });
      svg.querySelectorAll("[data-tpl]").forEach(function (t) { t.textContent = fill(t.dataset.tpl, {n: age}); });
    }
    input.addEventListener("input", draw);
    draw();
  }

  document.querySelectorAll(".blog-live").forEach(function (fig) {
    var kind = fig.dataset.live;
    if (kind === "value-curve") valueCurve(fig);
    else if (kind === "price-zones") priceZones(fig);
    else if (kind === "winter-values") winterValues(fig);
    else priceYears(fig);
  });
})();
