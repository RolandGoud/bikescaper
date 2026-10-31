"""Build webapp/places.json: where each town and village in the Netherlands and Belgium lies.

The listings map (/listings/map) looks up an ad's place (Marktplaats and 2dehands give the
seller's town, typed checks whatever the visitor wrote) in this file, so the site never asks a
geocoding service. The source is GeoNames (CC BY 4.0, https://www.geonames.org): every populated
place (feature class P) and municipality with its Dutch, French, German, Frisian and English names.

    curl -O https://download.geonames.org/export/dump/NL.zip            (and BE.zip)
    curl -o alt-NL.zip https://download.geonames.org/export/dump/alternatenames/NL.zip   (and BE)
    unzip each, then:
    python tools/build_places.py <folder with NL.txt, BE.txt, alt-NL.txt, alt-BE.txt>

To add a country later, add its code to COUNTRIES (and its sites to webapp/places.py).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from webapp.places import normalise  # noqa: E402

COUNTRIES = ("NL", "BE")
# Municipalities too, for names that are no town of their own (Texel, Súdwest-Fryslân).
MUNICIPALITIES = {"ADM2", "ADM3", "ADM4"}
LANGUAGES = {"", "nl", "fr", "de", "fy", "li", "en", "wa", "vls", "zea"}
OUT = os.path.join(os.path.dirname(__file__), "..", "webapp", "places.json")


def build(folder):
    out = {}
    for cc in COUNTRIES:
        places = {}
        with open(os.path.join(folder, f"{cc}.txt"), encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                town = p[6] == "P"
                if not (town or p[7] in MUNICIPALITIES):
                    continue
                places[p[0]] = {"names": {p[1], p[2]}, "lat": round(float(p[4]), 4),
                                "lng": round(float(p[5]), 4), "pop": int(p[14] or 0), "town": town}
        with open(os.path.join(folder, f"alt-{cc}.txt"), encoding="utf-8") as f:
            for line in f:
                a = line.rstrip("\n").split("\t")
                if a[1] in places and a[2] in LANGUAGES and not (len(a) > 7 and a[7] == "1"):  # skip historic names
                    places[a[1]]["names"].add(a[3])
        # One spot per name: a town beats a municipality of that name (Utrecht), then the bigger place
        # (Hengelo in Overijssel, not the one in Gelderland).
        best = {}
        for pid, place in places.items():
            own = {normalise(n) for n in place["names"] if n}
            for key in own:
                rank = (place["town"], place["pop"], pid)
                if key not in best or rank > best[key][0]:
                    best[key] = (rank, [place["lat"], place["lng"], place["pop"]])
        out[cc] = {k: v for k, (_, v) in sorted(best.items()) if k}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print({cc: len(v) for cc, v in out.items()}, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build(sys.argv[1])
