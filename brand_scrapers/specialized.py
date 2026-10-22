"""Specialized NL: road and gravel bikes.

The pages are Next.js server components; the product data (specs, prices per
size, colours, model year) is in the self.__next_f payload, not in the HTML.
"""
import json
import re

from .common import clean, is_ebike, log, normalize_specs

BRAND = "Specialized"
BASE = "https://www.specialized.com"
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
    prices, sizes, colours = [], [], []
    image = None
    for colour in product["colors"]:
        colours.append(clean(colour.get("displayName") or colour.get("colorName")))
        for size in colour.get("sizes") or []:
            if size.get("name") and size["name"] not in sizes:
                sizes.append(size["name"])
            for sku in (size.get("skus") or {}).get("values") or []:
                raw = ((sku.get("prices") or {}).get("regular") or {}).get("raw")
                if raw:
                    prices.append(raw)
        if not image and colour.get("plpImageID"):
            image = f"https://resources.specialized.com/image/{colour['plpImageID']}?q=80&w=1200&fm=jpg"
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
        "color_names": [c for c in colours if c],
        "sizes": sizes,
        "image_url": image,
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
