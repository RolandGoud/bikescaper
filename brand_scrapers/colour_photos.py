"""Add a photo per colour to the newest snapshot of each brand, without collecting the rest again.

    python -m brand_scrapers.colour_photos                  # all brands
    python -m brand_scrapers.colour_photos giant cube       # some

Reads each model's colours and their photo URLs from the brand's site again, saves the photos
under images/<Brand>/ and writes color_names, color_image_urls and color_images into the newest
data/<Brand>/ snapshot in place; prices, specs and dates stay as they were. Scott is read from
data/Scott/scott_gallery.json when it's there, since scott-sports.com (and orbea.com) only open
in a visible Chrome on a home PC.
"""
import argparse
import collections
import json
import logging
import os

from . import scott
from .__main__ import ADAPTERS
from .common import ROOT, Fetcher, dedupe, log, save_colour_images

FIELDS = ("color_names", "color_image_urls", "color_hexes")


def latest(brand):
    folder = os.path.join(ROOT, "data", brand)
    files = sorted(f for f in os.listdir(folder) if f.startswith(f"{brand.lower()}_bikes_") and f.endswith(".json"))
    return os.path.join(folder, files[-1]) if files else None


def scott_gallery():
    """{model name: bike with colour photos} from scott_gallery.json: every photo of every colour, side view first."""
    path = os.path.join(ROOT, "data", "Scott", "scott_gallery.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        gallery = json.load(fh)
    bikes = {}
    for name, entry in gallery.items():
        photos = collections.OrderedDict()
        for img in entry.get("images") or []:
            if img.get("color"):
                photos.setdefault(img["color"], []).append(img["src"])
        bikes[name.lower()] = {"color_names": list(photos),
                               "color_image_urls": [scott.cloudinary_width(scott.side_photo(p)) for p in photos.values()]}
    return bikes


def fresh(name, fetcher, limit=None):
    if name == "scott" and (gallery := scott_gallery()) is not None:
        return gallery
    return {b["name"].lower(): b for b in dedupe(ADAPTERS[name].scrape(fetcher, limit=limit))}


def run(names, limit=None):
    fetcher = Fetcher()
    done = {}
    for name in names:
        brand = ADAPTERS[name].BRAND
        path = latest(brand)
        if not path:
            continue
        with open(path, encoding="utf-8") as fh:
            bikes = json.load(fh)
        found = fresh(name, fetcher, limit)
        photos = 0
        for bike in bikes:
            new = found.get(bike["name"].lower())
            if not new or not new.get("color_names"):
                continue
            bike.update({k: new[k] for k in FIELDS if k in new})
            bike.setdefault("brand", brand)
            photos += sum(1 for p in save_colour_images(fetcher, bike) if p)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(bikes, fh, ensure_ascii=False, indent=2)
        done[brand] = (os.path.relpath(path, ROOT), photos)
        log.info("%s: %d colour photos in %s", brand, photos, path)
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("brands", nargs="*", help=", ".join(sorted(ADAPTERS)) + " (default: all)")
    parser.add_argument("--limit", type=int, help="products per brand, for testing")
    args = parser.parse_args()
    unknown = [b for b in args.brands if b not in ADAPTERS]
    if unknown:
        parser.error(f"unknown brand: {', '.join(unknown)}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for brand, (path, photos) in run(args.brands or sorted(ADAPTERS), args.limit).items():
        print(f"{brand}: {photos} colour photos -> {path}")


if __name__ == "__main__":
    main()
