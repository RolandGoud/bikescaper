"""Cervélo: road, gravel and TT bikes from the Dutch store (euro prices).

cervelo.com is a Shopify store, but its /products.json leaves the bikes out. The product
sitemap lists every bike, its handle ending in the model year (s5-ultegra-di2-2027);
/en-nl/products/<handle>.json gives the colours, sizes and Dutch prices, and the product
page embeds the spec sheet as URL-encoded JSON (`products: [JSON.parse(decodeURIComponent('...'))]`)
with one field per part (rear_derailleur, crankset, ...).
"""
import json
import re
from urllib.parse import unquote

from .common import clean, is_ebike, log, normalize_specs, parse_price, size_name

BRAND = "Cervelo"  # without the accent: it names the data/ and images/ folders and the snapshot file
SITE = "https://www.cervelo.com"
BASE = SITE + "/en-nl"
FAMILIES = {  # first word of the handle -> category
    "s5": "Race",
    "r5": "Race",
    "r3": "Race",
    "soloist": "Race",
    "caledonia": "Endurance",
    "aspero": "Gravel",
    "rouvida": "Gravel",
    "p5": "Triathlon / TT",
    "p": "Triathlon / TT",  # p-series
}
# Cervélo's spec fields -> the labels normalize_specs knows; fields not listed are dropped.
FIELDS = {
    "fork": "Voorvork", "one_piece_handlebar_stem": "Stuur/stuurpen (geïntegreerd)", "handlebars": "Stuur",
    "aero_basebar": "Stuur", "aero_extension": "Aero extensions", "stem": "Stuurpen", "seatpost": "Zadelpen",
    "saddle": "Zadel", "bb": "Bottom bracket", "headset": "Balhoofdstel", "front_thru_axle": "As voorwiel",
    "rear_thru_axle": "As achterwiel", "front_wheel": "Wiel voor", "rear_wheel": "Wiel achter",
    "tires": "Buitenband", "shifters": "Shifter", "left_shifter": "Shifter links", "right_shifter": "Shifter",
    "brakes": "Rem", "crankset": "Crankstel", "chainring": "Kettingblad", "power_meter": "Vermogensmeter",
    "chain": "Ketting", "cassette": "Cassette", "front_derailleur": "Voorderailleur",
    "rear_derailleur": "Achterderailleur", "rotors": "Remschijf", "weight": "Gewicht",
}
WORDS = {"di2": "Di2", "axs": "AXS", "grx": "GRX", "xplr": "XPLR", "cx": "CX", "e1": "E1", "rx": "RX"}


def family_of(handle):
    word = (handle or "").split("-")[0].lower()
    return word if word in FAMILIES else None


def category_of(handle):
    if handle.startswith("r5-cx"):  # the cyclocross R5
        return "Gravel"
    return FAMILIES[family_of(handle)]


def model_year(handle):
    m = re.search(r"-(20\d\d)$", handle or "")
    return int(m.group(1)) if m else None


def tidy_name(title):
    """"S5 ULTEGRA DI2" -> "S5 Ultegra Di2"; "ÁSPERO-5 GRX RX827 DI2" -> "Aspero-5 GRX RX827 Di2"."""
    out = []
    title = re.sub(r"(?i)á", "a", clean(title))  # ÁSPERO
    for word in title.split():
        low = word.lower()
        if low in WORDS:
            out.append(WORDS[low])
        elif re.search(r"\d", word) and not re.match(r"^[a-z]+-\d$", low):
            out.append(word.upper())  # S5, R5, RX827, 1X
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in word.split("-")))
    return " ".join(out)


def bike_handles(fetcher):
    """Bike handles from the product sitemaps: the ones that end in a model year and start with a known family."""
    index = fetcher.get(SITE + "/sitemap.xml") or ""
    handles = []
    for loc in re.findall(r"<loc>(https://www\.cervelo\.com/sitemap_products_[^<]+)</loc>", index):
        page = fetcher.get(loc.replace("&amp;", "&")) or ""
        for handle in re.findall(r"<loc>https://www\.cervelo\.com/products/([a-z0-9-]+)</loc>", page):
            if model_year(handle) and family_of(handle) and handle not in handles:
                handles.append(handle)
    return handles


def spec_sheet(page, handle):
    """The part fields of this build from the product page, as (label, value) pairs."""
    for blob in re.findall(r"JSON\.parse\(decodeURIComponent\('([^']*)'\)\)", page or ""):
        try:
            data = json.loads(unquote(blob))
        except ValueError:
            continue
        if not isinstance(data, dict) or not str(data.get("url", "")).endswith("/products/" + handle):
            continue
        return [(FIELDS[k], clean(v.get("value"))) for k, v in data.items()
                if k in FIELDS and isinstance(v, dict) and clean(v.get("value"))]
    return []


def colour_name(text):
    """"Reef Blue (S5 2027)" -> "Reef Blue"."""
    return clean(re.sub(r"\([^)]*\)", "", text or ""))


def parse(product, page, url, handle):
    name = tidy_name(product["title"])
    options = {o["name"].lower(): i + 1 for i, o in enumerate(product.get("options") or [])}
    colour_opt, size_opt = options.get("color"), options.get("size")
    variants = product.get("variants") or []
    images = {img.get("id"): img.get("src") for img in product.get("images") or []}
    colours, colour_images = [], []
    for v in variants:
        colour = colour_name(v.get(f"option{colour_opt}")) if colour_opt else None
        if colour and colour not in colours:
            colours.append(colour)
            colour_images.append(images.get(v.get("image_id")))
    sizes = list(dict.fromkeys(size_name(v.get(f"option{size_opt}")) for v in variants)) if size_opt else []
    prices = [parse_price(v.get("price")) for v in variants if parse_price(v.get("price"))]
    first = (product.get("images") or [{}])[0].get("src")
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": (variants[0].get("sku") or "")[:10] if variants else handle,
        "price": min(prices) if prices else None,
        "category": category_of(handle),
        "model_year": model_year(handle),
        "specifications": normalize_specs(spec_sheet(page, handle)),
        "color_names": colours,
        "sizes": sizes,
        "image_url": next((c for c in colour_images if c), None) or first,
        "color_image_urls": colour_images,
    }


def scrape(fetcher, limit=None):
    bikes = []
    for handle in bike_handles(fetcher):
        if limit is not None and len(bikes) >= limit:
            break
        url = f"{BASE}/products/{handle}"
        try:
            product = json.loads(fetcher.get(url + ".json") or "{}").get("product")
        except ValueError:
            product = None
        if not product or is_ebike(product.get("title"), handle):
            continue
        bike = parse(product, fetcher.get(url), url, handle)
        if not bike["specifications"]:
            log.warning("Cervelo: no spec sheet in %s", url)
        bikes.append(bike)
        log.info("Cervelo: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
