"""Specialized NL: road and gravel bikes.

The pages are Next.js server components; the product data (specs, prices per
size, colours, model year) is in the self.__next_f payload, not in the HTML.
"""
import json
import re

from .common import clean, is_ebike, log, normalize_specs

BRAND = "Specialized"
BASE = "https://www.specialized.com"
# Specialized's image server still serves the photos of bikes it sold years ago (the 2019 Roubaix, the
# 2020 Tarmac SL7), every colour and view under its own ID; PNG keeps the transparency, their JPEG turns it black.
IMAGE = "https://resources.specialized.com/image/{}?q=80&w=1200&fm=png"
SIDE_VIEW = re.compile(r"_HERO(?:-SQUARE)?$")
LISTINGS = [
    ("/nl/nl/shop/fietsen/racefietsen", "Racefietsen"),
    ("/nl/nl/shop/fietsen/gravelbikes", "Gravelbikes"),
]


def rsc_payload(page):
    parts = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>', page, re.S):
        try:
            parts.append(json.loads(m.group(1)))
        except ValueError:
            pass
    return "".join(parts)


def enclosing_object(text, idx):
    depth = 0
    for i in range(idx, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                try:
                    return json.JSONDecoder().raw_decode(text[i:])[0]
                except ValueError:
                    return None
            depth -= 1
    return None


def other_views(images, side):
    """The views of one colour besides the side view (front and rear three-quarter, close-ups), in Specialized's
    order: the photos named like the side view ("94920-04_TARMAC-SL7-..._FDSQ"), not the banners beside them."""
    images = sorted(images or [], key=lambda i: i.get("displayOrder") or 0)
    ids = dict.fromkeys(i.get("code") or i.get("id") for i in images)
    stem = SIDE_VIEW.sub("", side or "")
    return [IMAGE.format(i) for i in ids if stem and i and i.startswith(stem + "_") and not SIDE_VIEW.search(i)]


def archived_colours(page):
    """{colour: (side view URL, [other view URLs])} from a page of the 2019-2021 shop, where each option of the
    product's Color attribute carries its imageSet; {} for other layouts."""
    m = re.search(r'\{"name":"Colou?r","type":"swatch","options":\[', page)
    if not m:
        return {}
    try:
        options = json.JSONDecoder().raw_decode(page, m.end() - 1)[0]
    except ValueError:
        return {}
    found = {}
    for option in options:
        ids = [i.get("id") for i in option.get("imageSet") or [] if i.get("id")]
        side = next((i for i in ids if i.endswith("_HERO")), ids[0] if ids else None)
        name = clean(option.get("name") or "")
        if name and side:
            found.setdefault(name, (IMAGE.format(side), other_views(option.get("imageSet"), side)))
    return found


def page_colours(page, url):
    """{colour: (side view URL, [other view URLs])} from a product page of any year: today's layout or the 2019-2021 one."""
    try:
        bike = parse(page, url)
    except Exception:  # an older layout
        bike = None
    if bike and bike["color_names"]:
        return {c: (side, views) for c, side, views in
                zip(bike["color_names"], bike["color_image_urls"], bike["color_angle_urls"]) if side}
    return archived_colours(page)


def category_of(name, category_paths):
    low = f"{name} {category_paths}".lower()
    if "gravel" in low or re.search(r"\b(diverge|crux)\b", low):
        return "Gravel"
    if "triatlon" in low or "shiv" in low:
        return "Triathlon / TT"
    if "roubaix" in low:
        return "Endurance"
    return "Race"


def product_urls(fetcher):
    seen = {}
    for path, _label in LISTINGS:
        page = fetcher.get(BASE + path) or ""
        for href in re.findall(r'href="(/nl/nl/[^"?]+/p/\d+)(?:\?[^"]*)?"', page):
            seen.setdefault(href.rsplit("/", 1)[-1], BASE + href)
    return list(seen.values())


SITEMAP = BASE + "/nl/nl/sitemap.xml"


def sitemap_urls(fetcher):
    """Every product page in Specialized's NL sitemap, as /nl/nl/<name>/p/<id> URLs.

    The shop listings show only the bikes on sale; the sitemap also lists the ones Specialized stopped selling
    and still serves a page for (the Tarmac SL8 Expert - SRAM Rival AXS, every Venge). The sitemap writes
    them as /nl/<name>/p/<id>, which 404s: the page lives under /nl/nl/."""
    index = fetcher.get(SITEMAP) or ""
    urls = {}
    for sitemap in re.findall(r"<loc>\s*([^<\s]+Product[^<\s]*\.xml)\s*</loc>", index):
        for name, pid in re.findall(r"<loc>\s*https://www\.specialized\.com/nl/(?:nl/)?([^/<]+)/p/(\d+)\s*</loc>",
                                    fetcher.get(sitemap) or ""):
            urls.setdefault(pid, f"{BASE}/nl/nl/{name}/p/{pid}")
    return list(urls.values())


def parse(page, url):
    text = rsc_payload(page)
    product = None
    for m in re.finditer(r'"modelYear":\d{4}', text):
        candidate = enclosing_object(text, m.start())
        if candidate and candidate.get("isBike") and "colors" in candidate:
            product = candidate
            break
    if not product:
        return None
    pairs = []
    for m in re.finditer(r'\{"headline":"[^"]*","name":"[^"]*","specs":\[', text):
        group = enclosing_object(text, m.start() + 1)
        for s in (group or {}).get("specs", []):
            pairs.append((s.get("name") or s.get("code"), s.get("description")))
    if not pairs:  # fall back to the callouts at the top of the page
        pairs = [(product.get(f"callout{n}Title"), product.get(f"callout{n}Desc")) for n in range(1, 7)]
    prices, sizes, colours, colour_images, colour_hexes, colour_angles = [], [], [], [], [], []
    image = None
    for colour in product["colors"]:
        # PNG keeps the transparency; their JPEG turns it black
        photo = IMAGE.format(colour["plpImageID"]) if colour.get("plpImageID") else None
        image = image or photo
        name = clean(colour.get("displayName") or colour.get("colorName"))
        if name:
            colours.append(name)
            colour_images.append(photo)
            colour_hexes.append((colour.get("colorValues") or [None])[0])
            colour_angles.append(other_views(colour.get("images"), colour.get("plpImageID")))
        for size in colour.get("sizes") or []:
            if size.get("name") and size["name"] not in sizes:
                sizes.append(size["name"])
            for sku in (size.get("skus") or {}).get("values") or []:
                raw = ((sku.get("prices") or {}).get("regular") or {}).get("raw")
                if raw:
                    prices.append(raw)
    cats = [c.get("name") for c in product.get("categories") or []]
    paths = " ".join(c.get("url") or "" for c in product.get("categories") or [])
    return {
        "name": clean(product["name"]),
        "brand": BRAND,
        "url": url,
        "sku": product.get("code"),
        "price": min(prices) if prices else None,
        "category": category_of(product["name"], paths),
        "family": cats[-1] if cats else "",
        "model_year": product.get("modelYear"),
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "color_hexes": colour_hexes,  # the swatch colour Specialized shows for each
        "sizes": sizes,
        "image_url": image,
        "color_image_urls": colour_images,
        "color_angle_urls": colour_angles,  # each colour's other views
    }


def scrape(fetcher, limit=None):
    bikes = []
    for url in product_urls(fetcher)[:limit]:
        page = fetcher.get(url)
        bike = parse(page, url) if page else None
        if not bike:
            log.warning("Specialized: no product data in %s", url)
            continue
        if is_ebike(bike["name"], bike["category"], url):
            continue
        bikes.append(bike)
        log.info("Specialized: %s (%s)", bike["name"], bike["price"])
    return bikes
