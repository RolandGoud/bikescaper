"""Bikes the brands sell on another country's site but not on their Dutch one.

The Dutch site comes first: every adapter reads it, with its euro prices. Some bikes only show up on the brand's
other sites, though: a build Giant sells in France or Italy only (TCR Advanced 3, the KOM builds), the 2027 Domane
SL 4 Gen 5 that Trek lists in the US only, the Cannondale builds of its Asian and Latin American sites. People
import them and sell them second-hand here, so the catalogue needs their specs and photos to match an ad.

For each brand this lists the bikes on the other country sites, keeps those the Dutch site doesn't list and no
catalogue model or earlier year already covers (the same name, or for Trek the same line in the same or a later
generation), and reads the page of one of the countries that sells it: an English one when there is one, and
otherwise the page's labels translated through the same product's Dutch page. The price stays empty: a foreign
price in another currency (or the US's, before tax) is not the Dutch new price.

Writes data/years/countries/<Brand>.json, one bike per entry as an adapter returns it, plus "country" (the site it
was read from) and "source": "country". webapp/seed.py adds them after the catalogue, like the discontinued lines.

    python -m brand_scrapers.countries [trek giant cannondale] [--no-images] [--limit N]
"""
import argparse
import glob
import json
import os
import re
from datetime import date

from .common import ROOT, Fetcher, clean, is_ebike, log, normalize_specs, save_colour_images, save_image

OUT = os.path.join(ROOT, "data", "years", "countries")
FIRST_YEAR = 2018  # as the rest of the catalogue: nothing older


def compact(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower().replace("+", "plus").replace("é", "e"))


# data/years/ folders that hold prices only (tourbike: a German magazine's price lists), not catalogue models
NOT_MODELS = ("tourbike", "countries")


def model_files(brand):
    """The brand's scrapes and the files in data/years/ that hold its catalogue models and their year sheets."""
    return glob.glob(os.path.join(ROOT, "data", brand, "*.json")) + [
        p for p in glob.glob(os.path.join(ROOT, "data", "years", "**", f"{brand}.json"), recursive=True)
        if os.path.basename(os.path.dirname(p)) not in NOT_MODELS]


def known_names(brand):
    """compact() of every model name the catalogue has for a brand: its scrapes, and the year sheets and lines in
    data/years/ (a sheet_name too, the name a bike had in an earlier year)."""
    names = set()

    def add(name):
        if isinstance(name, str) and name:
            names.add(compact(name))

    for path in model_files(brand):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        for bike in data if isinstance(data, list) else []:
            if isinstance(bike, dict):
                add(bike.get("name"))
        models = data.get("models") if isinstance(data, dict) else None
        for name, years in (models or {}).items():
            add(name)
            for entry in (years or {}).values() if isinstance(years, dict) else []:
                if isinstance(entry, dict):
                    add(entry.get("sheet_name"))
    return names


def translate(fetcher, foreign_url, dutch_url, parse_pairs):
    """{foreign label: Dutch label} from one product both sites sell: the brands list a spec sheet's rows in the
    same order on every site."""
    foreign, dutch = fetcher.get(foreign_url) or "", fetcher.get(dutch_url) or ""
    a, b = parse_pairs(foreign), parse_pairs(dutch)
    if not a or len(a) != len(b):
        return {}
    return {clean(fa): clean(nb) for (fa, _), (nb, _) in zip(a, b)}


# --- Trek ----------------------------------------------------------------------------------------------------------

# Trek's sites and the language and currency its product API answers each in.
TREK_SITES = {"us": ("en_US", "USD"), "gb": ("en_GB", "GBP"), "de": ("de_DE", "EUR"), "be": ("nl_BE", "EUR"),
              "fr": ("fr_FR", "EUR"), "it": ("it_IT", "EUR"), "es": ("es_ES", "EUR"), "at": ("de_AT", "EUR"),
              "ch": ("de_CH", "CHF"), "dk": ("da_DK", "DKK"), "se": ("sv_SE", "SEK")}
TREK_SKIP = re.compile(r"frame ?set|frameset|\bcuadro\b|\bcadre\b|\btelaio\b|rahmen|\bramset\b|\bstel\b|\+|\brim\b|women|kids", re.I)  # framesets, e-bikes (Domane+), rim brakes


# Trek's English spec rows that normalize_specs doesn't know; rows already filled from another label stay as they are.
TREK_LABELS = {"Hub front": "Naaf voor", "Hub rear": "Naaf achter", "Brake rotor": "Remschijf",
               "Handlebar tape": "Stuurlint", "Skewer front": "As voorwiel", "Skewer rear": "As achterwiel",
               "Headset part (see also: Bearing)": "Balhoofdstel", "Rotor": "Remschijf", "Brake": "Rem",
               "Wheel front": "Wiel voor", "Wheel rear": "Wiel achter", "Spokes": "Spaken", "Tire": "Buitenband",
               "Crank": None, "Handlebar": None, "Stem": None}


def trek_specs(specs):
    out = {}
    for label, value in specs.items():
        key = TREK_LABELS.get(label, label)
        if key and key not in out and not (label in TREK_LABELS and key in specs):
            out[key] = value
    return out


def trek(fetcher, limit=None):
    from . import trek as adapter
    from .history import generation, line_of, trek_product, TREK_STOCK
    dutch = adapter.listed(fetcher)
    codes = {str(i["code"]) for i in dutch}
    known = known_names("Trek") | {compact(i["name"]) for i in dutch}
    lines = {}  # line -> the latest generation the catalogue has of it
    for name in known_names_raw("Trek") + [i["name"] for i in dutch]:
        lines[line_of(name)] = max(lines.get(line_of(name), -1), generation(name))
    found = {}
    for country, (lang, curr) in TREK_SITES.items():
        search = adapter.SEARCH.replace("/nl/", f"/{country}/").replace("lang=nl_NL", f"lang={lang}").replace(
            "curr=EUR", f"curr={curr}")
        for item in listed_at(fetcher, adapter, search):
            code, name = str(item["code"]), item["name"]
            if code in codes or code in found or compact(name) in known or TREK_SKIP.search(name) \
                    or TREK_STOCK.search(name) or is_ebike(name) or (item["model_year"] or 0) < FIRST_YEAR:
                continue
            # an earlier year of a line we have (Checkpoint SL 5, 2019): the year sheets' job, not a new model
            if generation(name) <= lines.get(line_of(name), -1):
                continue
            found[code] = (country, lang, curr, item)
    bikes = []
    for code, (country, lang, curr, item) in list(found.items())[:limit]:
        product = trek_product(fetcher, code)
        if not product or not product["specs"]:  # the Dutch API has no sheet for a bike it doesn't sell
            product = trek_product(fetcher, code, country=country, lang=lang, curr=curr)
            if product:
                product["specs"] = trek_specs(product["specs"])
        if not product or not product["specs"]:
            log.warning("Trek: no spec sheet for %s %s on the %s site", code, item["name"], country)
            continue
        colours = product["colours"]
        bikes.append({
            "name": item["name"], "brand": "Trek", "url": product["url"], "sku": code, "price": None,
            "category": product["category"], "model_year": item["model_year"], "specifications": product["specs"],
            "color_names": colours, "image_url": product["image_url"],
            "color_image_urls": [product["colour_image_urls"].get(c) for c in colours], "country": country})
        log.info("Trek: %s %s from the %s site", item["name"], item["model_year"], country)
    return bikes


def listed_at(fetcher, adapter, search):
    found, page = [], 0
    while True:
        try:
            data = fetcher.session.get(search.format(page=page), headers={"Accept": "application/json"},
                                       timeout=60).json()
        except (ValueError, OSError) as exc:
            log.warning("Trek search %s: %s", search[:60], exc)
            data = {}
        for p in data.get("products") or []:
            found.append({"code": p.get("code"), "name": (p.get("name") or "").strip(),
                          "model_year": adapter.model_year(p.get("marketingModelYear"))})
        page += 1
        if page >= ((data.get("pagination") or {}).get("totalPages") or 0):
            return [p for p in found if p["code"] and p["name"]]


def known_names_raw(brand):
    """The catalogue's names for a brand as written (for Trek's line and generation)."""
    return list(known_years(brand))


def known_years(brand):
    """{the catalogue's names for a brand, as written: {model years it has for it}}."""
    out = {}
    for path in model_files(brand):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, list):
            for b in data:
                if isinstance(b, dict) and isinstance(b.get("name"), str):
                    years = out.setdefault(b["name"], set())
                    years |= {y for y in [b.get("model_year"), *(b.get("years") or [])] if isinstance(y, int)}
        elif isinstance(data, dict):
            for name, entries in (data.get("models") or {}).items():
                out.setdefault(name, set()).update(int(y) for y in (entries or {}) if str(y).isdigit())
    return out


# --- Giant ---------------------------------------------------------------------------------------------------------

GIANT_SITEMAP = "https://static.giant-bicycles.com/sitemaps/sitemap-giant-{}.xml"
# English sites first: their labels need no translating.
GIANT_SITES = ["en-gb", "en-au", "en-us", "en-ca", "en-ie", "fr-fr", "de-de", "it-it", "es-es", "sv-se", "da-dk",
               "pl-pl", "nl-be", "de-ch", "fr-be"]
GIANT_PAGE = re.compile(r"https://www\.giant-bicycles\.com/([a-z]{2})/([a-z0-9-]+?)(?:-(20\d\d))?$")
GIANT_PARTS = re.compile(r"frameset|frame-set|testing|registration|sale|spacer|clamp|bottle|cage|holder|mount|stem|"
                         r"vorbau|flaschenhalter|fender|seatpost|seat-post|battery|extension", re.I)
# The ways Giant's sites write one build: "TCR Advanced SL 0 (Dura-Ace)", "...SL 0 DA", "...SL 0-Dura-Ace".
GIANT_WORDS = [(r"duraace", "da"), (r"procompact", "pc"), (r"kingofmountains?", "kom"), (r"ultegra", "ut")]
# The bike type some sites put before the name: "Vélo Route TCR Advanced 3", "Bici da corsa ...", "Rennrad ...".
GIANT_TYPE = re.compile(r"^(?:v[ée]lo (?:de )?(?:route|gravel|course|cyclocross|triathlon|clm)|bici(?:cletta)? da "
                        r"(?:corsa|strada|gravel)|rennrad|gravelbike|bicicleta de (?:carretera|gravel)|landsvägscykel"
                        r"|racercykel|rower szosowy)\s+", re.I)


def giant_name(name):
    """'Vélo Route TCR Advanced 3' -> 'TCR Advanced 3'; 'TCR Advanced 1 (KOM)' -> 'TCR Advanced 1 KOM'."""
    name = GIANT_TYPE.sub("", name.strip())
    return re.sub(r"\s*\(([^()]+)\)$", r" \1", name)


def giant_key(name):
    key = compact(name)
    for pattern, short in GIANT_WORDS:
        key = re.sub(pattern, short, key)
    return key


def giant_pages(fetcher, site):
    """{(slug, year)} -> url of the road and gravel bike pages in one site's sitemap."""
    from .giant import FAMILIES
    pages = {}
    for url in re.findall(r"<loc>([^<]+)</loc>", fetcher.get(GIANT_SITEMAP.format(site)) or ""):
        m = GIANT_PAGE.match(url)
        if m and m.group(2).startswith(FAMILIES) and not GIANT_PARTS.search(m.group(2)) \
                and not is_ebike(m.group(2).replace("-", " ")):
            pages[(m.group(2), m.group(3))] = url
    return pages


def giant(fetcher, limit=None):
    from . import giant as adapter
    fetcher.delays.update(adapter.HOST_DELAY)
    dutch = giant_pages(fetcher, "nl-nl")
    dutch_slugs = {slug for slug, _year in dutch}
    years = known_years("Giant")
    known = {giant_key(n) for n in years}
    # the shifters of the catalogue's bikes per name and year: France's "TCR Advanced SL 1 Di2" (2025) is the
    # Dutch site's "TCR Advanced SL 1" of that year, with Ultegra Di2; Germany's "Defy Advanced Pro 0 AXS" (2027)
    # is not the Dutch "Defy Advanced Pro 0", with Ultegra Di2
    shifters = known_shifters("Giant")
    # the newest page of each bike the Dutch site doesn't have, and the first site (English first) that has it
    wanted = {}
    for site in GIANT_SITES:
        for (slug, year), url in giant_pages(fetcher, site).items():
            if slug in dutch_slugs or (year and int(year) < FIRST_YEAR):
                continue
            if giant_key(slug) in known:
                continue
            have = wanted.get(slug)
            if not have or int(year or 0) > int(have[1] or 0):
                wanted[slug] = (site, year, url)
    labels = {}  # site -> {its label: the Dutch one}
    bikes = {}  # key -> bike: one per bike however many slugs the sites gave it, the newest year
    for slug, (site, year, url) in sorted(wanted.items())[:limit]:
        page = fetcher.get(url)
        bike = adapter.parse(page, url) if page else None
        if not bike:
            log.warning("Giant: no product data in %s", url)
            continue
        if not site.startswith("en-"):
            if site not in labels:
                labels[site] = giant_labels(fetcher, site, dutch)
            pairs = re.findall(r"<div class=label>(.*?)</div><div class=value>(.*?)</div>", page, re.S)
            bike["specifications"] = normalize_specs([(labels[site].get(clean(k), k), v) for k, v in pairs])
        bike["name"] = giant_name(bike["name"])
        key = giant_key(bike["name"])
        if key in known or is_ebike(bike["name"], bike["category"]):
            continue
        group = re.search(r"(di2|axs)$", key)
        if group and group.group(1) in shifters.get((key[:group.start()], bike["model_year"]), ""):
            log.info("Giant: %s %s is the Dutch site's bike of that year", bike["name"], bike["model_year"])
            continue
        if not bike["sizes"] or "Frame" not in bike["specifications"]:  # parts, and pages without a spec sheet
            log.info("Giant: %s has no spec sheet, left out", url)
            continue
        if key in bikes and (bikes[key]["model_year"] or 0) >= (bike["model_year"] or 0):
            continue
        bike.update(price=None, country=site)
        bike["category"] = adapter.category_of("", url)  # the page's label is in its own language
        bikes[key] = bike
        log.info("Giant: %s %s from the %s site", bike["name"], bike["model_year"], site)
    return list(bikes.values())


def known_shifters(brand):
    """{(giant_key(name), model year): its shifter, lowercase and compact} from the scrapes and year sheets."""
    out = {}
    for path in model_files(brand):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        rows = [(b.get("name"), b.get("model_year"), b.get("specifications")) for b in data if isinstance(b, dict)] \
            if isinstance(data, list) else \
            [(n, int(y), e.get("specs")) for n, es in ((data.get("models") or {}).items() if isinstance(data, dict) else [])
             for y, e in (es or {}).items() if str(y).isdigit() and isinstance(e, dict)]
        for name, year, specs in rows:
            if isinstance(name, str) and year and isinstance(specs, dict) and specs.get("Shifter"):
                out[(giant_key(name), int(year))] = out.get((giant_key(name), int(year)), "") + compact(specs["Shifter"])
    return out


def giant_labels(fetcher, site, dutch):
    """Giant's labels on one site in Dutch, read off a bike both sites sell this year."""
    pages = giant_pages(fetcher, site)
    pairs = lambda page: re.findall(r"<div class=label>(.*?)</div><div class=value>(.*?)</div>", page, re.S)
    for (slug, year), url in pages.items():
        if (slug, year) in dutch and year:
            found = translate(fetcher, url, dutch[(slug, year)], pairs)
            if found:
                return found
    return {}


# --- Cannondale ----------------------------------------------------------------------------------------------------

CANNONDALE_PAGE = re.compile(r"https://www\.cannondale\.com/([a-z]{2}-[a-z]{2})/bikes/road/([a-z-]+/[a-z0-9-]+/[a-z0-9-]+)$")
CANNONDALE_SKIP = re.compile(r"frameset|stvzo|-smu$", re.I)  # framesets, Germany's road-legal builds with lights


def cannondale(fetcher, limit=None):
    from . import cannondale as adapter
    by_site = {}
    for url in adapter.sitemap_urls(fetcher):
        m = CANNONDALE_PAGE.match(url)
        if m:
            by_site.setdefault(m.group(2), {})[m.group(1)] = url
    known = known_names("Cannondale")
    bikes, seen = [], set()
    for path, sites in sorted(by_site.items()):
        if "nl-nl" in sites or CANNONDALE_SKIP.search(path):
            continue
        site = next((s for s in sorted(sites) if s.startswith("en-")), None)
        if not site:
            log.info("Cannondale: %s only on sites without English (%s), left out", path, ", ".join(sorted(sites)))
            continue
        if limit is not None and len(bikes) >= limit:
            break
        url = sites[site]
        page = fetcher.get(url)
        bike = adapter.parse(page, url) if page else None
        if not bike or not bike["specifications"]:
            log.warning("Cannondale: no product data in %s", url)
            continue
        key = compact(bike["name"])
        if key in known or key in seen or is_ebike(bike["name"], bike["category"], url) \
                or (bike["model_year"] or FIRST_YEAR) < FIRST_YEAR:
            continue
        seen.add(key)
        bike.update(price=None, country=site)
        bikes.append(bike)
        log.info("Cannondale: %s %s from the %s site", bike["name"], bike["model_year"], site)
    return bikes


BRANDS = {"Trek": trek, "Giant": giant, "Cannondale": cannondale}

# English rows the Dutch pages label otherwise; after these, rows the site has no label for are left out (a model
# name, the colours and sizes the bike has its own fields for, a fender or rack).
LABELS = {"Front Tire": "Buitenband", "Rear Cogs": "Cassette", "Max Tyre Clearance": "Maximale bandenmaat",
          "Dégagement max des pneus": "Maximale bandenmaat", "Extra 1": "Extra's"}


def tidy_specs(specs):
    from webapp.reference import SPEC_LABELS
    out = {}
    for label, value in specs.items():
        label = LABELS.get(label, label)
        if label == "Gewicht":  # the number and size only: other sites follow it with a paragraph of footnote
            from webapp.checks import weight_short
            value = weight_short(value)
        if value and label in SPEC_LABELS and label not in out:
            out[label] = value
    return out


def run(brands, limit=None, images=True):
    fetcher = Fetcher()
    os.makedirs(OUT, exist_ok=True)
    report = {}
    for brand in brands:
        bikes = BRANDS[brand](fetcher, limit=limit)
        for bike in bikes:
            bike["specifications"] = tidy_specs(bike["specifications"])
            bike["source"] = "country"
            bike["checked_on"] = date.today().isoformat()
            if images:
                bike["image"] = save_image(fetcher, brand, bike["name"], bike.get("image_url"))
                save_colour_images(fetcher, bike)
        bikes.sort(key=lambda b: (b.get("category") or "", b["name"]))
        with open(os.path.join(OUT, f"{brand}.json"), "w", encoding="utf-8") as fh:
            json.dump(bikes, fh, ensure_ascii=False, indent=1)
        report[brand] = len(bikes)
    return report


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("brands", nargs="*", help=", ".join(BRANDS) + " (default: all)")
    ap.add_argument("--limit", type=int, help="bikes per brand, for testing")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    brands = [b for b in BRANDS if not args.brands or b.lower() in {a.lower() for a in args.brands}]
    for brand, count in run(brands, args.limit, not args.no_images).items():
        print(f"{brand}: {count} bikes only on other country sites")


if __name__ == "__main__":
    main()
