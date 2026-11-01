"""Spec sheets from earlier model years, read straight from the brands' NL sites.

Some brands keep their old bikes online long after they left the catalogue, and that is the
brand's own sheet, so it beats a Wayback Machine copy (which shows whatever was on the site the
day it was captured):

- Giant keeps a page per model year at /nl/defy-advanced-2-2021.
- Trek's product API still answers for archived bikes, with the model years a bike was sold
  (Domane AL 2 gen 3: 2021 - 2023) and its spec sheet. The product numbers come from the
  Wayback Machine listings (archive.py), and an earlier generation (Domane AL 2 Disc, gen 3) fills
  the years before the current one (gen 4).

    python -m brand_scrapers.history giant trek --cdx <cdx dir> [--db instance/bikecompare.sqlite3]
    python -m brand_scrapers.history giant trek --colours   # each colour's photo for the years already read
    python -m brand_scrapers.history giant trek --angles    # and each colour's other angles
    python -m brand_scrapers.history giant trek --archived --cdx <cdx dir>   # the lines they no longer sell

Writes data/years/site/<Brand>.json ({"checked_on", "years", "source", "models": {name: {year:
{captured, url, source, specs, price, image}}}}), which webapp/seed.py merges over
data/years/<Brand>.json, and the photo to images/<Brand>/years/<slug>_<year>_site.jpg.
"""
import argparse
import gzip
import io
import json
import os
import re
import sqlite3
from datetime import date
from urllib.parse import urlparse

from . import giant
from .archive import FIRST_YEAR, MIN_SPECS, compact, read_cdx, recognised
from .common import ROOT, Fetcher, frame, log, normalize_specs, trim


def giant_pages(url, years):
    base = re.sub(r"-20\d\d$", "", url.rstrip("/"))
    for year in years:
        yield year, f"{base}-{year}"


def giant_year(page):
    # A year Giant never sold this model under this URL serves the newest one, so go by the title.
    m = re.search(r"<title>[^<]*\((20\d\d)\)", page)
    return int(m.group(1)) if m else None


# Giant's 2027 names for bikes it sold under another name before: the TCR Advanced 2-PC ("Pro Compact"
# gearing) is the TCR Advanced 2's successor. {name: (earlier name, the earlier name's page URL without a year)}.
# Their earlier years are read from the earlier name's pages and marked with its name (sheet_name).
RENAMED = {
    "Giant": {
        "TCR Advanced 0-PC": ("TCR Advanced 0", "https://www.giant-bicycles.com/nl/tcr-advanced-0"),
        "TCR Advanced 1 - Pro Compact": ("TCR Advanced 1", "https://www.giant-bicycles.com/nl/tcr-advanced-1"),
        "TCR Advanced 2-PC": ("TCR Advanced 2", "https://www.giant-bicycles.com/nl/tcr-advanced-2"),
    },
}


# brand: (parser module, model URL -> [(year, page URL)], page -> the model year it shows, host delay)
SITES = {
    "Giant": (giant, giant_pages, giant_year, giant.HOST_DELAY),
}


def save_photo(fetcher, brand, slug, year, url, width=1000, colour=None, angle=None, rel=None):
    import html
    url = html.unescape((url or "").strip("\"'"))  # Giant's 2017 pages quote the og:image URL
    if not url:
        return None
    rel = rel or f"{brand}/years/{slug}_{year}{'_' + compact(colour) if colour else ''}{f'_{angle}' if angle else ''}_site.jpg"
    path = os.path.join(ROOT, "images", rel)
    if os.path.exists(path):
        return rel
    data = fetcher.get(url, binary=True)
    if not data:
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.split()[-1])
            img = bg
        # the side view is framed like the main photo; the other angles fill their own frame
        img = (trim if angle or "/gallery/" in rel else frame)(img.convert("RGB"))
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception as exc:  # a broken image shouldn't stop the run
        log.warning("image %s: %s", url, exc)
        return None
    return rel


TREK_API = "https://api.trekbikes.com/occ/v2/nl/products/{code}/{kind}?lang=nl_NL&curr=EUR"
# Numbers with a model year attached (1404000-2017) are from before 2018 and unknown to the API.
TREK_ROAD = re.compile(r"/fietsen/(?:racefietsen|gravel|cyclocross|triathlon)[^?]*/[pa]/(\d+)(?![\d-])")
TREK_SKIP = re.compile(r"elektrisch|e-bike|kinder|frameset|\brim\b|velg|dames|women", re.I)
# A stock item with its frame size and colour code ("DOMANE SL 6 56 BK"), not a model.
TREK_STOCK = re.compile(r"\b\d{2}\s+[A-Z]{2}$")


def colour_photos(fetcher, brand, slug, year, urls):
    """{colour: saved photo} for the colours we found a photo of that year."""
    saved = {c: save_photo(fetcher, brand, slug, year, u, colour=c) for c, u in (urls or {}).items() if u}
    return {c: rel for c, rel in saved.items() if rel}


def add_colour_photos(brand, fetcher=None):
    """Each colour's photo for the model years already in data/years/site/<Brand>.json, read again from the
    page or product the entry came from; the rest of the entry stays as it is."""
    path = os.path.join(ROOT, "data", "years", "site", f"{brand}.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if fetcher is None:
        fetcher = Fetcher(delays=SITES[brand][3]) if brand in SITES else Fetcher(delay=1.0)
    products = {}
    for name, entries in data["models"].items():
        for year, entry in entries.items():
            if entry.get("source") != "site" or len(entry.get("colours") or []) < 1 or entry.get("colour_images"):
                continue
            if brand == "Trek":
                code = trek_code(entry["url"])
                if not code:
                    continue
                if code not in products:
                    products[code] = trek_product(fetcher, code) or {}
                urls = products[code].get("colour_image_urls")
            else:
                page = fetcher.get(entry["url"])
                bike = SITES[brand][0].parse(page, entry["url"]) if page else None
                urls = dict(zip((bike or {}).get("color_names") or [], (bike or {}).get("color_image_urls") or []))
            entry["colour_images"] = colour_photos(fetcher, brand, compact(name), year, urls)
            log.info("%s %s %s: %d of %d colours", brand, name, year, len(entry["colour_images"]), len(entry["colours"]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)


def add_angles(brand, fetcher=None, names=None):
    """Every other angle of each colour (close-ups, front, rear) for the model years in
    data/years/site/<Brand>.json that have colour photos: entry["colour_angles"] = {colour: [saved photo]}."""
    path = os.path.join(ROOT, "data", "years", "site", f"{brand}.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if fetcher is None:
        fetcher = Fetcher(delays=SITES[brand][3]) if brand in SITES else Fetcher(delay=1.0)
    products = {}
    for name, entries in data["models"].items():
        for year, entry in entries.items():
            # a year that gave nothing is tried again, as add_colour_photos does
            if names and name not in names or entry.get("source") != "site" or not entry.get("colour_images") or entry.get("colour_angles"):
                continue
            if brand == "Trek":
                code = trek_code(entry["url"])
                if not code:
                    continue
                if code not in products:
                    products[code] = trek_product(fetcher, code)
                urls = (products[code] or {}).get("colour_angle_urls") or {}
            else:
                page = fetcher.get(entry["url"])
                bike = SITES[brand][0].parse(page, entry["url"]) if page else None
                urls = dict(zip((bike or {}).get("color_names") or [], (bike or {}).get("color_angle_urls") or []))
            angles = {}
            for colour in entry["colour_images"]:
                saved = [save_photo(fetcher, brand, compact(name), year, u, colour=colour, angle=n + 1)
                         for n, u in enumerate(urls.get(colour) or [])]
                if any(saved):
                    angles[colour] = [rel for rel in saved if rel]
            entry["colour_angles"] = angles
            log.info("%s %s %s: %d angles", brand, name, year, sum(len(a) for a in angles.values()))
            with open(path, "w", encoding="utf-8") as fh:  # after each year, so a stopped run keeps its work
                json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)


def _photo_stem(url):
    """"94920-04_TARMAC-SL7-SW-ETAP-CARB-CMLNSILGRN" from that colour's side view URL (_HERO or _HERO-SQUARE)."""
    from .specialized import SIDE_VIEW
    return SIDE_VIEW.sub("", (url or "").split("/")[-1].split("?")[0])


def _views_by_photo(colours):
    """{photo stem or casefolded colour name: [other view URLs]}: an old copy may spell a colour in capitals
    ("SATIN CARBON/TARMAC BLACK/CLEAN") where today's page doesn't, but the photo IDs are the same."""
    found = {}
    for name, (side, views) in colours.items():
        if views:
            found.setdefault(_photo_stem(side), views)
            found.setdefault(name.casefold(), views)
    return found


def _specialized_year(page):
    from . import specialized
    try:
        return (specialized.parse(page, "") or {}).get("model_year") if page else None
    except Exception:
        return None


def specialized_photos(pages_folders=(), fetcher=None):
    """Each colour's photo and its other views (entry["colours"], ["colour_images"], ["colour_angles"]) for
    Specialized's earlier model years, in data/years/Specialized.json (Wayback copies) and
    data/years/site/Specialized.json (its own old pages).

    Specialized's image server still serves the photos of bikes it sold years ago, so a photo's ID is all it
    takes. The IDs come from the Wayback copy of the page when it lists them (pages_folders: the folders
    `wayback.py fetch` saved them to; the 2019-2021 shop lists every colour's views), and else from the
    product page Specialized still serves, as long as that shows the same model year give or take one (a
    model year goes on sale the summer before, and some old IDs now show a later or earlier bike).
    A year without a photo of its own gets the first colour's."""
    from . import specialized
    fetcher = fetcher or Fetcher(delay=1.0)
    copies = {}  # (url, ts) -> the Wayback copy
    for folder in pages_folders:
        for dirpath, _dirs, files in os.walk(folder):
            for f in files:
                if f.endswith(".json") and os.path.exists(os.path.join(dirpath, f[:-5] + ".html.gz")):
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        meta = json.load(fh)
                    copies[(meta.get("url"), str(meta.get("ts")))] = os.path.join(dirpath, f[:-5] + ".html.gz")
    report = {}
    for path in (os.path.join(ROOT, "data", "years", "Specialized.json"),
                 os.path.join(ROOT, "data", "years", "site", "Specialized.json")):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        live = {}
        counts = report.setdefault(os.path.relpath(path, ROOT), {"years": 0, "from copy": 0, "from site": 0, "photos": 0})
        for name, entries in data["models"].items():
            for year, entry in entries.items():
                if entry.get("colour_images") or not entry.get("url"):
                    continue
                counts["years"] += 1
                colours, where = {}, None
                copy = copies.get((entry["url"], str(entry.get("ts"))))
                if copy:
                    with gzip.open(copy) as fh:
                        colours, where = specialized.page_colours(fh.read().decode("utf-8", "replace"), entry["url"]), "from copy"
                if not any(views for _side, views in colours.values()):
                    # No copy, or one with the side views only: the page Specialized still serves, if it's that year's bike.
                    if entry["url"] not in live:
                        page = fetcher.get(entry["url"])
                        live[entry["url"]] = specialized.page_colours(page, entry["url"]) if page else {}
                        live[entry["url"] + "#year"] = _specialized_year(page)
                    same_year = abs((live[entry["url"] + "#year"] or 0) - int(year)) <= 1
                    if same_year and not colours:
                        colours, where = live[entry["url"]], "from site"
                    elif same_year:  # the copy's colours, with the views the page has of the same photo
                        views_of = _views_by_photo(live[entry["url"]])
                        colours = {c: (side, views or views_of.get(_photo_stem(side)) or views_of.get(c.casefold()) or [])
                                   for c, (side, views) in colours.items()}
                if not colours:
                    continue
                slug = compact(name)
                shots, angles = {}, {}
                for colour, (side, views) in colours.items():
                    shot = save_photo(fetcher, "Specialized", slug, year, side, colour=colour)
                    if not shot:
                        continue
                    shots[colour] = shot
                    saved = [save_photo(fetcher, "Specialized", slug, year, u, colour=colour, angle=n + 1)
                             for n, u in enumerate(views)]
                    if any(saved):
                        angles[colour] = [rel for rel in saved if rel]
                if not shots:
                    continue
                entry["colours"] = entry.get("colours") or list(shots)
                entry["colour_images"], entry["colour_angles"] = shots, angles
                if not entry.get("image"):
                    entry["image"] = next(iter(shots.values()))
                counts[where] += 1
                counts["photos"] += len(shots) + sum(len(a) for a in angles.values())
                log.info("Specialized %s %s: %d colours, %d views (%s)", name, year, len(shots),
                         sum(len(a) for a in angles.values()), where)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return report


def trek_codes(cdx_folder):
    """Every Trek road and gravel bike product number in the Wayback Machine listings."""
    codes = set()
    for _ts, url in read_cdx(cdx_folder, "Trek"):
        m = TREK_ROAD.search(url)
        if m and not TREK_SKIP.search(url):
            codes.add(m.group(1))
    return sorted(codes)


def trek_years(text):
    """"2021 - 2023" -> [2021, 2022, 2023]; "2019" -> [2019]; "2024 - heden" runs to this year."""
    found = [int(y) for y in re.findall(r"20\d\d", text or "")]
    if not found:
        return []
    last = found[-1] if len(found) > 1 or not re.search(r"-\s*\D", text) else date.today().year
    return list(range(found[0], last + 1))


def trek_product(fetcher, code):
    """{code, name, years, url, specs, image_url} from Trek's product API, or None."""
    try:
        full = json.loads(fetcher.get(TREK_API.format(code=code, kind="full")) or "null")
        sheet = json.loads(fetcher.get(TREK_API.format(code=code, kind="specifications")) or "null")
    except ValueError:
        return None
    if not full or not sheet:
        return None
    items = [s for s in sheet.get("specs") or [] if s.get("marketingDescWithFrameSizesMap")]
    # Some parts are listed twice, once untranslated (the same text as the English service description):
    # put the translated one first, as normalize_specs keeps the first value per part.
    items.sort(key=lambda s: s["marketingDescWithFrameSizesMap"][0]["key"] == s.get("serviceDescription"))
    pairs = [(s.get("localizedSpecItemType"), s["marketingDescWithFrameSizesMap"][0]["key"]) for s in items]
    images = [i["assetId"] for group in full.get("assetImageList") or [] for i in group.get("images") or []]
    # The side-on shot of the whole bike ("...-A-Primary"); the others are close-ups and portraits.
    primary = next((i for i in images if re.search(r"[-_]Primary$", i)), None)
    # The colours it came in that year ("Crimson", "Plasma Pearl Grey/Purple Flip"), for dating an ad by its colour.
    options = [o for a in full.get("variantAttributesDirectory") or [] for o in a.get("options") or []
               if o.get("colorSwatchName") and o.get("displayName")]
    colours = [o["displayName"] for o in options]
    # Each colour's own side view: a variant names its colour swatch and the photo set ("A", "B") it's shown in.
    by_swatch = {o.get("value"): o["displayName"] for o in options}
    sets = {g.get("imageOption"): [i["assetId"] for i in g.get("images") or []] for g in full.get("assetImageList") or []}
    images_by_set = {g.get("imageOption"): [{"assetId": i["assetId"], "weight": i.get("weight") or 0,
                                             "accessorized": bool(i.get("accessorized"))} for i in g.get("images") or []]
                     for g in full.get("assetImageList") or []}
    colour_images, colour_angles = {}, {}
    for v in full.get("variants") or []:
        swatch = next((a.get("value") for a in v.get("variantAttributes") or [] if a.get("key") == "bike_colorSwatch"), None)
        side = next((i for i in sets.get(v.get("imageOption")) or [] if re.search(r"[-_]Primary$", i)), None)
        if by_swatch.get(swatch) and side:
            colour_images.setdefault(by_swatch[swatch], f"https://media.trekbikes.com/image/upload/f_png,w_1200/{side}")
        # The other angles of that colour, in Trek's own order; not the portrait crop or the bike with accessories.
        others = sorted((i for i in images_by_set.get(v.get("imageOption")) or []
                         if not i["accessorized"] and re.search(r"[-_]Alt\d+$", i["assetId"])), key=lambda i: i["weight"])
        if by_swatch.get(swatch) and others:
            colour_angles.setdefault(by_swatch[swatch], [
                f"https://media.trekbikes.com/image/upload/f_png,w_1200/{i['assetId']}" for i in others])
    # Trek's newer products leave modelYearIntroAndCurrent empty; their photos still carry the model year they
    # were shot for ("DomaneAL2-24-41587-A-Primary" is the 2024 Domane AL 2 Gen 4 in Crimson to Dark Carmine Fade).
    shot = next((int(m.group(1)) for i in images if (m := re.search(r"-([1-3]\d)-%s-" % re.escape(str(code)), i))), None)
    return {"code": code, "name": full.get("name") or "",
            "years": trek_years(full.get("modelYearIntroAndCurrent")) or ([2000 + shot] if shot else []),
            "years_from_photos": not trek_years(full.get("modelYearIntroAndCurrent")) and bool(shot),
            "colours": colours, "colour_image_urls": colour_images, "colour_angle_urls": colour_angles,
            "url": "https://www.trekbikes.com/nl/nl_NL" + (full.get("url") or f"/p/{code}/"),
            "category": full.get("defaultCategory") or "",
            "sheet_years": full.get("modelYearIntroAndCurrent"), "specs": normalize_specs(pairs),
            "image_url": f"https://media.trekbikes.com/image/upload/f_png,w_1200/{primary}" if primary else None}


def trek_code(url):
    """The product number in a Trek page url: /p/23522/, /a/33083/, or the newer
    /f/F221-5/domane-al-2-gen-4/41587/ (with or without the colour's variant number after it)."""
    m = re.search(r"/[pa]/(\d+)", url or "") or re.search(r"/f/[^/]+/[^/]+/(\d+)(?:/\d+)?/?$", url or "")
    return m.group(1) if m else None


def line_of(name):
    """A model line across generations: "Domane AL 2 Gen 4", "Domane AL 2 gen 3" and "Domane AL 2 Disc" -> domaneal2."""
    return compact(re.sub(r"\b(?:gen\s*\d+|disc)\b", " ", name.lower()))


def generation(name):
    m = re.search(r"\bgen\s*(\d+)", name, re.I)
    return int(m.group(1)) if m else 0


def archive_trek_codes():
    """{product number: {model years}} of the Trek pages the Wayback copies (data/years/Trek.json) were read from:
    a page is a product, and the years it was the model's page are the years that product was sold."""
    try:
        with open(os.path.join(ROOT, "data", "years", "Trek.json"), encoding="utf-8") as fh:
            archive = json.load(fh)
    except (OSError, ValueError):
        return {}
    found = {}
    for entries in archive.get("models", {}).values():
        for year, entry in entries.items():
            m = re.search(r"/p/(\d+)", entry.get("url") or "")
            if m and year.isdigit():
                found.setdefault(m.group(1), set()).add(int(year))
    return found


def trek_collect(models, fetcher, years, codes):
    seen = archive_trek_codes()
    products = [p for p in (trek_product(fetcher, c) for c in sorted(set(codes) | set(seen))) if p and p["years"]
                and recognised(p["specs"]) >= MIN_SPECS and not TREK_SKIP.search(p["name"])
                and not TREK_STOCK.search(p["name"])]
    for p in products:
        if p.get("years_from_photos"):
            # Its photos' year, and the years the Wayback copies found it as the model's page.
            p["years"] = sorted(set(p["years"]) | seen.get(p["code"], set()))
    log.info("Trek: %d archived bikes with a spec sheet", len(products))
    found, today = {}, date.today().isoformat()
    for name, _url in models:
        line, gen = line_of(name), generation(name)
        # Same line and no later generation than the model's own; for a year two bikes cover, the model's
        # own name, then the newer generation, then disc.
        mine = sorted((p for p in products if line_of(p["name"]) == line and not (gen and generation(p["name"]) > gen)),
                      key=lambda p: (compact(p["name"]) == compact(name), generation(p["name"]), "disc" in p["name"].lower()))
        for p in mine:  # later (better) ones overwrite
            for year in p["years"]:
                if year in years:
                    found.setdefault(name, {})[str(year)] = {
                        "captured": today, "url": p["url"], "source": "site", "sheet_years": p["sheet_years"],
                        "sheet_name": p["name"] if compact(p["name"]) != compact(name) else None,
                        "specs": p["specs"], "price": None, "colours": p["colours"],
                        "image": save_photo(fetcher, "Trek", compact(name), year, p["image_url"]),
                        "colour_images": colour_photos(fetcher, "Trek", compact(name), year, p["colour_image_urls"])}
        log.info("Trek %s: %s", name, sorted(found.get(name, {})))
    return found


def trek_archived(cdx_folder, db_path, fetcher=None, years=range(FIRST_YEAR, date.today().year + 1)):
    """Trek's discontinued lines: bikes in the Wayback listings whose line no catalogue model carries (Émonda
    SLR 7, gone since the Madone Gen 8). Second-hand ads are full of them, and without them an ad for one is
    matched to the nearest bike we have. Writes data/years/archived/Trek.json (one bike per line, as a
    catalogue scrape lists it, with the years it was sold) and adds their year sheets to data/years/site/Trek.json."""
    fetcher = fetcher or Fetcher(delay=1.0)
    conn = sqlite3.connect(db_path)
    have = {line_of(n) for (n,) in conn.execute("SELECT name FROM models WHERE brand = 'Trek'")}
    products = [p for p in (trek_product(fetcher, c) for c in trek_codes(cdx_folder)) if p and p["years"]
                and recognised(p["specs"]) >= MIN_SPECS and not TREK_SKIP.search(p["name"])
                and not TREK_STOCK.search(p["name"])]
    lines = {}
    for p in products:
        if line_of(p["name"]) not in have:
            lines.setdefault(line_of(p["name"]), []).append(p)
    bikes = []
    for line, found in sorted(lines.items()):
        found.sort(key=lambda p: (p["years"][-1], generation(p["name"])), reverse=True)
        newest = found[0]
        slug = compact(newest["name"])
        bikes.append({
            "name": newest["name"], "brand": "Trek", "url": newest["url"], "sku": newest["code"],
            "category": newest["category"], "specifications": newest["specs"],
            "color_names": list(dict.fromkeys(c for p in found for c in p["colours"])),
            "years": sorted({y for p in found for y in p["years"]}), "price": None,
            "image": save_photo(fetcher, "Trek", slug, None, newest["image_url"], rel=f"Trek/archived/{slug}.jpg")})
        log.info("Trek archived: %s %s", newest["name"], bikes[-1]["years"])
    sheets = trek_collect([(b["name"], b["url"]) for b in bikes], fetcher, years,
                          sorted({p["code"] for found in lines.values() for p in found}))
    _save_archived("Trek", bikes, sheets)
    return bikes


def _save_archived(brand, bikes, sheets):
    """data/years/archived/<Brand>.json (the discontinued lines, as a catalogue scrape lists them) and their year
    sheets next to the catalogue models' in data/years/site/<Brand>.json; those are left as they are."""
    out = os.path.join(ROOT, "data", "years", "archived", f"{brand}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(bikes, fh, ensure_ascii=False, indent=1)
    path = os.path.join(ROOT, "data", "years", "site", f"{brand}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        data = {"checked_on": date.today().isoformat(), "years": [], "source": f"{brand}'s own pages", "models": {}}
    data["years"] = sorted(set(data["years"]) | {int(y) for entries in sheets.values() for y in entries})
    for name, entries in sheets.items():
        data["models"].setdefault(name, {}).update(entries)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)


def own_years(brand, found, kept, fetcher):
    """The model years a brand's own store still lists besides the newest (Bianchi sells one build under the same
    name for several seasons; BMC keeps a Bike Archive back to 2016), read in the same run as the catalogue.

    `found` is every bike the adapter read, `kept` the catalogue after dedupe (the newest year of each name). The
    older years of a catalogue model go into data/years/site/<Brand>.json; a line that only older years have (the
    BMC Timemachine 01) into data/years/archived/<Brand>.json, with its years next to the others. Both files are
    written anew, since the store lists every year it has each time."""
    today = date.today().isoformat()
    newest = {b["name"]: b.get("model_year") for b in kept}

    def sheet(bike, year):
        slug = compact(bike["name"])
        urls = dict(zip(bike.get("color_names") or [], bike.get("color_image_urls") or []))
        return {"captured": today, "url": bike["url"], "source": "site", "specs": bike.get("specifications") or {},
                "price": bike.get("price"), "colours": bike.get("color_names") or [],
                "image": save_photo(fetcher, brand, slug, year, bike.get("image_url")),
                "colour_images": colour_photos(fetcher, brand, slug, year, urls)}

    sheets, lines = {}, {}
    for bike in found:
        year = bike.get("model_year")
        if not year or recognised(bike.get("specifications") or {}) < MIN_SPECS:
            continue
        if bike["name"] in newest:
            if year != newest[bike["name"]]:
                sheets.setdefault(bike["name"], {})[str(year)] = sheet(bike, year)
        else:
            lines.setdefault(bike["name"], []).append(bike)
    years = sorted({b["model_year"] for b in found if b.get("model_year")})
    os.makedirs(os.path.join(ROOT, "data", "years", "site"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "years", "site", f"{brand}.json"), "w", encoding="utf-8") as fh:
        json.dump({"checked_on": today, "years": years, "source": f"{brand}'s own store", "models": sheets},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
    archived, archived_sheets = [], {}
    for name, bikes in sorted(lines.items()):
        bikes.sort(key=lambda b: b["model_year"])
        line = dict(bikes[-1], years=[b["model_year"] for b in bikes],
                    image=save_photo(fetcher, brand, compact(name), None, bikes[-1].get("image_url"),
                                     rel=f"{brand}/archived/{compact(name)}.jpg"))
        archived.append(line)
        archived_sheets[name] = {str(b["model_year"]): sheet(b, b["model_year"]) for b in bikes}
        log.info("%s archived: %s %s", brand, name, line["years"])
    _save_archived(brand, archived, archived_sheets)
    return sum(len(v) for v in sheets.values()), len(archived)


def giant_archived(cdx_folder, db_path, fetcher=None, years=range(FIRST_YEAR, date.today().year + 1)):
    """Giant's discontinued lines (Defy Advanced SL, Contend SL): the bike pages in the Wayback listings whose
    line no catalogue model carries. Giant still serves a page per model year (/nl/defy-advanced-sl-1-2022)."""
    from .common import is_ebike
    fetcher = fetcher or Fetcher(delays=giant.HOST_DELAY)
    conn = sqlite3.connect(db_path)
    have = {line_of(n) for (n,) in conn.execute("SELECT name FROM models WHERE brand = 'Giant'")}
    slugs = {}
    for _ts, url in read_cdx(cdx_folder, "Giant"):
        m = re.match(r"https?://www\.giant-bicycles\.com/nl/([a-z0-9-]+)-(20\d\d)/?$", url)
        if m and m.group(1).startswith(giant.FAMILIES) and not is_ebike(m.group(1).replace("-", " "), url):
            slugs.setdefault(m.group(1), set()).add(int(m.group(2)))
    bikes, seen = [], set(have)
    for slug, found in sorted(slugs.items()):
        if line_of(slug.replace("-", " ")) in seen:
            continue
        url = f"https://www.giant-bicycles.com/nl/{slug}-{max(found)}"
        page = fetcher.get(url)
        bike = giant.parse(page, url) if page else None
        if not bike or not bike["sizes"] or "Frame" not in bike["specifications"] or is_ebike(bike["name"], bike["category"]):
            continue
        if line_of(bike["name"]) in seen:
            continue
        seen.add(line_of(bike["name"]))
        name = compact(bike["name"])
        bikes.append(dict(bike, years=sorted(found),
                          image=save_photo(fetcher, "Giant", name, None, bike["image_url"], rel=f"Giant/archived/{name}.jpg")))
        log.info("Giant archived: %s %s", bike["name"], sorted(found))
    sheets = collect("Giant", [(b["name"], b["url"]) for b in bikes], fetcher, years)
    for b in bikes:  # the years Giant still has a page for
        b["years"] = sorted({int(y) for y in sheets.get(b["name"], {})} | set(b["years"]))
    _save_archived("Giant", bikes, sheets)
    return bikes


# The brands that still serve their old product pages, with the URL names of their road and gravel lines.
OLD_PAGES = {
    "Specialized": (r"^(?:sworks)?(?:tarmac|roubaix|aethos|allez|diverge|crux|shiv|venge|ruby|amira|dolce)",
                    r"frameset|module|womens|turbo|creo|evo"),
    "Cannondale": (r"^(?:supersix|caad|synapse|topstone|systemsix|superslice|superx|slate)", r"neo|frameset|womens|kids"),
    "Cube": (r"^(?:attain|agree|litening|aerium|nuroad|crossrace|axial)", r"hybrid|frameset|kid|jersey|trapeze|ws"),
}


def pages_archived(brand, cdx_folder, db_path, fetcher=None):
    """The discontinued bikes of a brand that still serves its old product pages (Specialized: the Tarmac SL8
    builds, the Venge): every road and gravel page that no catalogue model has, read from the brand's own site,
    with the model year and price the page gives.

    The pages come from the Wayback listings (with cdx_folder) and, for a brand whose scraper has a
    sitemap_urls (Specialized), from the brand's own sitemap, which also lists the pages the Wayback Machine
    never saved. The bikes already in data/years/archived/<Brand>.json stay, so a run without the Wayback
    listings keeps the ones only those found. A page of a model we already have under another product number
    (the 2024 S-Works Tarmac SL8 next to the 2026 one) adds its model year to that model."""
    import importlib
    from .archive import URL_ID, url_name
    from .common import is_ebike
    module = importlib.import_module(f".{brand.lower()}", __package__)
    family, skip = (re.compile(r) for r in OLD_PAGES[brand])
    fetcher = fetcher or Fetcher(delay=1.0)
    out = os.path.join(ROOT, "data", "years", "archived", f"{brand}.json")
    try:
        with open(out, encoding="utf-8") as fh:
            bikes = json.load(fh)
    except (OSError, ValueError):
        bikes = []
    archived = {compact(b["name"]): b for b in bikes}
    conn = sqlite3.connect(db_path)
    seen = {compact(n) for (n,) in conn.execute("SELECT name FROM models WHERE brand = ?", (brand,))} - set(archived)
    # A product number in the URL that is also the bike's sku (Specialized) says which pages we already read;
    # other brands' URLs end in a model name or a year, so each URL stands for itself.
    by_id = brand == "Specialized"
    known = {str(b.get("sku")) for b in bikes} | set().union(*(b.get("skus") or [] for b in bikes)) if by_id else set()

    def key(url):
        m = by_id and re.search(URL_ID[brand], urlparse(url).path.rstrip("/"))
        return m.group(1) if m else url

    def wanted(url):
        name = url_name(brand, url)
        return name and family.match(name) and not skip.search(name) and name not in seen

    urls = {}
    for url in getattr(module, "sitemap_urls", lambda _f: [])(fetcher):  # every product number
        if wanted(url):
            urls.setdefault(key(url), url)
    named = {url_name(brand, u) for u in urls.values()}
    for _ts, url in sorted(read_cdx(cdx_folder, brand) if cdx_folder else [], reverse=True):
        if wanted(url) and url_name(brand, url) not in named:  # the newest copy of each URL name the sitemap lacks
            named.add(url_name(brand, url))
            urls.setdefault(key(url), url)
    sheets, today, added = {}, date.today().isoformat(), 0
    for pid, url in sorted(urls.items()):
        if pid in known:
            continue
        page = fetcher.get(url)
        try:
            bike = module.parse(page, url) if page else None
        except Exception as exc:
            log.warning("%s: %s", url, exc)
            continue
        if not bike or recognised(bike.get("specifications") or {}) < MIN_SPECS or is_ebike(bike["name"], bike["category"], url):
            continue
        bike["name"] = re.sub(r"\s+[–—]\s+", " - ", bike["name"])  # the catalogue writes "SL8 - SRAM RED AXS"
        slug = compact(bike["name"])
        if slug in seen:  # an old URL that now shows a current bike
            continue
        year = str(bike.get("model_year") or "")
        ours = archived.get(slug)
        if ours:  # another model year of a bike we have
            if by_id:
                ours.setdefault("skus", []).append(str(bike.get("sku")))
            if year.isdigit() and int(year) not in ours.setdefault("years", []):
                ours["years"] = sorted(ours["years"] + [int(year)])
            else:
                continue
        else:
            bike = dict(bike, image=save_photo(fetcher, brand, slug, None, bike.get("image_url"), rel=f"{brand}/archived/{slug}.jpg"),
                        years=[int(year)] if year.isdigit() else [])
            bikes.append(bike)
            archived[slug] = bike
            added += 1
        if year.isdigit():
            sheets.setdefault(archived[slug]["name"], {})[year] = {
                "captured": today, "url": url, "source": "site", "specs": bike["specifications"],
                "price": bike.get("price"), "colours": bike.get("color_names") or [],
                "image": bike.get("image") or save_photo(fetcher, brand, slug, year, bike.get("image_url"))}
        log.info("%s archived: %s %s%s", brand, bike["name"], year, "" if not ours else " (another year)")
    _save_archived(brand, bikes, sheets)
    log.info("%s archived: %d new models, %d in all", brand, added, len(bikes))
    return bikes


def collect(brand, models, fetcher, years):
    """{name: {year: entry}} for the model years the brand's site still has a page for."""
    module, pages, year_of, _delay = SITES[brand]
    found, today = {}, date.today().isoformat()
    for name, url in models:
        earlier = RENAMED.get(brand, {}).get(name)
        tries = [(y, u, None) for y, u in pages(url, years)]
        if earlier:  # after its own pages, the years only its earlier name has a page for
            tries += [(y, u, earlier[0]) for y, u in pages(earlier[1], years)]
        for year, page_url, sheet_name in tries:
            if sheet_name and str(year) in found.get(name, {}):
                continue
            page = fetcher.get(page_url)
            if not page or year_of(page) != year:
                continue
            try:
                bike = module.parse(page, page_url) or {}
            except Exception as exc:
                log.warning("%s: %s", page_url, exc)
                continue
            specs = bike.get("specifications") or {}
            if recognised(specs) < MIN_SPECS:
                continue
            found.setdefault(name, {})[str(year)] = {
                "captured": today, "url": page_url, "source": "site", "specs": specs,
                "price": bike.get("price"), "colours": bike.get("color_names") or [],
                "image": save_photo(fetcher, brand, compact(name), year, bike.get("image_url")),
                "colour_images": colour_photos(fetcher, brand, compact(name), year, dict(
                    zip(bike.get("color_names") or [], bike.get("color_image_urls") or [])))}
            if sheet_name:
                found[name][str(year)]["sheet_name"] = sheet_name
        log.info("%s %s: %s", brand, name, sorted(found.get(name, {})))
    return found


def run(brands, db_path, years, cdx_folder=None, names=None):
    """Read the model years of every catalogue model, or with `names` only of those models (the others'
    years stay as they are in the file)."""
    conn = sqlite3.connect(db_path)
    out_dir = os.path.join(ROOT, "data", "years", "site")
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for brand in brands:
        models = conn.execute("SELECT name, url FROM models WHERE brand = ? AND url != ''", (brand,)).fetchall()
        if names:
            models = [m for m in models if m[0] in names]
        if brand == "Trek":
            found = trek_collect(models, Fetcher(delay=1.0), years, trek_codes(cdx_folder))
        else:
            found = collect(brand, models, Fetcher(delays=SITES[brand][3]), years)
        path = os.path.join(out_dir, f"{brand}.json")
        # Years read in an earlier run stay unless this run read them again: a page that is
        # gone now (Trek drops a product's older years) doesn't make the year wrong.
        try:
            with open(path, encoding="utf-8") as fh:
                before = json.load(fh)
        except (OSError, ValueError):
            before = {"years": [], "models": {}}
        for name, entries in before["models"].items():
            for year, entry in entries.items():
                found.setdefault(name, {}).setdefault(year, entry)
        all_years = sorted(set(before["years"]) | set(years))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"checked_on": date.today().isoformat(), "years": all_years,
                       "source": f"{brand}'s own model-year pages", "models": found},
                      fh, ensure_ascii=False, indent=1, sort_keys=True)
        report[brand] = {y: sum(1 for v in found.values() if str(y) in v) for y in years}
    return report


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("brands", nargs="+")
    ap.add_argument("--db", default=os.path.join(ROOT, "instance", "bikecompare.sqlite3"))
    ap.add_argument("--first", type=int, default=FIRST_YEAR)
    ap.add_argument("--last", type=int, default=date.today().year)
    ap.add_argument("--cdx", help="folder with the Wayback Machine listings (for Trek's product numbers)")
    ap.add_argument("--colours", action="store_true", help="only add each colour's photo to the years already read")
    ap.add_argument("--angles", action="store_true", help="only add each colour's other angles to the years already read")
    ap.add_argument("--archived", action="store_true", help="add the discontinued lines (Trek, Giant: needs --cdx; Specialized also reads its sitemap)")
    ap.add_argument("--models", nargs="*", default=[], help="only these catalogue models (their names)")
    ap.add_argument("--pages", nargs="*", default=[],
                    help="Specialized --colours: the folders with the Wayback copies (wayback.py fetch), whose photo IDs come first")
    args = ap.parse_args()
    brands = [b for b in [*SITES, "Trek", *OLD_PAGES] if b.lower() in {a.lower() for a in args.brands}]
    if args.archived:
        for brand in brands:
            read = {"Trek": trek_archived, "Giant": giant_archived}.get(brand)
            bikes = read(args.cdx, args.db) if read else pages_archived(brand, args.cdx, args.db)  # Specialized: --cdx optional
            print(len(bikes), "discontinued", brand, "lines")
        raise SystemExit
    if args.angles:
        for brand in brands:
            add_angles(brand, names=args.models)
        raise SystemExit
    if args.colours and "Specialized" in brands:  # each colour's photo and other views, from its image server
        print(specialized_photos(args.pages))
        brands.remove("Specialized")
    if args.colours:
        for brand in brands:
            add_colour_photos(brand)
        raise SystemExit
    for brand, counts in run(brands, args.db, range(args.first, args.last + 1), args.cdx, args.models).items():
        print(brand, counts)
