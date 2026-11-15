// The ad's tiles (report.html, .ad-tiles.inline) put their label and value on one line. When one tile's value
// doesn't fit beside its label, all the tiles put their value under their label, so the row reads as one.
(function () {
  function fit(row) {
    row.classList.remove('stacked');
    var wraps = Array.prototype.some.call(row.children, function (tile) {
      var k = tile.querySelector(':scope > .k'), b = tile.querySelector(':scope > b');
      return k && b && b.getBoundingClientRect().top >= k.getBoundingClientRect().bottom - 1;
    });
    row.classList.toggle('stacked', wraps);
  }
  document.querySelectorAll('.ad-tiles.inline').forEach(function (row) {
    var width = 0;
    fit(row);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fit(row); });
    if (window.ResizeObserver) new ResizeObserver(function () {
      if (row.clientWidth !== width) { width = row.clientWidth; fit(row); }
    }).observe(row);
  });
})();
