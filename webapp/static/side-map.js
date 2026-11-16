/* Listings page: the small map beside the cards or the table (templates/listings.html), one dot per town in the
   colour of its most urgent price verdict. A dot opens the big map at that town. It is drawn only once it is on
   screen: below the wide layout it is hidden and the floating "Map" button takes its place. */
(function () {
  var el = document.getElementById("side-map");
  var data = document.getElementById("side-map-pins");
  if (!el || !data || !window.L) return;
  var pins = JSON.parse(data.textContent);
  var drawn = false;

  function draw() {
    if (drawn || !el.offsetParent) return;
    drawn = true;
    var css = getComputedStyle(document.documentElement);
    var dotColour = css.getPropertyValue("--map-land").trim() || "#4A4F5B";
    var borderColour = css.getPropertyValue("--accent").trim() || "#34D399";
    var home = L.latLngBounds([49.45, 2.5], [53.6, 7.25]);
    var map = L.map(el, {zoomControl: false, attributionControl: false, scrollWheelZoom: false, dragging: false,
                         doubleClickZoom: false, boxZoom: false, keyboard: false, touchZoom: false,
                         zoomSnap: 0.1, preferCanvas: true});
    map.fitBounds(home, {padding: [8, 8]});

    fetch(el.dataset.benelux).then(function (r) { return r.json(); }).then(function (geo) {
      function rings(kind) {
        var out = [];
        geo.features.forEach(function (f) {
          if (f.properties.kind === kind) f.geometry.coordinates.forEach(function (p) { out.push(p[0]); });
        });
        return out;
      }
      var land = rings("country"), lakes = rings("lake");
      function within(rs, x, y) {
        var hit = false;
        rs.forEach(function (ring) {
          for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
            if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) hit = !hit;
          }
        });
        return hit;
      }
      // Coarser dots than the big map's, to suit the smaller size.
      var renderer = L.canvas();
      for (var lat = 49.45; lat < 53.6; lat += 0.055) {
        for (var lng = 2.5; lng < 7.25; lng += 0.085) {
          if (within(land, lng, lat) && !within(lakes, lng, lat)) {
            L.circleMarker([lat, lng], {renderer: renderer, radius: 1.3, stroke: false, fillColor: dotColour, fillOpacity: 1, interactive: false}).addTo(map);
          }
        }
      }
      L.geoJSON(geo.features.filter(function (f) { return f.properties.kind === "border"; }), {interactive: false,
        style: {color: borderColour, weight: 2, opacity: 0.9, dashArray: "1 6", lineCap: "round"}}).addTo(map);
    });

    pins.forEach(function (pin) {
      var many = pin.ads > 1;
      var icon = L.divIcon({className: "map-pin " + pin.status + (many ? " many" : ""),
                            html: many ? "<span>" + pin.ads + "</span>" : "<span></span>",
                            iconSize: many ? [24, 24] : [14, 14]});
      L.marker([pin.lat, pin.lng], {icon: icon, title: pin.place, riseOnHover: true}).addTo(map)
        .on("click", function () { location.href = pin.link; });
    });
  }

  draw();
  addEventListener("resize", draw);
})();
