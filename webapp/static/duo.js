// Merged photo tiles: the cut between the ad photo and the catalogue photo follows the mouse,
// or a finger dragged sideways. A drag doesn't open the report; a plain click or tap still does.
document.querySelectorAll(".duo").forEach((tile) => {
  const range = tile.querySelector(".duo-range");
  let startX = null, dragged = false;
  const set = (pct) => {
    pct = Math.max(-10, Math.min(110, pct));  // the slant needs 10% past each edge to show one photo whole
    tile.style.setProperty("--cut", pct + "%");
    range.value = Math.round(pct);
  };
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
