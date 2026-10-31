"""Where an ad's place lies, for the listings map.

Looks the place up in places.json (built by tools/build_places.py from GeoNames), never online.
The country comes from the ad's site: Marktplaats is Dutch, 2dehands and 2ememain Belgian. A
typed-in check has no site and counts as Dutch.
An ad that names no place we know is left off the map. A new country is a
new entry in places.json and in SITE_COUNTRY.
"""
import json
import os
import re
import unicodedata
from functools import lru_cache
from urllib.parse import urlsplit

PLACES = os.path.join(os.path.dirname(__file__), "places.json")
SITE_COUNTRY = {"marktplaats.nl": "NL", "2dehands.be": "BE", "2ememain.be": "BE"}
COUNTRIES = ("NL", "BE")


def normalise(name):
    """'s-Hertogenbosch, 'S-HERTOGENBOSCH and s Hertogenbosch all become "s hertogenbosch"."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


@lru_cache(maxsize=1)
def _places():
    with open(PLACES, encoding="utf-8") as f:
        return json.load(f)


def country(listing_url):
    host = (urlsplit(listing_url if "//" in (listing_url or "") else "//" + (listing_url or "")).hostname or "").lower()
    return next((cc for site, cc in SITE_COUNTRY.items() if host == site or host.endswith("." + site)), None)


def _tries(name):
    """The place as written, then without a postcode, a bracketed part or a district after a dash or comma:
    "Amsterdam-Noord", "Utrecht (3512)", "3512 AB Utrecht" and "Gent, Oost-Vlaanderen" all find their town."""
    yield name
    bare = re.sub(r"\(.*?\)", " ", name)
    bare = re.sub(r"\b\d{4}\s?[a-zA-Z]{2}\b|\b\d{4}\b", " ", bare)
    yield bare
    for part in re.split(r"[,/]| - ", bare):
        yield part
    yield bare.split("-")[0]


def locate(place, listing_url=None):
    """(lat, lng, country) of the ad's place, or None when we can't tell where it is."""
    if not place:
        return None
    site = country(listing_url)
    places = _places()
    for attempt in _tries(place):
        key = normalise(attempt)
        found = [(cc, places[cc][key]) for cc in COUNTRIES if key in places.get(cc, {})]
        if found:
            # A name both countries have: the site's own country (the Netherlands for a typed check),
            # unless that's a hamlet and the other a real town. Marktplaats "Gent" is the Belgian city,
            # a typed "Bergen" the Dutch village and not Mons.
            home = site or COUNTRIES[0]
            cc, spot = max(found, key=lambda f: (f[1][2] + 1) * (10 if f[0] == home else 1))
            return spot[0], spot[1], cc
    return None
