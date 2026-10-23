"""Collect the road and gravel catalogue of the brands without a scraper of their own.

    python -m brand_scrapers                      # all brands
    python -m brand_scrapers giant cube --limit 3 # a quick test run

Writes data/<Brand>/<brand>_bikes_<timestamp>.json and one photo per model under
images/<Brand>/. E-bikes, mountain bikes and city bikes are left out, like the
Trek and Canyon data.
"""
import argparse
import logging
from datetime import datetime

from . import cannondale, cube, factor, giant, orbea, scott, specialized
from .common import Fetcher, dedupe, log, save_image, write_snapshot

ADAPTERS = {m.BRAND.lower(): m for m in (specialized, giant, cannondale, cube, factor, scott, orbea)}


def run(names, limit=None, images=True):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fetcher = Fetcher()
    written = {}
    for name in names:
        adapter = ADAPTERS[name]
        bikes = dedupe(adapter.scrape(fetcher, limit=limit))
        for bike in bikes:
            bike["image"] = save_image(fetcher, adapter.BRAND, bike["name"], bike.get("image_url")) if images else None
        bikes.sort(key=lambda b: (b["category"], b["name"]))
        written[adapter.BRAND] = (write_snapshot(adapter.BRAND, bikes, stamp), len(bikes))
        log.info("%s: %d bikes written to %s", adapter.BRAND, len(bikes), written[adapter.BRAND][0])
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("brands", nargs="*", help=", ".join(sorted(ADAPTERS)) + " (default: all)")
    parser.add_argument("--limit", type=int, help="products per brand, for testing")
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()
    unknown = [b for b in args.brands if b not in ADAPTERS]
    if unknown:
        parser.error(f"unknown brand: {', '.join(unknown)}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for brand, (path, count) in run(args.brands or sorted(ADAPTERS), args.limit, not args.no_images).items():
        print(f"{brand}: {count} bikes -> {path}")


if __name__ == "__main__":
    main()
