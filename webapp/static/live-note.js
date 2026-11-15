// The admin's account menu (base.html, _live_note.html): what the NAS is installing and what just went live.
// A spinner on the button while an update installs; afterwards a count of the changes this browser hasn't seen,
// marked in the list too. Opening the menu clears the count. While the page is open it asks /admin/live every
// few seconds, so the spinner and the list follow an update as it happens.
const note = document.querySelector(".live-note");
if (note) {
  const KEY = "bikecheck-live-seen";
  const POLL = 10000;
  const button = note.closest(".tools").querySelector(".tools-button");
  const menuButton = document.querySelector(".menu-button");  // on a phone the account menu folds behind it
  const marks = (sel) => [button.querySelector(sel), menuButton && menuButton.querySelector(sel)].filter(Boolean);
  if (menuButton) ["live-spin", "live-badge"].forEach((c) => menuButton.appendChild(button.querySelector(`.${c}`).cloneNode()));

  const store = (value) => {
    try { if (value === undefined) return localStorage.getItem(KEY); localStorage.setItem(KEY, value); }
    catch (e) { /* private window: nothing remembered, everything counts as new */ }
    return null;
  };
  const localTimes = () => note.querySelectorAll("time[data-local]").forEach((el) => {
    // The NAS's clock may run on UTC: show the times in this browser's own time.
    const t = new Date(el.dateTime);
    if (isNaN(t)) return;
    const hm = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    el.textContent = t.toDateString() === new Date().toDateString()
      ? hm : `${t.toLocaleDateString([], { day: "numeric", month: "short" })} ${hm}`;
  });
  let state = "";
  const show = () => {
    const inner = note.querySelector(".live-inner");
    const shas = inner.dataset.shas ? inner.dataset.shas.split(" ") : [];
    const seen = store();
    const upTo = seen && shas.includes(seen) ? shas.indexOf(seen) : shas.length;
    const fresh = new Set(shas.slice(0, upTo));
    const items = [...note.querySelectorAll("li[data-sha]")].filter((li) => fresh.has(li.dataset.sha));
    items.forEach((li) => li.classList.add("new"));
    const busy = Boolean(inner.dataset.updating);
    marks(".live-spin").forEach((s) => { s.hidden = !busy; });
    marks(".live-badge").forEach((b) => {
      b.textContent = items.length;
      b.hidden = busy || !items.length;
    });
    localTimes();
    state = `${inner.dataset.updating}|${inner.dataset.shas}`;
  };
  const markSeen = () => {
    const shas = note.querySelector(".live-inner").dataset.shas;
    if (shas) store(shas.split(" ")[0]);
    marks(".live-badge").forEach((b) => { b.hidden = true; });
  };
  [button, menuButton].forEach((b) => b && b.addEventListener("click", markSeen));
  button.addEventListener("mouseenter", markSeen);  // the menu opens on hover too

  const poll = async () => {
    if (document.visibilityState === "visible") {
      try {
        const resp = await fetch(note.dataset.url, { headers: { Accept: "text/html" }, cache: "no-store" });
        if (resp.ok) {
          const html = await resp.text();
          const box = document.createElement("div");
          box.innerHTML = html;
          const inner = box.querySelector(".live-inner");
          if (inner && `${inner.dataset.updating}|${inner.dataset.shas}` !== state) {
            note.querySelector(".live-inner").replaceWith(inner);
            show();
          }
        }
      } catch (e) { /* offline or the site is reloading: try again next time */ }
    }
    setTimeout(poll, POLL);
  };
  show();
  setTimeout(poll, POLL);
}
