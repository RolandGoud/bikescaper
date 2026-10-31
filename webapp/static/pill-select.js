// Every dropdown on the site becomes a button and a menu of big pills: the spec tier pills from the bike
// tiles for tiers (options with data-tier), neutral pills for everything else. The select stays in the form,
// hidden, and keeps the value: picking a pill sets it and fires its change event, so the forms and the
// scripts that listen to them work as before. Long lists get a search box. Without JavaScript the plain
// selects show. A select with data-native is left alone.
// A select with data-families (the size finder's model picker) gets one more level: its optgroups are families,
// each with a data-type (Road, Gravel…). The menu shows each type's families as small chips; a chip opens that
// family's options below the row (a family with one option picks it straight away). Typing in the search box
// shows every matching option under its family instead. Options there show their data-short label.
(() => {
  const check = '<svg class="check" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 7l3.5 3.5L12 4"/></svg>';
  const chevron = '<svg class="chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4"/></svg>';
  const SEARCH_FROM = 13;  // options; shorter lists are quick enough to scan
  const lang = document.documentElement.lang || "nl";
  const searchText = lang.startsWith("en") ? "Search…" : "Zoeken…";
  let ids = 0;

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const labelOf = (o) => o.dataset.label || o.textContent.trim();
  const pill = (o, text = labelOf(o)) => el("span", o.dataset.tier ? `tier t${o.dataset.tier}` : "tier plain-pill", text);

  // The select's name for screen readers: its aria-label, or its label's own text (not the options').
  const nameOf = (select) => {
    if (select.getAttribute("aria-label")) return select.getAttribute("aria-label");
    const label = select.labels && select.labels[0];
    if (!label) return "";
    return [...label.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(" ").trim();
  };

  const enhance = (select) => {
    if (select.dataset.pillReady || select.multiple || select.hasAttribute("data-native")) return;
    select.dataset.pillReady = "1";
    const id = `pill-select-${++ids}`;
    const box = el("div", "pill-select");
    box.dataset.name = select.name;
    // keep the select's size: its height, and its width where the layout doesn't stretch it
    if (select.offsetHeight) box.style.setProperty("--h", select.offsetHeight + "px");
    if (select.offsetWidth) box.style.setProperty("--w", select.offsetWidth + "px");
    const button = el("button");
    button.type = "button";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", id);
    const menu = el("div", "pill-menu");
    menu.hidden = true;
    const list = el("ul");
    list.id = id;
    list.setAttribute("role", "listbox");
    const name = nameOf(select);
    if (name) { button.setAttribute("aria-label", name); list.setAttribute("aria-label", name); }
    let search = null;
    menu.append(list);

    const families = select.hasAttribute("data-families");
    if (families) menu.classList.add("families");
    let items = [], active = -1, opened = null;  // opened: the family whose options show below its chips
    const shown = () => items.filter((li) => !li.hidden && !li.closest(".fam-panel")?.hidden);
    const setActive = (li) => {
      items.forEach((x) => x.classList.toggle("active", x === li));
      active = items.indexOf(li);
      if (!li) return;
      (search || button).setAttribute("aria-activedescendant", li.id);
      li.scrollIntoView({ block: "nearest" });
    };
    const step = (by) => {
      const vis = shown();
      if (!vis.length) return;
      const at = vis.indexOf(items[active]);
      setActive(vis[Math.max(0, Math.min(vis.length - 1, at < 0 ? 0 : at + by))]);
    };

    // (Re)build the pills from the select's options, also after a script changes them (value.js does).
    const build = () => {
      list.replaceChildren();
      items = [];
      let n = 0;
      const add = (o, into = list) => {
        const li = el("li");
        li.setAttribute("role", "option");
        li.id = `${id}-${n++}`;
        li.option = o;
        li.dataset.search = o.textContent.toLowerCase();
        const p = pill(o, families && o.dataset.short ? o.dataset.short : labelOf(o));
        const count = el("span", "n", o.dataset.count ?? "");
        p.append(count);
        li.append(p);
        if (o.disabled) li.setAttribute("aria-disabled", "true");
        into.append(li);
        items.push(li);
      };
      let row = null, type = null, panels = [];
      const flush = () => { panels.forEach((p) => list.append(p)); panels = []; };
      for (const child of select.children) {
        if (families && child.tagName === "OPTGROUP") {
          // a type heading and a row of family chips, then each family's options in a panel below the row
          if (child.dataset.type !== type) {
            flush();
            type = child.dataset.type;
            const head = el("li", "type", type);
            head.setAttribute("role", "presentation");
            row = el("li", "fam-row");
            row.setAttribute("role", "presentation");
            list.append(head, row);
          }
          const opts = [...child.children];
          const chip = el("button", "fam");
          chip.type = "button";
          chip.tabIndex = -1;
          chip.append(el("span", null, opts.length === 1 ? labelOf(opts[0]) : child.label));
          if (opts.length > 1) {
            chip.append(el("span", "n", opts.length));
            chip.insertAdjacentHTML("beforeend", chevron);
            chip.setAttribute("aria-expanded", "false");
          }
          const panel = el("li", "fam-panel");
          panel.setAttribute("role", "group");
          panel.setAttribute("aria-label", child.label);
          panel.append(el("div", "fam-title", child.label));
          const inner = el("ul");
          inner.setAttribute("role", "none");
          panel.append(inner);
          opts.forEach((o) => add(o, inner));
          chip.panel = panel;
          panel.chip = chip;
          row.append(chip);
          panels.push(panel);
        } else if (child.tagName === "OPTGROUP") {
          const head = el("li", "group", child.label);
          head.setAttribute("role", "presentation");
          list.append(head);
          [...child.children].forEach((o) => add(o));  // not forEach(add): its index would land in "into"
        } else { flush(); add(child); }
      }
      flush();
      const wantSearch = items.length >= SEARCH_FROM;
      if (wantSearch && !search) {
        search = el("input", "pill-search");
        search.type = "search";
        search.placeholder = searchText;
        search.setAttribute("role", "combobox");
        search.setAttribute("aria-controls", id);
        search.setAttribute("aria-expanded", "true");
        search.setAttribute("aria-autocomplete", "list");
        if (name) search.setAttribute("aria-label", name);
        search.addEventListener("input", filter);
        search.addEventListener("keydown", keys);
        menu.prepend(search);
      } else if (!wantSearch && search) { search.remove(); search = null; }
      render();
    };
    // Families: while searching every family with a match shows its options; otherwise only the opened one does.
    const layout = () => {
      if (!families) return;
      const searching = !!(search && search.value.trim());
      menu.classList.toggle("searching", searching);
      list.querySelectorAll(".fam-panel").forEach((p) => {
        const any = [...p.querySelectorAll('[role="option"]')].some((li) => !li.hidden);
        const one = p.querySelectorAll('[role="option"]').length === 1;
        p.hidden = searching ? !any : (p !== opened || one);
        p.chip.classList.toggle("on", p === opened && !searching);
        if (!one) p.chip.setAttribute("aria-expanded", p === opened && !searching);
      });
      list.querySelectorAll(".type, .fam-row").forEach((x) => { x.hidden = searching; });
    };
    const openFamily = (panel) => {
      opened = opened === panel ? null : panel;
      layout();
      if (opened) opened.scrollIntoView({ block: "nearest" });
    };
    const filter = () => {
      const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
      items.forEach((li) => { const t = li.dataset.search; li.hidden = !words.every((w) => t.includes(w)); });
      // a group heading shows while one of its options does
      list.querySelectorAll(".group").forEach((g) => {
        let next = g.nextElementSibling, any = false;
        while (next && !next.classList.contains("group")) { any ||= !next.hidden; next = next.nextElementSibling; }
        g.hidden = !any;
      });
      layout();
      setActive(shown()[0]);
    };
    const render = () => {
      const o = select.options[select.selectedIndex];
      button.replaceChildren(o && o.dataset.tier ? pill(o) : el("span", "plain", o ? labelOf(o) : ""));
      button.insertAdjacentHTML("beforeend", chevron);
      items.forEach((li) => {
        const on = li.option === o;
        li.setAttribute("aria-selected", on);
        li.closest(".fam-panel")?.chip.classList.toggle("picked", on);
        li.querySelector(".check")?.remove();
        if (on) li.querySelector(".n").insertAdjacentHTML("beforeend", check);
      });
    };
    const open = () => {
      document.querySelectorAll(".pill-select.open").forEach((b) => b !== box && b.close());
      menu.hidden = false;
      box.classList.add("open");
      // a menu wider than its button moves left to stay on screen
      menu.style.left = "";
      const over = menu.getBoundingClientRect().right - (document.documentElement.clientWidth - 16);
      if (over > 0) menu.style.left = -over + "px";
      button.setAttribute("aria-expanded", "true");
      // the picked option's family starts open
      const at = items.find((li) => li.option === select.options[select.selectedIndex]);
      opened = at?.closest(".fam-panel") || null;
      layout();
      if (search) { search.value = ""; filter(); search.focus(); }
      setActive(items.find((li) => li.option === select.options[select.selectedIndex]) || shown()[0]);
      document.addEventListener("pointerdown", outside, true);
    };
    const close = (refocus) => {
      menu.hidden = true;
      box.classList.remove("open");
      button.setAttribute("aria-expanded", "false");
      button.removeAttribute("aria-activedescendant");
      document.removeEventListener("pointerdown", outside, true);
      if (refocus) button.focus();
    };
    box.close = close;
    const outside = (e) => { if (!box.contains(e.target)) close(); };
    const pick = (li) => {
      if (!li || li.getAttribute("aria-disabled")) return;
      close(true);
      if (li.option.selected) return;
      li.option.selected = true;
      render();
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
    };
    function keys(e) {
      const shut = menu.hidden;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (shut) open(); else step(e.key === "ArrowDown" ? 1 : -1);
      } else if (shut) return;
      else if (e.key === "Home" && e.target === button) { e.preventDefault(); setActive(shown()[0]); }
      else if (e.key === "End" && e.target === button) { e.preventDefault(); setActive(shown().at(-1)); }
      else if (e.key === "Enter" || (e.key === " " && e.target === button)) { e.preventDefault(); pick(items[active]); }
      else if (e.key === "Escape") { e.preventDefault(); close(true); }
      else if (e.key === "Tab") close();
    }

    button.addEventListener("click", () => (menu.hidden ? open() : close()));
    button.addEventListener("keydown", keys);
    list.addEventListener("click", (e) => {
      const chip = e.target.closest(".fam");
      if (!chip) return pick(e.target.closest('[role="option"]'));
      const opts = chip.panel.querySelectorAll('[role="option"]');
      if (opts.length === 1) return pick(opts[0]);
      openFamily(chip.panel);
      setActive(shown().find((li) => chip.panel.contains(li)));
    });
    list.addEventListener("pointerdown", (e) => { if (e.target.closest(".fam")) e.preventDefault(); });  // keep focus in the search box
    list.addEventListener("pointermove", (e) => {
      const li = e.target.closest('[role="option"]');
      if (li && items.indexOf(li) !== active) setActive(li);
    });
    select.addEventListener("change", render);
    new MutationObserver(build).observe(select, { childList: true, subtree: true });

    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.classList.add("pill-select-native");
    select.after(box);
    box.append(button, menu);
    build();
    // a script may set the value without a change event (value.js does on load), so check once more
    requestAnimationFrame(render);
  };

  window.pillSelects = (root = document) => root.querySelectorAll("select").forEach(enhance);
  window.pillSelects();
})();
