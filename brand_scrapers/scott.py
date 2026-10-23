"""Scott NL: road, gravel and TT bikes (and framesets) from the NL product sitemap.

scott-sports.com sits behind Imperva, which answers requests and headless
browsers with a challenge, so pages are loaded in a visible Chrome (browser.py).
robots.txt only allows the /nl/en/ catalogue for the Netherlands. Each product
page carries a schema.org ProductGroup with the full spec list and one Product per
colour and size with its EUR price. Photos are on static.scott-sports.com, which
answers plain requests.
"""
import json
import re

from .browser import BrowserFetcher
from .common import clean, is_ebike, log, normalize_specs, parse_price, size_name

BRAND = "Scott"
BASE = "https://www.scott-sports.com/nl/en"
SITEMAP = BASE + "/sitemaps/Product-en-EUR-scottb2c_nl.xml"
FAMILIES = ("addict", "foil", "speedster", "plasma")
# Scott's labels that normalize_specs doesn't know.
LABELS = {
    "Fork": "Voorvork", "Rear Derailleur": "Achterderailleur", "Front Derailleur": "Voorderailleur",
    "Shifters": "Shifter", "Brakes": "Rem", "Front Disc Rotor": "Remschijf", "Rear Disc Rotor": "Remschijf achter",
    "BB-Set": "Bottom bracket", "Seat": "Zadel", "Front Tire": "Buitenband", "Rear Tire": "Achterband",
    "Front Hub": "Naaf voor", "Rear Hub": "Naaf achter", "Grips": "Stuurlint", "H'stem": "Stuurpen",
    "Front Rim": "Velg", "Rear Rim": "Velg achter",
}
SKIP = re.compile(r"^(Key Feature \d+|Max\. System Weight)$")


def product_urls(fetcher):
    xml = fetcher.get(SITEMAP, page=False) or ""
    urls = []
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.match(re.escape(BASE) + r"/product/scott-([a-z0-9-]+?)-(bike|frame-set)(-\d+)?$", url)
        if not m or not re.search(r"(^|-)(%s)(-|$)" % "|".join(FAMILIES), m.group(1)):
            continue
        if is_ebike(m.group(1).replace("-", " ")) or re.search(r"(^|-)(eride|e)(-|$)", m.group(1)):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def product_group(page):
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if item.get("@type") == "ProductGroup":
                return item
            if item.get("@type") == "Product" and item.get("offers"):  # bikes sold in one colour and size
                return dict(item, productGroupID=item.get("sku"), hasVariant=[item])
    return None


def category_of(name, categories):
    low = f"{name} {' '.join(categories)}".lower()
    if "gravel" in low:
        return "Gravel"
    if "plasma" in low or "triathlon" in low or " tri " in f" {low} ":
        return "Triathlon / TT"
    if "foil" in low or "aero" in low:
        return "Aero Race"
    if "addict rc" in low or "race" in low:
        return "Race"
    if "cyclocross" in low or "addict cx" in low:
        return "Cyclocross"
    return "Endurance"


def side_photo(images):
    """The straight side view, handlebars right.

    Each colour's gallery starts with a photo named by a plain number (2288186.png): the side
    view. The article-number photos after it (4276118549A.png, B, I, ...) are the 3/4 view and
    close-ups. Older models only have numbered photos, again with the side view first.
    """
    for pattern in (r"/\d{6,8}\.png$", r"/\d{6,8}\.jpe?g$", r"/\d{9,}A\.(png|jpe?g)$"):
        for src in images:
            if re.search(pattern, src):
                return src
    return images[0] if images else None


def parse(page, url):
    group = product_group(page)
    if not group:
        return None
    name = clean(group["name"])
    name = re.sub(r"^Scott\s+", "", name)
    name = re.sub(r"\s+Bike$", "", name)
    name = re.sub(r"\s*\(?20\d\d\)?$", "", name)
    name = re.sub(r"\s+Frame\s?set$", " Frameset", name, flags=re.I)
    pairs = []
    for prop in group.get("additionalProperty") or []:
        label = clean(prop.get("name"))
        if label and not SKIP.match(label):
            pairs.append((LABELS.get(label, label), prop.get("value")))
    categories = group.get("category") or []
    if isinstance(categories, str):  # older pages: "Aero Road Bikes"; current ones: ["Addict RC", "Road Bikes - Race"]
        categories = [categories]
    prices, sizes, colours, images = [], [], [], []
    for variant in group.get("hasVariant") or []:
        price = parse_price((variant.get("offers") or {}).get("price"))
        if price:
            prices.append(price)
        size = size_name(variant["size"]) if variant.get("size") else None
        if size and size not in sizes:
            sizes.append(size)
        colour = clean(variant.get("color"))
        if colour and colour not in colours:
            colours.append(colour)
        if not images:
            images = variant.get("image") or []
    images = images or group.get("image") or []
    if isinstance(images, str):
        images = [images]
    image = side_photo(images)
    if image:  # the originals are 4 MB PNGs; Cloudinary scales them on request
        image = image.replace("/image/upload/", "/image/upload/w_1400/")
    year = re.search(r'\\?"code\\?":\\?"(20\d\d)_SIZECHARTS', page)
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": group.get("productGroupID"),
        "price": min(prices) if prices else None,
        "category": category_of(name, categories),
        "family": categories[0] if len(categories) > 1 else "",
        "model_year": int(year.group(1)) if year else None,
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "sizes": sizes,
        "image_url": image,
    }


def scrape(fetcher, limit=None):
    browser = BrowserFetcher(delay=max(fetcher.delay, 2.0))
    bikes = []
    try:
        urls = product_urls(browser)
        log.info("Scott: %d product pages", len(urls))
        for url in urls:
            if limit and len(bikes) >= limit:
                break
            page = browser.get(url)
            bike = parse(page, url) if page else None
            if not bike:
                log.warning("Scott: no product data in %s", url)
                continue
            if is_ebike(bike["name"], bike["family"]) or not bike["price"]:
                continue
            bikes.append(bike)
            log.info("Scott: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    finally:
        browser.close()
    return bikes
