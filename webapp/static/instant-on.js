// Instant button state: a click on one of a row of links or submit buttons (the menu, the Cards/Table/Map switch,
// the 30d/90d/1 year periods, brand cards, bike types, filters, build pills, pages…) moves the row's highlight to it
// straight away, on the press itself, while the page or the in-place swap behind it still loads. The server's page
// then shows the same state, so nothing jumps. Buttons that only run script (type="button") switch themselves already.
//
// A row is found from the markup, not listed here: the nearest ancestor (at most three levels up) holding another
// link or submit button of the same kind (same tag, same first class) that is marked current (.on, aria-current or
// aria-pressed="true"), and not inside a different [role=group] or <nav>. data-instant="off" on an element, or on a
// row, leaves it alone. Links to a spot on the same page, new tabs and downloads are left alone too.
(() => {
  const CANDIDATE = 'a[href], button[type="submit"], button:not([type])';
  const STATE = new Set(["on", "go", "used", "off", "here", "dim", "nofit"]);
  const kind = (el) => el.tagName + "." + ([...el.classList].find((c) => !STATE.has(c)) || "");
  const marked = (el) => el.classList.contains("on") || el.hasAttribute("aria-current") || el.getAttribute("aria-pressed") === "true";
  const fence = (el) => el.closest('[role="group"], nav');
  // Pickers where nothing is chosen yet: the clicked one lights up even with no current one to take over from.
  const PICKER = ".brand-cards, .bike-types, .pick-cards, .pick-list";

  const skip = (el, e) => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return true;
    if (el.closest('[data-instant="off"]') || el.disabled) return true;
    if (el.tagName === "A") {
      if (el.target && el.target !== "_self") return true;
      if (el.hasAttribute("download")) return true;
      const url = new URL(el.href, location.href);
      if (url.origin !== location.origin) return true;
      if (url.hash && url.pathname === location.pathname && url.search === location.search) return true;  // same page
    } else if (el.form && el.form.target && el.form.target !== "_self") return true;
    return false;
  };

  // The current one(s) in the clicked element's row.
  const rowOf = (el) => {
    const k = kind(el), f = fence(el);
    let g = el.parentElement;
    for (let up = 0; g && up < 3 && g !== document.body; up++, g = g.parentElement) {
      const now = [...g.querySelectorAll(CANDIDATE)].filter((m) => m !== el && marked(m) && kind(m) === k && fence(m) === f);
      if (now.length) return now;
      if (g === f) break;  // never look past the clicked element's own group
    }
    return el.parentElement?.matches(PICKER) ? [] : null;
  };

  // What the last press changed, to put back if the press didn't become a click, or when the back button brings
  // this page back from the browser's cache.
  let last = null;
  const snap = (el) => ({ el, cls: el.className, cur: el.getAttribute("aria-current"), pressed: el.getAttribute("aria-pressed") });
  const restore = (s) => {
    s.el.className = s.cls;
    if (s.cur === null) s.el.removeAttribute("aria-current"); else s.el.setAttribute("aria-current", s.cur);
    if (s.pressed === null) s.el.removeAttribute("aria-pressed"); else s.el.setAttribute("aria-pressed", s.pressed);
  };
  const undo = () => { if (last) last.snaps.forEach(restore); last = null; };

  const light = (e) => {
    const el = e.target.closest?.(CANDIDATE);
    if (!el || skip(el, e)) return false;
    if (last && last.el === el) return true;  // already lit by the press
    const now = rowOf(el);
    if (!now) return false;
    undo();
    // The menu's Tools button is lit while one of its pages is the current one.
    const tools = fence(el)?.classList.contains("main-nav") && document.querySelector(".main-nav .tools-button");
    last = { el, from: location.href, snaps: [el, ...now, ...(tools ? [tools] : [])].map(snap) };
    const lit = !now.length || now.some((m) => m.classList.contains("on"));
    now.forEach((m) => {
      m.classList.remove("on");
      m.removeAttribute("aria-current");
      if (m.getAttribute("aria-pressed") === "true") m.setAttribute("aria-pressed", "false");
    });
    if (lit) el.classList.add("on");
    const cur = now.map((m) => last.snaps.find((s) => s.el === m).cur).find((v) => v !== null);
    if (cur) el.setAttribute("aria-current", cur);
    if (last.snaps.some((s) => s.pressed === "true")) el.setAttribute("aria-pressed", "true");
    if (tools) tools.classList.toggle("on", !!el.closest(".tools-menu"));
    return true;
  };

  // A mouse lights the row on the press; a finger or the keyboard on the click (a finger's press may be a scroll).
  let pressed = null;
  document.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse") return;
    pressed = light(e) ? last && last.el : null;
  }, true);
  document.addEventListener("click", (e) => {
    // let go on another element: the browser clicks on what both share, not on the pressed link
    if (pressed && e.target.closest?.(CANDIDATE) !== pressed) undo();
    pressed = null;
    light(e);
  }, true);
  // The press was let go somewhere else, or the link was dragged away (no click follows): put the row back.
  const unpress = () => {
    if (!pressed) return;
    const el = pressed;
    setTimeout(() => { if (pressed === el) { pressed = null; undo(); } }, 0);
  };
  document.addEventListener("pointerup", unpress, true);
  document.addEventListener("pointercancel", unpress, true);
  document.addEventListener("dragend", unpress, true);

  // Back to this page from the browser's cache: show it as it was, unless the click swapped the page in place
  // (the address changed without leaving: the groupsets and blog pages), where the state is the new page's.
  addEventListener("pageshow", (e) => {
    if (e.persisted && last && last.from === location.href) undo();
    last = null;
  });
})();
