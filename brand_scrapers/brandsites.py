"""Spec sheets of earlier model years from the brands' own sites, as the Wayback Machine kept them, for the brands
that no shop of ours covers: Canyon and Factor (sold only direct), and Specialized and Bianchi for the years and
models Rutland Cycling and Sigma Sports (brand_scrapers/uk.py) don't have.

The archive refuses our cloud machines, so the pages are read on a PC and saved as data/years/brandsites/raw.json
({"checked_on", "source", "models": {brand: {the site's name: {year: {archived_url, original_url, wayback_timestamp,
model_year, model_year_source, price, currency, weight, frame_sizes, photo_url, photo_live, specs: [{label, value}],
gallery?, gallery_live?}}}}}). This turns it into data/years/brandsites/<Brand>.json and
data/years/brandsites/lines/<Brand>.json the way mantel.py does for Mantel's, and webapp/seed.py merges them before
the shops' sheets.

Specialized's and Bianchi's pages don't say the model year, so for most of them it is the year of the copy
(model_year_source "capture_date_guess"); the sheet keeps year_guessed so the model page can say so. A price is the
brand's new price only when the page shows it in euros; any other currency is kept as price_foreign with its
currency. Photos the brand still serves go to images/<Brand>/years/<slug>_<year>_brandsite.jpg, and a page's other
product photos that still load (gallery) to ..._brandsite_<n>.jpg.

    python -m brand_scrapers.brandsites [--no-photos]
"""
import html
import os
import re
from datetime import datetime

from . import mantel, uk
from .common import ROOT, _LABEL_TO_KEY, clean, first_of_each, normalize_specs

SOURCE = "The brands' own sites (canyon.com, specialized.com, bianchi.com, factorbikes.com), copies in the Wayback Machine"
RAW = os.path.join(ROOT, "data", "years", "brandsites", "raw.json")
GALLERY_MAX = 8  # photos per sheet besides the main one

# The sites' labels (English, and Dutch on Specialized's NL pages) that normalize_specs doesn't know as such. Rows
# whose label it still doesn't know are dropped: Canyon's spare parts and manuals, Factor's geometry table (its
# numbers come through as labels: "53", "507"), Specialized's SWAT box.
LABELS = {
    # Canyon
    "shift-/ brake lever": "shifters", "shift lever": "shifters", "brake rotor": "rotors", "brake": "brakes",
    "material": "frame material", "seatclamps": "seat clamp", "chainring": "chainring", "wheel": "wheelset",
    "flat pedals": "pedals",
    # Bianchi
    "brakelevers": "brake levers", "bb": "bottom bracket", "sprocket": "cassette", "rearhub": "rear hub",
    "rearderailleur": "rear derailleur", "frontderailleur": "front derailleur", "tubolar": "tyres",
    # Factor
    "seat post": "seatpost",
    # Specialized
    "front tire": "front tyre", "chainrings": "kettingblad", "tandwielen": "cassette", "voorrem": "rem",
}
NOT_THERE = uk.NOT_THERE

# The sites' words in their names: Canyon's "New" badge and "7.0" for its 7, Bianchi's speeds and gearing
# ("Oltre XR4 - Ultegra Di2 11sp 52/36"), Factor's colourways and "Road Bike".
SITE_WORDS = re.compile(r"\b(?:all new|new|road bike|complete bike|full|compact|\d+x\d+sp|\d+sp|\d\d/\d\d)\b", re.I)
FACTOR_COLOURS = re.compile(r"\b(?:miami blue|pearl white|aqua blue|crimson red|sterling silver)\b", re.I)
CUSTOM = re.compile(r"\bcustom\b", re.I)  # a build to order is no one bike
SPELLING = uk.SPELLING + [(r"\bHydr\. Disc\b", "Disc"), (r"\bDura Ace\b", "Dura-Ace"), (r"\bDISC\b", "Disc"),
                          (r"(?<=\d)\.0\b", "")]


MENS = re.compile(r"^men'?s\s+", re.I)  # Specialized's "Men's Tarmac Comp" is its Tarmac Comp
# Factor's site named some bikes by what they are for: the "Allroad" page is the Vista's.
FACTOR_NAMES = {"Allroad": "Vista", "Road Race": "O2", "Road Super Light": "O2 VAM"}


def key(name):
    """Canyon's "Aeroad CF SL Disc 8.0" and "Aeroad CF SL 8 Disc" are one name, as the shops' word orders are."""
    return uk.key(MENS.sub("", re.sub(r"(?<=\d)\.0\b", "", name)))


def clean_name(name):
    """The site's name without its words, in our spelling: 'Oltre XR4 Disc - Dura Ace 11sp 52/36' ->
    'Oltre XR4 Disc Dura-Ace'. Empty for a page without a name or a build to order."""
    name = html.unescape(name or "")
    if CUSTOM.search(name):
        return ""
    # Bianchi repeats the family: "Infinito CV - Infinito CV Disc - Force eTap AXS 12sp"
    parts = [p.strip() for p in re.split(r"\s+[-–]\s+", name) if p.strip()]
    if len(parts) > 2 and parts[1].startswith(parts[0]):
        parts = parts[1:]
    name = " ".join(parts)
    name = FACTOR_COLOURS.sub(" ", SITE_WORDS.sub(" ", name))
    for pattern, ours in SPELLING:
        name = re.sub(pattern, ours, name)
    name = MENS.sub("", re.sub(r"\s+", " ", name).strip(" -–:"))
    if name.isupper() and len(name) > 6:  # "TARMAC ELITE"
        name = " ".join(w if len(w) < 3 or any(c.isdigit() for c in w) else w.title() for w in name.split())
    return FACTOR_NAMES.get(name, name)


def specs_of(rows):
    """The site's [{label, value}] as our labelled sheet."""
    pairs = []
    for row in rows:
        label, value = clean(row.get("label")).lower().rstrip(":"), clean(row.get("value"))
        if not value or NOT_THERE.match(value):
            continue
        label = LABELS.get(label, label)
        if label in _LABEL_TO_KEY:
            pairs.append((label, value))
    return normalize_specs(first_of_each(pairs))


def sheet(entry, specs):
    ts = str(entry.get("wayback_timestamp") or "")
    price, currency = entry.get("price"), entry.get("currency")
    out = {"captured": datetime.strptime(ts[:8], "%Y%m%d").date().isoformat() if len(ts) >= 8 else None,
           "ts": ts, "url": entry.get("original_url"), "source": "brandsite", "specs": specs,
           "price": float(price) if price and currency == "EUR" else None,
           "photo": entry.get("photo_url") if entry.get("photo_live") else None}
    if price and currency and currency != "EUR":
        out.update(price_foreign=float(price), currency=currency)
    if entry.get("model_year_source") == "capture_date_guess":
        out["year_guessed"] = True
    live = entry.get("gallery_live") or []
    out["gallery"] = [u for i, u in enumerate(entry.get("gallery") or [])
                      if (live[i] if i < len(live) else None) and u != entry.get("photo_url")][:GALLERY_MAX]
    return out


def keep(brand, entry):
    """Specialized kept old bikes' pages online for years (the 2014 S-Works Tarmac SL4 still in a 2021 copy), so
    the year of a copy says nothing about its model year: only a page whose article number dates it stays.
    Bianchi's copies are of its web store (2021 and 2022), which sold that season's bikes."""
    return not (brand == "Specialized" and entry.get("model_year_source") == "capture_date_guess")


class Sites(mantel.Shop):
    tag, folder, source = "brandsite", "brandsites", SOURCE
    clean_name = staticmethod(clean_name)
    specs_of = staticmethod(specs_of)
    sheet = staticmethod(sheet)
    key = staticmethod(key)
    keep = staticmethod(keep)


SITES = Sites()


def with_archived_photos(raw):
    """raw with the photos the brand no longer serves but the PC saved from the Wayback Machine
    (raw["archived_photos"]: {url: path under images/}) counted as live: the photo function finds them there."""
    saved = raw.get("archived_photos") or {}
    for years in (m for models in raw.get("models", {}).values() for m in models.values()):
        for entry in years.values():
            if entry.get("photo_url") in saved:
                entry["photo_live"] = True
            gallery = entry.get("gallery") or []
            live = list(entry.get("gallery_live") or []) + [None] * len(gallery)
            entry["gallery_live"] = [bool(live[i]) or u in saved for i, u in enumerate(gallery)]
    return raw


def convert(raw, photos=None):
    return mantel.convert(with_archived_photos(raw), photos, SITES)


def main(argv=None):
    import argparse
    import json
    import shutil
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw", default=RAW)
    parser.add_argument("--no-photos", action="store_true", help="leave the photos out")
    args = parser.parse_args(argv)
    with open(args.raw, encoding="utf-8") as fh:
        raw = json.load(fh)
    photos = None
    if not args.no_photos:
        from .common import Fetcher
        from .history import save_photo
        fetcher, saved = Fetcher(delay=1.0), raw.get("archived_photos") or {}

        def photos(brand, slug, year, url, n=None):
            rel = f"{brand}/years/{slug}_{year}_{SITES.tag}{f'_{n}' if n else ''}.jpg"
            if url in saved:  # the Wayback Machine's copy, saved on the PC
                source, target = os.path.join(ROOT, "images", saved[url]), os.path.join(ROOT, "images", rel)
                if not os.path.exists(source):
                    return None
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(source, target)
                return rel
            return save_photo(fetcher, brand, slug, year, url, rel=rel)
    mantel.save(raw, convert(raw, photos), SITES)


if __name__ == "__main__":
    main()
