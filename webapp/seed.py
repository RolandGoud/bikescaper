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


def pick_image(bike):
    for img in bike.get("hero_images") or []:
        path = img.get("local_path") or ""
        if path.lower().endswith((".jpg", ".jpeg", ".webp")) and os.path.exists(os.path.join(ROOT, path)):
            return path[len("images/"):] if path.startswith("images/") else path
    folder = os.path.join(ROOT, "images", bike["brand"], bike["name"].replace(" ", "_"))
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith((".jpg", ".jpeg", ".webp")):
                return f"{bike['brand']}/{os.path.basename(folder)}/{f}"
    return trek_image_by_name(bike) if bike["brand"] == "Trek" else None


def trek_image_by_name(bike):
    """Trek image files start with the model name without spaces, then the model year: DomaneSLR7-26-57892-..."""
    name = re.sub(r"\s*gen\s*\d+", "", bike["name"], flags=re.I).replace("+", "Plus").replace("É", "E")
    prefix = re.sub(r"[^A-Za-z0-9]", "", name).lower()
    best = None
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "images", "Trek")):
        for f in files:
            m = re.match(r"([A-Za-z0-9]+)[-_](\d{2})[-_]", f)
            if m and m.group(1).lower() == prefix and f.lower().endswith(".jpg"):
                rel = os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, "images"))
                if best is None or m.group(2) > best[0]:
                    best = (m.group(2), rel)
    return best[1] if best else None


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
    conn = db.connect(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Loaded {load(conn)} models into {db.DB_PATH}")
