"""Mark checked ads as removed once they're gone from Marktplaats or 2dehands.

Only ads someone pasted a link for are looked at, each at most once a day, a few seconds apart,
and only for the first DAYS_WATCHED days after the check (ads rarely live longer).

    python -m webapp.recheck            # one pass
    python -m webapp.recheck --forever  # a pass every hour (what the Docker image runs)
"""
import sys
import time
from datetime import datetime, timedelta, timezone

from . import db, fetch_ad

EVERY = timedelta(hours=20)  # a bit under a day, so the hourly loop doesn't drift past 24 h
DAYS_WATCHED = 90
PAUSE = 5  # seconds between requests to the site


def _stamp(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")  # same format as SQLite's datetime('now')


def due(conn, now):
    return conn.execute(
        "SELECT id, listing_url FROM checks WHERE listing_url IS NOT NULL AND removed_at IS NULL"
        " AND created_at >= ? AND (last_checked_at IS NULL OR last_checked_at <= ?) ORDER BY id",
        (_stamp(now - timedelta(days=DAYS_WATCHED)), _stamp(now - EVERY)),
    ).fetchall()


def run(conn, now=None, status=fetch_ad.ad_status, pause=PAUSE):
    """One pass. Returns how many ads it found removed."""
    removed = 0
    for i, row in enumerate(due(conn, now or datetime.now(timezone.utc))):
        if not fetch_ad.supported(fetch_ad.with_scheme(row["listing_url"])):
            continue  # typed-in links to other sites
        if i and pause:
            time.sleep(pause)
        result = status(row["listing_url"])
        if result is None:
            continue  # couldn't tell; try again next pass
        stamp = _stamp(now or datetime.now(timezone.utc))
        conn.execute("UPDATE checks SET last_checked_at = ?, removed_at = ? WHERE id = ?",
                     (stamp, stamp if result == "removed" else None, row["id"]))
        conn.commit()
        removed += result == "removed"
    return removed


if __name__ == "__main__":
    while True:
        conn = db.connect()
        try:
            found = run(conn)
            if found:
                print(f"recheck: {found} ad(s) removed", flush=True)
        except Exception as e:  # keep the loop alive; the next pass retries
            print(f"recheck failed: {e}", file=sys.stderr, flush=True)
        finally:
            conn.close()
        if "--forever" not in sys.argv:
            break
        time.sleep(3600)
