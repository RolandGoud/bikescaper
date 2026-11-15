// Selling page, step 1: the photo review prototype (webapp/photo_review.py). Sends the filled shot slots once,
// asks for the result every few seconds, then puts a verdict on each slot and the notes in a list.
(function () {
  var form = document.querySelector("[data-photo-review]");
  var out = document.querySelector("[data-review-out]");
  if (!form || !out || !window.sellPhotoSlots || !window.fetch) return;
  var status = out.querySelector("[data-review-status]"), body = out.querySelector("[data-review-body]");
  var list = out.querySelector("[data-review-list]"), item = out.querySelector("[data-review-item]");
  var words = JSON.parse(out.querySelector("[data-review-words]").textContent);
  var button = form.querySelector("button[type=submit]");
  var POLL_MS = 3000, GIVE_UP_MS = 180000;

  function say(text) { out.hidden = false; status.hidden = !text; status.textContent = text || ""; }
  function busy(on) { button.disabled = on; form.classList.toggle("busy", on); }
  function slot(key) { return document.querySelector('.shot[data-shot="' + key + '"]'); }
  function shotTitle(key) { var s = slot(key); return s ? s.querySelector(".shot-cap b").textContent : key; }

  function show(review, sent) {
    say("");
    list.textContent = "";
    out.querySelector("[data-review-summary]").textContent = review.summary || "";
    document.querySelectorAll(".shot[data-verdict]").forEach(function (s) { s.removeAttribute("data-verdict"); });
    review.photos.forEach(function (p) {
      var s = slot(p.shot);
      if (s) {
        s.setAttribute("data-verdict", p.verdict);
        var badge = s.querySelector(".shot-ok");
        badge.textContent = p.verdict === "keep" ? "✓" : p.verdict === "retake" ? "!" : "~";
        badge.title = words[p.verdict] || "";
      }
      var li = item.content.firstElementChild.cloneNode(true);
      li.setAttribute("data-verdict", p.verdict);
      if (sent[p.shot]) li.querySelector("img").src = sent[p.shot];
      li.querySelector("b").textContent = shotTitle(p.shot);
      li.querySelector(".verdict").textContent = words[p.verdict] || p.verdict;
      li.querySelector(".review-notes").textContent = p.notes || p.shows || "";
      var tip = li.querySelector(".review-tip");
      tip.textContent = p.tip || "";
      tip.hidden = !p.tip;
      var flags = [];
      if (p.stock_photo) flags.push(words.stock);
      if (p.privacy) flags.push(words.privacy + " " + p.privacy);
      var flag = li.querySelector(".review-flag");
      flag.textContent = flags.join(" ");
      flag.hidden = !flags.length;
      li.querySelector(".review-checks").textContent = ["light", "background", "sharpness", "angle", "details"]
        .filter(function (k) { return p.checks[k] && p.checks[k] !== "n/a"; })
        .map(function (k) { return words[k] + ": " + (words[p.checks[k]] || p.checks[k]); }).join(" · ");
      list.appendChild(li);
    });
    var missing = Array.prototype.filter.call(document.querySelectorAll(".shot[data-shot]"), function (s) {
      return !s.classList.contains("done");
    }).map(function (s) { return s.querySelector(".shot-cap b").textContent; });
    var m = out.querySelector("[data-review-missing]");
    m.querySelector("span").textContent = missing.join(", ");
    m.hidden = !missing.length;
    body.hidden = false;
    button.textContent = form.dataset.tAgain;
    out.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function poll(token, sent, since) {
    fetch(form.dataset.result.replace("TOKEN", encodeURIComponent(token)), {headers: {"X-Requested-With": "fetch"}})
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (r.status === "done") { busy(false); show(r, sent); }
        else if (r.status === "running" && Date.now() - since < GIVE_UP_MS) setTimeout(function () { poll(token, sent, since); }, POLL_MS);
        else { busy(false); say(form.dataset.tFailed); }
      })
      .catch(function () { busy(false); say(form.dataset.tFailed); });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (button.disabled) return;  // a double click starts one review, not two
    busy(true);
    window.sellPhotoSlots().then(function (photos) {
      if (!photos.length) { busy(false); say(form.dataset.tNone); return; }
      var data = new FormData(form), sent = {};
      photos.forEach(function (p) {
        data.append("shot-" + p.key, p.blob, p.key + ".jpg");
        sent[p.key] = URL.createObjectURL(p.blob);
      });
      body.hidden = true;
      say(form.dataset.tBusy);
      fetch(form.action, {method: "POST", body: data, headers: {"X-Requested-With": "fetch"}})
        .then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
        .then(function (r) {
          if (!r.ok || !r.j.token) { busy(false); say(r.j.error || form.dataset.tFailed); return; }
          poll(r.j.token, sent, Date.now());
        })
        .catch(function () { busy(false); say(form.dataset.tFailed); });
    });
  });
})();
