// Value estimator: the Model list only shows the models of the brand picked in Brand. Without
// JavaScript the list shows every model, grouped by brand.
(() => {
  const form = document.querySelector(".value-form");
  if (!form) return;
  const brand = form.elements.brand, model = form.elements.model;
  const groups = [...model.querySelectorAll("optgroup")];
  const show = (keepSelection) => {
    const group = groups.find((g) => g.dataset.brand === brand.value);
    if (!group) return;
    const chosen = keepSelection ? model.value : null;
    model.replaceChildren(...group.cloneNode(true).children);
    if (chosen && [...model.options].some((o) => o.value === chosen)) model.value = chosen;
  };
  // A model picked earlier (from a saved estimate or a model page) decides the brand.
  const start = groups.find((g) => [...g.children].some((o) => o.defaultSelected));
  if (start) brand.value = start.dataset.brand;
  show(true);
  brand.addEventListener("change", () => show(false));
})();
