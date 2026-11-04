"""The other photos of each current model (close-ups, front, rear), from its page on the brand's site.

    python -m brand_scrapers.galleries trek giant cannondale canyon cube specialized bmc lapierre scott orbea \
        factor ridley cervelo

Saves the photos to images/<Brand>/gallery/ and lists them in data/galleries/<Brand>.json as
{model page URL: {colour: [photo]}}; the colour is "" when the page shows one colour only. The side
view the catalogue already has is left out. Scott is read from data/Scott/scott_gallery.json (its
site only answers a visible Chrome); Orbea's pages are opened in that Chrome (browser.py), its photos
are fetched plainly. Factor's come from the family page, Ridley's are the frame's photo shoot. Bianchi
shows one photo per colour, the one the catalogue already has, so it has no reader.
"""
import argparse
import json
import os
import re
import sqlite3
from urllib.parse import quote, quote_plus, unquote

from . import bmc, factor, giant, lapierre, orbea, scott
from .nuxt import nuxt_state
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


def _canyon_views(page, pid):
    found = re.findall(r"https://www\.canyon\.com/dw/image/v2/[^\"'\s?]+/images/(?:top|detail)/[^\"'\s?]*[_/]%s_[^\"'\s?]+\.(?:png|jpe?g)"
                       % pid, page)
    return [u + "?sw=1200" for u in dict.fromkeys(found)]


def canyon(fetcher, model):
    # Canyon files each view under images/top/<year>_TOP-<n>/ and images/detail/, named by product number.
    # A build Canyon carried into a new model year gets a new number, and the old page loses its photos:
    # then the site's search finds the build's page under the same path with the newer number.
    pid = re.search(r"/(\d+)\.html", model["url"])
    if not pid:
        return {}
    found = _canyon_views(fetcher.get(model["url"]) or "", pid.group(1))
    if not found and model.get("name"):
        path = model["url"].split("?")[0][:pid.start()]
        results = fetcher.get("https://www.canyon.com/nl-nl/search?q=" + quote_plus(model["name"])) or ""
        newer = sorted({int(n) for n in re.findall(re.escape(path) + r"/(\d+)\.html", results)} - {int(pid.group(1))},
                       reverse=True)
        for number in newer:
            found = _canyon_views(fetcher.get(f"{path}/{number}.html") or "", number)
            if found:
                break
    return {"": found}


def cube(fetcher, model):
    # synqup_<sku>_S_00 is the side view; _D_00.._D_04 the details and _P_00 another angle.
    page = fetcher.get(model["url"]) or ""
    sku = re.search(r"/(\d+)$", model["url"].rstrip("/"))
    if not sku:
        return {}
    found = re.findall(r"https://file\.cube\.eu/[^\"'\s?]+/media/[^\"'\s?]+/synqup_%s_(?:D_\d\d|P_00)\.jpg" % sku.group(1), page)
    return {"": list(dict.fromkeys(found))}


_FACTOR_FAMILIES = {}


def _letters(text):
    return re.sub(r"[^a-z]", "", (text or "").lower())


def factor_page(fetcher, model):
    # A build's own page shows one photo per colour; its family page (/bikes/monza) has the studio shots of each
    # colour from four sides (Studio-MONZA-SteelGreen-Force-45-ds45.png: drive side and non-drive side, at 45
    # and 180 degrees) and the colour's close-ups (design-aluto-quattro_grey-01.jpg, Feature-MONZA-SteelGreen-01).
    handle = model["url"].rstrip("/").rsplit("/", 1)[-1]
    if not _FACTOR_FAMILIES:
        _FACTOR_FAMILIES.update({f: None for f in re.findall(r'href="/bikes/([a-z0-9-]+)"', fetcher.get(factor.BASE + "/bikes") or "")})
    family = max((f for f in _FACTOR_FAMILIES if handle.startswith(f + "-")), key=len, default=None)
    if not family:
        return {}
    if _FACTOR_FAMILIES[family] is None:
        page = fetcher.get(f"{factor.BASE}/bikes/{family}") or ""
        _FACTOR_FAMILIES[family] = list(dict.fromkeys(
            re.findall(r"https://images\.ctfassets\.net/[^\"'\s?\\]+\.(?:png|jpe?g|webp)", page)))
    photos = _FACTOR_FAMILIES[family]
    colours = json.loads(model.get("colors") or "[]") if isinstance(model.get("colors"), str) else model.get("colors") or []
    found = {}
    for colour in colours:
        whole, first = _letters(colour), _letters(colour.split()[0])
        mine = [u for u in photos if whole in _letters(u.rsplit("/", 1)[-1])] or (
            [u for u in photos if len(first) > 3 and first in _letters(u.rsplit("/", 1)[-1])])
        groupset = [w for w in handle[len(family) + 1:].split("-") if w in ("force", "red", "rival", "ultegra", "dura", "record")]
        views = {}
        for u in mine:  # one shot per side; the one of this build's groupset when there are several
            view = re.search(r"(?i)[-_](n?ds)(45|180)\.\w+$", u)
            if view and re.search(r"(?i)/(?:studio|pdp-hero)-", u):
                key = view.group(1).lower() + view.group(2)
                if key not in views or any(re.search(r"(?i)-%s-" % w, u) for w in groupset):
                    views[key] = u
        close = [u for u in mine if re.search(r"(?i)/(?:design|feature)-", u)]
        links = [views[k] + "?w=1600&fm=jpg" for k in ("ds45", "nds45", "ds180", "nds180") if k in views]
        links += [u + "?w=1600&fm=jpg" for u in close]
        if links:
            found[colour] = links
    return found


RIDLEY_MOST = 12


def ridley_page(fetcher, model):
    # Each frame has a photo shoot (the "inspirations" on its build pages: X-nightRS-1.jpg ...), shown on every
    # build of it; it doesn't follow the colour picked. Some shoots run to 150 photos: the first dozen will do,
    # and Windows' "... kopiëren" duplicates are left out.
    state = nuxt_state(fetcher.get(model["url"]) or "") or {}
    bike = ((state.get("data") or [{}])[0] or {}).get("bike") or {}
    pictures = (bike.get("inspirations") or {}).get("pictures") or []
    names = [p.get("name") for p in pictures if isinstance(p, dict) and re.search(r"(?i)\.(jpe?g|png)$", p.get("name") or "")
             and not re.search(r"(?i)\bkopi|\bcopy\b", p.get("name"))]
    names.sort(key=lambda n: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", n)])
    return {"": ["https://images.cyclingfactory.be/inspirations/" + quote(n) for n in names[:RIDLEY_MOST]]} if names else {}


def cervelo_page(fetcher, model):
    # Besides the side view per colour, a build page shows two or three close-ups of its family
    # (0L0R5HDI1C_CRANKSET-WEB-RESIZED.png), named by the article number of the build they show: only the
    # ones of this frame and groupset (the number without its colour digits) are of this bike.
    build = (model.get("sku") or "")[:8]
    if len(build) < 8:
        return {}
    page = fetcher.get(model["url"]) or ""
    found = re.findall(r"(?://www\.cervelo\.com/cdn/shop/files/|https://cdn\.shopify\.com/s/files/[\d/]+/files/)"
                       r"((?:\d+_\d+_)?%s\w{2}_(?!PROFILE)[A-Z]+-WEB[\w-]*\.(?:png|jpe?g|webp))" % re.escape(build), page)
    return {"": [f"https://www.cervelo.com/cdn/shop/files/{n}?width=1600" for n in dict.fromkeys(found)]} if found else {}


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
           "Orbea": orbea_page, "Factor": factor_page, "Ridley": ridley_page, "Cervelo": cervelo_page}
CHROME = ("Orbea",)
SHARED = ("Ridley",)  # brands whose gallery is the frame's, the same photos for every build: saved once, by name  # brands whose pages only open in a visible Chrome; their photos still answer plain requests


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
    models = conn.execute("SELECT name, url, sku, colors FROM models WHERE brand = ? AND url IS NOT NULL", (brand,)).fetchall()
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
            saved = [save_photo(fetcher, brand, slug, None, u, angle=n + 1, colour=colour or None, rel=(
                         f"{brand}/gallery/shared/{compact(unquote(u.split('?')[0].rsplit('/', 1)[-1].rsplit('.', 1)[0]))}.jpg"
                         if brand in SHARED else f"{brand}/gallery/{slug}{'_' + compact(colour) if colour else ''}_{n + 1}.jpg"))
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
