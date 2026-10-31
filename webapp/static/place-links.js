// A town inside a card (itself a link) can't be an <a>: these spans open the listings map at that town
// instead of the card's report (see place_link in templates/_macros.html).
document.addEventListener("click", function (e) {
  var place = e.target.closest && e.target.closest(".place-link[data-href]");
  if (!place) return;
  e.preventDefault();
  e.stopPropagation();
  window.location.href = place.dataset.href;
}, true);
document.addEventListener("keydown", function (e) {
  var place = e.target.closest && e.target.closest(".place-link[data-href]");
  if (!place || (e.key !== "Enter" && e.key !== " ")) return;
  e.preventDefault();
  e.stopPropagation();
  window.location.href = place.dataset.href;
}, true);
