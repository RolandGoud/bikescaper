// The site menu: the phone's Menu button folds the links open and shut, and the Tools dropdown opens on a
// click as well as on hover. A click elsewhere or Escape closes both.
const header = document.querySelector(".site-header");
const menuButton = header.querySelector(".menu-button");
// The Tools dropdown and, once logged in, the account menu: each opens on its own.
const dropdowns = [...header.querySelectorAll(".tools")];

const setMenu = (open) => {
  header.classList.toggle("menu-open", open);
  menuButton.setAttribute("aria-expanded", open);
};
const setTools = (tools, open) => {
  tools.classList.toggle("open", open);
  tools.querySelector(".tools-button").setAttribute("aria-expanded", open);
};

menuButton.addEventListener("click", () => setMenu(!header.classList.contains("menu-open")));
dropdowns.forEach((tools) => tools.querySelector(".tools-button")
  .addEventListener("click", () => setTools(tools, !tools.classList.contains("open"))));
document.addEventListener("click", (e) => {
  if (!header.contains(e.target)) setMenu(false);
  dropdowns.forEach((tools) => { if (!tools.contains(e.target)) setTools(tools, false); });
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  setMenu(false);
  dropdowns.forEach((tools) => setTools(tools, false));
});

// Brand cards (groupsets page, size finder): a click or tap starts the sprint animation, kept through the
// navigation. With a mouse the hover already runs the road; on a phone the tap is the only cue.
document.addEventListener("click", (e) => {
  const card = e.target.closest(".brand-cards a");
  if (!card) return;
  card.classList.add("go");
  // A plain click that would load a new page at once: give the sprint a third of a second first. (The groupsets
  // page fetches and morphs instead, and has already claimed the click.)
  if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  setTimeout(() => { window.location.href = card.href; }, 350);
});
