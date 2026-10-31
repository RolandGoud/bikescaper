"""New prices of earlier model years from the bike database of TOUR and BIKE (Delius Klasing).

The magazines keep a page per model and model year with its German list price (UVP), fed by the
industry's Bidex data. German and Dutch list prices are usually the same or within a few percent
(Giant: 32 of 37 checked within 5%), so this only fills years we have no Dutch price for, and
the site says it's the German price.

    python -m brand_scrapers.tourbike trek giant specialized cannondale

Writes data/years/tourbike/<Brand>.json ({"checked_on", "source", "models": {name: {year: {price,
prices, url, captured}}}}), under the database's own model names; webapp/seed.py matches them to ours.
robots.txt allows the model pages (only /api/ is closed, the sitemap aside).
"""
import argparse
import json
import logging
import os
import re
from datetime import date

from .archive import BRANDS
from .common import ROOT, Fetcher, log

SITES = ["https://www.tour-magazin.de", "https://www.bike-magazin.de"]  # road and gravel, MTB; one database
SOURCE = "TOUR/BIKE bike database (Delius Klasing), German list prices"
MODEL_URL = re.compile(r"/marken/([^/]+)/modell/[^/]*-([0-9a-f]{24})/$")


def model_urls(fetcher, brands):
    """{brand slug: {model id: German page URL}} from both sites' sitemaps."""
    found = {}
    for site in SITES:
        index = fetcher.get(f"{site}/api/sitemap") or ""
        for sitemap in re.findall(r"<loc>([^<]*/sitemap/models/\d+/?)</loc>", index):
            for url in re.findall(r"<loc>([^<]+)</loc>", fetcher.get(sitemap) or ""):
                m = MODEL_URL.search(url)
                if m and m.group(1) in brands:
                    found.setdefault(m.group(1), {}).setdefault(m.group(2), url)
    return found


def parse(page):
    """{name, year, prices} from a model page's embedded data, or None."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page or "", re.S)
    try:
        content = json.loads(m.group(1))["props"]["pageProps"]["content"]
        model = content["model"]["model"]
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    prices = sorted({p["price"] for v in content["model"].get("variants") or [] for p in v.get("prices") or []
                     if p.get("price")})
    if not prices and model.get("_search", {}).get("priceMin"):
        prices = [model["_search"]["priceMin"]]
    if not model.get("year") or not prices:
        return None
    return {"name": model["name"].strip(), "year": int(model["year"]), "prices": prices}


def run(brands, fetcher=None):
    fetcher = fetcher or Fetcher(delay=1.0)
    slugs = {b.lower(): b for b in brands}
    out_dir = os.path.join(ROOT, "data", "years", "tourbike")
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for slug, pages in model_urls(fetcher, slugs).items():
        brand, models = slugs[slug], {}
        for url in pages.values():
            bike = parse(fetcher.get(url))
            if bike:
                models.setdefault(bike["name"], {})[str(bike["year"])] = {
                    "price": float(bike["prices"][0]), "prices": bike["prices"], "url": url,
                    "captured": date.today().isoformat()}
        with open(os.path.join(out_dir, f"{brand}.json"), "w", encoding="utf-8") as fh:
            json.dump({"checked_on": date.today().isoformat(), "source": SOURCE, "models": models},
                      fh, ensure_ascii=False, indent=1, sort_keys=True)
        report[brand] = sum(len(y) for y in models.values())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("brands", nargs="*", help=", ".join(BRANDS) + " (default: all)")
    args = parser.parse_args()
    names = {b.lower(): b for b in BRANDS}
    unknown = [b for b in args.brands if b.lower() not in names]
    if unknown:
        parser.error(f"unknown brand: {', '.join(unknown)}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for brand, count in run([names[b.lower()] for b in args.brands] or BRANDS).items():
        print(f"{brand}: {count} model years with a price")


if __name__ == "__main__":
    main()
