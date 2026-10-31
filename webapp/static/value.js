// Value estimator: the fields are filled left to right, and each one stays greyed out (disabled) until the one
// to its left has a value: Brand, then Model, then Model year, then Condition and Asking price (Condition starts
// on Normal use, so the asking price opens with it). Estimate opens with them. The Model list only shows the
// models of the brand picked in Brand, starting on "Pick a model…" so a brand alone doesn't pick one.
// Without JavaScript every field is open and the list shows every model, grouped by brand.
(() => {
  const form = document.querySelector(".value-form");
  if (!form) return;
  const { brand, model, year, condition, asking } = form.elements;
  const submit = form.querySelector('button[type="submit"]');
  const groups = [...model.querySelectorAll("optgroup")];
  const placeholder = (text) => { const o = new Option(text, "", true, true); o.disabled = true; return o; };
  const show = (keepSelection) => {
    const group = groups.find((g) => g.dataset.brand === brand.value);
    if (!group) { model.replaceChildren(placeholder(model.dataset.placeholder)); model.disabled = true; return; }
    const chosen = keepSelection ? model.value : null;
    model.replaceChildren(placeholder(model.dataset.pick), ...group.cloneNode(true).children);
    model.value = chosen && [...model.options].some((o) => o.value === chosen) ? chosen : "";
    model.disabled = false;
  };
  // each field opens once the one before it has a value
  const chain = () => {
    year.disabled = model.disabled || !model.value;
    const open = !year.disabled && year.value.trim() !== "";
    condition.disabled = asking.disabled = submit.disabled = !open;
  };
  // A model picked earlier (from a saved estimate or a model page) decides the brand.
  const start = groups.find((g) => [...g.children].some((o) => o.defaultSelected));
  if (start) brand.value = start.dataset.brand;
  show(true);
  chain();
  brand.addEventListener("change", () => { show(false); chain(); });
  model.addEventListener("change", chain);
  year.addEventListener("input", chain);
})();
