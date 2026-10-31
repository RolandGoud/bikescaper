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
    source_file TEXT,
    last_seen TEXT,       -- date of the newest catalogue scrape that listed the model
    latest_scrape TEXT,   -- date of the brand's newest catalogue scrape
    missed_scrapes INTEGER, -- scrapes since last_seen that no longer listed it
    colorways TEXT,       -- JSON list of {name, swatch, image}; image is NULL without a photo of that colour
    photo_years TEXT,     -- JSON list of model years named in the brand's photo files
    year_specs TEXT       -- JSON {year: archived spec sheet} from data/years/, see webapp/seed.py
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
    model_id INTEGER REFERENCES models(id),  -- user-corrected match, NULL = automatic
    photos TEXT,          -- JSON list of photo URLs read from the ad's link, NULL when typed in
    last_checked_at TEXT, -- when the ad's link was last re-checked (UTC)
    removed_at TEXT,      -- when we first found the ad gone from the site, NULL while it's up
    source TEXT           -- NULL = a visitor's check, "daily" = made by webapp.daily_checks
);
CREATE TABLE IF NOT EXISTS check_results (
    check_id INTEGER PRIMARY KEY REFERENCES checks(id),
    inputs TEXT NOT NULL,     -- fingerprint of what the check read from the ad (webapp/stored_checks.py)
    result BLOB NOT NULL,     -- the run_check report, pickled with catalogue models kept by slug
    computed_at TEXT NOT NULL -- when it was worked out (UTC); a recheck deletes the row
);
CREATE TABLE IF NOT EXISTS estimates (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    model_id INTEGER NOT NULL REFERENCES models(id),
    year INTEGER,         -- model year as typed in, NULL = not given
    condition TEXT,       -- NULL = normal use, else a key of checks.CONDITION_LABEL
    asking_price REAL     -- NULL = not given
);
CREATE TABLE IF NOT EXISTS photo_review_interest (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    kind TEXT NOT NULL,   -- "click" on the paid photo review offer, or "email" left to hear when it launches
    email TEXT,           -- only for kind "email"
    token TEXT,           -- the secret in the confirmation link mailed to that address
    confirmed_at TEXT,    -- when the link was opened; only confirmed addresses count
    model_id INTEGER,     -- the model of the seller's ad, when known
    lang TEXT
);
"""
ADDED_CHECK_COLUMNS = [("photos", "TEXT"), ("last_checked_at", "TEXT"), ("removed_at", "TEXT"),
                       ("source", "TEXT")]
ADDED_INTEREST_COLUMNS = [("token", "TEXT"), ("confirmed_at", "TEXT")]
ADDED_COLUMNS = [("last_seen", "TEXT"), ("latest_scrape", "TEXT"), ("missed_scrapes", "INTEGER"),
                 ("colorways", "TEXT"), ("photo_years", "TEXT"), ("year_specs", "TEXT")]


def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Databases made before a column existed get it added; the seed fills it in.
    have = {r["name"] for r in conn.execute("PRAGMA table_info(models)")}
    for column, kind in ADDED_COLUMNS:
        if column not in have:
            conn.execute(f"ALTER TABLE models ADD COLUMN {column} {kind}")
    have = {r["name"] for r in conn.execute("PRAGMA table_info(checks)")}
    for column, kind in ADDED_CHECK_COLUMNS:
        if column not in have:
            conn.execute(f"ALTER TABLE checks ADD COLUMN {column} {kind}")
    have = {r["name"] for r in conn.execute("PRAGMA table_info(photo_review_interest)")}
    for column, kind in ADDED_INTEREST_COLUMNS:
        if column not in have:
            conn.execute(f"ALTER TABLE photo_review_interest ADD COLUMN {column} {kind}")
    return conn


def model_from_row(row):
    if row is None:
        return None
    m = dict(row)
    m["colors"] = json.loads(m["colors"] or "[]")
    m["colorways"] = json.loads(m.get("colorways") or "[]")
    m["photo_years"] = json.loads(m.get("photo_years") or "[]")
    m["year_specs"] = json.loads(m.get("year_specs") or "{}")
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
