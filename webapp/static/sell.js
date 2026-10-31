// Selling page: send the form again when an answer changes, copy buttons, and the photo review offer.
(function () {
  var form = document.getElementById("sell-form");
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { if (form) form.requestSubmit(); });
  });
  // The free-text answer goes along when it loses focus with a change, or on Enter.
  document.querySelectorAll('input[name="service"]').forEach(function (el) {
    el.addEventListener("change", function () { if (form) form.requestSubmit(); });
  });

  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.dataset.copy.split(" ").map(function (id) {
        var el = document.getElementById(id);
        return el ? (el.tagName === "TEXTAREA" ? el.value : el.textContent.trim()) : "";
      }).join("\n\n");
      navigator.clipboard.writeText(text).then(function () {
        var was = btn.textContent;
        btn.textContent = "✓";
        setTimeout(function () { btn.textContent = was; }, 1500);
      });
    });
  });

  // The photo review isn't built yet: count the click and say so, without leaving the page.
  var dialog = document.getElementById("fake-door");
  document.querySelectorAll("[data-fake-door]").forEach(function (offer) {
    offer.addEventListener("submit", function (e) {
      if (!dialog || !dialog.showModal) return;
      e.preventDefault();
      fetch(offer.action, {method: "POST", body: new FormData(offer), headers: {"X-Requested-With": "fetch"}});
      dialog.showModal();
    });
  });
  if (dialog) {
    // A missing close button used to throw here and stop the rest of this file, so the examples' arrows did nothing.
    var close = dialog.querySelector("[data-close]");
    if (close) close.addEventListener("click", function () { dialog.close(); });
    var notify = dialog.querySelector("form");  // only there when the site can send mail
    if (notify) notify.addEventListener("submit", function (e) {
      e.preventDefault();
      fetch(notify.action, {method: "POST", body: new FormData(notify), headers: {"X-Requested-With": "fetch"}});
      notify.hidden = true;
      dialog.querySelector(".thanks").hidden = false;
      setTimeout(function () { dialog.close(); }, 4000);
    });
  }
})();

// The examples of improved ads: one at a time, paged with the arrows.
(function () {
  var box = document.querySelector(".examples");
  if (!box) return;
  var items = box.querySelectorAll(".example"), count = box.querySelector(".row-count"), at = 0;
  function show(i) {
    at = (i + items.length) % items.length;
    items.forEach(function (el, n) { el.hidden = n !== at; });
    if (count) count.textContent = (at + 1) + " / " + items.length;
  }
  var prev = box.querySelector(".ex-prev"), next = box.querySelector(".ex-next");
  if (prev) prev.addEventListener("click", function () { show(at - 1); });
  if (next) next.addEventListener("click", function () { show(at + 1); });
})();
