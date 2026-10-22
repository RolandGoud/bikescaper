"""Factor: road, gravel and TT bikes from the EU store (euro prices; there is no Dutch site).

The store is a Shopify Hydrogen app. Each family page (/bikes/monza) lists its
builds in the Remix loader data, and each build's page (/bike-builder/<handle>)
has the price, sizes and spec lists.
"""
import json
import re

from .common import clean, log, normalize_specs, parse_price

BRAND = "Factor"
BASE = "https://eu.factorbikes.com"
SKIP = ("lando", "track", "raiden")  # mountain and track bikes
GRAVEL = ("aluto", "sarana", "ostro-gravel", "elara")
TT = ("slick", "hanzo")


def loader_data(page):
    start = page.find("window.__remixContext = ")
    if start < 0:
        return {}
    end = page.find(";</script>", start)
    try:
        return json.loads(page[start + len("window.__remixContext = "):end])["state"]["loaderData"]
    except (ValueError, KeyError):
        return {}


def family_urls(fetcher):
    page = fetcher.get(BASE + "/bikes") or ""
    families = sorted(set(re.findall(r'href="/bikes/([a-z0-9-]+)"', page)))
    return [f for f in families if not any(s in f for s in SKIP)]


def category_of(family):
    if family.startswith(GRAVEL):
        return "Gravel"
    if family.startswith(TT):
        return "Triathlon / TT"
    return "Race"


def builds(fetcher, family):
    page = fetcher.get(f"{BASE}/bikes/{family}") or ""
    for route in loader_data(page).values():
        cards = ((route or {}).get("shopifyData") or {}).get("bikeCards") if isinstance(route, dict) else None
        if cards:
            return cards
    return []


def parse(page, url, card):
    data = next((v for k, v in loader_data(page).items() if "bike-builder" in k), None)
    if not data:
        return None
    content = data.get("content") or {}
    pairs = []
    for key, rows in content.items():
        if key.endswith("Specs") and isinstance(rows, list):
            pairs += [(r.get("title"), (r.get("details") or "").replace("</br>", " ")) for r in rows]
    variant = data.get("defaultVariant") or {}
    price = parse_price((card.get("price") or {}).get("amount")) or parse_price((variant.get("price") or {}).get("amount"))
    sizes = list(dict.fromkeys(re.findall(r'\{"name":"Size","value":"([^"]+)"\}', page)))
    colours = list(dict.fromkeys(re.findall(r'\{"name":"Colou?r","value":"([^"]+)"\}', page)))
    image = (card.get("image") or {}).get("url") or (variant.get("image") or {}).get("url")
    return {
        "name": clean(card.get("model") or data.get("framesetTitle")),
        "brand": BRAND,
        "url": url,
        "sku": card.get("handle"),
        "price": price,
        "category": "",
        "model_year": None,
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "sizes": sizes,
        # Shopify's CDN resizes and converts on request.
        "image_url": (image + ("&" if "?" in image else "?") + "width=1200&format=jpg") if image else None,
    }


def scrape(fetcher, limit=None):
    bikes = []
    for family in family_urls(fetcher):
        for card in builds(fetcher, family):
            if limit is not None and len(bikes) >= limit:
                return bikes
            url = BASE + (card.get("linkUrl") or f"/bike-builder/{card.get('handle')}")
            page = fetcher.get(url)
            bike = parse(page, url, card) if page else None
            if not bike:
                log.warning("Factor: no product data in %s", url)
                continue
            bike["category"] = category_of(family)
            bikes.append(bike)
            log.info("Factor: %s (%s)", bike["name"], bike["price"])
    return bikes
