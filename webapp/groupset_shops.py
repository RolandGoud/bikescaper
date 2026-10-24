"""Where to buy a groupset: affiliate links to web shops, shown on each groupset's shop page (/groupsets/<key>/shop).

The shops live in groupset_shops.json, read on every page view so a change shows without a restart. Each shop has a
`name` and a `url`: an affiliate deep link (from Daisycon, TradeTracker or Awin) to the shop's search, with {q} where
the search words go. `groupsets` maps a groupset key to its own link when the shop has a better page for it:

    {"id": "bike-shop", "name": "Example Bikes", "url": "https://ds1.nl/c/?...&dl=search%3Fq%3D{q}",
     "groupsets": {"r8100": "https://ds1.nl/c/?...&dl=shimano-ultegra-r8100"}}

A shop without an https link still shows, as a mock-up whose link goes nowhere ("#"), until its affiliate link is
filled in. Like the sponsored offers, we only link out: no advertiser scripts, pixels or images.
"""
import json
import os
from urllib.parse import quote_plus

PATH = os.path.join(os.path.dirname(__file__), "groupset_shops.json")


def load(path=PATH):
    """Every shop, or [] when the file is missing or broken."""
    try:
        with open(path, encoding="utf-8") as f:
            shops = json.load(f)
    except (OSError, ValueError):
        return []
    return [s for s in shops if isinstance(s, dict) and s.get("name")]


def links(shops, gen):
    """[(shop name, url)] for groupset generation `gen`: the shop's own page for it, else its search for the brand
    and name ("Shimano Ultegra R8000"), else "#"."""
    found = []
    for shop in shops:
        url = (shop.get("groupsets") or {}).get(gen["key"]) \
            or (shop.get("url") or "").replace("{q}", quote_plus(f"{gen['brand']} {gen['name']}"))
        found.append((shop["name"], url if url.startswith("https://") else "#"))
    return found
