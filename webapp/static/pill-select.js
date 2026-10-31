// Every dropdown on the site becomes a button and a menu of big pills: the spec tier pills from the bike
// tiles for tiers (options with data-tier), neutral pills for everything else. The select stays in the form,
// hidden, and keeps the value: picking a pill sets it and fires its change event, so the forms and the
// scripts that listen to them work as before. Long lists get a search box. Without JavaScript the plain
// selects show. A select with data-native is left alone.
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
  const pill = (o) => el("span", o.dataset.tier ? `tier t${o.dataset.tier}` : "tier plain-pill", labelOf(o));

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

    let items = [], active = -1;
    const shown = () => items.filter((li) => !li.hidden);
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
      const add = (o) => {
        const li = el("li");
        li.setAttribute("role", "option");
        li.id = `${id}-${n++}`;
        li.option = o;
        const p = pill(o);
        const count = el("span", "n", o.dataset.count ?? "");
        p.append(count);
        li.append(p);
        if (o.disabled) li.setAttribute("aria-disabled", "true");
        list.append(li);
        items.push(li);
      };
      for (const child of select.children) {
        if (child.tagName === "OPTGROUP") {
          const head = el("li", "group", child.label);
          head.setAttribute("role", "presentation");
          list.append(head);
          [...child.children].forEach(add);
        } else add(child);
      }
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
    const filter = () => {
      const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
      items.forEach((li) => { const t = li.textContent.toLowerCase(); li.hidden = !words.every((w) => t.includes(w)); });
      // a group heading shows while one of its options does
      list.querySelectorAll(".group").forEach((g) => {
        let next = g.nextElementSibling, any = false;
        while (next && !next.classList.contains("group")) { any ||= !next.hidden; next = next.nextElementSibling; }
        g.hidden = !any;
      });
      setActive(shown()[0]);
    };
    const render = () => {
      const o = select.options[select.selectedIndex];
      button.replaceChildren(o && o.dataset.tier ? pill(o) : el("span", "plain", o ? labelOf(o) : ""));
      button.insertAdjacentHTML("beforeend", chevron);
      items.forEach((li) => {
        const on = li.option === o;
        li.setAttribute("aria-selected", on);
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
    list.addEventListener("click", (e) => pick(e.target.closest('[role="option"]')));
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
