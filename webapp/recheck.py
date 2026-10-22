"""Mark checked ads as removed once they're gone from Marktplaats or 2dehands.

Only ads someone pasted a link for are looked at, each at most once a day, a few seconds apart,
and only for the first DAYS_WATCHED days after the check (ads rarely live longer).

    python -m webapp.recheck            # one pass by hand

On the server the site runs it itself: under gunicorn each worker starts a background thread
that tries a pass every hour, and a lock file next to the database lets only one of them work
at a time. So a plain restart of the container is enough to get it going.
"""
import fcntl
import os
import sys
import threading
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


def run_locked(db_path):
    """One pass, unless another process is already doing one."""
    with open(os.path.abspath(db_path) + ".recheck.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        conn = db.connect(db_path)
        try:
            found = run(conn)
            if found:
                print(f"recheck: {found} ad(s) removed", flush=True)
        finally:
            conn.close()


def start_background(db_path, first_after=120, every=3600):
    def loop():
        time.sleep(first_after)  # let the site start first
        while True:
            try:
                run_locked(db_path)
            except Exception as e:  # keep the loop alive; the next pass retries
                print(f"recheck failed: {e}", file=sys.stderr, flush=True)
            time.sleep(every)

    threading.Thread(target=loop, name="recheck", daemon=True).start()


if __name__ == "__main__":
    run_locked(db.DB_PATH)
