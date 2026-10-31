"""Check one current Marktplaats ad of each popular model, once a day.

POPULAR are the five catalogue families with the most bike ads on Marktplaats (counted on
22 October 2026). For each, one search for the newest ads, then the first one that is a whole
bike (not a part), has a real price and photos, isn't checked yet and that we confidently match
to the family is read like a pasted link and saved as a check. If the ad turns out to have no
photos after all, the next suitable one is read instead (at most TRIES ads per family). So about
ten requests a day, PAUSE seconds apart. No rider height is filled in, as with a visitor who leaves it empty.

The checks get source = "daily", so they can be told apart or removed:

    python -m webapp.daily_checks            # one pass by hand
    python -m webapp.daily_checks --remove   # delete every check this made

On the server it runs next to the re-check (see recheck.py): every worker tries a pass each
hour and a lock file lets one of them work, at most once every EVERY (the file also holds when
the last pass began). DAILY_CHECKS=0 turns it off.
"""
import fcntl
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from . import ad_photos, checks, db, fetch_ad
from .recheck import EVERY, _stamp

SOURCE = "daily"
POPULAR = ["Giant TCR", "Specialized Tarmac", "Giant Defy", "Trek Domane", "Trek Emonda"]
SEARCH = "https://www.marktplaats.nl/lrp/api/search?"
BIKES = 445  # Marktplaats' "Fietsen en Brommers"
PAUSE = 5
TRIES = 3


def search(query):
    """The newest ads for a query: [{"url", "title", "price", "photos"}], photos being how many."""
    params = {"query": query, "l1CategoryId": BIKES, "limit": 30, "offset": 0,
              "sortBy": "SORT_INDEX", "sortOrder": "DECREASING"}
    request = urllib.request.Request(SEARCH + urlencode(params),
                                     headers={"User-Agent": fetch_ad.USER_AGENT, "Accept-Language": "nl"})
    with urllib.request.urlopen(request, timeout=fetch_ad.TIMEOUT) as response:
        data = json.loads(response.read(fetch_ad.MAX_BYTES))
    return [{"url": "https://www.marktplaats.nl" + ad["vipUrl"], "title": ad.get("title") or "",
             "price": ((ad.get("priceInfo") or {}).get("priceCents") or 0) / 100,
             "photos": len(ad.get("pictures") or ad.get("imageUrls") or [])}
            for ad in data.get("listings") or [] if ad.get("vipUrl")]


def is_bike(url):
    """Ads filed under a bike category: /v/fietsen-en-brommers/fietsen-racefietsen/..., not fietsonderdelen."""
    parts = urlsplit(url).path.split("/")
    return len(parts) > 3 and parts[3].startswith("fietsen-")


def pick(models, family, ads, seen):
    """The first ad worth checking for a family ("Giant TCR"), or None."""
    brand, name = family.split(" ", 1)
    for ad in ads:
        if (not is_bike(ad["url"]) or ad["price"] < 100 or not ad.get("photos")
                or fetch_ad.ad_id(ad["url"]) in seen):
            continue
        ranked = checks.match_models(models, ad["title"])
        top = ranked[0][1] if ranked else None
        # The family anywhere in the name, so "S-Works Tarmac SL9" counts as a Tarmac.
        if (top and top["brand"] == brand and checks.family_of(name) in checks._tokens(top["name"])
                and checks.confidence(ranked) in ("high", "medium")):
            return ad
    return None


def run(conn, search=search, fetch=fetch_ad.fetch_listing, pause=PAUSE):
    """One pass. Returns the ids of the checks it saved."""
    models = db.all_models(conn)
    seen = {fetch_ad.ad_id(r["listing_url"]) for r in conn.execute(
        "SELECT listing_url FROM checks WHERE listing_url IS NOT NULL")}
    saved = []
    for i, family in enumerate(POPULAR):
        if i and pause:
            time.sleep(pause)
        try:
            ads = search(family)
            skipped = set(seen)
            listing = None
            for _ in range(TRIES):
                ad = pick(models, family, ads, skipped)
                if ad is None:
                    break
                if pause:
                    time.sleep(pause)
                listing = fetch(ad["url"])
                if listing["photos"]:
                    break
                skipped.add(fetch_ad.ad_id(ad["url"]))  # no photos after all: try the next ad
                listing = None
            if listing is None:
                continue
        except Exception as e:  # one model failing doesn't stop the others
            print(f"daily check of {family} failed: {e}", file=sys.stderr, flush=True)
            continue
        cur = conn.execute(
            "INSERT INTO checks (listing_url, title, description, asking_price, location, photos, source)"
            " VALUES (?,?,?,?,?,?,?)",
            (listing["listing_url"], listing["title"], listing["description"], listing["asking_price"],
             listing["location"], json.dumps(listing["photos"]) if listing["photos"] else None, SOURCE))
        conn.commit()
        seen.add(fetch_ad.ad_id(listing["listing_url"]))
        saved.append(cur.lastrowid)
    return saved


def remove(conn, db_path):
    """Delete every check this made, with its stored photos. Returns how many."""
    ids = [r["id"] for r in conn.execute("SELECT id FROM checks WHERE source = ?", (SOURCE,))]
    for check_id in ids:
        shutil.rmtree(os.path.join(ad_photos.folder(db_path), str(check_id)), ignore_errors=True)
    conn.execute("DELETE FROM check_results WHERE check_id IN (SELECT id FROM checks WHERE source = ?)", (SOURCE,))
    conn.execute("DELETE FROM checks WHERE source = ?", (SOURCE,))
    conn.commit()
    return len(ids)


def run_locked(db_path, now=None):
    """One pass, unless another process is doing one or the last began less than EVERY ago."""
    with open(os.path.abspath(db_path) + ".daily.lock", "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        now = now or datetime.now(timezone.utc)
        lock.seek(0)
        last = lock.read().strip()  # when the last pass began, so a pass that found nothing waits too
        if last and last > _stamp(now - EVERY):
            return
        lock.seek(0)
        lock.truncate()
        lock.write(_stamp(now))
        lock.flush()
        conn = db.connect(db_path)
        try:
            saved = run(conn)
            for check_id in saved:  # keep the photos now, as a pasted link does, not on a first page view
                try:
                    ad_photos.store(conn, db_path, check_id)
                except Exception as e:  # a page view of the check tries again
                    print(f"storing photos of check {check_id} failed: {e}", file=sys.stderr, flush=True)
            if saved:
                print(f"daily checks: saved {len(saved)}", flush=True)
        finally:
            conn.close()


def start_background(db_path, first_after=300, every=3600):
    if os.environ.get("DAILY_CHECKS", "1") == "0":
        return

    def loop():
        time.sleep(first_after)  # after the site and the first re-check pass
        while True:
            try:
                run_locked(db_path)
            except Exception as e:  # keep the loop alive; the next pass retries
                print(f"daily checks failed: {e}", file=sys.stderr, flush=True)
            time.sleep(every)

    threading.Thread(target=loop, name="daily-checks", daemon=True).start()


if __name__ == "__main__":
    if "--remove" in sys.argv[1:]:
        print(f"removed {remove(db.connect(db.DB_PATH), db.DB_PATH)} daily check(s)")
    else:
        run_locked(db.DB_PATH)
