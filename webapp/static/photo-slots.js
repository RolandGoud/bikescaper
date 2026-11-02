// Selling page, step 1: the seller's own photo in each shot's slot, taken with the camera in the page (the
// shot's outline over the live view) or picked from the phone, and the last step's list in upload order.
// The photos are kept in this browser only (IndexedDB, made smaller first) and never sent anywhere.
// Without IndexedDB (a private window, blocked storage) a photo still shows until the page changes.
(function () {
  var slots = document.querySelectorAll(".shot[data-shot]");
  var order = document.querySelector("[data-shots]");
  if (!slots.length && !order) return;
  var MAX = 1600, mem = {};

  var dbp = new Promise(function (resolve) {
    try {
      var req = indexedDB.open("sell-photos", 1);
      req.onupgradeneeded = function () { req.result.createObjectStore("shots"); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { resolve(null); };
    } catch (e) { resolve(null); }
  });
  function tx(mode, fn) {
    return dbp.then(function (db) {
      if (!db) return null;
      return new Promise(function (resolve) {
        try {
          var t = db.transaction("shots", mode), req = fn(t.objectStore("shots"));
          t.oncomplete = function () { resolve(req && req.result); };
          t.onerror = t.onabort = function () { resolve(null); };
        } catch (e) { resolve(null); }
      });
    });
  }
  function load(key) { return mem[key] ? Promise.resolve(mem[key]) : tx("readonly", function (s) { return s.get(key); }); }

  // A phone photo is often 5–10 MB; a smaller JPEG is plenty to check the angle and keeps storage small.
  function shrink(file) {
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        var scale = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
        var c = document.createElement("canvas");
        c.width = Math.round(img.naturalWidth * scale); c.height = Math.round(img.naturalHeight * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob(function (b) { resolve(b || file); }, "image/jpeg", 0.85);
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function show(slot, blob) {
    var mine = slot.querySelector(".mine");
    if (mine.src) URL.revokeObjectURL(mine.src);
    if (blob) mine.src = URL.createObjectURL(blob); else mine.removeAttribute("src");
    mine.hidden = !blob;
    slot.querySelector(".outline").hidden = !!blob;
    slot.querySelector(".shot-ok").hidden = !blob;
    slot.querySelector(".shot-remove").hidden = !blob;
    slot.querySelector("[data-add]").hidden = !!blob;
    slot.querySelector("[data-replace]").hidden = !blob;
    slot.classList.toggle("done", !!blob);
    count();
  }
  function count() {
    var n = document.querySelectorAll(".shot.done").length;
    var el = document.querySelector("[data-count-n]");
    if (el) el.textContent = n;
    var bar = document.querySelector("[data-count-bar]");
    if (bar) bar.style.width = (100 * n / slots.length) + "%";
  }

  document.querySelectorAll("[data-count], .shot-actions, [data-local]").forEach(function (el) { el.hidden = false; });
  function save(slot, blob) {
    mem[slot.dataset.shot] = blob;
    show(slot, blob);
    tx("readwrite", function (s) { return s.put(blob, slot.dataset.shot); });
  }

  // The camera in the page. getUserMedia needs a secure page (https or localhost); without it, or when the
  // seller says no, the phone's own picker opens instead.
  var cam = document.getElementById("camera"), stream = null, camSlot = null;
  var canCam = !!(cam && cam.showModal && window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  function stopCam() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
  }
  function openCam(slot) {
    camSlot = slot;
    cam.querySelector("[data-camera-title]").textContent = slot.querySelector(".shot-cap b").textContent;
    cam.querySelector("[data-camera-outline]").src = slot.querySelector(".outline").src;
    navigator.mediaDevices.getUserMedia({audio: false, video: {facingMode: {ideal: "environment"}, width: {ideal: 1920}, height: {ideal: 1440}}})
      .then(function (s) {
        stream = s;
        cam.querySelector("video").srcObject = s;
        cam.showModal();
      })
      .catch(function () { slot.querySelector("input[type=file]").click(); });
  }
  if (canCam) {
    cam.addEventListener("close", stopCam);
    cam.querySelector("[data-camera-close]").addEventListener("click", function () { cam.close(); });
    cam.querySelector(".camera-shutter").addEventListener("click", function () {
      // The frame on screen is 4:3 with the video covering it, so keep the same middle part of the video.
      var v = cam.querySelector("video"), vw = v.videoWidth, vh = v.videoHeight;
      if (!vw || !vh) return;
      var sw = vw, sh = vh;
      if (vw / vh > 4 / 3) sw = vh * 4 / 3; else sh = vw * 3 / 4;
      var scale = Math.min(1, MAX / sw), c = document.createElement("canvas");
      c.width = Math.round(sw * scale); c.height = Math.round(sh * scale);
      c.getContext("2d").drawImage(v, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, c.width, c.height);
      var slot = camSlot;
      c.toBlob(function (b) { if (b) save(slot, b); }, "image/jpeg", 0.85);
      cam.close();
    });
  }

  slots.forEach(function (slot) {
    var key = slot.dataset.shot, input = slot.querySelector("input[type=file]");
    var shoot = slot.querySelector(".shot-camera");
    if (canCam) {
      shoot.hidden = false;
      shoot.addEventListener("click", function () { openCam(slot); });
    }
    // Tapping the outline does the same as the first button.
    slot.querySelector(".shot-media").addEventListener("click", function () { if (canCam) openCam(slot); else input.click(); });
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      shrink(file).then(function (blob) { save(slot, blob); });
      input.value = "";
    });
    slot.querySelector(".shot-remove").addEventListener("click", function () {
      delete mem[key];
      show(slot, null);
      tx("readwrite", function (s) { return s.delete(key); });
    });
    load(key).then(function (blob) { if (blob) show(slot, blob); });
  });

  // The last step: the photos the seller added, in the order to upload them.
  if (order) {
    var items = order.querySelectorAll("li[data-shot]"), none = document.querySelector(".photo-order-none");
    Promise.all(Array.prototype.map.call(items, function (li) {
      return load(li.dataset.shot).then(function (blob) {
        li.hidden = !blob;
        if (blob) li.querySelector("img").src = URL.createObjectURL(blob);
        return !!blob;
      });
    })).then(function (have) {
      var any = have.some(Boolean);
      order.hidden = !any;
      if (none) none.hidden = any;
    });
  }
})();
