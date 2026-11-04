"""Wilier: road, gravel and TT bikes from wilier.com (euro list prices; there is no Dutch site).

wilier.com is a Nuxt 2 app (its state is read by nuxt.py). Each category page links its model
families (/en/bikes/road/filante-slr); a family page carries the model year, the colours with
their photos, the geometry table with stack and reach, and every build (`variants`) with its
EU list price in cents and its full spec sheet.
"""
import re

from .common import clean, log, normalize_specs, size_name
from .nuxt import nuxt_state

BRAND = "Wilier"
SITE = "https://www.wilier.com"
CATEGORIES = {"road": "Race", "gravel": "Gravel", "time-trial-triathlon": "Triathlon / TT"}
# Wilier's spec fields -> the labels normalize_specs knows; fields not listed are left out.
FIELDS = {
    "frame": "Frame", "fork": "Voorvork", "shifters": "Shifter", "groupset": "Groepset", "brakes": "Rem",
    "rotors": "Remschijf", "front_derailleur": "Voorderailleur", "rear_derailleur": "Achterderailleur",
    "crankset": "Crankstel", "bottom_bracket": "Bottom bracket", "cassette": "Cassette", "chain": "Ketting",
    "wheelset": "Wiel voor", "tyres": "Buitenband", "h_bar": "Stuur", "stem": "Stuurpen", "headset": "Balhoofdstel",
    "saddle": "Zadel", "seatpost": "Zadelpen", "clearance": "Maximale bandenmaat", "weight": "Gewicht",
    "frame_weight": "Framegewicht",
}
CAPS = {"di2": "Di2", "axs": "AXS", "grx": "GRX", "xplr": "XPLR", "sram": "SRAM", "etap": "eTap", "ekar": "Ekar",
        "wrl": "WRL"}


def families(page, category):
    return list(dict.fromkeys(re.findall(rf'href="(/en/bikes/{category}/[a-z0-9-]+)"', page or "")))


def tidy_groupset(text):
    """"SHIMANO DURA ACE Di2 2x12 R9270 " -> "Shimano Dura-Ace Di2 2x12"; "-" (a frameset) -> ""."""
    text = clean(text)
    if not re.search(r"[A-Za-z]", text) or re.search(r"(?i)telaio|frame\s*kit|frameset", text):
        return ""  # a frameset: "-", "Solo telaio / Framekit only", "Kit telaio ... / ... Frameset kit"
    text = re.sub(r"(?i)\b(\d+x\d+)\s*(?:sp|s|speed)\b", r"\1", text)  # "1x12s" -> "1x12"
    words = []
    for word in re.sub(r"(?i)\bdura[\s-]ace\b", "Dura-Ace", text).split():
        low = word.lower()
        if low in CAPS:
            words.append(CAPS[low])
        elif re.match(r"^[A-Z]{1,3}-?\d", word) or re.match(r"^\d+x\d+$", low):
            words.append(word.upper() if not re.match(r"^\d+x\d+$", low) else low)  # R9270, RX820, 2x12
        else:
            words.append("-".join(p[:1].upper() + p[1:].lower() for p in word.split("-")))
    return re.sub(r"\s+[A-Z]{1,2}\d{4}[A-Z]?\b", "", " ".join(words))  # drop part numbers (R9270)


def category_of(product):
    slug = ((product.get("category") or {}).get("slug")) or ""
    category = CATEGORIES.get(slug, "")
    if category == "Race" and any(u.get("slug") == "endurance" for u in product.get("usages") or []):
        return "Endurance"
    return category


def geometry(product):
    """Stack and reach per size from the family's geometry table."""
    table = product.get("geometries_table") or {}
    sizes = {}
    for size, stack, reach in zip(table.get("label") or [], table.get("stack") or [], table.get("reach") or []):
        if isinstance(stack, (int, float)) and isinstance(reach, (int, float)) and stack and reach:
            sizes[size_name(size)] = {"stack": stack, "reach": reach}
    return sizes


def photo(entry):
    images = (entry or {}).get("image") or []
    first = images[0] if images else {}
    conversions = first.get("conversions") or {}
    return first.get("original_url") or next(iter(conversions.values()), None)


def parse(product, variant, url):
    groupset = tidy_groupset(variant.get("groupset"))
    model = clean(product.get("name"))
    name = f"{model} {groupset}" if groupset else f"{model} Frameset"
    pairs = [(label, variant.get(key)) for key, label in FIELDS.items()
             if isinstance(variant.get(key), str) and clean(variant[key]) not in ("", "-", "N/A")
             and not (key == "groupset" and clean(variant.get("shifters")))]  # the groupset only stands in for shifters
    # Skip the made-to-order paint ("QA Customizable color - example"): it is not a colour you can buy as shown.
    colours = [c for c in product.get("colors") or [] if c.get("name") and "customizable" not in c["name"].lower()]
    year = ((product.get("year") or {}).get("name")) or ""
    price = variant.get("msrp")
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": clean(str(variant.get("code") or "")).split(" ")[0] or product.get("slug"),
        "price": price / 100 if isinstance(price, (int, float)) and price else None,
        "category": category_of(product),
        "model_year": int(year) if year.isdigit() else None,
        "specifications": normalize_specs(pairs),
        "color_names": [re.sub(r"(?i)^new\s+(?:-\s+)?", "", clean(c["name"])) for c in colours],  # "NEW - C9 Bottle Green"
        "sizes": [size_name(s) for s in (product.get("geometries_table") or {}).get("label") or []],
        "image_url": next((photo(c) for c in colours if photo(c)), None),
        "color_image_urls": [photo(c) for c in colours],
    }


def scrape(fetcher, limit=None):
    bikes = []
    for category in CATEGORIES:
        for path in families(fetcher.get(f"{SITE}/en/bikes/{category}"), category):
            url = SITE + path
            state = nuxt_state(fetcher.get(url))
            product = ((state or {}).get("data") or [{}])[0].get("product") if state else None
            if not product or product.get("is_ebike"):
                continue
            for variant in product.get("variants") or []:
                if limit is not None and len(bikes) >= limit:
                    return bikes
                bike = parse(product, variant, url)
                bikes.append(bike)
                log.info("Wilier: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
            if not product.get("variants"):
                log.warning("Wilier: no builds in %s", url)
    return bikes
