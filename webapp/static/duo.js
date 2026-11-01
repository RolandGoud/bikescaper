// Merged photo tiles: the cut between the ad photo and the catalogue photo follows the mouse,
// or a finger dragged sideways. A drag doesn't open the report; a plain click or tap still does.
// Each tile starts at a random cut between 25% and 75%, so the cards don't all look the same
// and both photos always show.
document.querySelectorAll(".duo").forEach((tile) => {
  if (tile.closest(".ad-stage")) return;  // the report's heading: a fixed cut, no slider
  const range = tile.querySelector(".duo-range");
  let startX = null, dragged = false;
  const set = (pct) => {
    pct = Math.max(-10, Math.min(110, pct));  // the slant needs 10% past each edge to show one photo whole
    tile.style.setProperty("--cut", pct + "%");
    range.value = Math.round(pct);
  };
  set(25 + Math.random() * 50);
  const at = (e) => {
    const box = tile.getBoundingClientRect();
    return ((e.clientX - box.left) / box.width) * 120 - 10;
  };
  tile.addEventListener("pointerdown", (e) => {
    startX = e.clientX;
    dragged = false;
    if (e.pointerType !== "mouse") tile.setPointerCapture(e.pointerId);
  });
  tile.addEventListener("pointermove", (e) => {
    const touching = tile.hasPointerCapture(e.pointerId);
    if (e.pointerType !== "mouse" && !touching) return;
    if (startX !== null && (e.buttons || touching) && Math.abs(e.clientX - startX) > 4) dragged = true;
    set(at(e));
  });
  const end = () => { startX = null; };
  tile.addEventListener("pointerup", end);
  tile.addEventListener("pointercancel", end);
  tile.addEventListener("dragstart", (e) => e.preventDefault());
  tile.addEventListener("click", (e) => { if (dragged) { e.preventDefault(); dragged = false; } });
  range.addEventListener("input", () => set(Number(range.value)));
});

// A new ad's photos are copied to our disk, and then lined up with the catalogue bike, in the background
// after the page was made, so its tile first shows the photo as it is. Such a tile has data-refresh: ask for
// its finished ad side a few times, further apart each time, and swap it in once its photo has loaded,
// instead of the framing only coming right after a reload.
document.querySelectorAll(".duo[data-refresh]").forEach((tile) => {
  const waits = [1500, 2500, 4000, 6000, 10000, 15000, 20000];  // about a minute in all, then it stays as it is
  let tries = 0;
  const swap = (html) => new Promise((done) => {
    const box = document.createElement("div");
    box.innerHTML = html.trim();
    const side = box.firstElementChild, old = tile.querySelector(".ad-side");
    if (!side || !old) return done();
    const img = side.querySelector("img");
    const put = () => { old.replaceWith(side); done(); };
    if (!img || (old.querySelector("img") || {}).outerHTML === img.outerHTML) return put();
    img.loading = "eager";  // a detached lazy image never loads
    img.addEventListener("load", put, { once: true });
    img.addEventListener("error", done, { once: true });  // keep what shows
  });
  const ask = () => {
    fetch(tile.dataset.refresh, { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(async ({ html, settled }) => {
        await swap(html);
        if (settled) delete tile.dataset.refresh;
        else if (tries < waits.length) setTimeout(ask, waits[tries++]);
      })
      .catch(() => { if (tries < waits.length) setTimeout(ask, waits[tries++]); });
  };
  setTimeout(ask, waits[tries++]);
});
