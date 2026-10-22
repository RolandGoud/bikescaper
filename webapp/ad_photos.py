"""Keep our own copy of each checked ad's photos, so they still show after the ad is gone.

They go in an "ad-photos" folder next to the database (on the NAS: the data volume, which
survives restarts and code updates), one folder per check: ad-photos/<check id>/01.jpg ...
The check's `photos` list then holds those names instead of the site's URLs.
"""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import fetch_ad

# The image servers Marktplaats and 2dehands use; nothing else is downloaded.
IMAGE_HOSTS = ("marktplaats.com", "marktplaats.nl", "2dehands.com", "2dehands.be", "2ememain.com", "2ememain.be")
MAX_PHOTOS = 24
MAX_BYTES = 5_000_000
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def folder(db_path):
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "ad-photos")


def is_stored(photo):
    return not photo.startswith(("http://", "https://"))


def _allowed(url):
    host = (urlsplit(url).hostname or "").lower()
    return urlsplit(url).scheme == "https" and any(host == h or host.endswith("." + h) for h in IMAGE_HOSTS)


def _download(url):
    """(bytes, extension), or None when it isn't a photo we can take."""
    if not _allowed(url):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": fetch_ad.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=fetch_ad.TIMEOUT) as response:
            ext = TYPES.get(response.headers.get_content_type())
            data = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    if not ext or not data or len(data) > MAX_BYTES:
        return None
    return data, ext


def store(conn, db_path, check_id, download=_download):
    """Download the check's photos that are still links. Returns how many are stored now.

    A photo that fails stays a link, so the page still shows it and the next try picks it up.
    """
    row = conn.execute("SELECT photos FROM checks WHERE id = ?", (check_id,)).fetchone()
    photos = json.loads(row["photos"]) if row and row["photos"] else []
    if all(is_stored(p) for p in photos):
        return len(photos)
    target = os.path.join(folder(db_path), str(check_id))
    os.makedirs(target, exist_ok=True)
    kept = []
    for n, photo in enumerate(photos[:MAX_PHOTOS], 1):
        got = None if is_stored(photo) else download(photo)
        if got:
            data, ext = got
            name = f"{check_id}/{n:02d}{ext}"
            with open(os.path.join(folder(db_path), name), "wb") as f:
                f.write(data)
            photo = name
        kept.append(photo)
    conn.execute("UPDATE checks SET photos = ? WHERE id = ?", (json.dumps(kept), check_id))
    conn.commit()
    return sum(is_stored(p) for p in kept)


def missing(conn):
    """Checks that still have photos as links (new ones, or made before photos were stored)."""
    return [r["id"] for r in conn.execute(
        "SELECT id FROM checks WHERE photos LIKE '%\"http%' ORDER BY id")]
