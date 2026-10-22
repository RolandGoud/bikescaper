"""Load the existing bikescaper output (Trek and Canyon NL) into the site database.

Run from the repo root:  python -m webapp.seed
"""
import html
import json
import os
import re
import sys

from . import db

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# The richest snapshot per brand. The Trek file from 18 July 2025 has full spec
# sheets; the later August export lost most of them.
SOURCES = [
    ("Trek", "data/Trek/trek_bikes_20250718_100005.json"),
    ("Canyon", "data/Canyon/canyon_bikes_20250803_081317.json"),
]


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
    if bike["brand"] == "Canyon":
        return canyon_image(bike["name"])
    if bike["brand"] == "Trek":
        return trek_image_by_name(bike)
    return None


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
    key = _canyon_key(name)
    exact = [s for s in canyon_shots() if s[0] == key]
    # "Endurace AllRoad" has only all-road-5 pictures; take the closest longer name.
    near = [s for s in canyon_shots() if s[0].startswith(key)]
    # "Aeroad CF SLX 7 AXS SPEED" is filed as aeroad_cf-slx-7-axs; take the longest shorter name.
    shorter = [s for s in canyon_shots() if key.startswith(s[0])]
    shorter = [s for s in shorter if len(s[0]) == max(len(t[0]) for t in shorter)]
    for found in (exact, near, shorter):
        if found:
            return sorted(found, key=lambda s: (-int(s[1]), s[2]))[0][2]
    return None


def trek_image_by_name(bike):
    """Trek image files start with the model name without spaces, then the model year: DomaneSLR7-26-57892-A-Primary_01.

    Prefer the newest year, the first colour (A) and a Primary (side view) shot.
    """
    name = re.sub(r"\s*gen\s*\d+", "", bike["name"], flags=re.I)
    prefix = compact(name)
    best = None
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "images", "Trek")):
        for f in files:
            m = re.match(r"([A-Za-z0-9]+)[-_](\d{2})[-_]\d+[-_]([A-Z])[-_](\w+?)_(\d+)\.jpg$", f)
            # Some files add a word: FXSport6Carbon, MadoneSLR8AXSRed, DOMANEPLUSSLR8AXSUS.
            if m and m.group(1).lower() in (prefix, prefix + "carbon", prefix + "red", prefix + "us"):
                rel = os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, "images"))
                rank = (-int(m.group(2)), m.group(4).lower() != "primary", m.group(3), int(m.group(5)), rel)
                if best is None or rank < best:
                    best = rank
    return best[-1] if best else None


def refresh_images(conn):
    """Re-pick the photo of every model already in the database, keeping saved checks intact."""
    count = 0
    for brand, rel in SOURCES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            for bike in json.load(fh):
                bike.setdefault("brand", brand)
                cur = conn.execute("UPDATE models SET image = ? WHERE slug = ?",
                                   (pick_image(bike), slugify(f"{brand} {bike['name']}")))
                count += cur.rowcount
    conn.commit()
    return count


def load(conn):
    conn.execute("DELETE FROM models")
    count = 0
    for brand, rel in SOURCES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            bikes = json.load(fh)
        for bike in bikes:
            bike.setdefault("brand", brand)
            colors = bike.get("color_names") or ([bike["color"]] if bike.get("color") else [])
            price = float(bike["price"]) if bike.get("price") not in (None, "") else None
            conn.execute(
                "INSERT OR REPLACE INTO models (brand, name, slug, category, price_eur, sku, url, colors,"
                " specs, image, seen_on, source_file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    pick_image(bike),
                    snapshot_date(rel),
                    rel,
                ),
            )
            count += 1
    conn.commit()
    return count


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    conn = db.connect(args[0] if args else None)
    if "--if-empty" in sys.argv and conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]:
        print(f"Models already loaded; refreshed photos of {refresh_images(conn)} models")
    else:
        print(f"Loaded {load(conn)} models into {db.DB_PATH}")
