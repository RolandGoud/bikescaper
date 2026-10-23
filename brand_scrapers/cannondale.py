"""Cannondale NL: road, endurance, gravel and cyclocross bikes.

Product URLs come from the sitemap (/nl-nl/bikes/road/<category>/<family>/<model>).
Each product page has schema.org ProductGroup JSON with prices per variant, a
spec list in the HTML and a dataLayer item with the category.
"""
import json
import re

from .common import clean, is_ebike, log, normalize_specs, parse_price

BRAND = "Cannondale"
SITEMAPS = ["https://a304077.sitemaphosting6.com/4356448/sitemap1.xml",
            "https://a304077.sitemaphosting6.com/4356448/sitemap2.xml"]


def product_urls(fetcher):
    urls = []
    for sitemap in SITEMAPS:
        for url in re.findall(r"<loc>([^<]+)</loc>", fetcher.get(sitemap) or ""):
            if re.match(r"https://www\.cannondale\.com/nl-nl/bikes/road/[a-z-]+/[a-z0-9-]+/[a-z0-9-]+$", url):
                urls.append(url)
    return list(dict.fromkeys(urls))


def product_group(page):
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") in ("ProductGroup", "Product"):
            return data
    return {}


def parse(page, url):
    group = product_group(page)
    header = re.search(r'window\.PDP_HEADER = "([^"]+)"', page)
    name = clean(header.group(1) if header else group.get("name"))
    if not name:
        return None
    variants = group.get("hasVariant") or ([group] if group.get("offers") else [])
    prices, sizes, colours, colour_images = [], [], [], []
    for v in variants:
        offers = v.get("offers") or []
        for offer in offers if isinstance(offers, list) else [offers]:
            if parse_price(offer.get("price")):
                prices.append(parse_price(offer["price"]))
        if v.get("size") and v["size"] not in sizes:
            sizes.append(v["size"])
        if v.get("color") and v["color"] not in colours:
            colours.append(v["color"])
            # Each colour's gallery: _PD is the side view, _3Q and _D1.. the angles and close-ups.
            photos = v.get("image") or []
            photos = [photos] if isinstance(photos, str) else photos
            colour_images.append(next((u for u in photos if "_PD." in u), photos[0] if photos else None))
    if not prices:
        m = re.search(r"item_variant:[^}]*?price: ([\d.]+)", page)
        prices = [float(m.group(1))] if m else []
    pairs = re.findall(r'<strong class="name">(.*?)</strong>\s*<div class="desc">(.*?)</div>', page, re.S)
    specs = normalize_specs(pairs)
    cat = re.search(r'item_category3: "([^"]*)"', page)
    year = re.search(r"COLL(20\d\d)", page) or re.search(r"/C(\d\d)_", page)
    image = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": clean(specs.get("Model Code")) or group.get("productGroupID"),
        "price": min(prices) if prices else None,
        "category": cat.group(1) if cat else "",
        "model_year": (int(year.group(1)) if len(year.group(1)) == 4 else 2000 + int(year.group(1))) if year else None,
        "specifications": specs,
        "color_names": colours,
        "sizes": sizes,
        "image_url": widen_jpeg(image.group(1)) if image else None,
        "color_image_urls": [widen_jpeg(u) if u else None for u in colour_images],
    }


def widen_jpeg(url):
    """widen serves any width and format: ask for an 1000px JPEG instead of the 2000px PNG."""
    return re.sub(r"/\d+px@1x/(.+)\.png", r"/1000px@1x/\1.jpg", url)


def scrape(fetcher, limit=None):
    bikes = []
    for url in product_urls(fetcher)[:limit]:
        page = fetcher.get(url)
        bike = parse(page, url) if page else None
        if not bike:
            log.warning("Cannondale: no product data in %s", url)
            continue
        if is_ebike(bike["name"], bike["category"], url):
            continue
        bikes.append(bike)
        log.info("Cannondale: %s (%s)", bike["name"], bike["price"])
    return bikes
