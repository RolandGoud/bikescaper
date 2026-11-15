// The match picker (report edit mode): the "Our match" pencil opens a page overlay with the catalogue's models, their
// model years, colours, parts and new prices, to pick the model, the model year and the colour at once. Each can stay
// on "Automatic" (empty). Vastzetten posts the same form the small pop-up used to (field "match").
(() => {
  const dialog = document.getElementById("match-picker");
  const dataEl = document.getElementById("match-picker-data");
  if (!dialog || !dataEl) return;
  const data = JSON.parse(dataEl.textContent), t = data.t, auto = data.auto;
  const form = dialog.querySelector("form");
  const field = (name) => form.elements[name];
  const $ = (sel) => dialog.querySelector(sel);
  const models = data.models;
  // What's picked; "" is automatic.
  const sel = { model: data.set.model || "", year: data.set.year ? +data.set.year : "", colour: data.set.colour || "" };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fill = (text, values) => text.replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
  const pctClass = (p) => (p == null ? "" : p >= 80 ? "hi" : p >= 50 ? "mid" : "lo");
  const find = (slug) => models.find((m) => m.slug === slug);
  const shownModel = () => find(sel.model || auto.model) || models[0];
  const wantedYear = () => sel.year || auto.year;
  // The year's catalogue entry, or the nearest one when we have none for that year.
  const yearEntry = (m, year) => {
    if (!m || !m.years.length) return null;
    if (!year) return m.years[0];
    return m.years.find((y) => y.year === year) ||
      [...m.years].sort((a, b) => Math.abs(a.year - year) - Math.abs(b.year - year) || b.year - a.year)[0];
  };
  const wantedColour = () => sel.colour || (!sel.model || sel.model === auto.model ? auto.colour : "");
  const same = (a, b) => (a || "").toLowerCase().replace(/\s+/g, "") === (b || "").toLowerCase().replace(/\s+/g, "");
  const thumb = (m) => { const y = m.years[0]; return (y && (y.image || (y.colours.find((c) => c.image) || {}).image)) || m.image; };
  const yearSpan = (m) => (m.years.length > 1 ? `${m.years[m.years.length - 1].year}–${m.years[0].year}` : m.years.length ? m.years[0].year : "");
  const adPart = (part) => {
    if (part.key !== "Groupset" || !data.ad_groupset) return false;
    const name = data.ad_groupset.toLowerCase().replace(/^(shimano|sram|campagnolo)\s+/, "");
    return part.value.toLowerCase().includes(name);
  };

  function renderModels() {
    const box = $(".pk-models");
    const autoModel = find(auto.model);
    const row = (m, value, title, sub, pct) => `<button type="button" role="option" class="pk-m${value === "" ? " auto" : ""}${sel.model === value ? " on" : ""}" aria-selected="${sel.model === value}" data-model="${esc(value)}">
      <span class="pk-thumb">${m && thumb(m) ? `<img src="${esc(thumb(m))}" alt="" loading="lazy">` : ""}</span>
      <span><b>${esc(title)}</b><small><span class="pk-pct ${pctClass(pct)}">${sub}</span></small></span></button>`;
    box.innerHTML = row(autoModel, "", t.automatic, esc(auto.label || "–") + (auto.pct != null ? ` · ${auto.pct}%` : ""), auto.pct) +
      models.map((m) => row(m, m.slug, `${m.brand} ${m.name}`,
        (m.pct != null ? esc(fill(t.match, { pct: m.pct })) + " · " : "") + `<span class="pk-span">${yearSpan(m)}</span>`, m.pct)).join("");
  }

  function render() {
    const m = shownModel(), want = wantedYear(), y = yearEntry(m, want), colour = wantedColour();
    renderModels();
    field("model").value = sel.model;
    field("year").value = sel.year;
    field("colour").value = sel.colour;
    // The photo: the colour's in that year, else the year's, else the model's.
    const c = y && y.colours.find((k) => same(k.name, colour));
    const img = (c && c.image) || (y && (y.image || (y.colours.find((k) => k.image) || {}).image)) || (m && m.image);
    const hero = $(".pk-hero img");
    hero.hidden = !img;
    if (img) hero.src = img;
    $(".pk-mark").textContent = [y && y.year, c && c.name].filter(Boolean).join(" · ");
    $(".pk-mark").hidden = !y;
    $(".pk-brand").textContent = m ? m.brand : "";
    $(".pk-name").textContent = m ? m.name : "–";
    const note = $(".pk-note");
    note.hidden = !(m && (!m.years.length || (want && y && y.year !== want)));
    note.textContent = m && !m.years.length ? t.no_years : y ? fill(t.no_year, { year: want, shown: y.year }) : "";

    // The model years: automatic, the catalogue's years, and a year set by hand that the catalogue hasn't.
    const years = m ? m.years.map((e) => e.year) : [];
    if (sel.year && !years.includes(sel.year)) years.push(sel.year), years.sort((a, b) => b - a);
    $(".pk-years").innerHTML = `<button type="button" class="pk-chip auto${sel.year === "" ? " on" : ""}" data-year="" aria-pressed="${sel.year === ""}">${esc(t.automatic)}${auto.year ? ": " + auto.year : ""}</button>` +
      years.map((v) => `<button type="button" class="pk-chip${sel.year === v ? " on" : ""}" data-year="${v}" aria-pressed="${sel.year === v}">${v}</button>`).join("");
    $(".pk-other-year").value = "";

    // The colours of the year shown.
    $(".pk-colour-k").textContent = y ? fill(t.colour_in, { year: y.year }) : t.colour;
    const autoColour = !sel.model || sel.model === auto.model ? auto.colour : "";
    const tiles = y ? y.colours : [];
    $(".pk-colours").innerHTML = `<button type="button" class="pk-ct auto${sel.colour === "" ? " on" : ""}" data-colour="" aria-pressed="${sel.colour === ""}"><span>${esc(t.automatic)}${autoColour ? ":<br>" + esc(autoColour) : ""}</span></button>` +
      tiles.map((k) => {
        const on = sel.colour !== "" && same(k.name, sel.colour);
        return `<button type="button" class="pk-ct${on ? " on" : ""}" data-colour="${esc(k.name)}" aria-pressed="${on}">
          <span class="pk-ct-photo">${k.image ? `<img src="${esc(k.image)}" alt="" loading="lazy">` : `<i style="background:${esc(k.swatch || "var(--line-strong)")}"></i>`}</span>
          <span>${esc(k.name)}</span></button>`;
      }).join("") + (y && !tiles.length ? `<p class="small muted">${esc(t.no_colours)}</p>` : "");
    const typed = $(".pk-other-colour");
    if (document.activeElement !== typed) typed.value = sel.colour && !tiles.some((k) => same(k.name, sel.colour)) ? sel.colour : "";

    // The year's main parts and new price.
    $(".pk-specs").hidden = !(y && y.parts.length);
    $(".pk-specs-k").textContent = y ? fill(t.specs, { year: y.year }) : "";
    $(".pk-parts").innerHTML = y ? y.parts.map((p) => `<dt>${esc(p.label)}</dt><dd${adPart(p) ? ' class="hit"' : ""}>${esc(p.value)}${adPart(p) ? ` <small>✓ ${esc(t.as_ad)}</small>` : ""}</dd>`).join("") : "";
    $(".pk-price-box").hidden = !(y && y.price);
    $(".pk-price-k").textContent = y ? fill(t.price, { year: y.year }) : "";
    $(".pk-price").textContent = (y && y.price) || "";

    // The choice as it will be locked; what stays automatic says so.
    const part = (value, set) => esc(value || "–") + (set ? "" : ` <small>(${esc(t.auto_lc)})</small>`);
    $(".pk-sel b").innerHTML = [part(m && `${m.brand} ${m.name}`, sel.model), part(sel.year || auto.year, sel.year),
      part(sel.colour || autoColour, sel.colour)].join(" · ");
  }

  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) return dialog.close();  // the backdrop: a click outside the box
    const b = e.target.closest("button");
    if (!b) return;
    if (b.matches("[data-close]")) return dialog.close();
    if (b.dataset.model !== undefined) {
      if (b.dataset.model !== sel.model) sel.colour = "";  // a colourway's name belongs to its model
      sel.model = b.dataset.model;
    } else if (b.dataset.year !== undefined) {
      sel.year = b.dataset.year ? +b.dataset.year : "";
    } else if (b.dataset.colour !== undefined) {
      sel.colour = b.dataset.colour;
    } else if (b.matches("[data-all-auto]")) {
      sel.model = sel.year = sel.colour = "";
      render();
      return;  // and the form is sent, with everything back to automatic
    } else return;
    render();
  });
  $(".pk-other-year").addEventListener("change", (e) => { if (e.target.value) { sel.year = +e.target.value; render(); } });
  $(".pk-other-colour").addEventListener("input", (e) => { sel.colour = e.target.value.trim(); render(); });

  // Another model from the search: loaded from the catalogue and added to the list.
  const search = $(".pk-search");
  search.addEventListener("change", async () => {
    const typed = search.value.trim().toLowerCase();
    const hit = [...dialog.querySelectorAll("#pk-all option")].find((o) => o.value.toLowerCase() === typed);
    if (!hit) return;
    const slug = hit.dataset.slug;
    let m = find(slug);
    if (!m) {
      const res = await fetch(data.more.replace("SLUG", encodeURIComponent(slug)), { credentials: "same-origin" });
      if (!res.ok) return;
      m = await res.json();
      models.push(m);
    }
    if (m.slug !== sel.model) sel.colour = "";
    sel.model = m.slug;
    search.value = "";
    render();
    reveal($(".pk-m.on"));
  });
  // Enter in the search or the colour field picks, it doesn't lock.
  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches(".pk-search, .pk-other-colour")) {
      e.preventDefault();
      e.target.dispatchEvent(new Event("change"));
    }
  });

  // Scroll a picked button into view within its own list only (sideways on a phone), not the overlay.
  const reveal = (el) => {
    const box = el && el.parentElement;
    if (!box) return;
    if (box.scrollWidth > box.clientWidth) box.scrollLeft = el.offsetLeft - box.offsetLeft - (box.clientWidth - el.offsetWidth) / 2;
    const list = box.closest(".pk-rail");
    if (list && list.scrollHeight > list.clientHeight && getComputedStyle(list).overflowY === "auto")
      list.scrollTop = el.offsetTop - list.offsetTop - (list.clientHeight - el.offsetHeight) / 2;
  };

  const open = () => {
    render();
    dialog.showModal();
    document.body.classList.add("pk-open");
    reveal($(".pk-m.on"));
    reveal($(".pk-years .on"));
  };
  dialog.addEventListener("close", () => document.body.classList.remove("pk-open"));
  document.querySelectorAll("[data-open-picker]").forEach((pen) => {
    pen.addEventListener("click", open);
    if (pen.hasAttribute("data-open-now")) open();
  });
})();
