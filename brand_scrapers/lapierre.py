"""Lapierre: road, gravel and TT bikes from the Belgian store (euro prices; there is no Dutch site).

lapierrebikes.com is a Shopify store. /en-be/products.json lists every bike with its sizes,
colours (each colour's variants name its photo) and price; the product page adds the spec
sheet (<p><strong>Label</strong>: value</p> rows) and the geometry table. The model year is
in the photo's file name (LAPIERRE_MY26_..., sometimes base64-encoded by Lapierre's image
pipeline).
"""
import base64
import re

from .common import clean, is_ebike, log, normalize_specs, parse_price, shopify_products, size_name

BRAND = "Lapierre"
BASE = "https://lapierrebikes.com/en-be"
FAMILIES = {  # first word of the name -> category; the rest (XR, Prorace, Zesty, Spicy, ...) are mountain bikes
    "xelius": "Race",
    "pulsium": "Endurance",
    "sensium": "Endurance",
    "aerostorm": "Triathlon / TT",
    "crosshill": "Gravel",
}
# Lapierre's labels that normalize_specs doesn't know; None drops the row.
LABELS = {
    "derailleur rear": "Achterderailleur", "derailleur front": "Voorderailleur", "shifter right": "Shifter",
    "shifter left": "Shifter links", "front fork": "Voorvork", "wheel set": "Wiel voor", "pedal": "Pedaal",
    "grips": "Stuurlint", "gear": None, "number of gears": None, "maximum loadable weight": None,
    "modular rail system": None, "travel": None, "rear travel": None, "shock": None, "damper": None,
}


def family_of(name):
    word = re.sub(r"[^a-z]", "", name.split()[0].lower().replace("é", "e")) if name else ""
    return word if word in FAMILIES else None


def tidy_name(title):
    """"xelius DRS 8.0" and "Xélius DRS 5.0" -> "Xelius DRS ..."; "Aérostorm drs" -> "Aerostorm DRS"."""
    name = clean(title).split(" -- ")[0]
    name = re.sub(r"(?i)\bx[ée]lius\b", "Xelius", name)
    name = re.sub(r"(?i)\ba[ée]rostorm\b", "Aerostorm", name)
    return re.sub(r"\bdrs\b", "DRS", name)


def model_year(images):
    """MY26 from the photo's file name; a name like czM6Ly9... is base64 of the original S3 path."""
    for img in images or []:
        stem = img.get("src", "").split("/")[-1].split("?")[0].rsplit(".", 1)[0]
        texts = [stem]
        try:
            texts.append(base64.urlsafe_b64decode(stem.split("_")[0] + "=" * (-len(stem.split("_")[0]) % 4))
                         .decode("utf-8", "ignore"))
        except ValueError:
            pass
        for text in texts:
            m = re.search(r"\bMY ?(\d\d)\b|_MY(\d\d)_|MY(\d\d)\b", text)
            if m:
                return 2000 + int(next(g for g in m.groups() if g))
    return None


def sized(url, width=1200):
    return (url + ("&" if "?" in url else "?") + f"width={width}") if url else None


def parse_page(page):
    """(spec pairs, has a geometry table) from a product page."""
    pairs = []
    for label, value in re.findall(r"<p><strong>(.*?)</strong>\s*:\s*(.*?)</p>", page or "", re.S):
        label = clean(label)
        key = LABELS.get(label.lower(), label)
        if key and clean(value):
            pairs.append((key, value))
    return pairs


def parse(product, page, url):
    name = tidy_name(product["title"])
    options = {o["name"].lower(): i + 1 for i, o in enumerate(product.get("options") or [])}
    colour_opt, size_opt = options.get("color"), options.get("frame size")
    variants = product.get("variants") or []
    colours, colour_images = [], []
    for v in variants:
        colour = clean(v.get(f"option{colour_opt}")) if colour_opt else None
        if colour and colour not in colours:
            colours.append(colour)
            colour_images.append(sized((v.get("featured_image") or {}).get("src")))
    if not colours and " -- " in product["title"]:  # "Xelius DRS Frameset -- cold rain grey - glossy"
        colours = [clean(product["title"].split(" -- ", 1)[1])]
        colour_images = [sized((product.get("images") or [{}])[0].get("src"))]
    sizes = list(dict.fromkeys(size_name(v.get(f"option{size_opt}")) for v in variants)) if size_opt else []
    prices = [parse_price(v.get("price")) for v in variants if parse_price(v.get("price"))]
    image = colour_images[0] if colour_images and colour_images[0] else sized((product.get("images") or [{}])[0].get("src"))
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": (variants[0].get("sku") or "")[:5] if variants else product.get("handle"),
        "price": min(prices) if prices else None,
        "category": FAMILIES.get(family_of(name), ""),
        "model_year": model_year(product.get("images")),
        "specifications": normalize_specs(parse_page(page)),
        "color_names": [c[:1].upper() + c[1:] for c in colours],
        "sizes": sizes,
        "image_url": image,
        "color_image_urls": colour_images,
    }


def scrape(fetcher, limit=None):
    bikes = []
    for product in shopify_products(fetcher, BASE):
        if limit is not None and len(bikes) >= limit:
            break
        name = tidy_name(product["title"])
        if not family_of(name) or product.get("product_type") == "E-Bikes" or is_ebike(name):
            continue
        url = f"{BASE}/products/{product['handle']}"
        page = fetcher.get(url)
        bike = parse(product, page, url)
        if not bike["specifications"]:
            log.warning("Lapierre: no spec sheet in %s", url)
        bikes.append(bike)
        log.info("Lapierre: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
