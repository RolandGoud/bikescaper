"""Spec sheets of earlier model years from two UK bike shops, Rutland Cycling and Sigma Sports, as the Wayback
Machine kept them.

Mantel (brand_scrapers/mantel.py) never sold Specialized, Bianchi or Cannondale before 2021; these two shops did,
with the full spec table, the model year and a photo on each page. The archive refuses our cloud machines, so the
pages are read on a PC and saved as data/years/uk/raw.json ({"checked_on", "source", "models": {brand: {the shop's
name: {year: {archived_url, original_url, shop, model_year, model_year_source, price, currency, frame_sizes,
photo_url, photo_live, specs: [{label, value}]}}}}}). This turns it into data/years/uk/<Brand>.json and
data/years/uk/lines/<Brand>.json the way mantel.py does for Mantel's, and webapp/seed.py merges them after Mantel's.

The shops' prices are in pounds and are shop prices, so they never become a sheet's (euro) new price: a sheet keeps
them as price_gbp with the shop's name. Photos the shop still serves (photo_live) go to
images/<Brand>/years/<slug>_<year>_uk.jpg.

    python -m brand_scrapers.uk [--no-photos]
"""
import os
import re
from datetime import datetime

from . import mantel
from .common import ROOT, _LABEL_TO_KEY, clean, first_of_each, normalize_specs

SOURCE = "Rutland Cycling and Sigma Sports (UK bike shops), copies in the Wayback Machine"
RAW = os.path.join(ROOT, "data", "years", "uk", "raw.json")

# The shops' English labels that normalize_specs doesn't know as such. Rows whose label it still doesn't know after
# this are dropped: shop notes ("Manufacturers disclaimer", "Model above"), the rear shock of a few gravel bikes,
# and misspellings too rare to list.
LABELS = {
    "chainset": "crankset", "chainrings": "kettingblad", "brakeset": "brakes",
    "post clamp": "seat binder", "number of gears": "versnellingen", "gears": "versnellingen",
    "manufacturer claimed weight": "weight", "manufacturer's claimed weight": "weight",
    "claimed manufacturer weight": "weight",
    "handlebar tape": "bar tape", "grips/bar tape": "bar tape", "grip / tape": "bar tape",
    "handlebar/stem": "cockpit", "integrated handlebar and stem": "cockpit",
    "rim/wheelset": "wheelset", "cassette / freewheel": "cassette",
    "fronjt derailleur": "front derailleur", "front deraailleur": "front derailleur",
    "accessories": "extra's", "extras": "extra's",
}
DRIVETRAIN = "drivetrain"  # Rutland's name for the rear derailleur on Specialized's sheets
NOT_THERE = re.compile(r"^(?:not included|n/?a|none|-)$", re.I)

# The shops' words in their names: "Tarmac SL6 Expert Disc Carbon Road Bike 2019", "CAAD13 Force ETap AXS 12-Speed".
# A returned bike ("Return Bianchi Oltre XR3 Ultegra 61cm") and the shop's own builds keep the bike's name. "Carbon"
# stays: Cannondale's "Synapse Carbon" is not its aluminium Synapse.
SHOP_WORDS = re.compile(r"^(?:return|sigma sports exclusive)\b|\b(?:(?:carbon |alloy |aluminium )?(?:road|gravel|"
                        r"adventure|cyclocross|endurance|aero|race) bike|road(?= womens)|bike|(?:1x)?1[12]-speed|20[12]\d|\d\dcm)\b", re.I)
WOMEN = re.compile(r"\bwomens\b", re.I)
BRANDS = re.compile(r"\b(?:specialized|bianchi|cannondale)\b", re.I)
SPELLING = [(r"\bEtap\b|\bETap\b|\beTAP\b|\bETAP\b", "eTap"), (r"\bSram\b", "SRAM"), (r"\bCrux\b", "Crux"),
            (r"\bCruX\b", "Crux"), (r"\bdi2\b", "Di2"), (r"\bdisc\b", "Disc"), (r"\bDura Ace\b", "Dura-Ace")]


def key(name):
    """'Aria Ultegra Disc' and 'Aria Disc Ultegra' -> 'aria disc ultegra': the shops put a name's words in any order."""
    return " ".join(sorted(set(mantel.key(name).split())))


def clean_name(name):
    """The shop's name without its words, in our spelling: 'Tarmac SL6 Expert Disc Carbon Road Bike 2019' ->
    'Tarmac SL6 Expert Disc'. Empty when the page had no name."""
    name = WOMEN.sub("Women's", BRANDS.sub(" ", SHOP_WORDS.sub(" ", (name or "").strip())))
    for pattern, ours in SPELLING:
        name = re.sub(pattern, ours, name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    if re.search(r"\bS-Works\b", name, re.I):  # Specialized's "S-Works" comes first: "Tarmac SL7 S-Works eTap"
        name = "S-Works " + re.sub(r"\s+", " ", re.sub(r"\bS-Works\b", " ", name, flags=re.I)).strip(" -")
    return name


def specs_of(rows):
    """The shop's [{label, value}] as our labelled sheet."""
    pairs, drivetrain = [], None
    for row in rows:
        label, value = clean(row.get("label")).lower().rstrip(":"), clean(row.get("value"))
        if not value or NOT_THERE.match(value):
            continue
        if label == DRIVETRAIN:
            drivetrain = value
            continue
        label = LABELS.get(label, label)
        if label in _LABEL_TO_KEY:
            pairs.append((label, value))
    if drivetrain and not any(_LABEL_TO_KEY[label] == "Achterderailleur" for label, _ in pairs):
        pairs.append(("rear derailleur", drivetrain))
    return normalize_specs(first_of_each(pairs))  # "Handlebar" and "Handlebars" are one row of ours


def sheet(entry, specs):
    ts = (re.search(r"/web/(\d{14})", entry.get("archived_url") or "") or [None, ""])[1]
    return {"captured": datetime.strptime(ts[:8], "%Y%m%d").date().isoformat() if ts else None,
            "ts": ts, "url": entry.get("original_url"), "source": "uk", "shop": entry.get("shop"), "specs": specs,
            "price": None, "price_gbp": float(entry["price"]) if entry.get("price") else None,
            "photo": entry.get("photo_url") if entry.get("photo_live") else None}


class Shops(mantel.Shop):
    tag, folder, source = "uk", "uk", SOURCE
    clean_name = staticmethod(clean_name)
    specs_of = staticmethod(specs_of)
    sheet = staticmethod(sheet)
    key = staticmethod(key)


UK = Shops()


def convert(raw, photos=None):
    return mantel.convert(raw, photos, UK)


def main(argv=None):
    mantel.main(argv, UK, RAW, __doc__)


if __name__ == "__main__":
    main()
