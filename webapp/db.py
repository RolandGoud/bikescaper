import json
import os
import sqlite3

DB_PATH = os.environ.get(
    "BIKECOMPARE_DB",
    os.path.join(os.path.dirname(__file__), "..", "instance", "bikecompare.sqlite3"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    category TEXT,
    price_eur REAL,
    sku TEXT,
    url TEXT,
    colors TEXT,          -- JSON list
    specs TEXT,           -- JSON object, as scraped (Dutch labels)
    image TEXT,           -- path under images/, or NULL
    seen_on TEXT,         -- date of the catalogue snapshot (YYYY-MM-DD)
    source_file TEXT
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    listing_url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    asking_price REAL,
    location TEXT,
    rider_height INTEGER,
    model_id INTEGER REFERENCES models(id)   -- user-corrected match, NULL = automatic
);
"""


def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def model_from_row(row):
    if row is None:
        return None
    m = dict(row)
    m["colors"] = json.loads(m["colors"] or "[]")
    m["specs"] = json.loads(m["specs"] or "{}")
    return m


def all_models(conn):
    return [model_from_row(r) for r in conn.execute("SELECT * FROM models ORDER BY brand, name")]


def get_model(conn, model_id=None, slug=None):
    if slug is not None:
        row = conn.execute("SELECT * FROM models WHERE slug = ?", (slug,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
    return model_from_row(row)
