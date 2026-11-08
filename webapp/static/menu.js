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
