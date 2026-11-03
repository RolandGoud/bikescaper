"""Ridley: road, gravel, cyclocross and TT bikes from the Dutch site (euro prices).

ridley-bikes.com is a Nuxt app whose pages embed their state as minified JavaScript (read by
nuxt.py). Any bike listing page carries the whole range: platforms (Aero-to-Weight, Endurance,
...) with their frame models (Falcn RS 2.0, Grifn, ...), each with its builds (`$$groupsets`)
and their price. Ridley sells each size and colour as its own item, so one item page per build
gives the spec sheet, the model year ("Collectie Ridley 2027"), the other colours and sizes,
and the geometry.
"""
import json
import re

from .common import clean, log, normalize_specs, parse_price, size_name
from .nuxt import nuxt_state

BRAND = "Ridley"
BASE = "https://www.ridley-bikes.com/nl_NL"
LISTING = BASE + "/bikes/categories/road"
PLATFORMS = {  # Ridley's platform code -> category; Track, Hardtail (MTB) and Kids are left out
    "AerotoAero": "Race",
    "AerotoWeight": "Race",
    "StiffnessToWeight": "Race",
    "EnduranceROAD": "Endurance",
    "Adventure": "Gravel",
    "GravelALLROAD": "Gravel",
    "PerformanceGRAVEL": "Gravel",
    "XNight": "Cyclocross",
    "XRide": "Cyclocross",
    "TimeTrial": "Triathlon / TT",
    "Triathlon": "Triathlon / TT",
}
# Ridley's attribute names -> the labels normalize_specs knows; attributes not listed are left out.
FIELDS = {
    "frame": "Frame", "fork": "Voorvork", "material": "Material", "groupset": "Groepset",
    "right_shifter": "Shifter", "left_shifter": "Shifter links", "rear_derailleur": "Achterderailleur",
    "front_derailleur": "Voorderailleur", "crank": "Crankstel", "cassette": "Cassette", "chain": "Ketting",
    "brakes": "Rem", "front_brake": "Rem", "rear_brake": "Achterrem", "rotor": "Remschijf",
    "wheelset": "Wiel voor", "front_wheel": "Wiel voor", "rear_wheel": "Wiel achter", "outer_tyre": "Buitenband",
    "handlebar": "Stuur", "stem": "Stuurpen", "cockpit": "Stuur/stuurpen (geïntegreerd)", "seatpost": "Zadelpen",
    "saddle": "Zadel", "pedals": "Pedaal", "max_tire_clearance_700c": "Maximale bandenmaat",
}
GROUPSET_WORDS = [(r"\bsram\b", "SRAM"), (r"\bdi2\b", "Di2"), (r"\bdura ace\b", "Dura-Ace"), (r"\s+(?://|-)\s+", " "),
                  (r"\bgrx(\d)", r"GRX \1"), (r"\bcues\b", "CUES"), (r",.*$", "")]


def tidy_groupset(text):
    """"Sram Red AXS 2x12sp" -> "SRAM Red AXS 2x12"; "Shimano 105 DI2 // 2x12s" -> "Shimano 105 Di2 2x12"; "Shimano 105 - 2x12" -> "Shimano 105 2x12"."""
    text = clean(text)
    for pattern, repl in GROUPSET_WORDS:
        text = re.sub(pattern, repl, text, flags=re.I)
    text = re.sub(r"(\d+x\d+)(?:sp|s)\b", r"\1", text, flags=re.I)
    return clean(text)


def model_year(attributes):
    """2027 from "Collectie Ridley 2027" or the collection code CY_RID2027."""
    for text in (attributes.get("collection_year"), attributes.get("collections")):
        m = re.search(r"(20\d\d)", str(text or ""))
        if m:
            return int(m.group(1))
    return None


def builds(listing):
    """(platform code, frame model, build) for every road, gravel, cyclocross and TT build in the range."""
    found = []
    for platform in (((listing or {}).get("state") or {}).get("bikes") or {}).get("items") or []:
        if platform.get("code") not in PLATFORMS:
            continue
        for frame in platform.get("frameplatformdetails") or []:
            if str(frame.get("electric")).lower() in ("ja", "yes", "true") or str(frame.get("electricBool")) == "True":
                continue
            for build in frame.get("$$groupsets") or []:
                if build.get("designs"):
                    found.append((platform["code"], frame, build))
    return found


SIZES = ["3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL"]


def image_of(entry):
    """The 2048 px photo; relations only name the 400 px one, which has a 2048 px twin."""
    images = (entry or {}).get("images") or {}
    image = images.get("image") if isinstance(images, dict) else None
    if isinstance(image, dict):
        image = image.get("highres") or image.get("uhd") or image.get("midres") or image.get("thumb")
    image = image or (entry or {}).get("image")
    return image.replace("_image_400x.", "_image_2048x.") if isinstance(image, str) else None


def colour_name(attributes):
    """"FR226L2As - Silver/Black/Candy Red Metallic" -> "Silver/Black/Candy Red Metallic"; a bare paint code
    ("KAD27D6S") falls back on the base colours ("Silver/Red")."""
    paint = (attributes or {}).get("paint_des")
    if paint and " - " in paint:
        return clean(paint.split(" - ", 1)[1])
    base = [clean(attributes.get(k)) for k in ("primary_basecolour", "secondary_basecolour") if (attributes or {}).get(k)]
    return "/".join(base) or None


def geometry_rows(attributes):
    table = (attributes or {}).get("excel_frame_geometry") or []
    if isinstance(table, str):  # some items carry the table as a JSON string
        try:
            table = json.loads(table)
        except ValueError:
            table = []
    return table if isinstance(table, list) else []


def sizes_of(item, relations):
    sizes = [(item.get("attributes") or {}).get("frame_size")]
    sizes += [((r.get("variantattribute") or {}).get("value")) for r in relations.get("othersizes") or []]
    found = {size_name(s) for s in sizes if s}
    return sorted(found, key=lambda s: (SIZES.index(s) if s in SIZES else len(SIZES), s))


def geometry(item):
    """Stack (row S) and reach (row R) per size from the item's geometry table."""
    table = geometry_rows(item.get("attributes"))
    if not table:
        return {}
    rows = {str(r[0]).strip(): r[1:] for r in table[1:] if r}
    sizes = {}
    for size, stack, reach in zip(table[0][1:], rows.get("S", []), rows.get("R", [])):
        if isinstance(stack, (int, float)) and isinstance(reach, (int, float)) and stack and reach:
            sizes[size_name(size)] = {"stack": stack, "reach": reach}
    return sizes


def parse(platform, frame, build, state, url):
    data = (state.get("data") or [{}])[0]
    item, relations = data.get("bike") or {}, data.get("relations") or {}
    attributes = item.get("attributes") or {}
    groupset = tidy_groupset(build.get("groupset"))
    name = clean(f"{frame.get('model')} {groupset}") if groupset.lower() != "frameset" else f"{frame.get('model')} Frameset"
    colours, colour_images = [], []
    for entry in [{"attributes": attributes, "images": attributes.get("images")}] + (relations.get("otherdesigns") or []):
        colour = colour_name(entry.get("attributes"))
        if colour and colour not in colours:
            colours.append(colour)
            colour_images.append(image_of(entry.get("attributes")) or image_of(entry))
    prices = [parse_price(d.get("msrp")) for d in build.get("designs") or [] if parse_price(d.get("msrp"))]
    price = parse_price((data.get("price") or {}).get("msrp")) or (min(prices) if prices else None)
    pairs = [(FIELDS[k], v) for k, v in attributes.items()
             if k in FIELDS and isinstance(v, str) and clean(v) and "niet inbegrepen" not in v.lower()]
    return {
        "name": name,
        "brand": BRAND,
        "url": url,
        "sku": attributes.get("modelcode") or item.get("externalid"),
        "price": price,
        "category": PLATFORMS[platform],
        "model_year": model_year(attributes),
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "sizes": sizes_of(item, relations),
        "image_url": image_of(attributes) or next((c for c in colour_images if c), None) or image_of(build["designs"][0]),
        "color_image_urls": colour_images,
    }


def scrape(fetcher, limit=None):
    bikes = []
    for platform, frame, build in builds(nuxt_state(fetcher.get(LISTING))):
        if limit is not None and len(bikes) >= limit:
            break
        code = build["designs"][0].get("externalid")
        if not code:
            continue
        url = f"{BASE}/bikes/{code}"
        state = nuxt_state(fetcher.get(url))
        if not state:
            log.warning("Ridley: no bike data in %s", url)
            continue
        bike = parse(platform, frame, build, state, url)
        if not bike["specifications"]:
            log.warning("Ridley: no spec sheet in %s", url)
        bikes.append(bike)
        log.info("Ridley: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
