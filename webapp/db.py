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
    model_year INTEGER,   -- the model year the brand gives the bike in that snapshot, or NULL
    source_file TEXT,
    last_seen TEXT,       -- date of the newest catalogue scrape that listed the model
    latest_scrape TEXT,   -- date of the brand's newest catalogue scrape
    missed_scrapes INTEGER, -- scrapes since last_seen that no longer listed it
    colorways TEXT,       -- JSON list of {name, swatch, image}; image is NULL without a photo of that colour
    photo_years TEXT,     -- JSON list of model years named in the brand's photo files
    year_specs TEXT,      -- JSON {year: archived spec sheet} from data/years/, see webapp/seed.py
    sizes TEXT            -- JSON list of the frame sizes the brand's site sells it in, as scraped
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
    posted_at TEXT,       -- when the ad was placed on the site (UTC), read from the ad; NULL = unknown
    gone_reason TEXT,     -- with removed_at: "expired", "removed" (by the seller) or NULL = can't tell
    source TEXT,          -- NULL = a visitor's check, "daily" = made by webapp.daily_checks
    too_old INTEGER,      -- the bike's model year when it's from before checks.FIRST_YEAR: the check isn't published;
                          -- 0 = published, NULL = not worked out yet (webapp/stored_checks.py)
    overrides TEXT        -- JSON of what an admin set by hand (checks.OVERRIDE_KEYS): kept on every recheck
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
    asking_price REAL,    -- NULL = not given
    updated_at TEXT,      -- when a quick follow-up estimate was folded into this one, NULL = never
    revisions TEXT        -- JSON list of the earlier inputs it replaced, oldest first, for "this was not an update"
);
CREATE TABLE IF NOT EXISTS sell_ads (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,      -- when the seller last changed it in the helper, NULL = never after the first go
    ad_link TEXT,         -- the ad's link when an ad that's online was checked, NULL = a new ad made here
    title TEXT NOT NULL,  -- the title as put in (or read from the link)
    description TEXT,     -- the text as put in; never shown in the archive, only to the browser that made it
    asking_price REAL,
    model_id INTEGER NOT NULL REFERENCES models(id),  -- the model we recognised, or the one the seller picked
    answers TEXT          -- JSON of the answers given in the helper (year, size, condition, ...)
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
                       ("source", "TEXT"), ("posted_at", "TEXT"), ("gone_reason", "TEXT"),
                       ("too_old", "INTEGER"), ("overrides", "TEXT")]
ADDED_ESTIMATE_COLUMNS = [("updated_at", "TEXT"), ("revisions", "TEXT")]
ADDED_INTEREST_COLUMNS = [("token", "TEXT"), ("confirmed_at", "TEXT")]
ADDED_COLUMNS = [("last_seen", "TEXT"), ("latest_scrape", "TEXT"), ("missed_scrapes", "INTEGER"),
                 ("colorways", "TEXT"), ("photo_years", "TEXT"), ("year_specs", "TEXT"),
                 ("model_year", "INTEGER"), ("sizes", "TEXT")]


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
    have = {r["name"] for r in conn.execute("PRAGMA table_info(estimates)")}
    for column, kind in ADDED_ESTIMATE_COLUMNS:
        if column not in have:
            conn.execute(f"ALTER TABLE estimates ADD COLUMN {column} {kind}")
    if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")  # one worker folds; the others wait, then see it done
        if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
            fold_old_estimates(conn)
            conn.execute("PRAGMA user_version = 1")
        conn.commit()
    have = {r["name"] for r in conn.execute("PRAGMA table_info(photo_review_interest)")}
    for column, kind in ADDED_INTEREST_COLUMNS:
        if column not in have:
            conn.execute(f"ALTER TABLE photo_review_interest ADD COLUMN {column} {kind}")
    return conn


ESTIMATE_FIELDS = ("year", "condition", "asking_price")
REVISION_MINUTES = 10  # webapp/app.py folds a new estimate into the last one made this soon before


def fold_old_estimates(conn):
    """Once, for estimates saved before quick follow-ups were folded together: an estimate made within
    REVISION_MINUTES of the one just before it, for the same model and with at most two of year, condition
    and asking price changed, becomes an update of that one, as the value page now does. It is kept in the
    earlier row's revisions, so "This was not an update" splits it off again. Returns the ids folded away."""
    rows = [dict(r) for r in conn.execute("SELECT *, julianday(created_at) AS made FROM estimates ORDER BY id")]
    folded, prev = [], None
    for row in rows:
        if prev is not None and row["model_id"] == prev["model_id"] and not row.get("revisions") \
                and 0 <= (row["made"] - prev["last"]) * 1440 <= REVISION_MINUTES \
                and sum(prev[f] != row[f] for f in ESTIMATE_FIELDS) <= 2:
            revisions = json.loads(prev.get("revisions") or "[]") + \
                [{f: prev[f] for f in ESTIMATE_FIELDS} | {"updated_at": prev.get("updated_at")}]
            prev.update({f: row[f] for f in ESTIMATE_FIELDS}, updated_at=row["created_at"],
                        revisions=json.dumps(revisions), last=row["made"])
            conn.execute("UPDATE estimates SET year = ?, condition = ?, asking_price = ?, updated_at = ?, revisions = ? "
                         "WHERE id = ?", (prev["year"], prev["condition"], prev["asking_price"], prev["updated_at"],
                                          prev["revisions"], prev["id"]))
            conn.execute("DELETE FROM estimates WHERE id = ?", (row["id"],))
            folded.append(row["id"])
            continue
        prev = row
        prev["last"] = conn.execute("SELECT julianday(?)", (row.get("updated_at") or row["created_at"],)).fetchone()[0]
    return folded


PUBLISHED = "coalesce(too_old, 0) = 0"  # SQL for the checks the site shows (webapp/stored_checks.py settle_ages)


def model_from_row(row):
    if row is None:
        return None
    m = dict(row)
    m["colors"] = json.loads(m["colors"] or "[]")
    m["colorways"] = json.loads(m.get("colorways") or "[]")
    m["photo_years"] = json.loads(m.get("photo_years") or "[]")
    m["year_specs"] = json.loads(m.get("year_specs") or "{}")
    m["sizes"] = json.loads(m.get("sizes") or "[]")
    m["specs"] = json.loads(m["specs"] or "{}")
    return m


def catalogue_version(conn):
    """A cheap fingerprint of the models table that changes when the seed reloads or refreshes it."""
    return tuple(conn.execute(
        "SELECT count(*), max(id), total(length(name) + length(slug) + length(coalesce(specs, ''))"
        " + length(coalesce(year_specs, '')) + length(coalesce(colors, '')) + length(coalesce(colorways, '')) + length(coalesce(sizes, ''))"
        " + length(coalesce(image, '')) + length(coalesce(last_seen, '')) + length(coalesce(latest_scrape, ''))"
        " + coalesce(price_eur, 0) + coalesce(missed_scrapes, 0) + coalesce(model_year, 0)) FROM models").fetchone())


def all_models(conn):
    return [model_from_row(r) for r in conn.execute("SELECT * FROM models ORDER BY brand, name")]


def get_model(conn, model_id=None, slug=None):
    if slug is not None:
        row = conn.execute("SELECT * FROM models WHERE slug = ?", (slug,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
    return model_from_row(row)
