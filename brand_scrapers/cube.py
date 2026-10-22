"""Cube NL: road, cyclocross, TT and gravel bikes.

Cube's shop lists every colour as its own product. The family pages
(/nl-nl/bikes/road/road-race/attain) list them all; the product pages have the
price in microdata and the spec table as HTML rows.
"""
import re

from .common import clean, is_ebike, log, normalize_specs, parse_price

BRAND = "Cube"
BASE = "https://www.cube.eu"
CATEGORIES = {"road-race": "Race", "cyclocross": "Cyclocross", "triathlon-time-trial": "Triathlon / TT",
              "gravel": "Gravel"}


def family_pages(fetcher):
    page = fetcher.get(BASE + "/nl-nl/") or ""
    links = set(re.findall(r'href="(https://www\.cube\.eu/nl-nl/bikes/(?:road|gravel)/[a-z0-9/-]+)"', page))
    # Family pages only (/road/road-race/attain); products found on two pages are deduped later.
    return sorted(link for link in links if link.count("/") >= 6)


def product_urls(fetcher):
    urls = {}
    for family in family_pages(fetcher):
        category = next((label for key, label in CATEGORIES.items() if f"/{key}" in family), "")
        for n in range(1, 6):
            page = fetcher.get(family + (f"?p={n}" if n > 1 else "")) or ""
            # The page also links the shop's featured products; keep the ones named after this family.
            fam = family.rstrip("/").rsplit("/", 1)[-1]
            found = [u for u in re.findall(r'href="(https://www\.cube\.eu/nl-nl/cube-[a-z0-9.-]+/\d+)"', page)
                     if f"cube-{fam}" in u]
            new = [u for u in found if u not in urls]
            for u in new:
                urls[u] = category
            if not new or f"?p={n + 1}" not in page:
                break
    return urls


def parse(page, url):
    h1 = re.search(r'<h1 class="product-detail-name"[^>]*>(.*?)</h1>', page, re.S)
    title = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    if not h1 or not title:
        return None
    # og:title is "Cube Attain C:62 SLX bali´n´blue"; the h1 holds the model without the colour.
    words = re.sub(r"^Cube\s+", "", clean(title.group(1)), flags=re.I).split()
    n = len(clean(h1.group(1)).split())
    name, colour = " ".join(words[:n]), " ".join(words[n:])
    price = re.search(r'itemprop="price"\s+content="([^"]+)"', page)
    image = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    pairs = re.findall(r'<h4 class="title">(.*?)</h4>\s*</div>\s*<div[^>]*>\s*<p class="mb-0">(.*?)</p>', page, re.S)
    pairs += re.findall(r'cube-key-features-item-label">(.*?)</span>\s*<span class="cube-key-features-item-value[^"]*">'
                        r'(.*?)</span>', page, re.S)
    pairs = [(label[:1].upper() + label[1:], value) for label, value in pairs
             if clean(label).lower() not in ("kleur", "art. nr.", "prijs*")]
    sizes = next((re.findall(r"(\d{2}|XS|S|M|L|XL)\s*(?:cm)?(?=,|$)", clean(v)) for k, v in pairs if k == "Maat"), [])
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": url.rsplit("/", 1)[-1],
        "price": parse_price(price.group(1)) if price else None,
        "category": "",
        "model_year": None,
        "specifications": normalize_specs(pairs),
        "color_names": [colour.replace("´n´", " 'n' ")] if colour else [],
        "sizes": sizes,
        "image_url": image.group(1) if image else None,
    }


def scrape(fetcher, limit=None):
    bikes, names = [], {}
    for url, category in list(product_urls(fetcher).items())[:limit]:
        page = fetcher.get(url)
        bike = parse(page, url) if page else None
        if not bike or "Frame" not in bike["specifications"]:  # accessories are listed on family pages too
            log.warning("Cube: no bike data in %s", url)
            continue
        if is_ebike(bike["name"], url):
            continue
        bike["category"] = category
        if bike["name"].lower() in names:  # another colour of a model we already have
            names[bike["name"].lower()]["color_names"] += bike["color_names"]
            continue
        names[bike["name"].lower()] = bike
        bikes.append(bike)
        log.info("Cube: %s (%s)", bike["name"], bike["price"])
    return bikes
