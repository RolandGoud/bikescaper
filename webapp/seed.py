"""Load the bikescaper output into the site database.

Run from the repo root:  python -m webapp.seed
"""
import functools
import glob
import html
import json
import os
import re
import sys
import urllib.request

from . import db
from .reference import COLOUR_WORDS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# The richest snapshot per brand. The Trek file from 18 July 2025 has full spec
# sheets; the later August export lost most of them.
FIXED_SOURCES = [
    ("Canyon", "data/Canyon/canyon_bikes_20250803_081317.json"),
]
# Brands collected by brand_scrapers/: the newest snapshot of each.
COLLECTED = ["Trek", "Specialized", "Giant", "Cannondale", "Cube", "Factor", "Scott", "Orbea"]


def latest_snapshot(brand):
    folder = os.path.join(ROOT, "data", brand)
    if not os.path.isdir(folder):
        return None
    files = sorted(f for f in os.listdir(folder) if re.match(rf"{brand.lower()}_bikes_\d{{8}}_\d{{6}}\.json$", f))
    return f"data/{brand}/{files[-1]}" if files else None


def collected_sources():
    return FIXED_SOURCES + [(brand, path) for brand in COLLECTED if (path := latest_snapshot(brand))]


SOURCES = collected_sources()
REPO = "RolandGoud/bikescaper"


def fetch_missing_snapshots(branch=None):
    """Download the newest snapshot of each collected brand whose data/<Brand>/ folder is missing.

    An older NAS compose file unpacks only data/Trek and data/Canyon; this lets a plain restart
    still load the other brands. Photos come with images/, which every compose file unpacks.
    """
    branch = branch or os.environ.get("BRANCH") or "main"
    fetched = 0
    for brand in COLLECTED:
        if latest_snapshot(brand):
            continue
        try:
            api = f"https://api.github.com/repos/{REPO}/contents/data/{brand}?ref={branch}"
            with urllib.request.urlopen(api, timeout=30) as resp:
                listing = json.load(resp)
            names = sorted(f["name"] for f in listing
                           if re.match(rf"{brand.lower()}_bikes_\d{{8}}_\d{{6}}\.json$", f["name"]))
            if not names:
                continue
            url = f"https://raw.githubusercontent.com/{REPO}/{branch}/data/{brand}/{names[-1]}"
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
            json.loads(data)  # don't save a half or broken download
            os.makedirs(os.path.join(ROOT, "data", brand), exist_ok=True)
            with open(os.path.join(ROOT, "data", brand, names[-1]), "wb") as fh:
                fh.write(data)
            fetched += 1
        except (OSError, ValueError) as exc:
            print(f"Couldn't download the {brand} catalogue: {exc}")
    return fetched


def slugify(text):
    text = text.lower().replace("+", " plus ").replace("é", "e")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def snapshot_date(path):
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_", path)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def compact(text):
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("+", "plus").replace("é", "e"))


def pick_image(bike):
    """The product shot: the bike from the side on a plain background.

    The scraper saved every picture on the product page, including close-ups,
    award badges and pictures of other models, so the first saved picture is
    often wrong. Pick by filename instead.
    """
    if bike.get("image"):  # brand_scrapers saves one product shot per model
        # and one per colour: show the first colour's, the one the model page's first swatch names
        first = (bike.get("color_images") or [None])[0]
        return first if first and os.path.exists(os.path.join(ROOT, "images", first)) else bike["image"]
    if bike["brand"] == "Canyon":
        return canyon_image(bike["name"])
    if bike["brand"] == "Trek":
        return trek_image_by_name(bike)
    return None


def swatch(name):
    """A CSS colour for a colour name, two-tone for "Black/Grey"; None when no word is recognised."""
    parts = []
    for part in (name or "").lower().split("/"):
        words = re.findall(r"[a-z]+", part)
        hexes = [h for w, h in COLOUR_WORDS if w in words]
        if not hexes:
            continue
        r, g, b = (int(hexes[0][i:i + 2], 16) for i in (1, 3, 5))
        shade = 0.6 if "dark" in words else 1.4 if "light" in words else 1
        parts.append("#%02x%02x%02x" % tuple(min(255, int(c * shade)) for c in (r, g, b)))
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else f"linear-gradient(135deg, {parts[0]} 50%, {parts[1]} 50%)"


_CANYON_FILES = None


def canyon_colour_image(sku, colour_id):
    """Canyon's side view of one colourway: a FULL shot naming the product number and colour id."""
    global _CANYON_FILES
    if _CANYON_FILES is None:
        _CANYON_FILES = sorted(
            (os.path.relpath(os.path.join(d, f), os.path.join(ROOT, "images")) for d, _dirs, files
             in os.walk(os.path.join(ROOT, "images", "Canyon")) for f in files
             if ("FULL" in f or f.startswith("full_")) and f.lower().endswith((".jpg", ".jpeg", ".webp"))),
            reverse=True)  # newest model year first
    found = [p for p in _CANYON_FILES if f"_{sku}_" in os.path.basename(p) and colour_id in os.path.basename(p)]
    return found[0] if found else None


def photo_years(bike):
    """Model years in the brand's own photo file names for this model (Trek "-26-", Canyon "2026_FULL_")."""
    if bike["brand"] == "Canyon":
        return sorted({int(year) for _key, year, _path in canyon_matches(bike["name"])})
    if bike["brand"] == "Trek":
        prefix = compact(re.sub(r"\s*gen\s*\d+", "", bike["name"], flags=re.I))
        years = set()
        for _dirpath, _dirs, files in os.walk(os.path.join(ROOT, "images", "Trek")):
            for f in files:
                m = re.match(r"([A-Za-z0-9]+)[-_](\d{2})[-_]\d+[-_][A-Z][-_]", f)
                if m and m.group(1).lower() in (prefix, prefix + "carbon", prefix + "red", prefix + "us"):
                    years.add(2000 + int(m.group(2)))
        return sorted(years)
    return []


def colorways(bike, image):
    """[{name, swatch, image, hex, photo_hex}] per colour the brand lists; the model's own photo when it has one colour.

    The photos are Canyon's own files, or the ones brand_scrapers saved per colour (color_images); a
    photo that another colour of the model already has is left out, it's not of this colour. hex is
    the swatch colour the brand shows, where it gives one (Specialized); photo_hex the frame's colour
    in the photo. The swatch is the brand's colour, else the photo's, else one read from the name.
    """
    names = bike.get("color_names") or ([bike["color"]] if bike.get("color") else [])
    ids = bike.get("color_ids") or []
    saved = bike.get("color_images") or []
    urls = bike.get("color_image_urls") or []
    hexes = bike.get("color_hexes") or []
    ways = []
    for i, name in enumerate(names):
        if bike["brand"] == "Canyon":
            photo = canyon_colour_image(bike.get("sku"), ids[i]) if i < len(ids) else None
        else:
            photo = saved[i] if i < len(saved) and saved[i] and os.path.exists(os.path.join(ROOT, "images", saved[i])) else None
            if photo and i < len(urls) and urls[i] in urls[:i]:
                photo = None
        if len(names) == 1:
            photo = photo or image
        brand_hex = hexes[i] if i < len(hexes) else None
        photo_hex = photo_colour(photo)
        ways.append({"name": name, "swatch": brand_hex or photo_hex or swatch(name), "image": photo,
                     "hex": brand_hex, "photo_hex": photo_hex})
    return ways


def photo_colour(image):
    try:
        return _photo_colour(image, os.path.getmtime(os.path.join(ROOT, "images", image))) if image else None
    except OSError:
        return None


@functools.lru_cache(maxsize=4096)
def _photo_colour(image, _mtime):
    """The frame's colour in a catalogue photo, as #rrggbb; None without a usable photo.

    Looks at the top of the frame, between the wheels and above the cranks, where the paint is. When a
    fifth of that is coloured, the commonest hue wins; else it's a white, grey or black bike, and the
    light or the dark pixels win, whichever there are enough of.
    """
    try:
        import numpy as np
        from PIL import Image
        with Image.open(os.path.join(ROOT, "images", image)) as img:
            img = img.convert("RGB")
            img.thumbnail((320, 320))
    except (OSError, ValueError):
        return None
    a = np.asarray(img, dtype=np.float32)
    corners = np.concatenate([a[:3, :3].reshape(-1, 3), a[-3:, -3:].reshape(-1, 3),
                              a[:3, -3:].reshape(-1, 3), a[-3:, :3].reshape(-1, 3)])
    diff = np.abs(a - np.median(corners, axis=0)).max(axis=2)
    ys, xs = np.nonzero(diff > 30)
    if len(xs) < 50:
        return None
    x0, y0, w, h = xs.min(), ys.min(), xs.max() - xs.min(), ys.max() - ys.min()
    top = (slice(int(y0 + .08 * h), int(y0 + .48 * h)), slice(int(x0 + .3 * w), int(x0 + .7 * w)))
    px = a[top][diff[top] > 10] / 255
    if len(px) < 30:
        return None
    mx = px.max(axis=1)
    spread = np.maximum(mx - px.min(axis=1), 1e-6)
    coloured = (spread / np.maximum(mx, 1e-6) > 0.22) & (mx > 0.2)
    if coloured.mean() >= 0.2:
        c, cmx, d = px[coloured], mx[coloured], spread[coloured]
        r, g, b = c[:, 0], c[:, 1], c[:, 2]
        hue = np.where(cmx == r, ((g - b) / d) % 6, np.where(cmx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
        bins = (hue * 24).astype(int) % 24
        counts = np.bincount(bins, minlength=24)
        peak = (counts + np.roll(counts, 1) + np.roll(counts, -1)).argmax()
        colour = np.median(c[np.isin(bins, [(peak - 1) % 24, peak, (peak + 1) % 24])], axis=0)
    else:
        light = px[mx > 0.6]
        colour = np.median(light if len(light) >= 0.35 * len(px) else px[mx <= 0.6], axis=0)
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in colour)


def _canyon_key(text):
    # Canyon file names abbreviate: "Young Hero" is yh, a frameset is frs, and
    # some files keep "sl" (cf-sl-7) where the model name has dropped it.
    text = compact(text).replace("younghero", "yh").replace("discframeandbrakekit", "frs")
    return re.sub(r"cfsl(?!x)", "cf", text).replace("disc", "")


_CANYON_SHOTS = None


def canyon_shots():
    """Canyon's side views are the files named *_FULL_* or full_*: (key, year, path)."""
    global _CANYON_SHOTS
    if _CANYON_SHOTS is None:
        _CANYON_SHOTS = []
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "images", "Canyon")):
            for f in files:
                m = (re.match(r"(\d{4})_FULL_([a-z]+)_([a-z0-9-]+?)_\d{4}_", f)
                     or re.match(r"full_(\d{4})_(?:[a-z]+_)?[\d-]+_([a-z]+)-([a-z0-9-]+?)_(?:R\d|P\d)", f))
                if m:
                    rel = os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, "images"))
                    _CANYON_SHOTS.append((_canyon_key(m.group(2) + m.group(3)), m.group(1), rel))
    return _CANYON_SHOTS


def canyon_image(name):
    found = canyon_matches(name)
    return sorted(found, key=lambda s: (-int(s[1]), s[2]))[0][2] if found else None


def canyon_matches(name):
    """Canyon side views filed under this model: (key, year, path)."""
    key = _canyon_key(name)
    exact = [s for s in canyon_shots() if s[0] == key]
    # "Endurace AllRoad" has only all-road-5 pictures; take the closest longer name.
    near = [s for s in canyon_shots() if s[0].startswith(key)]
    # "Aeroad CF SLX 7 AXS SPEED" is filed as aeroad_cf-slx-7-axs; take the longest shorter name.
    shorter = [s for s in canyon_shots() if key.startswith(s[0])]
    shorter = [s for s in shorter if len(s[0]) == max(len(t[0]) for t in shorter)]
    for found in (exact, near, shorter):
        if found:
            return found
    return []


def trek_image_by_name(bike):
    """Trek image files start with the model name without spaces, then the model year: DomaneSLR7-26-57892-A-Primary_01.

    Prefer the newest year and the first colour (A).
    """
    name = re.sub(r"\s*gen\s*\d+", "", bike["name"], flags=re.I)
    prefix = compact(name)
    best = None
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "images", "Trek")):
        for f in files:
            m = re.match(r"([A-Za-z0-9]+)[-_](\d{2})[-_]\d+[-_]([A-Z])[-_](\w+?)_(\d+)\.jpg$", f)
            # Some files add a word: FXSport6Carbon, MadoneSLR8AXSRed, DOMANEPLUSSLR8AXSUS.
            # Only Primary files are studio side views; Portrait ones are styled photos on a dark set.
            if m and m.group(1).lower() in (prefix, prefix + "carbon", prefix + "red", prefix + "us") and m.group(4).lower() == "primary":
                rel = os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, "images"))
                rank = (-int(m.group(2)), m.group(3), int(m.group(5)), rel)
                if best is None or rank < best:
                    best = rank
    return best[-1] if best else None


def scrape_history(brand):
    """{model name (lowercase): date last listed} and the dates of every scrape of this brand's catalogue.

    Reads every dated JSON export in data/<brand>/; several exports on one day count as one scrape.
    """
    seen, dates = {}, set()
    for path in sorted(glob.glob(os.path.join(ROOT, "data", brand, "*.json"))):
        date = snapshot_date(os.path.basename(path))
        if not date:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                bikes = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(bikes, list) or not bikes:
            continue
        dates.add(date)
        for bike in bikes:
            name = (bike.get("name") or "").strip().lower()
            if name and seen.get(name, "") < date:
                seen[name] = date
    return seen, sorted(dates)


def catalogue_status(brand, name, history):
    """(last_seen, latest_scrape, missed_scrapes) for one model."""
    seen, dates = history
    last = seen.get(name.strip().lower())
    if not dates or not last:
        return None, dates[-1] if dates else None, None
    return last, dates[-1], sum(1 for d in dates if d > last)


def refresh_status(conn):
    """Update every model's catalogue status from the scrapes on disk, keeping saved checks intact."""
    histories = {brand: scrape_history(brand) for brand, _rel in SOURCES}
    count = 0
    for row in conn.execute("SELECT id, brand, name FROM models").fetchall():
        if row["brand"] in histories:
            conn.execute("UPDATE models SET last_seen = ?, latest_scrape = ?, missed_scrapes = ? WHERE id = ?",
                         (*catalogue_status(row["brand"], row["name"], histories[row["brand"]]), row["id"]))
            count += 1
    conn.commit()
    return count


def refresh_images(conn):
    """Re-pick the photo, colourways and photo years of every model already in the database, keeping saved checks intact."""
    count = 0
    for brand, rel in SOURCES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            for bike in json.load(fh):
                bike.setdefault("brand", brand)
                image = pick_image(bike)
                cur = conn.execute("UPDATE models SET image = ?, colorways = ?, photo_years = ? WHERE slug = ?",
                                   (image, json.dumps(colorways(bike, image), ensure_ascii=False),
                                    json.dumps(photo_years(bike)), slugify(f"{brand} {bike['name']}")))
                count += cur.rowcount
    conn.commit()
    return count


def _years_file(*parts):
    try:
        with open(os.path.join(ROOT, "data", "years", *parts), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def year_specs(brand, name, _cache={}):
    """The model's spec sheets from earlier years: the brand's own pages for old models
    (data/years/site/<Brand>.json, see brand_scrapers/history.py) and, for years those lack,
    Wayback Machine copies of the brand's NL site (data/years/<Brand>.json).

    {"checked": [years looked up], "checked_on": date, "years": {year: {captured, url, price, specs,
    source?, sheet_years?, sheet_name?, colours?, price_url?, price_captured?} or {captured, url, unreadable: true}}}; a checked year
    without an entry had no page.
    """
    if brand not in _cache:
        _cache[brand] = (_years_file(f"{brand}.json"), _years_file("site", f"{brand}.json"))
    archive, site = _cache[brand]
    if not archive and not site:
        return {}
    years = dict((archive or {}).get("models", {}).get(name.strip(), {}))
    for year, entry in (site or {}).get("models", {}).get(name.strip(), {}).items():
        if entry.get("specs") or year not in years:
            copy = years.get(year) or {}
            # The brand's own old pages carry no price: keep the one the Wayback copy showed, and say where it's from.
            if not entry.get("price") and copy.get("price"):
                entry = dict(entry, price=copy["price"], price_url=copy.get("url"), price_captured=copy.get("captured"))
            years[year] = entry
    found = [f for f in (archive, site) if f]
    return {"checked": sorted({y for f in found for y in f["years"]}),
            "checked_on": max(f["checked_on"] for f in found), "years": years}


def refresh_year_specs(conn):
    """Re-read data/years/ for every model already in the database."""
    count = 0
    for row in conn.execute("SELECT id, brand, name FROM models").fetchall():
        count += conn.execute("UPDATE models SET year_specs = ? WHERE id = ?",
                              (json.dumps(year_specs(row["brand"], row["name"]), ensure_ascii=False),
                               row["id"])).rowcount
    conn.commit()
    return count


def insert_bike(conn, brand, bike, rel, verb="INSERT OR REPLACE"):
    bike.setdefault("brand", brand)
    colors = bike.get("color_names") or ([bike["color"]] if bike.get("color") else [])
    price = float(bike["price"]) if bike.get("price") not in (None, "") else None
    image = pick_image(bike)
    cur = conn.execute(
        f"{verb} INTO models (brand, name, slug, category, price_eur, sku, url, colors,"
        " specs, image, seen_on, source_file, colorways, photo_years, year_specs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            brand,
            bike["name"].strip(),
            slugify(f"{brand} {bike['name']}"),
            html.unescape(bike.get("category") or ""),
            price,
            str(bike.get("sku") or ""),
            bike.get("url"),
            json.dumps(colors, ensure_ascii=False),
            json.dumps(bike.get("specifications") or {}, ensure_ascii=False),
            image,
            snapshot_date(rel),
            rel,
            json.dumps(colorways(bike, image), ensure_ascii=False),
            json.dumps(photo_years(bike)),
            json.dumps(year_specs(brand, bike["name"]), ensure_ascii=False),
        ),
    )
    return cur.rowcount


def add_other_scrapes(conn):
    """Add models that only other scrapes list (dropped since, or new), newest scrape first.

    Discontinued models matter here: second-hand ads are full of them. Existing rows are left alone,
    so saved checks keep their matches.
    """
    count = 0
    have = {r[0] for r in conn.execute("SELECT slug FROM models")}
    for brand, _rel in SOURCES:
        paths = [p for p in glob.glob(os.path.join(ROOT, "data", brand, "*.json"))
                 if snapshot_date(os.path.basename(p))]
        for path in sorted(paths, key=lambda p: snapshot_date(os.path.basename(p)), reverse=True):
            try:
                with open(path, encoding="utf-8") as fh:
                    bikes = json.load(fh)
            except (OSError, ValueError):
                continue
            for bike in bikes if isinstance(bikes, list) else []:
                slug = slugify(f"{brand} {bike.get('name') or ''}")
                if bike.get("name") and slug not in have:
                    have.add(slug)
                    count += insert_bike(conn, brand, bike, os.path.relpath(path, ROOT), "INSERT OR IGNORE")
    conn.commit()
    return count


def add_archived(conn):
    """Add the lines the brands no longer sell (data/years/archived/<Brand>.json, brand_scrapers/history.py
    --archived): Émonda SLR, Defy Advanced SL. Existing rows are left alone, so saved checks keep their matches."""
    count = 0
    have = {r[0] for r in conn.execute("SELECT slug FROM models")}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "years", "archived", "*.json"))):
        brand = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding="utf-8") as fh:
                bikes = json.load(fh)
        except (OSError, ValueError):
            continue
        for bike in bikes:
            slug = slugify(f"{brand} {bike.get('name') or ''}")
            if bike.get("name") and slug not in have:
                have.add(slug)
                count += insert_bike(conn, brand, dict(bike), os.path.relpath(path, ROOT), "INSERT OR IGNORE")
    conn.commit()
    return count


def load(conn):
    conn.execute("DELETE FROM models")
    count = 0
    for brand, rel in SOURCES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            for bike in json.load(fh):
                count += insert_bike(conn, brand, bike, rel)
    conn.commit()
    count += add_other_scrapes(conn)
    count += add_archived(conn)
    refresh_status(conn)
    return count


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if fetch_missing_snapshots():
        SOURCES = collected_sources()
    conn = db.connect(args[0] if args else None)
    if "--if-empty" in sys.argv and conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]:
        print(f"Models already loaded; refreshed photos of {refresh_images(conn)} models,"
              f" added {add_other_scrapes(conn)} from other scrapes and {add_archived(conn)} discontinued lines,"
              f" updated status of {refresh_status(conn)},"
              f" read earlier years for {refresh_year_specs(conn)}")
    else:
        print(f"Loaded {load(conn)} models into {db.DB_PATH}")
