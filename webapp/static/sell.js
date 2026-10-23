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
    dialog.querySelector("[data-close]").addEventListener("click", function () { dialog.close(); });
    var notify = dialog.querySelector("form");
    notify.addEventListener("submit", function (e) {
      e.preventDefault();
      fetch(notify.action, {method: "POST", body: new FormData(notify), headers: {"X-Requested-With": "fetch"}});
      notify.hidden = true;
      dialog.querySelector(".thanks").hidden = false;
      setTimeout(function () { dialog.close(); }, 1800);
    });
  }
})();
