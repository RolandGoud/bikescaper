"""The other photos of each current model (close-ups, front, rear), from its page on the brand's site.

    python -m brand_scrapers.galleries trek giant cannondale canyon cube specialized bmc lapierre scott orbea

Saves the photos to images/<Brand>/gallery/ and lists them in data/galleries/<Brand>.json as
{model page URL: {colour: [photo]}}; the colour is "" when the page shows one colour only. The side
view the catalogue already has is left out. Scott is read from data/Scott/scott_gallery.json (its
site only answers a visible Chrome); Orbea's pages are opened in that Chrome (browser.py), its photos
are fetched plainly. Bianchi, Cervélo and Factor show one photo per colour, the one the catalogue
already has, so they have no reader.
"""
import argparse
import json
import os
import re
import sqlite3

from . import bmc, giant, lapierre, orbea, scott
from .archive import compact
from .common import ROOT, Fetcher, clean, log, shopify_products
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


_LISTINGS = {}


def _shopify_product(fetcher, model, base):
    """The store's JSON of a Shopify product (/products/<handle>.json), or {}. A product the store lists but
    doesn't sell in this country answers 404 there; its entry in /products.json has the same photos."""
    url = model["url"].split("?")[0]
    if not url.startswith(base):  # an archived line's page on web.archive.org
        return {}
    try:
        product = json.loads(fetcher.get(url + ".json") or "{}").get("product")
    except ValueError:
        product = None
    if product:
        return product
    if base not in _LISTINGS:
        _LISTINGS[base] = {p.get("handle"): p for p in shopify_products(fetcher, base)}
    return _LISTINGS[base].get(url.rsplit("/", 1)[-1]) or {}


def bmc_page(fetcher, model):
    # One colour per product, its photos numbered: bmc-2027-kaius-01-three-gravel-bike-black-1.jpg is the side view.
    fetcher.delays.update(bmc.HOST_DELAY)
    number = lambda src: int((re.search(r"-(\d+)(?:_[\w-]+)?\.\w+(?:\?|$)", src) or [0, 0])[1])
    images = sorted((i["src"] for i in _shopify_product(fetcher, model, bmc.BASE).get("images") or []), key=number)
    return {"": [bmc.sized(src) for src in images if number(src) != 1]} if images else {}


def lapierre_page(fetcher, model):
    # The photos come in one run per colour: the colour's side view (the image its variants point to) first,
    # then that colour's other angles. The geometry drawing sits between the runs.
    product = _shopify_product(fetcher, model, lapierre.BASE)
    options = {o["name"].lower(): i + 1 for i, o in enumerate(product.get("options") or [])}
    variants = {v["id"]: v for v in product.get("variants") or []}
    runs, colour = {}, ""
    for img in sorted(product.get("images") or [], key=lambda i: i.get("position") or 0):
        if re.search(r"(?i)geometr", (img.get("alt") or "") + img.get("src", "")):
            continue
        if img.get("variant_ids"):  # a side view: a new colour starts
            v = variants.get(img["variant_ids"][0]) or {}
            name = clean(v.get(f"option{options['color']}")) if "color" in options else ""
            colour = name[:1].upper() + name[1:]
            runs.setdefault(colour, [])
            continue
        runs.setdefault(colour, []).append(lapierre.sized(img["src"]))
    runs = {c: u for c, u in runs.items() if u}
    return {"": next(iter(runs.values()))} if len(runs) == 1 else runs


def scott_page(fetcher, model):
    # data/Scott/scott_gallery.json has every photo of every colour, the side view among them.
    path = os.path.join(ROOT, "data", "Scott", "scott_gallery.json")
    entry = next((e for e in (json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}).values()
                  if e.get("url") == model["url"]), None)
    by_colour = {}
    for img in (entry or {}).get("images") or []:
        by_colour.setdefault(img.get("color") or "", []).append(img["src"])
    return {c: [scott.cloudinary_width(s) for s in srcs if s != scott.side_photo(srcs)]
            for c, srcs in by_colour.items() if len(srcs) > 1}


def orbea_page(fetcher, model):
    # The page's product JSON lists each photo with its colour code and view ("side", ...).
    product = orbea.js_json(fetcher.get(model["url"]) or "", "product") or {}
    names = {c.get("code"): clean(c.get("name")) for c in product.get("colors") or [] if c.get("name")}
    found = {}
    for img in product.get("images") or []:
        if img.get("view") != "side" and img.get("src") and img.get("color") in names:
            found.setdefault(names[img["color"]], []).append(img["src"])
    return {"": next(iter(found.values()))} if len(names) == 1 and found else found


READERS = {"Trek": trek, "Giant": giant_page, "Cannondale": cannondale, "Canyon": canyon, "Cube": cube,
           "Specialized": specialized, "BMC": bmc_page, "Lapierre": lapierre_page, "Scott": scott_page,
           "Orbea": orbea_page}
CHROME = ("Orbea",)  # brands whose pages only open in a visible Chrome; their photos still answer plain requests


def collect(brand, db_path, fetcher=None):
    path = os.path.join(ROOT, "data", "galleries", f"{brand}.json")
    found = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    fetcher = fetcher or Fetcher(delay=1.0)
    pages = fetcher
    if brand in CHROME and isinstance(fetcher, Fetcher):
        from .browser import BrowserFetcher
        pages = BrowserFetcher(delay=2.0)
    try:
        _collect(brand, db_path, path, found, fetcher, pages)
    finally:
        if pages is not fetcher:
            pages.close()


def _collect(brand, db_path, path, found, fetcher, pages):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    models = conn.execute("SELECT name, url FROM models WHERE brand = ? AND url IS NOT NULL", (brand,)).fetchall()
    for model in models:
        if found.get(model["url"]):  # a page that gave nothing is tried again
            continue
        try:
            urls = READERS[brand](pages, dict(model))
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
