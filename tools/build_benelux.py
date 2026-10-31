"""Build webapp/static/benelux.json: the shapes the listings map (/listings/map) draws its dots in.

From Natural Earth (public domain, https://www.naturalearthdata.com), 1:10m:
the Netherlands and Belgium (kind "country", the dots go inside), their provinces ("province", kept for
later use), the big lakes ("lake", no dots there: IJsselmeer, Lauwersmeer, Frisian lakes) and the land
border between them ("border", drawn as a dotted line). Coordinates are rounded to 3 decimals (~100 m).

    for f in ne_10m_admin_0_countries ne_10m_admin_1_states_provinces ne_10m_lakes ne_10m_lakes_europe \\
             ne_10m_admin_0_boundary_lines_land; do
      curl -O https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/$f.geojson
    done
    python tools/build_benelux.py <folder with those files>

A new country: add it to COUNTRIES and BOX, and its borders to BORDERS.
"""
import json
import os
import sys

COUNTRIES = ("NLD", "BEL")
BORDERS = [{"Belgium", "Netherlands"}]
BOX = (2.5, 49.4, 7.3, 53.7)  # west, south, east, north: leaves out the Caribbean Netherlands
OUT = os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "benelux.json")


def rounded(line):
    out = []
    for x, y in line:
        p = [round(x, 3), round(y, 3)]
        if not out or p != out[-1]:
            out.append(p)
    return out


def in_box(ring):
    return any(BOX[0] < x < BOX[2] and BOX[1] < y < BOX[3] for x, y in ring)


def polygons(geometry):
    ps = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [[rounded(r) for r in p] for p in ps if in_box(p[0])]


def feature(kind, kind_type, coordinates, **props):
    return {"type": "Feature", "properties": {"kind": kind, **props},
            "geometry": {"type": kind_type, "coordinates": coordinates}}


def build(folder):
    def load(name):
        with open(os.path.join(folder, name + ".geojson"), encoding="utf-8") as f:
            return json.load(f)["features"]
    out = []
    for f in load("ne_10m_admin_0_countries"):
        if f["properties"]["ADM0_A3"] in COUNTRIES:
            out.append(feature("country", "MultiPolygon", polygons(f["geometry"]), cc=f["properties"]["ADM0_A3"]))
    for f in load("ne_10m_admin_1_states_provinces"):
        if f["properties"]["adm0_a3"] in COUNTRIES:
            out.append(feature("province", "MultiPolygon", polygons(f["geometry"]),
                               cc=f["properties"]["adm0_a3"], name=f["properties"]["name"]))
    for name in ("ne_10m_lakes", "ne_10m_lakes_europe"):
        for f in load(name):
            ps = polygons(f["geometry"])
            if ps:
                out.append(feature("lake", "MultiPolygon", ps, name=f["properties"].get("name")))
    for f in load("ne_10m_admin_0_boundary_lines_land"):
        if {f["properties"].get("ADM0_LEFT"), f["properties"].get("ADM0_RIGHT")} in BORDERS:
            g = f["geometry"]
            lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            out.append(feature("border", "MultiLineString", [rounded(l) for l in lines]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": out}, f, separators=(",", ":"))
    print(len(out), "features,", os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build(sys.argv[1])
