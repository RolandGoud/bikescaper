"""Giant NL: road, gravel and TT bikes from the NL sitemap.

Product pages are server-rendered HTML. Their URLs end in the model year
(tcr-advanced-pro-0-di2-2027); the sitemap still lists older years, so only the
current years are read. robots.txt asks for a crawl delay of a few seconds.
"""
import re

from .common import clean, is_ebike, log, normalize_specs, parse_price

BRAND = "Giant"
SITEMAP = "https://static.giant-bicycles.com/sitemaps/sitemap-giant-nl-nl.xml"
HOST_DELAY = {"www.giant-bicycles.com": 4}
FAMILIES = ("tcr", "propel", "defy", "contend", "revolt", "trinity", "tcx", "ocr", "fastroad")
FIRST_YEAR = 2025


def product_urls(fetcher, first_year=FIRST_YEAR):
    xml = fetcher.get(SITEMAP) or ""
    urls = []
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.match(r"https://www\.giant-bicycles\.com/nl/([a-z0-9-]+)-(20\d\d)$", url)
        if not m or m.group(1).startswith("bikes-") or int(m.group(2)) < first_year:
            continue
        if m.group(1).startswith(FAMILIES) and not is_ebike(m.group(1).replace("-", " "), url):
            urls.append(url)
    return urls


def category_of(label, url):
    """Giant's label ("Aero Race Fiets"), without "Fiets"; from the family when the page has none."""
    label = re.sub(r"\s*Fiets$", "", label or "").strip()
    if label and not label.lower().startswith(FAMILIES):
        return label
    slug = url.rsplit("/", 1)[-1]
    for families, name in ((("revolt",), "Gravel"), (("propel",), "Aero Race"), (("defy",), "Endurance"),
                           (("trinity",), "Triathlon / TT"), (("tcx",), "Cyclocross"), (("fastroad",), "Fitness")):
        if slug.startswith(families):
            return name
    return "Race"


def parse(page, url):
    name = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    if not name:
        return None
    title = re.search(r'<meta property=og:title content="([^"]+)"', page)
    # og:title reads "TCR Advanced Pro 0-Di2 (2027) |  Race Fiets | Giant Bicycles Nederland"
    category = clean(title.group(1).split("|")[1]) if title and title.group(1).count("|") >= 2 else ""
    price = re.search(r'class=currentprice>([^<]+)<', page)
    image = re.search(r"<meta property=og:image content=([^ >]+)>", page)
    pairs = re.findall(r"<div class=label>(.*?)</div><div class=value>(.*?)</div>", page, re.S)
    sizes = [clean(s) for s in re.findall(r"<th scope=col name=framesize>(.*?)</th>", page)]
    product_id = re.search(r"data-product-id=(\d+)", page)
    year = re.search(r"-(20\d\d)$", url)
    colours = next((clean(v).split(", ") for k, v in pairs if clean(k) == "Kleuren"), [])
    colours = [c for c in colours if c]
    return {
        "name": re.sub(r"\s*\(?20\d\d\)?$", "", clean(name.group(1))),  # some h1s end in the model year
        "brand": BRAND,
        "url": url,
        "sku": product_id.group(1) if product_id else None,
        "price": parse_price(price.group(1)) if price else None,
        "category": category_of(category, url),
        "model_year": int(year.group(1)) if year else None,
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "sizes": list(dict.fromkeys(sizes)),
        # The og:image is padded to 800x600 on white; ask for a larger one.
        "image_url": image.group(1).replace("h_600", "h_750").replace("w_800", "w_1000") if image else None,
        "color_image_urls": [colour_photo(page, i) for i in range(len(colours))],
    }


def colour_photo(page, i):
    """The side view of the page's i-th colour. Giant names photos by colour letter: MY25TCRAdvanced2-KOM_ColorBIllusionWhite.jpg
    is the side view of colour B, with -D1, -Rear, -Front and _Action for the close-ups, other angles and
    riding photos."""
    letter = "ABCDEFGH"[i] if i < 8 else None
    found = sorted(set(re.findall(r"([a-z0-9]{20}/MY\d\d[A-Za-z0-9_-]*?_Color%s[A-Za-z0-9_]*\.jpg)" % letter, page)))
    found = [f for f in found if not re.search(r"(?i)[-_](D-?\d+|Rear|Front|Action|B)(?=[-_.])|blacktires", f)]
    if not found:
        return None
    return "https://images2.giant-bicycles.com/b_white%2Cc_pad%2Ch_750%2Cq_80%2Cw_1000/" + min(found, key=len)


def scrape(fetcher, limit=None):
    fetcher.delays.update(HOST_DELAY)
    bikes = []
    for url in product_urls(fetcher)[:limit]:
        page = fetcher.get(url)
        bike = parse(page, url) if page else None
        if not bike:
            log.warning("Giant: no product data in %s", url)
            continue
        if is_ebike(bike["name"], bike["category"]):
            continue
        if not bike["sizes"] or "Frame" not in bike["specifications"]:  # clamps, spacers and other parts
            continue
        bikes.append(bike)
        log.info("Giant: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
