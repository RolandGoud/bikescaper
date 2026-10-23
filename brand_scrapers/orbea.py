"""Orbea NL: road, gravel and TT bikes from the family catalogue pages.

orbea.com sits behind Cloudflare, which answers requests and headless browsers
with a challenge, so pages are loaded in a visible Chrome (browser.py). The
product pages are Livewire/Alpine: the bike (price, model year, colours, sizes,
components grouped in Dutch) is a `product = JSON.parse('...')` in an x-init
attribute. Photos are on www.orbea.com/uploads, which answers plain requests.
"""
import html
import json
import re

from .browser import BrowserFetcher
from .common import clean, is_ebike, log, normalize_specs, parse_price

BRAND = "Orbea"
BASE = "https://www.orbea.com/nl-nl"
FAMILIES = {  # catalogue slug -> category
    "orca": "Race",
    "orca_aero": "Aero Race",
    "avant": "Endurance",
    "terra": "Gravel",
    "terra_race": "Gravel",
    "ordu": "Triathlon / TT",
}
# Orbea's Dutch labels that normalize_specs doesn't know.
LABELS = {
    "fietsframe": "Frame", "hendels": "Shifter", "kettingwiel": "Cassette", "balhoofdlager perb": "Balhoofdstel",
    "balhoofdlager": "Balhoofdstel", "voorwielas": "As voorwiel", "achterwielas": "As achterwiel",
    "stuurlint": "Stuurlint", "trapas": "Bottom bracket",
}


def product_urls(fetcher):
    urls = {}
    for family in FAMILIES:
        page = fetcher.get(f"{BASE}/catalog/fietsen-road-{family}") or ""
        for slug in re.findall(r'href="%s/([a-z0-9-]+)\?color=' % re.escape(BASE), page):
            urls.setdefault(f"{BASE}/{slug}", family)
    return urls


def js_json(page, var):
    m = re.search(r"\b%s\s*=\s*JSON\.parse\('((?:[^'\\]|\\.)*)'\)" % var, page)
    if not m:
        return None
    body = html.unescape(m.group(1)).replace('"', '\\"').replace("\\'", "'")
    try:
        return json.loads(json.loads(f'"{body}"'))
    except ValueError:
        return None


def parse(page, url, family):
    product = js_json(page, "product")
    if not product or product.get("type") != "bike":
        return None
    attrs = {a.get("attribute"): a.get("value") for a in product.get("attributes") or []}
    pairs = []
    for group in (product.get("componentsGrouped") or {}).values():
        for label, value in (group or {}).items():
            label = clean(label)
            if clean(value).upper() in ("", "N/A", "-"):
                continue
            pairs.append((LABELS.get(label.lower(), label), value))
    colours = product.get("colors") or []
    featured = product.get("featured_color") or (colours[0]["code"] if colours else None)
    side = [i for i in product.get("images") or [] if i.get("view") == "side"] or product.get("images") or []
    image = next((i["src"] for i in side if i.get("color") == featured), side[0]["src"] if side else None)
    price = product.get("price") or {}
    return {
        "name": re.sub(r"\s*\(?20\d\d\)?$", "", clean(product.get("name"))),
        "brand": BRAND,
        "url": url,
        "sku": product.get("code"),
        "price": parse_price(price.get("discounted_amount") or price.get("amount")),
        "category": FAMILIES[family],
        "family": family.replace("_", " ").title(),
        "model_year": product.get("year"),
        "specifications": normalize_specs(pairs),
        "color_names": [clean(c.get("name")) for c in colours if c.get("name")],
        "sizes": [s.get("name") or code for code, s in (product.get("sizes") or {}).items()],
        "image_url": image,
        "_ebike": attrs.get("BIKE_TYPE", "BIKE") != "BIKE" or attrs.get("PRODUCT_TYPE", "BIKE") != "BIKE",
    }


def scrape(fetcher, limit=None):
    browser = BrowserFetcher(delay=max(fetcher.delay, 2.0))
    bikes = []
    try:
        urls = product_urls(browser)
        log.info("Orbea: %d product pages", len(urls))
        for url, family in urls.items():
            if limit and len(bikes) >= limit:
                break
            page = browser.get(url)
            bike = parse(page, url, family) if page else None
            if not bike:
                log.warning("Orbea: no product data in %s", url)
                continue
            if bike.pop("_ebike") or is_ebike(bike["name"]) or not bike["price"]:
                continue
            bikes.append(bike)
            log.info("Orbea: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    finally:
        browser.close()
    return bikes
