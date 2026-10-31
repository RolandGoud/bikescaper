"""Giant NL: road, gravel and TT bikes from the NL sitemap.

Product pages are server-rendered HTML. Their URLs end in the model year
(tcr-advanced-pro-0-di2-2027); the sitemap still lists older years, so only the
current years are read. robots.txt asks for a crawl delay of a few seconds.
"""
import re

from .common import clean, is_ebike, log, normalize_specs, parse_price

BRAND = "Giant"
SITEMAP = "https://static.giant-bicycles.com/sitemaps/sitemap-giant-nl-nl.xml"
HOST_DELAY = {"www.giant-bicycles.com": 4}
FAMILIES = ("tcr", "propel", "defy", "contend", "revolt", "trinity", "tcx", "ocr", "fastroad")
FIRST_YEAR = 2025


def product_urls(fetcher, first_year=FIRST_YEAR):
    xml = fetcher.get(SITEMAP) or ""
    urls = []
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.match(r"https://www\.giant-bicycles\.com/nl/([a-z0-9-]+)-(20\d\d)$", url)
        if not m or m.group(1).startswith("bikes-") or int(m.group(2)) < first_year:
            continue
        if m.group(1).startswith(FAMILIES) and not is_ebike(m.group(1).replace("-", " "), url):
            urls.append(url)
    return urls


def category_of(label, url):
    """Giant's label ("Aero Race Fiets"), without "Fiets"; from the family when the page has none."""
    label = re.sub(r"\s*Fiets$", "", label or "").strip()
    if label and not label.lower().startswith(FAMILIES):
        return label
    slug = url.rsplit("/", 1)[-1]
    for families, name in ((("revolt",), "Gravel"), (("propel",), "Aero Race"), (("defy",), "Endurance"),
                           (("trinity",), "Triathlon / TT"), (("tcx",), "Cyclocross"), (("fastroad",), "Fitness")):
        if slug.startswith(families):
            return name
    return "Race"


def parse(page, url):
    name = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    if not name:
        return None
    title = re.search(r'<meta property=og:title content="([^"]+)"', page)
    # og:title reads "TCR Advanced Pro 0-Di2 (2027) |  Race Fiets | Giant Bicycles Nederland"
    category = clean(title.group(1).split("|")[1]) if title and title.group(1).count("|") >= 2 else ""
    price = re.search(r'class=currentprice>([^<]+)<', page)
    image = re.search(r"<meta property=og:image content=([^ >]+)>", page)
    pairs = re.findall(r"<div class=label>(.*?)</div><div class=value>(.*?)</div>", page, re.S)
    sizes = [clean(s) for s in re.findall(r"<th scope=col name=framesize>(.*?)</th>", page)]
    product_id = re.search(r"data-product-id=(\d+)", page)
    year = re.search(r"-(20\d\d)$", url)
    model = re.sub(r"\s*\(?20\d\d\)?$", "", clean(name.group(1)))  # some h1s end in the model year
    colours = next((clean(v).split(", ") for k, v in pairs if clean(k) == "Kleuren"), [])
    colours = [c for c in colours if c] or photo_colours(page, model)
    return {
        "name": model,
        "brand": BRAND,
        "url": url,
        "sku": product_id.group(1) if product_id else None,
        "price": parse_price(price.group(1)) if price else None,
        "category": category_of(category, url),
        "model_year": int(year.group(1)) if year else None,
        "specifications": normalize_specs(pairs),
        "color_names": colours,
        "sizes": list(dict.fromkeys(sizes)),
        # The og:image is padded to 800x600 on white; ask for a larger one.
        "image_url": image.group(1).replace("h_600", "h_750").replace("w_800", "w_1000") if image else None,
        "color_image_urls": [colour_photo(page, model, c, colours) for c in colours],
        "color_angle_urls": [colour_angles(page, model, c, colours) for c in colours],
    }


IMAGES = "https://images2.giant-bicycles.com/b_white%2Cc_pad%2Ch_750%2Cq_80%2Cw_1000/"
# Riding photos and the studio shots on a black background (_B, or a -1 twin of a close-up).
NOT_A_VIEW = re.compile(r"(?i)action|[-_]B$")
# The close-ups, front and rear views, as opposed to the side view: -D2, _D-005-2, -Front, _back, _Road-5, _W_03.
CLOSE_UP = re.compile(r"(?i)[-_](D[-_]?\d+|Rear|Front|Frount|Back|F|Angle|Road|MTB|W_\d+)(?=[-_.\d]|$)")


def _photo_sets(page, model):
    """This model's studio photos on the page, one set per colour: [(shade, side view, [other angles])].

    Giant names photos by model year, model and colour letter, but not consistently:
    MY25TCRAdvanced2-KOM_ColorBIllusionWhite.jpg, MY23DefyAdvancedPro1ColorA_Airglow_D1.jpg,
    MY26TCRAdvancedPro-DA_ColorACarbon_RossoCorsa.jpg (the "Dura-Ace" model) with its close-ups as
    _ColorACarbonRossoCorsa-D4, MY21ContendAR1_ColorAMetallicNavy_Road-5, _W_03, _back. So a photo belongs
    to this model when it starts like the page's own photo (og:image) or like the model's name, and to a
    colour by its letter. The side view is the page's own photo or the shortest name of the letter that
    isn't a close-up; the rest are its other angles. The page also shows other models' photos, which
    neither prefix matches."""
    name = "-?".join(re.escape(c) for c in re.sub(r"[^A-Za-z0-9]", "", model))
    prefixes = [r"MY\d\d%s(?:-[A-Za-z]+)?" % name]
    own = re.search(r"<meta property=og:image content=[^ >]*/(MY\d\d[A-Za-z0-9-]+?)_?Color[A-H]", page)
    if own:
        prefixes.insert(0, re.escape(own.group(1)))
    sets = {}
    for path, year, letter, rest in re.findall(r"([a-z0-9]{20}/(MY\d\d)[A-Za-z0-9-]*?_?Color([A-H])([A-Za-z0-9_-]*)\.jpg)", page):
        stem = path.split("/", 1)[1]
        if not any(re.match(r"(?:%s)_?Color[A-H]" % p, stem) for p in prefixes) or NOT_A_VIEW.search(rest):
            continue
        group = sets.setdefault((year, letter), [])
        if path not in group:
            group.append(path)
    og = re.search(r"<meta property=og:image content=[^ >]*/([a-z0-9]{20}/[^/ >]+\.jpg)", page)
    found = []
    for group in sets.values():
        stem = {g: g.split("/", 1)[1][:-4] for g in group}
        sides = [g for g in group if not CLOSE_UP.search(stem[g])]
        # the side view on black tyres (-blacktires) only when there is no other
        side = (og.group(1) if og and og.group(1) in group and "blacktires" not in og.group(1)
                else min(sides, key=lambda g: ("blacktires" in g, len(g))) if sides else None)
        # a close-up's twin on black is the close-up's name with -1 or -2 after it (-D11-1, _D-5-2)
        others = set(stem.values()) - {stem.get(side)}
        angles = [g for g in group if g != side and "blacktires" not in g
                  and re.sub(r"(?<=\d)-\d$", "", stem[g]) not in others - {stem[g]}]
        shade = re.sub(r"^.*?Color[A-H]_?", "", stem[side if side else group[0]])
        shade = shade[:CLOSE_UP.search(shade).start()] if CLOSE_UP.search(shade) else shade
        found.append((shade, side, angles))
    return found


def _photo_set(page, model, colour, colours=None):
    """(side view, other angles) of one colour: the set whose side view names the colour, or the only set
    when the page lists one colour (MY20Contend1_ColorA.jpg names none). The side view is None when the
    page shows only that colour's close-ups; its own photo (og:image) is then the side view."""
    keys = [re.sub(r"[^A-Za-z0-9]", "", part).lower() for part in colour.split("/")]
    sets = _photo_sets(page, model)
    for shade, side, angles in sorted(sets, key=lambda s: len(s[1] or "~" * 99)):
        if any(k and re.sub(r"[^A-Za-z0-9]", "", shade).lower().startswith(k) for k in keys):
            return side, angles
    if len(sets) == 1 and colours is not None and len(colours) == 1:
        return sets[0][1], sets[0][2]
    return None, []


def photo_colours(page, model):
    """The colours of this model as its side-view photos name them (MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite.jpg:
    "Icicle White"), in the order of the letters; for the pages whose spec sheet has no Kleuren line."""
    found = []
    for shade, side, _angles in sorted(_photo_sets(page, model), key=lambda s: re.sub(r"^.*?(Color[A-H])", r"\1", (s[1] or "") + (s[2] or [""])[0])):
        words = [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", w) for w in re.split(r"[_-]+", re.sub(r"\d+$", "", shade)) if w]
        if words and "/".join(words) not in found:
            found.append("/".join(words))
    return found


def colour_photo(page, model, colour, colours=None):
    """The side view of one colour of this model. The page's colour list isn't in the order of the letters,
    so the photo's name has to match the colour."""
    side, angles = _photo_set(page, model, colour, colours)
    if side:
        return IMAGES + side
    # only its close-ups are named like the rest: the page's own photo is the side view, when it is of this colour
    own = re.search(r"<meta property=og:image content=[^ >]*/([a-z0-9]{20}/[^/ >]+\.jpg)", page)
    keys = [re.sub(r"[^A-Za-z0-9]", "", part).lower() for part in colour.split("/")]
    if own and angles and (colours is not None and len(colours) == 1
                           or any(k and k in re.sub(r"[^A-Za-z0-9]", "", own.group(1)).lower() for k in keys)):
        return IMAGES + own.group(1)
    return None


def colour_angles(page, model, colour, colours=None):
    """The other angles of one colour (close-ups, front, rear), in the page's order; not the side view
    colour_photo gives, nor riding photos."""
    _side, angles = _photo_set(page, model, colour, colours)
    return [IMAGES + a for a in angles]


def scrape(fetcher, limit=None):
    fetcher.delays.update(HOST_DELAY)
    bikes = []
    for url in product_urls(fetcher)[:limit]:
        page = fetcher.get(url)
        bike = parse(page, url) if page else None
        if not bike:
            log.warning("Giant: no product data in %s", url)
            continue
        if is_ebike(bike["name"], bike["category"]):
            continue
        if not bike["sizes"] or "Frame" not in bike["specifications"]:  # clamps, spacers and other parts
            continue
        bikes.append(bike)
        log.info("Giant: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
