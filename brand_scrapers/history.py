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

Writes data/years/site/<Brand>.json ({"checked_on", "years", "source", "models": {name: {year:
{captured, url, source, specs, price, image}}}}), which webapp/seed.py merges over
data/years/<Brand>.json, and the photo to images/<Brand>/years/<slug>_<year>_site.jpg.
"""
import argparse
import io
import json
import os
import re
import sqlite3
from datetime import date

from . import giant
from .archive import FIRST_YEAR, MIN_SPECS, compact, read_cdx, recognised
from .common import ROOT, Fetcher, frame, log, normalize_specs


def giant_pages(url, years):
    base = re.sub(r"-20\d\d$", "", url.rstrip("/"))
    for year in years:
        yield year, f"{base}-{year}"


def giant_year(page):
    # A year Giant never sold this model under this URL serves the newest one, so go by the title.
    m = re.search(r"<title>[^<]*\((20\d\d)\)", page)
    return int(m.group(1)) if m else None


# brand: (parser module, model URL -> [(year, page URL)], page -> the model year it shows, host delay)
SITES = {
    "Giant": (giant, giant_pages, giant_year, giant.HOST_DELAY),
}


def save_photo(fetcher, brand, slug, year, url, width=1000):
    import html
    url = html.unescape((url or "").strip("\"'"))  # Giant's 2017 pages quote the og:image URL
    if not url:
        return None
    rel = f"{brand}/years/{slug}_{year}_site.jpg"
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
        img = frame(img.convert("RGB"))
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
    primary = next((i for i in images if i.endswith("_Primary")), images[0] if images else None)
    return {"code": code, "name": full.get("name") or "", "years": trek_years(full.get("modelYearIntroAndCurrent")),
            "url": "https://www.trekbikes.com/nl/nl_NL" + (full.get("url") or f"/p/{code}/"),
            "sheet_years": full.get("modelYearIntroAndCurrent"), "specs": normalize_specs(pairs),
            "image_url": f"https://media.trekbikes.com/image/upload/f_png,w_1200/{primary}" if primary else None}


def line_of(name):
    """A model line across generations: "Domane AL 2 Gen 4", "Domane AL 2 gen 3" and "Domane AL 2 Disc" -> domaneal2."""
    return compact(re.sub(r"\b(?:gen\s*\d+|disc)\b", " ", name.lower()))


def generation(name):
    m = re.search(r"\bgen\s*(\d+)", name, re.I)
    return int(m.group(1)) if m else 0


def trek_collect(models, fetcher, years, codes):
    products = [p for p in (trek_product(fetcher, c) for c in codes) if p and p["years"]
                and recognised(p["specs"]) >= MIN_SPECS and not TREK_SKIP.search(p["name"])]
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
                        "specs": p["specs"], "price": None,
                        "image": save_photo(fetcher, "Trek", compact(name), year, p["image_url"])}
        log.info("Trek %s: %s", name, sorted(found.get(name, {})))
    return found


def collect(brand, models, fetcher, years):
    """{name: {year: entry}} for the model years the brand's site still has a page for."""
    module, pages, year_of, _delay = SITES[brand]
    found, today = {}, date.today().isoformat()
    for name, url in models:
        for year, page_url in pages(url, years):
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
                "price": bike.get("price"),
                "image": save_photo(fetcher, brand, compact(name), year, bike.get("image_url"))}
        log.info("%s %s: %s", brand, name, sorted(found.get(name, {})))
    return found


def run(brands, db_path, years, cdx_folder=None):
    conn = sqlite3.connect(db_path)
    out_dir = os.path.join(ROOT, "data", "years", "site")
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for brand in brands:
        models = conn.execute("SELECT name, url FROM models WHERE brand = ? AND url != ''", (brand,)).fetchall()
        if brand == "Trek":
            found = trek_collect(models, Fetcher(delay=1.0), years, trek_codes(cdx_folder))
        else:
            found = collect(brand, models, Fetcher(delays=SITES[brand][3]), years)
        path = os.path.join(out_dir, f"{brand}.json")
        # Years read in an earlier run stay unless this run read them again.
        try:
            with open(path, encoding="utf-8") as fh:
                before = json.load(fh)
        except (OSError, ValueError):
            before = {"years": [], "models": {}}
        for name, entries in before["models"].items():
            for year, entry in entries.items():
                if int(year) not in years:
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
    args = ap.parse_args()
    brands = [b for b in [*SITES, "Trek"] if b.lower() in {a.lower() for a in args.brands}]
    for brand, counts in run(brands, args.db, range(args.first, args.last + 1), args.cdx).items():
        print(brand, counts)
