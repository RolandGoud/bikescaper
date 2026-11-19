"""Scott's earlier model years, from Wayback Machine copies of scott-sports.com's product pages.

Scott is in none of the shops' archives we read (Mantel, Rutland, Sigma) as fully as on its own site, and its live
site only keeps the current season. The Wayback Machine has its product pages from 2018 on, on the Dutch, British,
American and global English catalogues. Many copies are Imperva's bot check instead of the page (a few hundred
bytes), so per page and year the largest copy is read.

Pages before 2023 list the specs as <h4 class="specs-list__title"> rows; later ones carry the schema.org
ProductGroup the live adapter (scott.py) reads. Older pages don't state the model year, but each bike's article
number does in effect: Scott numbers a season's bikes in one series (265xxx, 274xxx, 280xxx, 286xxx...), see SERIES.
Mantel's pages of Scott's bikes (mantel-wayback/build-json.pl did the other brands') go into data/years/mantel/raw.json.

The archive refuses cloud machines, so this runs on a PC, in three steps, then brandsites.py (and mantel.py) turn the
result into year sheets and retired lines:

    python -m brand_scrapers.scott_archive cdx <work dir>      # the archived copies
    python -m brand_scrapers.scott_archive fetch <work dir>    # the best copy per page and year (resumable)
    python -m brand_scrapers.scott_archive build <work dir>    # adds Scott to data/years/brandsites/raw.json
    python -m brand_scrapers.scott_archive photos <work dir>   # their photos: live, else the archive's copy
    python -m brand_scrapers.brandsites --brand Scott
    python -m brand_scrapers.scott_archive mantel <work dir>         # Mantel's copies of its Scott pages
    python -m brand_scrapers.scott_archive mantel-build <work dir>   # adds Scott to data/years/mantel/raw.json
    python -m brand_scrapers.mantel --brand Scott
"""
import argparse
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from .common import ROOT, clean, is_ebike, log

# English catalogues first: their labels need no translating. The others' copies are read where no English one is
# left of a page that year (Germany's 2019 Addict RC, Belgium's Foil Disc), their labels translated (LABELS).
SITES = ["nl/en", "gb/en", "us/en", "global/en", "be/en", "dk/en", "se/en", "ca/en", "au/en", "nz/en", "za/en", "in/en",
         "at/de", "de/de", "ch/de", "be/fr", "fr/fr", "ch/fr", "ca/fr", "it/it", "ch/it", "es/es", "mx/es", "pt/pt",
         "cz/cs", "pl/pl"]
FIRST_YEAR = 2018
UA = {"User-Agent": "bikescaper-archive/1.0 (personal research)"}
ROAD = re.compile(r"(?:^|-)(?:addict|foil|speedster|plasma)(?:-|$)")
NOT_BIKES = re.compile(r"(?:^|-)(?:eride|e|hanger|dropout|seatpost|stem|handlebar|bar|clamp|bag|bottle|kit|plug|"
                       r"protector|cover|spacer|cable|guard|mount|light|tube|box|drink|bearing|part|parts|axle|"
                       r"replacement|tee|shirt|jersey|helmet|shoe|glove|bib|short|suit|jr|junior|kids|anzug|tuta|mono|combinaison|body|"
                       r"mostek|cockpit|syncros)(?:-|$)")
# The colours older pages put in a page's name and URL: "SCOTT Addict 10 Bike blue", ".../scott-addict-10-bike-blue".
COLOUR_WORDS = ("white|black|blue|red|orange|green|grey|gray|silver|yellow|purple|pink|brown|beige|bronze|gold|"
                "carbon|onyx|marine|pearl|stellar|prism|komodo|dark|light|deep|raw|metallic|matt|gloss|blk|oyx|carb|"
                "grn|pr|kom|dk|peach|teal|mint|petrol|olive|cherry|lime|sand|navy")
TRAILING_COLOUR = re.compile(r"(?:\s+(?:%s)\b)+$" % COLOUR_WORDS, re.I)


# Scott's spec labels on its German, French, Italian and Czech pages, as its English pages write them. Rows not listed
# keep their label, which brandsites.py then drops unless it knows it (lbs weights, the max. system weight).
LABELS = {
    # German
    "Rahmen": "Frame", "Gabel": "Fork", "Schaltwerk": "Rear Derailleur", "Umwerfer": "Front Derailleur",
    "Schalthebel": "Shifters", "Kurbelsatz": "Crankset", "Innenlager": "BB-Set", "Kette": "Chain",
    "Kassette": "Cassette", "Bremsen": "Brakes", "Bremsscheibe": "Rotor", "Lenker": "Handlebar", "Vorbau": "H'stem",
    "Sattelstütze": "Seatpost", "Sattel": "Seat", "Steuersatz": "Headset", "Laufradsatz": "Wheelset",
    "Vorderreifen": "Front Tire", "Hinterreifen": "Rear Tire", "Bereifung": "Tires",
    "Gewicht in Kg (ca.)": "Approx weights in KG", "Zubehör": "Accessories", "Bremshebel": "Brake Levers",
    "Vorderradnabe": "Hub (Front)", "Hinterradnabe": "Hub (Rear)", "Speichen": "Spokes", "Felgen": "Rims",
    # French
    "Cadre": "Frame", "Fourche": "Fork", "Dérailleur arrière": "Rear Derailleur", "Dérailleur avant": "Front Derailleur",
    "Manettes de dérailleur": "Shifters", "Pédalier": "Crankset", "Boitier de pédalier": "BB-Set", "Chaîne": "Chain",
    "Freins": "Brakes", "Disque de frein": "Rotor", "Cintre": "Handlebar", "Potence": "H'stem",
    "Tige de selle": "Seatpost", "Selle": "Seat", "Jeu de direction": "Headset", "Paire de roues": "Wheelset",
    "Pneu avant": "Front Tire", "Pneu arrière": "Rear Tire", "Poids en Kg (App.)": "Approx weights in KG",
    # Italian
    "Telaio": "Frame", "Forcella": "Fork", "Deragliatore posteriore": "Rear Derailleur",
    "Deragliatore anteriore": "Front Derailleur", "Leve del cambio": "Shifters", "Guarnitura": "Crankset",
    "Movimento Centrale": "BB-Set", "Catena": "Chain", "Cassetta": "Cassette", "Freni": "Brakes",
    "Disco del freno": "Rotor", "Manubrio": "Handlebar", "Attacco manubrio": "H'stem", "Reggisella": "Seatpost",
    "Sella": "Seat", "Serie sterzo": "Headset", "Mozzo anteriore": "Hub (Front)", "Mozzo posteriore": "Hub (Rear)",
    "Raggi": "Spokes", "Cerchio": "Rims", "Gomma anteriore": "Front Tire", "Gomma posteriore": "Rear Tire",
    "Peso in kg (approx.)": "Approx weights in KG",
    # Czech
    "Rám": "Frame", "Vidlice": "Fork", "Přehazovačka": "Rear Derailleur", "Přesmykač": "Front Derailleur",
    "Řazení": "Shifters", "Kliky": "Crankset", "Řetěz": "Chain", "Kazeta": "Cassette", "Brzdy": "Brakes",
    "Řidítka": "Handlebar", "Sedlovka": "Seatpost", "Hlavové složení": "Headset", "Sada kol": "Wheelset",
    "Přední plášť": "Front Tire", "Zadní plášť": "Rear Tire", "Hmotnost v kg (cca)": "Approx weights in KG",
    "Příslušenství": "Accessories", "Brzdové páky": "Brake Levers",
}


def get(url, tries=5):
    for attempt in range(tries):
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except Exception:  # the archive drops connections when busy
            time.sleep(5 * (attempt + 1))
    return None


def page_key(url):
    """'https://www.scott-sports.com/gb/en/product/scott-addict-10-bike-blue?article=1' -> 'addict-10-bike-blue'."""
    path = urllib.parse.urlparse(url).path.rstrip("/").lower()
    return re.sub(r"^(?:scott|sco)-(?:bike-)?", "", path.rsplit("/", 1)[-1])


def wanted(url):
    slug = page_key(url)
    return "/product/" in url.lower() and ROAD.search(slug) and not NOT_BIKES.search(slug) \
        and not is_ebike(slug.replace("-", " "))


def cdx(work):
    """work/captures.json: [timestamp, url, length] of every archived road-bike page copy from FIRST_YEAR on."""
    rows = []
    for site in SITES:
        query = urllib.parse.urlencode([("url", f"scott-sports.com/{site}/product/"), ("matchType", "prefix"),
                                        ("output", "json"), ("fl", "timestamp,original,length"),
                                        ("filter", "statuscode:200"), ("from", str(FIRST_YEAR)),
                                        ("collapse", "digest")])
        body = get("https://web.archive.org/cdx/search/cdx?" + query) or b"[]"
        found = [r for r in json.loads(body)[1:] if wanted(r[1])]
        log.info("%s: %d copies of road-bike pages", site, len(found))
        rows += found
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "captures.json"), "w") as fh:
        json.dump(rows, fh)
    return rows


def decode(body):
    """A page's text: UTF-8, or Windows-1252 for the pages Scott served that way (France's "Dérailleur arrière")."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", "replace")


def save_raw(raw, fh):
    """As the PC's Perl wrote raw.json (JSON::PP pretty), so adding Scott leaves the other brands' lines as they are."""
    fh.write(json.dumps(raw, indent=3, separators=(",", " : "), sort_keys=True, ensure_ascii=False) + "\n")


def best_copies(rows):
    """{(page key, capture year): (timestamp, url)}: the largest copy, a real page rather than the bot check, from
    an English site where there is one."""
    best = {}
    for ts, url, length in rows:
        length = int(length or 0)
        if length < 10000:
            continue
        k, rank = (page_key(url), ts[:4]), (not site_of(url).endswith("/en"), -length)
        if k not in best or rank < best[k][2]:
            best[k] = (ts, url, rank)
    return {k: v[:2] for k, v in best.items()}


def site_of(url):
    """'https://www.scott-sports.com/de/de/product/...' -> 'de/de'."""
    m = re.search(r"scott-sports\.com/([a-z]+/[a-z]{2})/", url)
    return m.group(1) if m else ""


def fetch(work):
    with open(os.path.join(work, "captures.json")) as fh:
        copies = best_copies(json.load(fh))
    folder = os.path.join(work, "pages")
    os.makedirs(folder, exist_ok=True)
    log.info("%d copies to read", len(copies))
    for n, ((slug, year), (ts, url)) in enumerate(sorted(copies.items()), 1):
        path = os.path.join(folder, f"{slug}_{year}.html.gz")
        if os.path.exists(path):
            continue
        body = get(f"https://web.archive.org/web/{ts}id_/{url}")
        if body:
            with gzip.open(path, "wb") as fh:
                fh.write(json.dumps({"ts": ts, "url": url}).encode() + b"\n" + body)
        if n % 25 == 0:
            log.info("%d/%d", n, len(copies))
        time.sleep(1.0)


def old_specs(page):
    """[{label, value}] of a page before 2023: <h4 class="specs-list__title"> Frame</h4> <div ...content"> ..."""
    rows = re.findall(r'<h4 class="specs-list__title">\s*(.*?)\s*</h4>\s*<div class="specs-list__content">(.*?)</div>',
                      page, re.S)
    out = []
    for label, value in rows:
        value = re.sub(r"<br\s*/?>", ", ", value)
        label = clean(html.unescape(re.sub(r"<[^>]+>", " ", label)))
        out.append({"label": LABELS.get(label, label),
                    "value": clean(html.unescape(re.sub(r"<[^>]+>", " ", value)))})
    return out


def articles(page):
    """The six-digit article numbers of a page's bike, most frequent first: its photos' (/265/265370_..._png_zoom),
    else its ?article=265370020 links. The links also go to other products the page shows (a bike of the same
    season, a suit), so the photos come first; build() drops link numbers that many pages share."""
    from collections import Counter
    photos = Counter(re.findall(r"/(\d{6})A?_\d+_(?:png|jpg)_", page))
    links = Counter(re.findall(r"article=(\d{6})\d{3}", page))
    return [n for n, _ in photos.most_common()] or [n for n, _ in links.most_common()]


def last_url(url):
    """Some pages glue the site's base onto a photo's address: 'https://www.scott-sports.com/gb/enhttps://pictures...'."""
    starts = [m.start() for m in re.finditer(r"https?://", url)]
    return url[starts[-1]:] if starts else url


def old_photo(page, number):
    """The side view of the article: the photo named by the plain number (265370_209530_png_zoom_3.jpg), else the 3/4
    view (265370A_...), else og:image. Scott's old photo hosts are gone; photos() reads them from the archive."""
    for side in ("", "A"):
        m = re.search(r"([^\"'\s(]+/%s%s_\d+_png_zoom_\d+\.jpg)" % (number, side), page)
        if m:
            return last_url(m.group(1))
    m = re.search(r'property="og:image"\s+content="([^"]+)"', page)
    return last_url(html.unescape(m.group(1))) if m else None


def name_of(raw, slug=""):
    """'SCOTT Addict 10 Bike blue' -> 'Addict 10'; 'Vélo SCOTT FOIL 30' -> 'Foil 30'; 'Rámová sada SCOTT Foil RC Pro
    HMX' (.../scott-foil-rc-pro-hmx-frame-set) -> 'Foil RC Pro HMX Frameset'."""
    name = clean(html.unescape(raw or ""))
    name = re.sub(r"^.*?\b(?:SCOTT|SCO)\s+(?:Bike\s+)?", "", name, flags=re.I)  # "Bicicleta SCOTT ...", "Vélo SCOTT ..."
    name = re.sub(r"\s+\(?20\d\d\)?$", "", name)
    name = re.sub(r"\s+(?:Frame\s?set|Rahmenset|Rahmen-Set)\b.*$", " Frameset", name, flags=re.I)
    name = re.sub(r"\s+(?:Bike|Fahrrad|Rennrad)\b.*$", "", name, flags=re.I)  # "Bike blue": the colour follows
    name = TRAILING_COLOUR.sub("", name)
    name = re.sub(r"\bdisc\b", "Disc", name)
    name = re.sub(r"\b(?:ADDICT|FOIL|SPEEDSTER|PLASMA|CONTESSA|GRAVEL)\b", lambda m: m.group(0).title(), name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    if re.search(r"frame-?set", slug) and not name.endswith("Frameset"):
        name += " Frameset"
    return name


def read(page, url, ts=""):
    """{name, articles, specs, photo, model_year} of one archived page, or None."""
    from . import scott
    group = scott.product_group(page)
    if group and group.get("additionalProperty"):
        bike = scott.parse(page, url) or {}
        specs = [{"label": LABELS.get(clean(p.get("name")), clean(p.get("name"))), "value": clean(p.get("value"))}
                 for p in group.get("additionalProperty") or [] if not scott.SKIP.match(clean(p.get("name")) or "")]
        return {"name": name_of(group.get("name"), page_key(url)), "articles": [str(group.get("productGroupID") or "")[:6]],
                "specs": specs, "photo": bike.get("image_url"), "model_year": bike.get("model_year") or year_on(page)}
    specs = old_specs(page)
    title = re.search(r"<title>\s*(.*?)\s*</title>", page, re.S)
    if not specs or not title:
        return None
    nums = articles(page)
    return {"name": name_of(title.group(1).split("|")[0], page_key(url)), "articles": nums, "specs": specs,
            "photo": old_photo(page, nums[0] if nums else "-"), "model_year": year_on(page)}


def year_on(page):
    """The model year a page states: its size chart's ("2024_SIZECHARTS", "Bikes-SizeChart-2021-BIKE")."""
    m = re.search(r"(20\d\d)_SIZECHARTS|SizeChart-(20\d\d)-", page)
    return int(m.group(1) or m.group(2)) if m else None


# Scott numbers each season's bikes in a series of its own. The years are those of the copies that date themselves
# (a size chart's year, a Mantel page's model year, the live catalogue's bikes) and of when a series first turns up:
# 265370 (Addict Gravel 10 Disc) in August 2018, when Scott shows the next season, so 2019.
SERIES = {"265": 2019, "269": 2019, "274": 2020, "275": 2020, "280": 2021, "281": 2021, "286": 2022, "287": 2022,
          "288": 2023, "289": 2023, "290": 2024, "293": 2025, "423": 2024, "425": 2026, "427": 2027}


def article_of(entry, shared):
    """The page's own article number: the first not shared by many pages (another product's link)."""
    return next((n for n in entry["articles"] if n not in shared), None)


def shared_articles(found):
    """Article numbers that pages of three or more bikes link to: another product's, not the page's own."""
    names = {}
    for e in found:
        for n in set(e["articles"]):
            names.setdefault(n, set()).add(e["name"])
    return {n for n, bikes in names.items() if len(bikes) >= 3}


def build(work, raw_path=None):
    raw_path = raw_path or os.path.join(ROOT, "data", "years", "brandsites", "raw.json")
    found = []
    folder = os.path.join(work, "pages")
    for name in sorted(os.listdir(folder)):
        with gzip.open(os.path.join(folder, name), "rb") as fh:
            meta, _, body = fh.read().partition(b"\n")
        meta = json.loads(meta)
        entry = read(decode(body), meta["url"], meta["ts"])
        if entry and entry["name"]:
            found.append(dict(entry, ts=meta["ts"], url=meta["url"]))
    shared = shared_articles(found)
    models = {}
    for e in found:
        year, source, number = e["model_year"], "page", article_of(e, shared)
        if not year and number:
            year, source = SERIES.get(number[:3]), "article_series"
        if not year or year < FIRST_YEAR or is_ebike(e["name"]) or re.search(r"\b(?:JR|Junior|Suit)\b", e["name"]):
            continue
        sheet = {"archived_url": f"https://web.archive.org/web/{e['ts']}/{e['url']}", "original_url": e["url"],
                 "wayback_timestamp": e["ts"], "model_year": year, "model_year_source": source,
                 "price": None, "currency": None, "weight": None, "frame_sizes": None,
                 "photo_url": e["photo"], "photo_live": False, "specs": e["specs"]}
        kept = models.setdefault(e["name"], {}).get(str(year))
        if not kept or len(e["specs"]) > len(kept["specs"]):  # a colour's page of the same bike, or another country
            models[e["name"]][str(year)] = sheet
    with open(raw_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    raw["models"]["Scott"] = models
    raw["checked_on"] = date.today().isoformat()
    if "scott-sports.com" not in raw.get("source", ""):
        raw["source"] = raw.get("source", "").replace(" via Wayback", ", scott-sports.com via Wayback")
    with open(raw_path, "w", encoding="utf-8") as fh:
        save_raw(raw, fh)
    log.info("Scott: %d sheets for %d models", sum(len(y) for y in models.values()), len(models))
    return models


# --- Mantel's Scott pages ------------------------------------------------------------------------------------------
# mantel.py reads data/years/mantel/raw.json, which a PC made from Mantel's archived pages for the brands it had then;
# these add Scott's to it the same way (mantel-wayback/build-json.pl, in Python).

MANTEL_LOCALES = ("", "be", "be-fr")  # Dutch and French labels, which mantel.py knows
MANTEL_YEAR = ("Modeljaar", "Année modèle", "Model year", "Modelyear")
MANTEL_WEIGHT = ("Gewicht", "Poids", "Weight")
MANTEL_SIZES = ("Framemaat", "Framematen", "Taille de cadre", "Frame size")
MANTEL_DRIVE = ("Schakelgroep", "Derailleur achter", "Achterderailleur", "Groupe de transmission",
                "Dérailleur arrière", "Groupset", "Rear derailleur")


def mantel_slug(url):
    """('be', 'scott-addict-rc-20') for https://www.mantel.com/be/scott-addict-rc-20?r=..."""
    parts = [p for p in urllib.parse.urlparse(url).path.lower().split("&")[0].split("/") if p]
    return ("/".join(parts[:-1]), parts[-1]) if parts else ("", "")


def mantel_wanted(url):
    locale, slug = mantel_slug(url)
    core = re.sub(r"^scott-(?:scott-)?", "", slug)
    return locale in MANTEL_LOCALES and slug.startswith("scott-") and ROAD.search(core) \
        and not NOT_BIKES.search(core) and not re.search(r"-\d{5,}$", core) and not is_ebike(core.replace("-", " "))


def mantel_cdx(work):
    query = urllib.parse.urlencode([("url", "mantel.com/"), ("matchType", "prefix"), ("output", "json"),
                                    ("fl", "timestamp,original,length"), ("filter", "statuscode:200"),
                                    ("filter", "original:.*scott.*"), ("from", str(FIRST_YEAR)),
                                    ("collapse", "digest")])
    rows = [r for r in json.loads(get("https://web.archive.org/cdx/search/cdx?" + query) or b"[]")[1:]
            if mantel_wanted(r[1])]
    best = {}  # (slug, capture year) -> the largest copy, Dutch pages before Belgian ones
    for ts, url, length in rows:
        locale, slug = mantel_slug(url)
        k, rank = (slug, ts[:4]), (MANTEL_LOCALES.index(locale), -int(length or 0))
        if k not in best or rank < best[k][0]:
            best[k] = (rank, ts, url)
    folder = os.path.join(work, "mantel")
    os.makedirs(folder, exist_ok=True)
    log.info("Mantel: %d copies of %d Scott pages", len(best), len({s for s, _ in best}))
    for (slug, year), (_rank, ts, url) in sorted(best.items()):
        path = os.path.join(folder, f"{slug}_{year}.html.gz")
        if os.path.exists(path):
            continue
        body = get(f"https://web.archive.org/web/{ts}id_/{url}")
        if body:
            with gzip.open(path, "wb") as fh:
                fh.write(json.dumps({"ts": ts, "url": url}).encode() + b"\n" + body)
        time.sleep(1.0)


def _text(fragment):
    return clean(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def mantel_page(page, ts, url):
    """One Mantel page as raw.json's entry: (name, entry), or None for a page without a bike's spec table."""
    page = re.sub(r'data-content="[^"]*"', "", page)
    name = None
    m = re.search(r'<h1[^>]*itemprop="name"[^>]*>(.*?)</h1>', page, re.S)
    if m:
        name = _text(re.sub(r'<(strong|span)[^>]*itemprop="brand"[^>]*>.*?</\1>', "", m.group(1), flags=re.S))
    if not name:
        m = re.search(r'property="og:title"\s+content="([^"]+)"', page)
        name = re.sub(r"\s*(?:kopen\?|\|).*$", "", re.sub(r"^Acheter\s+", "", html.unescape(m.group(1)) if m else ""), flags=re.I)
    name = re.sub(r"^(?:Scott\s+)+", "", clean(name), flags=re.I)
    if re.search(r"\bContessa\b", name, re.I):  # Scott's women's line: Mantel's "WSD" and "dames" say it again
        name = re.sub(r"\s*\b(?:WSD|dames|women'?s)\b", "", name, flags=re.I)
    name = re.sub(r"\s*\brim ?brake\b", " Rim Brake", name, flags=re.I)  # "Speedster 40 rimbrake", "... rim brake"
    order, spec = [], {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)(?=<t[dh][^>]*>|$)", row, re.S)]
        if len(cells) < 2 or not cells[0] or len(cells[0]) >= 40 or not cells[1] or re.match(r"^[\d€]", cells[0]):
            continue
        two = len(cells) == 2
        if cells[0] not in spec:
            order.append(cells[0])
            spec[cells[0]] = (cells[1], two)
        elif two > spec[cells[0]][1] or (two == spec[cells[0]][1] and len(cells[1]) > len(spec[cells[0]][0])):
            spec[cells[0]] = (cells[1], two)
    for a, b, value in re.findall(r'(?:</a>\s*([^<>]{1,40}?)|<span class="word-break">\s*([^<>]{1,40}?)\s*</span>)'
                                  r'\s*</div>\s*</div>\s*<div class="col-(?:6|7)[^"]*">\s*(.*?)\s*</div>', page, re.S):
        label, value = clean(a or b), _text(value)
        if label and value and len(value) < 300 and (label not in spec or len(value) > len(spec[label][0])):
            if label not in spec:
                order.append(label)
            spec[label] = (value, True)
    pick = lambda labels: next((spec[l][0] for l in labels if l in spec), None)
    if not name or not pick(MANTEL_DRIVE):
        return None
    year, source = re.search(r"(20\d\d)", pick(MANTEL_YEAR) or ""), "page"
    if not year:
        year, source = re.search(r"-(20[12]\d)(?:-|$)", mantel_slug(url)[1]), "slug"  # ...-2025-racefiets
    year = int(year.group(1)) if year else None
    price = re.search(r'itemprop="price"[^>]*content="([^"]+)"', page, re.I) \
        or re.search(r'"offers"\s*:\s*\[?\s*\{[^}]*?"price"\s*:\s*"?([\d.]+)', page)
    image = re.search(r'property="og:image"\s+content="([^"]+)"', page, re.I) \
        or re.search(r'src="([^"]*product\.php\?image_id=\d+[^"]*)"', page, re.I)
    image_id = re.search(r"image_id=(\d+)", image.group(1)) if image else None
    try:
        price = float(price.group(1).replace(",", ".")) if price else None
    except ValueError:
        price = None
    return name, {
        "model_year": year, "model_year_source": source, "wayback_timestamp": ts,
        "archived_url": f"https://web.archive.org/web/{ts}/{url}", "original_url": url, "price_eur": price,
        "weight": pick(MANTEL_WEIGHT), "frame_sizes": pick(MANTEL_SIZES),
        "photo_id": int(image_id.group(1)) if image_id else None,
        "photo_url_live": f"https://cdn.mantel.com/images/product.php?image_id={image_id.group(1)}&w=1500&h=1125"
        if image_id else None,
        "specs": [{"label": l, "value": spec[l][0]} for l in order]}


def mantel_build(work, raw_path=None):
    raw_path = raw_path or os.path.join(ROOT, "data", "years", "mantel", "raw.json")
    folder, models = os.path.join(work, "mantel"), {}
    for name in sorted(os.listdir(folder)):
        with gzip.open(os.path.join(folder, name), "rb") as fh:
            meta, _, body = fh.read().partition(b"\n")
        meta = json.loads(meta)
        found = mantel_page(decode(body), meta["ts"], meta["url"])
        # Mantel's pages from 2024 on don't say the year; one the URL doesn't give is left out, since the shop
        # kept selling earlier seasons' stock
        if not found or not found[1]["model_year"] or found[1]["model_year"] < FIRST_YEAR:
            continue
        model, entry = found
        kept = models.setdefault(model, {}).get(str(entry["model_year"]))
        if not kept or len(entry["specs"]) > len(kept["specs"]):
            models[model][str(entry["model_year"])] = entry
    with open(raw_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    raw["models"]["Scott"] = models
    with open(raw_path, "w", encoding="utf-8") as fh:
        save_raw(raw, fh)
    log.info("Mantel: %d Scott sheets for %d models", sum(len(y) for y in models.values()), len(models))
    return models


def photos(work, raw_path=None):
    """The Scott sheets' photos: live where Scott still serves them (photo_live), else the Wayback Machine's copy,
    saved under images/_wayback/Scott/ and listed in raw["archived_photos"], as the PC did for Canyon and Factor."""
    import hashlib
    import io
    from PIL import Image
    raw_path = raw_path or os.path.join(ROOT, "data", "years", "brandsites", "raw.json")
    with open(raw_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    saved = raw.setdefault("archived_photos", {})
    entries = [e for years in raw["models"].get("Scott", {}).values() for e in years.values() if e.get("photo_url")]
    for n, entry in enumerate(entries, 1):
        url = entry["photo_url"]
        rel = f"_wayback/Scott/{hashlib.sha1(url.encode()).hexdigest()[:16]}.jpg"
        if url in saved or os.path.exists(os.path.join(ROOT, "images", rel)):  # saved by an earlier, cut-off run
            saved[url] = rel
            continue
        live = get(url, tries=1)
        if live and _image(live):
            entry["photo_live"] = True
            continue
        body = None
        for ts, copy in [(entry["wayback_timestamp"], url)] + other_sizes(url):
            for attempt in range(2):  # the archive answers 429 when asked too often
                body = get(f"https://web.archive.org/web/{ts}im_/{copy}", tries=2)
                if body and _image(body):
                    break
                body = None
                time.sleep(15)
            if body:
                break
        if not body:
            log.info("no photo for %s", entry["original_url"])
            continue
        img = Image.open(io.BytesIO(body))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.split()[-1])
            img = bg
        os.makedirs(os.path.join(ROOT, "images", "_wayback", "Scott"), exist_ok=True)
        img.convert("RGB").save(os.path.join(ROOT, "images", rel), "JPEG", quality=88)
        saved[url] = rel
        if n % 10 == 0:
            log.info("%d/%d photos", n, len(entries))
        time.sleep(4.0)
    with open(raw_path, "w", encoding="utf-8") as fh:
        save_raw(raw, fh)


def other_sizes(url):
    """[(timestamp, url)] of the archive's copies of the same photo in other sizes (265370_209530_png_overview_4.png
    for ..._png_zoom_3.jpg), largest first: the archive kept some sizes of a photo and not others."""
    m = re.match(r"https?://(.+/\d{6}A?)_", url)
    if not m:
        return []
    query = urllib.parse.urlencode([("url", m.group(1) + "_"), ("matchType", "prefix"), ("output", "json"),
                                    ("fl", "timestamp,original,length"), ("filter", "statuscode:200"),
                                    ("filter", "mimetype:image/.*")])
    rows = json.loads(get("https://web.archive.org/cdx/search/cdx?" + query, tries=2) or b"[]")[1:]
    return [(ts, u) for ts, u, _length in sorted(rows, key=lambda r: -int(r[2] or 0)) if u != url][:3]


def _image(body):
    import io
    from PIL import Image
    try:
        Image.open(io.BytesIO(body)).verify()
        return True
    except Exception:
        return False


def main(argv=None):
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["cdx", "fetch", "build", "photos", "mantel", "mantel-build"])
    ap.add_argument("work", help="folder for the copies (outside the repo)")
    args = ap.parse_args(argv)
    {"cdx": cdx, "fetch": fetch, "build": build, "photos": photos, "mantel": mantel_cdx,
     "mantel-build": mantel_build}[args.step](args.work)


if __name__ == "__main__":
    main(sys.argv[1:])
