"""Sponsored offers on the home page: affiliate links we show in our own cards and banners.

The offers live in sponsored.json, read on every page view so a change shows without a restart.
Each offer has an affiliate `url` (from Daisycon, TradeTracker or Awin), the `slots` it may fill
("card" in the Net gecheckt row, "banner" below that row, "side" in the right margin on wide
screens), an optional `image` under static/ and, per language, a title, text and button text:

    {"id": "insurance", "slots": ["card"], "advertiser": "Example.nl",
     "url": "https://ds1.nl/c/?...", "image": "sponsored/insurance.jpg",
     "nl": {"title": "...", "text": "...", "cta": "..."}, "en": {...}}

An offer without a url still shows, as a mock-up whose link goes nowhere ("#"), until its
affiliate link is filled in. Remove an offer from the file to take it off the site. We only link
out: no advertiser scripts, pixels or images from their servers, so the site sets no tracking
cookies and needs no cookie banner. The network tracks the visitor after the click, on its side.
"""
import json
import os
import random

PATH = os.path.join(os.path.dirname(__file__), "sponsored.json")
SLOTS = ("card", "banner", "side")


def load(path=PATH):
    """Every offer, or [] when the file is missing or broken. One without an https link points at "#"."""
    try:
        with open(path, encoding="utf-8") as f:
            offers = json.load(f)
    except (OSError, ValueError):
        return []
    return [o if (o.get("url") or "").startswith("https://") else {**o, "url": "#"}
            for o in offers if isinstance(o, dict)]


def pick(offers, lang, rng=random):
    """One offer per slot, in the visitor's language (English when an offer has no Dutch),
    never the same offer twice on a page. A slot with no offer left is None."""
    picked, used = {}, set()
    for slot in SLOTS:
        fits = [o for o in offers if slot in o.get("slots", []) and o.get("id") not in used]
        if not fits:
            picked[slot] = None
            continue
        offer = rng.choice(fits)
        used.add(offer.get("id"))
        text = offer.get(lang) or offer.get("en") or offer.get("nl") or {}
        picked[slot] = {"url": offer["url"], "advertiser": offer.get("advertiser", ""),
                        "image": offer.get("image"), **text}
    return picked
