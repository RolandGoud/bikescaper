/* Listings page: the day lines over the cards (templates/listings.html). A card's line runs on through the gap
   to the next card in its row, and a row that starts in the middle of a day names that day again, dimmer.
   With one card per row (phones) only the first card of a day has a line. */
(function () {
  var grid = document.querySelector('.listing-grid');
  if (!grid) return;
  function mark() {
    var items = [].slice.call(grid.children).filter(function (el) { return el.classList.contains('dated'); });
    items.forEach(function (el, i) {
      var prev = items[i - 1], next = items[i + 1];
      el.classList.toggle('row-start', !!prev && prev.offsetTop !== el.offsetTop);
      el.classList.toggle('joins', !!next && next.offsetTop === el.offsetTop);
    });
  }
  mark();
  addEventListener('resize', mark);
  addEventListener('load', mark);
})();
