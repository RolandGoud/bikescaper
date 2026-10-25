"""The other photos of each current model (close-ups, front, rear), from its page on the brand's site.

    python -m brand_scrapers.galleries trek giant cannondale canyon cube specialized

Saves the photos to images/<Brand>/gallery/ and lists them in data/galleries/<Brand>.json as
{model page URL: {colour: [photo]}}; the colour is "" when the page shows one colour only. The side
view the catalogue already has is left out. Scott and Orbea only answer a visible Chrome
(browser.py) and Factor shows one photo per build, so they have no reader here yet.
"""
import argparse
import json
import os
import re
import sqlite3

from . import giant
from .archive import compact
from .common import ROOT, Fetcher, log
from .history import save_photo, trek_product


def _jsonld_images(page):
    found = []
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") in ("Product", "ProductGroup"):
                for part in [item] + (item.get("hasVariant") or []):  # Cannondale lists them per variant
                    images = part.get("image") or []
                    found += images if isinstance(images, list) else [images]
    return list(dict.fromkeys(str(i) for i in found))


def trek(fetcher, model):
    code = re.search(r"/p/(\d+)", model["url"])
    product = trek_product(fetcher, code.group(1)) if code else None
    return (product or {}).get("colour_angle_urls") or {}


def giant_page(fetcher, model):
    page = fetcher.get(model["url"])
    bike = giant.parse(page, model["url"]) if page else None
    return {c: a for c, a in zip((bike or {}).get("color_names") or [], (bike or {}).get("color_angle_urls") or []) if a}


def cannondale(fetcher, model):
    # The Product's images: the profile shot (_PD) first, then three-quarter and close-ups.
    page = fetcher.get(model["url"]) or ""
    return {"": [i for i in _jsonld_images(page) if not re.search(r"_PD\.\w+$", i)]}


def canyon(fetcher, model):
    # Canyon files each view under images/top/<year>_TOP-<n>/ and images/detail/, named by product number.
    page = fetcher.get(model["url"]) or ""
    pid = re.search(r"/(\d+)\.html", model["url"])
    if not pid:
        return {}
    found = re.findall(r"https://www\.canyon\.com/dw/image/v2/[^\"'\s?]+/images/(?:top|detail)/[^\"'\s?]*[_/]%s_[^\"'\s?]+\.(?:png|jpe?g)"
                       % pid.group(1), page)
    return {"": [u + "?sw=1200" for u in dict.fromkeys(found)]}


def cube(fetcher, model):
    # synqup_<sku>_S_00 is the side view; _D_00.._D_04 the details and _P_00 another angle.
    page = fetcher.get(model["url"]) or ""
    sku = re.search(r"/(\d+)$", model["url"].rstrip("/"))
    if not sku:
        return {}
    found = re.findall(r"https://file\.cube\.eu/[^\"'\s?]+/media/[^\"'\s?]+/synqup_%s_(?:D_\d\d|P_00)\.jpg" % sku.group(1), page)
    return {"": list(dict.fromkeys(found))}


def specialized(fetcher, model):
    # The hero shot names the bike and colour (97227-30_AETHOS-EXPERT-AXS-..._HERO-PDP); the other views share that name.
    page = fetcher.get(model["url"]) or ""
    hero = re.search(r"/([\w-]+)_HERO-PDP\.webp", page)
    if not hero:
        return {}
    found = re.findall(r"https://resources\.specialized\.com/media-libraries/[^\"'\s?]+/%s_(?!HERO)[A-Z0-9-]+\.webp"
                       % re.escape(hero.group(1)), page)
    return {"": list(dict.fromkeys(found))}


READERS = {"Trek": trek, "Giant": giant_page, "Cannondale": cannondale, "Canyon": canyon, "Cube": cube,
           "Specialized": specialized}


def collect(brand, db_path, fetcher=None):
    path = os.path.join(ROOT, "data", "galleries", f"{brand}.json")
    found = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    fetcher = fetcher or Fetcher(delay=1.0)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    models = conn.execute("SELECT name, url FROM models WHERE brand = ? AND url IS NOT NULL", (brand,)).fetchall()
    for model in models:
        if found.get(model["url"]):  # a page that gave nothing is tried again
            continue
        try:
            urls = READERS[brand](fetcher, dict(model))
        except Exception as exc:  # one page shouldn't stop the run
            log.warning("%s %s: %s", brand, model["name"], exc)
            continue
        slug = compact(model["name"])
        gallery = {}
        for colour, links in urls.items():
            saved = [save_photo(fetcher, brand, slug, None, u, angle=n + 1, colour=colour or None,
                                rel=f"{brand}/gallery/{slug}{'_' + compact(colour) if colour else ''}_{n + 1}.jpg")
                     for n, u in enumerate(links)]
            if any(saved):
                gallery[colour] = [rel for rel in saved if rel]
        found[model["url"]] = gallery
        log.info("%s %s: %d photos", brand, model["name"], sum(len(g) for g in gallery.values()))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:  # after each model, so a stopped run keeps its work
            json.dump(found, fh, ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("brands", nargs="+")
    ap.add_argument("--db", default=os.path.join(ROOT, "instance", "bikecompare.sqlite3"))
    args = ap.parse_args()
    for brand in [b for b in READERS if b.lower() in {a.lower() for a in args.brands}]:
        collect(brand, args.db)
