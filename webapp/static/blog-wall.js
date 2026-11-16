// /blog: the category pills filter the wall in place, with the "spotlight" transition. The wall goes dark, one
// beam sweeps across and lights the new tiles as it passes, and each headline number counts up as the light
// reaches it. Without JavaScript the pills are ordinary links; with "reduce motion" the wall simply fades over.
(function () {
  "use strict";
  var DUR = 800, DIM = 160;
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function countUp(el, target) {
    var m = target.match(/\d[\d.,]*/);
    if (!m) return;
    var digits = m[0].replace(/[.,]/g, ""), n = parseInt(digits, 10), sep = (m[0].match(/[.,]/) || [""])[0];
    var t0 = performance.now(), dur = 520;
    (function step(now) {
      var k = Math.min(1, (now - t0) / dur), v = Math.round(n * (1 - Math.pow(1 - k, 3))), s = String(v);
      if (sep) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
      el.textContent = target.replace(m[0], s);
      if (k < 1) requestAnimationFrame(step); else el.textContent = target;
    })(t0);
  }

  async function spotlight(wall, next) {
    wall.classList.add("wall-dim");
    await sleep(DIM);
    var nums = Array.from(next.querySelectorAll(".brick-num")), targets = nums.map(function (n) { return n.textContent; });
    nums.forEach(function (n) { n.textContent = n.textContent.replace(/\d[\d.,]*/, "0"); });
    next.classList.add("wall-reveal");
    next.style.setProperty("--p", "-20%");
    wall.replaceWith(next);
    var box = next.getBoundingClientRect(), beam = document.createElement("div");
    beam.className = "wall-beam";
    beam.setAttribute("aria-hidden", "true");
    Object.assign(beam.style, {top: (box.top + scrollY - 40) + "px", height: (box.height + 80) + "px", width: (box.width * 0.6) + "px"});
    document.body.appendChild(beam);
    var start = performance.now(), lit = new Set();
    await new Promise(function (done) {
      (function step(now) {
        var k = Math.min(1, (now - start) / DUR), p = -20 + (1 - Math.pow(1 - k, 3)) * 140;
        next.style.setProperty("--p", p + "%");
        beam.style.left = (box.left + box.width * (p / 100 - 0.3)) + "px";
        nums.forEach(function (n, i) {
          if (!lit.has(i) && n.getBoundingClientRect().left - box.left < box.width * p / 100) { lit.add(i); countUp(n, targets[i]); }
        });
        if (k < 1) requestAnimationFrame(step); else done();
      })(start);
    });
    nums.forEach(function (n, i) { if (!lit.has(i)) n.textContent = targets[i]; });
    beam.remove();
    next.classList.remove("wall-reveal");
  }

  async function fade(wall, next) {
    next.classList.add("wall-fade");
    wall.replaceWith(next);
    await sleep(20);
    next.classList.remove("wall-fade");
  }

  var busy = false;
  async function show(href, push) {
    if (busy) return;
    busy = true;
    try {
      var doc = new DOMParser().parseFromString(await (await fetch(href)).text(), "text/html");
      var wall = document.querySelector(".blog-wall"), next = doc.querySelector(".blog-wall");
      if (!wall || !next) { location.href = href; return; }
      next = document.adoptNode(next);
      var imgs = Array.from(next.querySelectorAll("img"));
      imgs.forEach(function (i) { i.loading = "eager"; });
      // wait for the pictures (at most half a second), so the beam lights tiles, not empty boxes
      await Promise.race([Promise.all(imgs.map(function (i) { return i.decode().catch(function () {}); })), sleep(500)]);
      document.querySelector(".filters").replaceWith(document.adoptNode(doc.querySelector(".filters")));
      bind();
      if (push) history.pushState({blog: true}, "", href);
      document.title = doc.title;
      await (calm ? fade : spotlight)(wall, next);
    } catch (e) {
      location.href = href;
    } finally {
      busy = false;
    }
  }

  function bind() {
    document.querySelectorAll(".blog-index .filters a").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button) return;  // new tab: leave it to the browser
        ev.preventDefault();
        if (a.getAttribute("aria-current") !== "page") show(a.href, true);
      });
    });
  }
  window.addEventListener("popstate", function () { show(location.href, false); });
  bind();
})();
