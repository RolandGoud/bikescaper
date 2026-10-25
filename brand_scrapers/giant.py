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
    model = re.sub(r"\s*\(?20\d\d\)?$", "", clean(name.group(1)))  # some h1s end in the model year
    colours = next((clean(v).split(", ") for k, v in pairs if clean(k) == "Kleuren"), [])
    colours = [c for c in colours if c]
    return {
        "name": model,
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
        "color_image_urls": [colour_photo(page, model, c) for c in colours],
        "color_angle_urls": [colour_angles(page, model, c) for c in colours],
    }


def colour_photo(page, model, colour):
    """The side view of one colour of this model. Giant names photos by model and colour:
    MY25TCRAdvanced2-KOM_ColorBIllusionWhite.jpg, with -D1, -Rear, -Front and _Action for the close-ups,
    other angles and riding photos. The page also shows other models' photos, and its colour list
    isn't in the order of the letters, so both names have to match."""
    name = "-?".join(re.escape(c) for c in re.sub(r"[^A-Za-z0-9]", "", model))  # "Pro 0 Di2" is filed as Pro0-Di2
    keys = [re.sub(r"[^A-Za-z0-9]", "", part).lower() for part in colour.split("/")]
    found = []
    for path, shade in re.findall(r"([a-z0-9]{20}/MY\d\d%s(?:-[A-Za-z]+)?_Color[A-H]([A-Za-z0-9_-]*)\.jpg)" % name, page):
        if re.search(r"(?i)[-_](D-?\d+|Rear|Front|Action|B)(?=[-_.\d]|$)|blacktires", shade + "."):
            continue
        if any(k and re.sub(r"[^A-Za-z0-9]", "", shade).lower().startswith(k) for k in keys):
            found.append(path)
    if not found:
        return None
    return "https://images2.giant-bicycles.com/b_white%2Cc_pad%2Ch_750%2Cq_80%2Cw_1000/" + min(found, key=len)


def colour_angles(page, model, colour):
    """The other angles of one colour (close-ups, front, rear: the -D1, -Front and -Rear photos), in the page's
    order; not the side view colour_photo gives, nor riding photos."""
    name = "-?".join(re.escape(c) for c in re.sub(r"[^A-Za-z0-9]", "", model))
    keys = [re.sub(r"[^A-Za-z0-9]", "", part).lower() for part in colour.split("/")]
    found = []
    for path, shade in re.findall(r"([a-z0-9]{20}/MY\d\d%s(?:-[A-Za-z]+)?_Color[A-H]([A-Za-z0-9_-]*)\.jpg)" % name, page):
        if not re.search(r"(?i)[-_](D-?\d+|Rear|Front)(?=[-_.\d]|$)", shade + ".") or re.search(r"(?i)action|blacktires", shade):
            continue
        if any(k and re.sub(r"[^A-Za-z0-9]", "", shade).lower().startswith(k) for k in keys) and path not in found:
            found.append(path)
    return ["https://images2.giant-bicycles.com/b_white%2Cc_pad%2Ch_750%2Cq_80%2Cw_1000/" + f for f in found]


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
