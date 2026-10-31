"""Check reports are worked out once and kept in the database, not run again on every page view.

A stored report is used as long as what went into it is the same: the ad's title, description, price,
link, the rider's height, the model someone picked, and the ad photos stored on our disk. When one of
those changes (a different model picked, the photos finished downloading) the check runs again by itself.
A change to the matching itself, or to the catalogue, does not: that's what a recheck is for, from the
report page (one check) or the Statistics page (all of them), or by hand. A recheck keeps the check's
own date: the ad's age and value stay as of the day it was checked.

    python -m webapp.stored_checks           # forget every stored report; each runs again when next shown

Catalogue models are kept by their slug, not copied into the stored report, so a report shows the
catalogue as it is now and survives a reload of the models table (which hands out new ids).
"""
import hashlib
import io
import json
import os
import pickle
import sys
from datetime import date

from . import checks, db


def inputs_key(listing):
    """A fingerprint of everything run_check reads from the listing."""
    photos = [os.path.basename(p) for p in listing.get("photo_paths") or []]
    wanted = {k: listing.get(k) for k in ("title", "description", "asking_price", "listing_url",
                                          "rider_height", "model_id")}
    if listing.get("photo_groupset"):
        # Only when there is one, so checks without it keep the reports they have.
        # The version makes reports stored before the crankset and the hover on each row run again.
        wanted["photo_groupset"] = dict(listing["photo_groupset"], label_version=3)
    return hashlib.sha1(json.dumps(dict(wanted, photos=photos), sort_keys=True, default=str).encode()).hexdigest()


class _Pickler(pickle.Pickler):
    def __init__(self, file, models):
        super().__init__(file, protocol=pickle.HIGHEST_PROTOCOL)
        self.slugs = {id(m): m["slug"] for m in models}

    def persistent_id(self, obj):
        return ("model", self.slugs[id(obj)]) if type(obj) is dict and id(obj) in self.slugs else None


class _Unpickler(pickle.Unpickler):
    def __init__(self, file, models):
        super().__init__(file)
        self.by_slug = {m["slug"]: m for m in models}

    def persistent_load(self, pid):
        kind, slug = pid
        return self.by_slug[slug]  # KeyError when the model is gone: the check then runs again


def dump(result, models):
    out = io.BytesIO()
    _Pickler(out, models).dump(result)
    return out.getvalue()


def load(data, models):
    result = _Unpickler(io.BytesIO(data), models).load()
    shown = result.get("model") if isinstance(result, dict) else None
    if shown is not None and not any(shown is m for m in models):
        # run_check shows a copy of the model with another photo (a colourway, a model year), which the
        # pickle kept whole: rebuild it on today's model so its id and data follow a catalogue reload.
        today = {m["slug"]: m for m in models}[shown["slug"]]  # KeyError when gone: the check runs again
        result["model"] = dict(today, **{k: shown[k] for k in ("image", "year_photo") if k in shown})
    return result


def report(conn, models, listing, store=True, today=None):
    """The check report for a listing (a checks row as listing_dict makes it): the stored one when its inputs
    haven't changed, otherwise a fresh run_check. That fresh one is stored, unless `store` is False (a
    report for another rider height than the check's own, say). A listing without an id is never stored.
    Age and value are worked out as of the day the check was made, not the day it runs (again), so a
    recheck changes what the matching finds but keeps the check's own date."""
    if today is None and listing.get("created_at"):
        today = date.fromisoformat(listing["created_at"][:10])
    if listing.get("id") is None:
        return checks.run_check(models, listing, today)
    key = inputs_key(listing)
    row = conn.execute("SELECT inputs, result FROM check_results WHERE check_id = ?", (listing["id"],)).fetchone()
    if row is not None and row["inputs"] == key:
        try:
            return load(row["result"], models)
        except Exception as e:  # the model left the catalogue, or the code changed under the pickle
            print(f"stored report of check {listing['id']} unusable ({e!r}); running it again", file=sys.stderr)
    result = checks.run_check(models, listing, today)
    if store:
        conn.execute("INSERT OR REPLACE INTO check_results (check_id, inputs, result, computed_at)"
                     " VALUES (?, ?, ?, datetime('now'))", (listing["id"], key, dump(result, models)))
        conn.commit()
    return result


def computed_at(conn, check_id):
    """When the stored report of this check was worked out (UTC, 'YYYY-MM-DD HH:MM:SS'), or None."""
    row = conn.execute("SELECT computed_at FROM check_results WHERE check_id = ?", (check_id,)).fetchone()
    return row["computed_at"] if row else None


def summary(conn):
    """{stored, oldest, newest}: how many reports are kept and when they were worked out."""
    row = conn.execute("SELECT COUNT(*) AS n, MIN(computed_at) AS oldest, MAX(computed_at) AS newest"
                       " FROM check_results").fetchone()
    return {"stored": row["n"], "oldest": row["oldest"], "newest": row["newest"]}


def forget(conn, check_id=None):
    """Drop the stored report of one check, or of every check: it runs again the next time it's shown."""
    if check_id is None:
        n = conn.execute("DELETE FROM check_results").rowcount
    else:
        n = conn.execute("DELETE FROM check_results WHERE check_id = ?", (check_id,)).rowcount
    conn.commit()
    return n


if __name__ == "__main__":
    c = db.connect(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Forgot {forget(c)} stored reports; each check runs again the next time it's shown.")
