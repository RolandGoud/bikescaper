"""Rose: road and gravel bikes from the Dutch store (euro prices).

rosebikes.nl is a Nuxt 3 app. The road and gravel category pages link each model family
(/fietsen/race/race/shave), whose /modellen page links every build (/p/rose-shave-ultegra-di2-2726129).
A build's page embeds its product data (`__NUXT_DATA__`, read by nuxt.py): one variant per colour and
size with its price in cents, photos, the rider height it starts at, and the parts list. Rose gives no
model year.
"""
import re

from .common import clean, is_ebike, log, normalize_specs, size_name
from .nuxt import nuxt_data

BRAND = "Rose"
SITE = "https://www.rosebikes.nl"
CATEGORIES = ("/fietsen/race", "/fietsen/gravel")
SECTIONS = {"race/race": "Race", "race/endurance": "Endurance", "gravel/": "Gravel"}  # path -> category
# The parts list names wheels, cranks and brakes twice (front and rear, crank and power meter, lever and calliper).
SECOND = {"Wielen": "Wiel achter", "Remmen": "Remgreep", "Crankstel": "Vermogensmeter", "Banden": "Achterband"}
LABELS = {"Wielen": "Wiel voor", "Banden": "Buitenband", "Remmen": "Rem", "Rem-schakelverstellers": "Shifter",
          "Schakelverstellers": "Shifter", "Powermeter": "Vermogensmeter", "Koplamp": "Verlichting", "Fietsbel": "Bel",
          "Stuur-stuurpencombinatie": "Stuur/stuurpen (geïntegreerd)", "Kettinggeleiding": None}


def families(page):
    """Model family paths in a category page, without the e-bikes."""
    found = []
    for path in re.findall(r'href="(/fietsen/(?:race|gravel)/[a-z-]+/[a-z0-9-]+)"', page or ""):
        if not re.search(r"(?:^|/)e-|elektrisch|-plus$", path.split("/fietsen/", 1)[1]) and path not in found:
            found.append(path)
    return found


def builds(page):
    return list(dict.fromkeys(re.findall(r'href="(/p/rose-[a-z0-9-]+-\d+)"', page or "")))


def category_of(path):
    tail = path.split("/fietsen/", 1)[-1]
    return next((c for prefix, c in SECTIONS.items() if tail.startswith(prefix)), "")


def product_of(state):
    for key, value in ((state or {}).get("data") or {}).items():
        if key.startswith("evon:product:") and isinstance(value, dict):
            return ((value.get("productDetail") or {}).get("product")) or None
    return None


def parts(variant):
    """(label, value) pairs from a variant's parts list; repeated labels get their second meaning."""
    pairs, seen = [], set()
    for group in ((variant.get("partsList") or {}).get("groups")) or []:
        for item in group.get("items") or []:
            title = clean(item.get("title"))
            value = clean(item.get("subtitle")).strip(" ,")
            if not title or not value or "niet bij de levering" in value.lower():
                continue
            label = SECOND.get(title, title) if title in seen else LABELS.get(title, title)
            seen.add(title)
            if label:
                pairs.append((label, re.sub(r"^(?:VR|HR):\s*", "", value)))
    return pairs


def attribute(variant, kind):
    return next((clean(a.get("value")) for a in variant.get("superAttributes") or [] if a.get("type") == kind), None)


def size_chart(variants):
    """Rider heights per size: Rose gives the height each size starts at; it runs to the next size's start."""
    starts = {}
    for v in variants:
        size, low = attribute(v, "size"), v.get("bodyHeightMin")
        if size and str(low or "").isdigit():
            starts.setdefault(size_name(size), int(low))
    order = sorted(starts.items(), key=lambda kv: kv[1])
    chart = {}
    for i, (size, low) in enumerate(order):
        high = order[i + 1][1] - 1 if i + 1 < len(order) else low + 7
        chart[size] = {"low": low, "high": high}
    return chart


def parse(product, url, category):
    variants = product.get("variants") or []
    colours, colour_images = [], []
    for v in variants:
        colour = attribute(v, "color")
        if colour and colour not in colours:
            colours.append(colour)
            colour_images.append((v.get("images") or [None])[0])
    sizes = list(dict.fromkeys(size_name(attribute(v, "size")) for v in variants if attribute(v, "size")))
    prices = [v["price"]["value"] / 100 for v in variants if (v.get("price") or {}).get("value")]
    return {
        "name": re.sub(r"(?i)\bdura[\s-]ace\b", "Dura-Ace", clean(product.get("name"))),
        "brand": BRAND,
        "url": url,
        "sku": product.get("productSku"),
        "price": min(prices) if prices else None,
        "category": category,
        "model_year": None,
        "specifications": normalize_specs(parts(variants[0])) if variants else {},
        "color_names": [c[:1].upper() + c[1:] for c in colours],
        "sizes": sizes,
        "image_url": next((c for c in colour_images if c), None),
        "color_image_urls": colour_images,
    }


def scrape(fetcher, limit=None):
    bikes, seen = [], set()
    for category_path in CATEGORIES:
        for family in families(fetcher.get(SITE + category_path)):
            for path in builds(fetcher.get(SITE + family + "/modellen")):
                if limit is not None and len(bikes) >= limit:
                    return bikes
                if path in seen:
                    continue
                seen.add(path)
                url = SITE + path
                product = product_of(nuxt_data(fetcher.get(url)))
                if not product or is_ebike(product.get("name")):
                    continue
                bike = parse(product, url, category_of(family))
                if not bike["specifications"]:
                    log.warning("Rose: no parts list in %s", url)
                bikes.append(bike)
                log.info("Rose: %s (%s)", bike["name"], bike["price"])
    return bikes
