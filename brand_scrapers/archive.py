"""Spec sheets from earlier years, from Wayback Machine copies of the brands' NL sites.

The Wayback Machine can't be reached from every network, so this runs in three steps:

  1. On a PC that can reach it: `python brand_scrapers/wayback.py cdx` lists the archived pages per brand.
  2. `python -m brand_scrapers.archive match <cdx dir> wanted.json` picks, per catalogue model and
     year, the archived copy of the model's page closest to spring (15 April); `python brand_scrapers/wayback.py fetch
     wanted.json` downloads those copies.
  3. `python -m brand_scrapers.archive parse <pages dir>` reads the spec sheets with each brand's own
     parser and writes data/years/<Brand>.json, which webapp/seed.py loads.
"""
import gzip
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urlparse

from .common import ROOT

BRANDS = ["Trek", "Canyon", "Specialized", "Giant", "Cannondale", "Cube", "Factor"]
FIRST_YEAR = 2020
SPRING = (4, 15)  # the copy closest to this date stands for its year
# The part of a product URL that names the model, per brand.
URL_NAME = {
    "Trek": r"/([^/]+)/p/\d+$",
    "Specialized": r"/([^/]+)/p/\d+$",
    "Canyon": r"/([^/]+)/\d+\.html$",
    "Giant": r"^/nl/([^/]+)$",
    "Cannondale": r"^/nl-nl/bikes/(?:[^/]+/)+([^/]+?)(?:/\d{4})?$",
    "Cube": r"^/nl(?:-nl)?/(?:.*/)?cube-([^/]+)(?:/\d+)?$",  # not the German or English pages under cube.eu/nl-de/
    "Factor": r"/(?:bike-builder|bikes)/([^/]+)$",
}
SKIP = re.compile(r"/(?:outlet|outlet-bikes|kids|e-bikes|electric|electric-bikes|elektrische-fietsen|gear|equipment|"
                  r"fietsuitrusting|onderdelen|kleding|apparel)/")


def compact(text):
    text = text.lower().replace("+", "plus").replace("é", "e")
    return re.sub(r"[^a-z0-9]", "", text)


def url_name(brand, url):
    """The model name part of an archived product URL, compacted, or None for other pages."""
    path = urlparse(url).path.rstrip("/")
    if SKIP.search(path + "/"):
        return None
    m = re.search(URL_NAME[brand], path)
    if not m:
        return None
    name = m.group(1)
    if brand == "Giant":
        name = re.sub(r"-20\d\d$", "", name)
    if brand == "Specialized":
        name = re.sub(r"^(?:mens|womens)-", "", name)
    if brand == "Cannondale":
        name = re.sub(r"-(?:smu|c\d{5}u)$", "", name)
    return compact(name)


# The product number at the end of a product URL, which some brands keep across model years.
URL_ID = {"Trek": r"/p/(\d+)$", "Specialized": r"/p/(\d+)$", "Canyon": r"/(\d+)\.html$", "Cube": r"/(\d+)$"}


def model_year(brand, url):
    """The model year a product URL names (Giant's /nl/tcr-advanced-2-2025), or None."""
    m = brand == "Giant" and re.search(r"-(20\d\d)$", urlparse(url).path.rstrip("/"))
    return int(m.group(1)) if m else None


def url_id(brand, url):
    m = brand in URL_ID and re.search(URL_ID[brand], urlparse(url).path.rstrip("/"))
    return m.group(1) if m else None


def catalogue(db_path):
    """{brand: {name: product number}} for every model in the site database."""
    conn = sqlite3.connect(db_path)
    return {brand: dict(conn.execute("SELECT name, sku FROM models WHERE brand = ?", (brand,))) for brand in BRANDS}


def read_cdx(folder, brand):
    """{(timestamp, url)} from every <folder>/**/<brand>.txt (the CDX lists can come in several runs)."""
    rows = set()
    for dirpath, _dirs, files in os.walk(folder):
        if f"{brand}.txt" in files:
            with open(os.path.join(dirpath, f"{brand}.txt"), encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) == 2 and parts[0][:4].isdigit():
                        rows.add((parts[0], parts[1].split("?")[0].split("#")[0]))
    return rows


def match_model(brand, key, names):
    """The catalogue name this URL is about: an exact match, else (Cube adds the colour) the longest prefix."""
    if key in names:
        return names[key]
    if brand == "Cube":
        best = max((k for k in names if key.startswith(k)), key=len, default=None)
        return names.get(best)
    return None


def match(cdx_folder, out_path, db_path):
    wanted, report = [], {}
    for brand, names in catalogue(db_path).items():
        keys = {compact(n): n for n in names}
        ids = {sku: n for n, sku in names.items() if sku}
        captures = defaultdict(list)  # (name, year) -> [(timestamp, url)]
        for ts, url in read_cdx(cdx_folder, brand):
            key = url_name(brand, url)
            if key is None:
                continue
            name = match_model(brand, key, keys) or ids.get(url_id(brand, url))
            year = model_year(brand, url) or int(ts[:4])  # a 2025 page captured in 2026 is still the 2025 sheet
            if name and year >= FIRST_YEAR:
                captures[(name, year)].append((ts, url))
        for (name, year), caps in sorted(captures.items()):
            spring = datetime(year, *SPRING)
            caps.sort(key=lambda c: abs((datetime.strptime(c[0][:8], "%Y%m%d") - spring).days))
            wanted.append({"brand": brand, "name": name, "slug": compact(name), "year": year,
                           "ts": caps[0][0], "url": caps[0][1],
                           "alternatives": [{"ts": t, "url": u} for t, u in caps[1:4]]})
        found = {name for name, _y in captures}
        report[brand] = {"models": len(names), "with_any_year": len(found),
                         "per_year": {y: sum(1 for _n, yy in captures if yy == y) for y in range(FIRST_YEAR, date.today().year + 1)}}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(wanted, fh, ensure_ascii=False, indent=1)
    return wanted, report


# ---------------------------------------------------------------- reading the archived pages

# Menu and footer headings that some layouts also mark up as dt/dd or name/desc pairs.
NAV_LABELS = {"support", "ondersteuning", "catalogus", "over cannondale", "company", "dealer", "shop", "winkel",
              "service", "contact", "klantenservice", "bedrijf", "over ons"}

MIN_SPECS = 6  # fewer recognised parts than this is a page without a real spec list


def _generic_pairs(page):
    """(label, value) pairs from definition lists, two-cell table rows and Cannondale's name/desc items."""
    from bs4 import BeautifulSoup
    from .common import clean
    text = lambda tag: clean(str(tag))  # get_text() skips text inside <template>, where Trek keeps its specs
    soup = BeautifulSoup(page, "lxml")
    pairs = []
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            pairs.append((text(dt), text(dd)))
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            pairs.append((text(cells[0]), text(cells[1])))
    for name in soup.select("strong.name"):
        desc = name.find_next_sibling(class_="desc")
        if desc:
            pairs.append((text(name), text(desc)))
    # Trek marks size-dependent parts with a star ("*Crankstel").
    pairs = [(label, value) for label, value in pairs if clean(label).lower() not in NAV_LABELS]
    # A value without a letter is a geometry row (crank length 165,0, stack 529), not a part.
    return [(label.lstrip("*").strip(), value) for label, value in pairs
            if label.strip() and re.search(r"[^\W\d_]", value)]


def _specialized_pairs(page):
    from . import specialized
    text = specialized.rsc_payload(page)
    pairs = []
    for m in re.finditer(r'\{"headline":"[^"]*","name":"[^"]*","specs":\[', text):
        group = specialized.enclosing_object(text, m.start() + 1)
        pairs += [(s.get("name") or s.get("code"), s.get("description")) for s in (group or {}).get("specs", [])]
    if not pairs:  # the older Next.js pages keep the specs in __NEXT_DATA__
        for m in re.finditer(r'"(?:label|name)":"([^"]{2,40})","(?:value|description)":"([^"]*)"', page):
            pairs.append((m.group(1), m.group(2)))
    return pairs


def _canyon_specs(page):
    import logging
    from bs4 import BeautifulSoup
    from canyon_bikes_scraper import CanyonBikeScraper
    logging.disable(logging.INFO)
    scraper = _canyon_specs.scraper = getattr(_canyon_specs, "scraper", None) or CanyonBikeScraper()
    from webapp.reference import SPEC_LABELS
    specs = scraper.extract_canyon_specifications(BeautifulSoup(page, "lxml")) or {}
    # Its keys are mostly the shared ones with "_" for spaces ("Bottom_bracket"); use whichever SPEC_LABELS knows.
    return {(k if k in SPEC_LABELS else k.replace("_", " ")): v for k, v in specs.items() if v}


def read_specs(brand, page, url):
    """(specs, price) from an archived product page, specs as the shared keys of brand_scrapers.common."""
    import importlib
    from .common import normalize_specs, parse_price
    specs, price = {}, None
    if brand in ("Giant", "Cube", "Cannondale"):
        try:
            bike = importlib.import_module(f"brand_scrapers.{brand.lower()}").parse(page, url) or {}
        except Exception:  # an older page layout: fall back to the generic reader below
            bike = {}
        specs, price = bike.get("specifications") or {}, bike.get("price")
    if brand == "Canyon":
        specs = _canyon_specs(page)
    elif brand == "Specialized":
        specs = normalize_specs(_specialized_pairs(page))
    if len(specs) < MIN_SPECS:
        specs = normalize_specs(_generic_pairs(page)) or specs
    # Values without a letter (crank length 165,0, stack 529) mean the reader took a geometry table
    # for the spec list. A few are dropped; more and the whole sheet is suspect, so it counts as unreadable.
    # Trek lists a part per size group ("Maat: 44, 49 Bontrager Comp"); keep the part, the first group's.
    specs = {k: re.sub(r"^Maat: (?:(?:\d{2}|[23]?X{0,2}[SML]|ML|XL{1,2})\b,? ?)+", "", str(v)).strip() or v
             for k, v in specs.items()}
    specs = {k: v for k, v in specs.items() if not re.fullmatch(r"[23]?X{0,2}[SML]|ML|XL{1,2}|\d{2}", k)}  # size-table rows
    numeric = [k for k, v in specs.items() if not re.search(r"[^\W\d_]", str(v))]
    specs = {} if len(numeric) >= 3 else {k: v for k, v in specs.items() if k not in numeric}
    if price is None:
        m = (re.search(r'"price"\s*:\s*"?([\d.,]+)', page)
             or re.search(r'<meta[^>]+(?:product:price:amount|itemprop="price")[^>]+content="([\d.,]+)"', page))
        price = parse_price(m.group(1)) if m else None
    return specs, (price if price and 100 <= price <= 30000 else None)


def recognised(specs):
    from webapp.reference import SPEC_LABELS
    return sum(1 for k in specs if k in SPEC_LABELS)


def parse(pages_folder, years_folder=None):
    """Read every <brand>/<slug>/<year>.html.gz under pages_folder into data/years/<Brand>.json.

    A photo saved next to a page (<year>.jpg) is copied to images/<Brand>/years/.
    """
    import shutil
    years_folder = years_folder or os.path.join(ROOT, "data", "years")
    os.makedirs(years_folder, exist_ok=True)
    report = {}
    for brand in BRANDS:
        models, counts = {}, defaultdict(int)
        for path in sorted(glob_pages(pages_folder, brand)):
            with open(path[:-len(".html.gz")] + ".json", encoding="utf-8") as fh:
                meta = json.load(fh)
            with gzip.open(path) as fh:
                page = fh.read().decode("utf-8", "replace")
            if brand == "Cube" and not re.search(r"cube\.eu/nl(?:-nl)?/", meta["url"]):
                continue  # the German and English shopfronts under cube.eu/nl-de/ and /nl-en/
            year = model_year(brand, meta["url"]) or meta["year"]
            if year < FIRST_YEAR or models.get(meta["name"], {}).get(str(year), {}).get("specs"):
                continue  # two copies of the same model year: keep the readable one
            specs, price = read_specs(brand, page, meta["url"])
            ts = str(meta["ts"])
            entry = {"captured": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", "ts": ts, "url": meta["url"]}
            if recognised(specs) >= MIN_SPECS:
                entry.update(specs=specs, price=price)
                counts["specs"] += 1
            else:
                entry["unreadable"] = True
                counts["unreadable"] += 1
            photo = path[:-len(".html.gz")] + ".jpg"
            if os.path.exists(photo):
                rel = f"{brand}/years/{meta['slug']}_{year}.jpg"
                os.makedirs(os.path.join(ROOT, "images", brand, "years"), exist_ok=True)
                shutil.copyfile(photo, os.path.join(ROOT, "images", rel))
                entry["image"] = rel
                counts["photos"] += 1
            models.setdefault(meta["name"], {})[str(year)] = entry
        out = {"checked_on": date.today().isoformat(), "years": list(range(FIRST_YEAR, date.today().year + 1)),
               "source": "Wayback Machine copies of the brand's NL site", "models": models}
        with open(os.path.join(years_folder, f"{brand}.json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        report[brand] = dict(counts)
    return report


def glob_pages(folder, brand):
    for dirpath, _dirs, files in os.walk(folder):
        if os.path.basename(os.path.dirname(dirpath)) == brand:
            yield from (os.path.join(dirpath, f) for f in files if f.endswith(".html.gz"))


if __name__ == "__main__":
    if sys.argv[1] == "match":
        db = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("BIKECOMPARE_DB", os.path.join(ROOT, "instance", "bikecompare.sqlite3"))
        wanted, report = match(sys.argv[2], sys.argv[3], db)
        print(f"{len(wanted)} pages to fetch")
        for brand, r in report.items():
            print(brand, r)
    elif sys.argv[1] == "parse":
        for brand, counts in parse(sys.argv[2]).items():
            print(brand, counts)
