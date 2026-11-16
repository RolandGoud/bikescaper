// /blog: the category pills filter the wall in place, with the "reflow" transition: tiles that stay glide to their
// new place and size, the others fade. Without JavaScript the pills are ordinary links; with "reduce motion", or in
// a browser without view transitions, the wall simply fades over.
(function () {
  "use strict";
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // Reflow: every tile carries its article as a view-transition name, so a tile that stays glides to its new
  // place and size, and the others fade out or in (the View Transitions API; CSS in style.css).
  function name(b) { var a = b.querySelector("h2 a"); return a ? "brick-" + a.getAttribute("href").split("/").pop() : "none"; }
  async function reflow(wall, next) {
    wall.querySelectorAll(".brick").forEach(function (b) { b.style.viewTransitionName = name(b); });
    next.querySelectorAll(".brick").forEach(function (b) { b.style.viewTransitionName = name(b); });
    await document.startViewTransition(function () { wall.replaceWith(next); }).finished;
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
      // wait for the pictures (at most half a second), so new tiles don't fade in empty
      await Promise.race([Promise.all(imgs.map(function (i) { return i.decode().catch(function () {}); })), sleep(500)]);
      document.querySelector(".filters").replaceWith(document.adoptNode(doc.querySelector(".filters")));
      bind();
      if (push) history.pushState({blog: true}, "", href);
      document.title = doc.title;
      await (calm || !document.startViewTransition ? fade : reflow)(wall, next);
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
