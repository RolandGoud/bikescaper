"""BMC: road, gravel and TT bikes from the Dutch store (nl.bmc-switzerland.com, euro prices).

bmc-switzerland.com is a Shopify store. /products.json lists every bike with its sizes and price,
tagged "Bikes | Road | Racing | Teammachine SLR"; the model year is in the photo's file name
(bmc-2027-teammachine-slr-three-road-bike-white-1.jpg), and so is the colour. The product page
adds the spec sheet (<p><b>Label:</b><br>value</p>) and the geometry table, which gives the
rider height per size.

BMC keeps its old bikes online as "Bike Archive" products (2016 on, specs without a price):
archive() reads them for the earlier model years and the lines BMC no longer sells.
"""
import re

from .common import clean, first_of_each, log, normalize_specs, parse_price, shopify_products, size_name

BRAND = "BMC"
BASE = "https://nl.bmc-switzerland.com"
HOST_DELAY = {"nl.bmc-switzerland.com": 3.0}  # the store answers 429 to a faster crawl
DISCIPLINES = ("road", "gravel")
CATEGORIES = {"racing": "Race", "aero": "Aero Race", "endurance": "Endurance", "performance": "Gravel",
              "exploration": "Gravel", "gravel": "Gravel"}
# BMC's labels that normalize_specs doesn't know; None drops the row.
LABELS = {
    "brake levers / calipers": "Rem", "rotors": "Remschijf", "hubs (f/r)": "Naven", "hubs": "Naven",
    "tires": "Buitenband", "rims": "Velg", "chainrings": "Kettingblad", "weight without pedals": "Gewicht",
    "tire clearance": "Maximale bandenmaat", "wheelset": "Wiel voor", "shifters": "Shifter", "grips": "Stuurlint",
    "power meter": "Vermogensmeter", "in the box": "Accessories", "front suspension": "Vering",
    "rear suspension": "Demper", "gears": None, "cassette size": None, "rotor size (f/r)": None,
    "general product safety regulation (gpsr)": None, "tubeless information": None, "system weight limit": None,
}


def tidy_name(title):
    """"Teammachince SLR01 DISC ONE" -> "Teammachine SLR 01 DISC ONE", as BMC writes its current bikes."""
    name = clean(title).replace("Teammachince", "Teammachine")
    name = re.sub(r"\b(SLR|ALR|URS|GF|TM|RM|CX)0(\d)\b", r"\1 0\2", name)
    return re.sub(r"\s+", " ", name).strip()


def discipline(product):
    """"road", "gravel" or None from the tags ("Bikes | Road | Racing", "Road | Endurance", "Frames | Gravel")."""
    for tag in product.get("tags") or []:
        parts = [p.strip().lower() for p in tag.split("|")]
        if parts and parts[0] in ("bikes", "frames"):
            parts = parts[1:]
        if parts and parts[0] in DISCIPLINES:
            return parts[0]
    return None


def category_of(product, name):
    low = name.lower()
    road = re.search(r"\broad\b|\btmr\s*0", low)  # Timemachine Road, once named TMR01: an aero road bike
    if low.startswith("speedmachine") or (low.startswith("timemachine") and not road):
        return "Triathlon / TT"
    if low.startswith("crossmachine"):
        return "Cyclocross"
    for tag in sorted(product.get("tags") or [], key=lambda t: -t.count("|")):
        parts = [p.strip().lower() for p in tag.split("|")]
        for part in parts:
            if part in CATEGORIES:
                return CATEGORIES[part]
    return "Gravel" if discipline(product) == "gravel" else "Road"


def photo_facts(src):
    """(model year, colour) from a photo name: bmc-2027-teammachine-slr-three-road-bike-white-1_<uuid>.jpg."""
    stem = (src or "").split("/")[-1].split("?")[0]
    year = re.match(r"bmc-(20\d\d)-", stem)
    colour = re.search(r"-(?:road|gravel|track|aero)-(?:bike|frameset|module)(?:-frame)?-([a-z-]+?)-\d+(?:[_.-]|$)", stem)
    return (int(year.group(1)) if year else None,
            re.sub(r"^(?:road|gravel) bike ", "", colour.group(1).replace("-", " ")).title() if colour else None)


def handle_year(handle):
    """bikes-bmc-27a-000020 -> 2027, bikes-bmc-24-10619-009 -> 2024."""
    m = re.search(r"-bmc-(\d\d)[a-z]?-", handle or "")
    return 2000 + int(m.group(1)) if m and 15 <= int(m.group(1)) <= 40 else None


def sized(url, width=1200):
    return (url + ("&" if "?" in url else "?") + f"width={width}") if url else None


def spec_pairs(page):
    pairs = re.findall(r"<p><b>([^<]+?)</b>\s*(?:<br\s*/?>)?(.*?)</p>", page or "", re.S)
    return first_of_each([(clean(label).rstrip(":").strip(), value) for label, value in pairs], LABELS)


def wanted(product):
    title = product.get("title") or ""
    return (discipline(product) and not re.search(r"\bAMP\b|\bUSA\b", title, re.I)
            and product.get("product_type") in ("Bikes", "Frames", "Bike Archive"))


def parse(product, page, url):
    images = product.get("images") or []
    year, colour = photo_facts(images[0]["src"] if images else "")
    variants = product.get("variants") or []
    prices = [parse_price(v.get("price")) for v in variants if parse_price(v.get("price"))]
    sizes = [size_name(v.get("option1")) for v in variants if v.get("option1") and v.get("option1") != "Default Title"]
    name = tidy_name(product["title"])
    image = sized(images[0]["src"]) if images else None
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": product.get("handle"),
        "price": min(prices) if prices else None,
        "category": category_of(product, name),
        "model_year": year or handle_year(product.get("handle")),
        "specifications": normalize_specs(spec_pairs(page)),
        "color_names": [colour] if colour else [],
        "sizes": list(dict.fromkeys(sizes)),
        "image_url": image,
        "color_image_urls": [image] if colour else [],
    }


def read(fetcher, archived, limit=None):
    """The road and gravel bikes of the catalogue (archived=False) or of the Bike Archive (True); the colours of a
    model sold as two products in one year are put together."""
    fetcher.delays.update(HOST_DELAY)
    bikes = {}
    for product in shopify_products(fetcher, BASE):
        if limit is not None and len(bikes) >= limit:
            break
        if not wanted(product) or (product.get("product_type") == "Bike Archive") != archived:
            continue
        url = f"{BASE}/products/{product['handle']}"
        page = fetcher.get(url)
        if not page:
            log.warning("BMC: no page for %s", url)
            continue
        bike = parse(product, page, url)
        key = (bike["name"].lower(), bike["model_year"])
        if key in bikes:
            have = bikes[key]
            for c, u in zip(bike["color_names"], bike["color_image_urls"]):
                if c not in have["color_names"]:
                    have["color_names"].append(c)
                    have["color_image_urls"].append(u)
            continue
        bikes[key] = bike
        log.info("BMC: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return list(bikes.values())


def scrape(fetcher, limit=None):
    """The bikes on sale, every model year the store still lists (dedupe keeps the newest; history.py the rest)."""
    return read(fetcher, archived=False, limit=limit)


def archive(fetcher, limit=None):
    return read(fetcher, archived=True, limit=limit)
