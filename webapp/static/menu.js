// The site menu: the phone's Menu button folds the links open and shut, and the Tools dropdown opens on a
// click as well as on hover. A click elsewhere or Escape closes both.
const header = document.querySelector(".site-header");
const menuButton = header.querySelector(".menu-button");
const tools = header.querySelector(".tools");
const toolsButton = tools.querySelector(".tools-button");

const setMenu = (open) => {
  header.classList.toggle("menu-open", open);
  menuButton.setAttribute("aria-expanded", open);
};
const setTools = (open) => {
  tools.classList.toggle("open", open);
  toolsButton.setAttribute("aria-expanded", open);
};

menuButton.addEventListener("click", () => setMenu(!header.classList.contains("menu-open")));
toolsButton.addEventListener("click", () => setTools(!tools.classList.contains("open")));
document.addEventListener("click", (e) => {
  if (!header.contains(e.target)) setMenu(false);
  if (!tools.contains(e.target)) setTools(false);
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  setMenu(false);
  setTools(false);
});
