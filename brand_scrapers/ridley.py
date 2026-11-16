"""Ridley: road, gravel, cyclocross and TT bikes from the Dutch site (euro prices).

Since early November 2026 ridley-bikes.com is a Nuxt 3 app: its pages no longer carry the range, which the site
loads from Cycling Factory's API (`V1/families`): platforms (Aero-to-Weight, Endurance, ...) with their frame models
(Falcn RS 2.0, Grifn, ...), each listing its items (`configurations`) with their build and price. Ridley sells each
size and colour as its own item, so the items are grouped by build, and one item page per build gives the spec sheet,
the model year ("Collectie Ridley 2027"), the other colours and sizes, and the geometry. The item pages embed their
state as Nuxt 3 JSON (`__NUXT_DATA__`, read by nuxt.py); the old site's minified `window.__NUXT__` is read too.

A few bikes are only in the site's menu, not in the API's range: the Invenio collection (Ridley x Tomorrowland). Their
item pages are read as well, with the other builds they link to.
"""
import json
import os
import re

from .common import ROOT, clean, log, normalize_specs, parse_price, size_name
from .nuxt import nuxt_data, nuxt_state

BRAND = "Ridley"
BASE = "https://www.ridley-bikes.com/nl_NL"
LISTING = BASE + "/bikes/categories/road"
FAMILIES = "https://api.cyclingfactory.be/V1/families?locale={locale}&brand=Ridley"
# Ridley's Belgian site, in Dutch with euro prices: it serves the same item pages when the Dutch one fails (in November
# 2026 nl_NL answered "Did not find locale" for most bikes in the range while nl_BE showed them).
FALLBACK = "https://www.ridley-bikes.com/nl_BE"
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
    """"Sram Red AXS 2x12sp" -> "SRAM Red AXS 2x12"; "Shimano 105 DI2 // 2x12s" -> "Shimano 105 Di2 2x12"; "Shimano 105 - 2x12" -> "Shimano 105 2x12"; "2X12" -> "2x12"."""
    text = clean(text)
    for pattern, repl in GROUPSET_WORDS:
        text = re.sub(pattern, repl, text, flags=re.I)
    text = re.sub(r"(\d+x\d+)(?:sp|s)\b", r"\1", text, flags=re.I)
    text = re.sub(r"\b(\d+)X(\d+)\b", r"\1x\2", text)  # "2X12" as the other builds write it
    return clean(text)


def model_year(attributes):
    """2027 from "Collectie Ridley 2027" or the collection code CY_RID2027."""
    for text in (attributes.get("collection_year"), attributes.get("collections")):
        m = re.search(r"(20\d\d)", str(text or ""))
        if m:
            return int(m.group(1))
    return None


def builds(listing):
    """(platform code, frame model, build) for every road, gravel, cyclocross and TT build in the range.

    `listing` is the API's families ({"result": [platform, ...]}) or the old site's page state; a build is
    {"groupset": ..., "designs": [{"externalid", "msrp"}, ...]}, one design per size and colour."""
    listing = listing or {}
    platforms = listing.get("result") if "result" in listing else \
        ((listing.get("state") or {}).get("bikes") or {}).get("items")
    found = []
    for platform in platforms or []:
        if platform.get("code") not in PLATFORMS:
            continue
        for frame in platform.get("frameplatformdetails") or []:
            if str(frame.get("electric")).lower() in ("ja", "yes", "true") or str(frame.get("electricBool")) == "True":
                continue
            for build in frame.get("$$groupsets") or group_builds(frame.get("configurations")):
                if build.get("designs"):
                    found.append((platform["code"], frame, build))
    return found


def group_builds(configurations):
    """The API's items of a frame, one per size and colour, grouped by build in the order they come."""
    found = {}
    for item in configurations or []:
        if not item.get("externalid") or not clean(item.get("groupset")):
            continue
        key = item.get("groupsetCode") or tidy_groupset(item["groupset"]).lower()
        build = found.setdefault(key, {"groupset": item["groupset"], "designs": []})
        build["designs"].append({"externalid": item["externalid"], "msrp": item.get("msrp")})
    return list(found.values())


def item_data(page):
    """{"bike", "price", "relations"} of an item page: the Nuxt 3 page's async data, or the old site's state."""
    data = nuxt_data(page)
    if data:
        return next((v for v in (data.get("data") or {}).values() if isinstance(v, dict) and v.get("bike")), None)
    state = nuxt_state(page)
    found = ((state or {}).get("data") or [None])[0]
    return found if isinstance(found, dict) and found.get("bike") else None


def menu_items(fetcher):
    """Item codes the site's menu links to (/bikes/SBIKAFRID340): the Invenio collection is only there."""
    return list(dict.fromkeys(links_in((nuxt_data(fetcher.get(LISTING)) or {}).get("pinia"))))


def links_in(value):
    """The item codes of every /bikes/<code> link in a page's state."""
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [code for v in value for code in links_in(v)]
    m = re.match(r"^/bikes/((?:SBI|FFS)[A-Z0-9]+)(?:\?|$)", value) if isinstance(value, str) else None
    return [m.group(1)] if m else []


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
    """The colour name from the paint: "FR226L2As - Silver/Black/Candy Red Metallic" -> "Silver/Black/Candy Red
    Metallic", "FEN01As (Arctic Grey Metallic - White)" -> "Arctic Grey Metallic/White". A bare paint code
    ("KAD27D6S") falls back on the base colours ("Silver/Red"), then on the main paint ("Zilver // 0" -> "Zilver")."""
    attributes = attributes or {}
    paint = clean(attributes.get("paint_des"))
    m = re.match(r"^\S+\s*(?:\((.+)\)|-\s+(.+))$", paint)
    if m:
        return clean(re.sub(r"\s+-\s+", "/", m.group(1) or m.group(2)))
    base = [clean(attributes.get(k)) for k in ("primary_basecolour", "secondary_basecolour") if attributes.get(k)]
    if base:
        return "/".join(base)
    main = clean(str(attributes.get("paint_bac") or "").split("//")[0])
    return main or None


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


def parse(platform, frame, build, data, url):
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
             if k in FIELDS and isinstance(v, str) and clean(v) and "niet inbegrepen" not in v.lower()
             and clean(v).lower() != "frameset"]  # a frameset names "Frameset" as its shifter and groupset
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
    bikes, seen, done = [], set(), set()
    text = fetcher.get(FAMILIES.format(locale="nl_NL"))
    try:
        listing = json.loads(text) if text else {}
    except ValueError:
        listing = {}
    found = builds(listing)
    if not found:
        log.warning("Ridley: no bikes in the range from %s", FAMILIES.format(locale="nl_NL"))
    known = {d["externalid"] for _, _, b in found for d in b["designs"]}
    for platform, frame, build in found:
        if limit is not None and len(bikes) >= limit:
            break
        bike = read_build(fetcher, platform, frame, build)
        if bike and bike["name"] not in seen:
            seen.add(bike["name"])
            bikes.append(bike)
    # the menu's bikes outside the range (the Invenio collection), and the other builds their pages link to
    queue = [c for c in menu_items(fetcher) if c not in known]
    while queue and (limit is None or len(bikes) < limit):
        code = queue.pop(0)
        if code in done:
            continue
        done.add(code)
        url = f"{BASE}/bikes/{code}"
        data = item_data(fetcher.get(url))
        item = (data or {}).get("bike") or {}
        attributes = item.get("attributes") or {}
        platform = platform_of(item)
        if not platform or str(attributes.get("electric")).lower() in ("ja", "yes", "true"):
            continue
        for kind in ("othergroupsets", "otherdesigns"):
            queue += [r["externalid"] for r in (data.get("relations") or {}).get(kind) or []
                      if r.get("externalid") and r["externalid"] not in known]
        frame = {"model": attributes.get("model")}
        build = {"groupset": attributes.get("groupset"), "designs": [{"externalid": code}]}
        bike = parse(platform, frame, build, data, url)
        if bike["name"] not in seen and bike["specifications"]:
            seen.add(bike["name"])
            bikes.append(bike)
            log.info("Ridley: %s %s (%s), from the menu", bike["name"], bike["model_year"], bike["price"])
    return bikes


def platform_of(item):
    """The platform code of an item outside the range: its frame_family is the code in lowercase ("enduranceroad")."""
    family = clean(item.get("frame_family")).lower()
    return next((code for code in PLATFORMS if code.lower() == family), None)


_dutch_failures = []  # item pages the Dutch site failed on in this run


def item_page(fetcher, code):
    """(item data, whether it came from the Belgian site). After a few failures the Dutch site is skipped."""
    if len(_dutch_failures) < 3:
        data = item_data(fetcher.get(f"{BASE}/bikes/{code}"))
        if data or fetcher.status == 404:
            return data, False
        _dutch_failures.append(code)
    return item_data(fetcher.get(f"{FALLBACK}/bikes/{code}")), True


def read_build(fetcher, platform, frame, build):
    code = build["designs"][0].get("externalid")
    if not code:
        return None
    url = f"{BASE}/bikes/{code}"
    data, belgian = item_page(fetcher, code)
    if not data:
        log.warning("Ridley: no bike data in %s", url)
        return None
    if belgian:  # the price list's Dutch price, not the Belgian page's
        data = dict(data, price=None)
    bike = parse(platform, frame, build, data, url)
    if not bike["specifications"]:
        log.warning("Ridley: no spec sheet in %s", url)
    log.info("Ridley: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bike


# --- Earlier model years -------------------------------------------------------------------------------------------

# Ridley keeps the item page of bikes it no longer sells (the 2020 Noah Fast Disc: /bikes/SBINFDRID001), with the
# spec sheet, the collection year and the photos, but no list of them. Item codes are SBI + three letters for the frame
# + RID + a number counted up over the years, so probe() tries the numbers of each frame's letters (HEAD requests)
# and writes the codes found; archive() reads those pages and the other builds and colours each one links to.
CODES = os.path.join(ROOT, "data", "years", "archived", "ridley_codes.txt")
FIRST_YEAR = 2018
# Letters of frames Ridley no longer lists, tried besides those in its sitemap: a guess at each old line's code.
OLD_LETTERS = ("NOF NFA NFR NOA NSL NOS NHD NOD NDI HSX HLX HES HSL HEL HSD FSL FSX FEA FES LIZ LSL XND XNI XNS XNA "
               "XNC XRI XRD XBO XTR KAS KSP KAN KAF KAC KAL KAD DFD DEA DEN DFA GRI GRA GRC NFD HED FEN ASD TRI TRF "
               "ORY FAD").split()
SITEMAP = "https://www.ridley-bikes.com/sitemap_products.xml"


def probe(fetcher, step=2, beyond=100, old_numbers=40):
    """The item codes Ridley's Belgian site answers for, from every frame's letters (those in the sitemap, up to
    `beyond` past its highest number, and OLD_LETTERS up to `old_numbers`). Sizes of a build get consecutive numbers,
    so every second number finds each build and colour; archive() follows their links to the rest."""
    import concurrent.futures
    top = {}
    for code in re.findall(r"/bikes/SBI([A-Z0-9]{3})RID(\d{3})", fetcher.get(SITEMAP) or ""):
        top[code[0]] = max(top.get(code[0], 0), int(code[1]))
    codes = [f"SBI{p}RID{n:03d}" for p, m in top.items() for n in range(1, m + beyond + 1, step)]
    codes += [f"SBI{p}RID{n:03d}" for p in OLD_LETTERS if p not in top for n in range(1, old_numbers + 1)]

    def answers(code):
        for _ in range(3):
            try:
                status = fetcher.session.head(f"{FALLBACK}/bikes/{code}", timeout=30, allow_redirects=False).status_code
            except OSError:
                continue
            if status in (200, 404):
                return status == 200
        return False

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        found = [code for code, ok in zip(codes, pool.map(answers, codes)) if ok]
    os.makedirs(os.path.dirname(CODES), exist_ok=True)
    with open(CODES, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(found)) + "\n")
    log.info("Ridley: %d of %d item codes answer", len(found), len(codes))
    return found


def archive(fetcher, limit=None):
    """A bike per build and model year from 2018 on, read from the item pages of the codes probe() found (and the
    builds and colours they link to); no price, as it isn't the new price of today."""
    try:
        with open(CODES, encoding="utf-8") as fh:
            queue = [line.strip() for line in fh if line.strip()]
    except OSError:
        log.warning("Ridley: no %s, run `python -m brand_scrapers.ridley --probe` first", CODES)
        return []
    try:  # the range's items are the catalogue's own year: the scrape reads them
        current = {d["externalid"] for _, _, b in builds(json.loads(fetcher.get(FAMILIES.format(locale="nl_NL")) or "{}"))
                   for d in b["designs"]}
    except ValueError:
        current = set()
    bikes, builds_seen, done = [], set(), set(current)
    while queue and (limit is None or len(bikes) < limit):
        code = queue.pop(0)
        if code in done:
            continue
        done.add(code)
        data, _ = item_page(fetcher, code)
        item = (data or {}).get("bike") or {}
        attributes = item.get("attributes") or {}
        platform = platform_of(item)
        year = model_year(attributes)
        relations = (data or {}).get("relations") or {}
        done.update(r.get("externalid") for r in relations.get("othersizes") or [])  # the same build, another size
        if not platform or not year or year < FIRST_YEAR or str(attributes.get("electric")).lower() in ("ja", "yes", "true"):
            continue
        for kind, related in relations.items():
            if kind.startswith("other") and kind != "othersizes":
                queue += [r["externalid"] for r in related or [] if r.get("externalid") and r["externalid"] not in done]
        key = (clean(attributes.get("model")).lower(), tidy_groupset(attributes.get("groupset")).lower(), year)
        if key in builds_seen:
            continue
        builds_seen.add(key)
        frame = {"model": attributes.get("model")}
        build = {"groupset": attributes.get("groupset"), "designs": [{"externalid": code}]}
        bike = dict(parse(platform, frame, build, dict(data, price=None), f"{BASE}/bikes/{code}"), price=None)
        if bike["specifications"]:
            bikes.append(bike)
            log.info("Ridley: %s %s, an earlier year", bike["name"], bike["model_year"])
    return bikes


if __name__ == "__main__":
    import logging
    import sys
    from .common import Fetcher
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if "--probe" in sys.argv:
        print(f"{len(probe(Fetcher()))} item codes -> {CODES}")
