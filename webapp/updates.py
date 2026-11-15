"""What the NAS's last updates put live, for the admin's "Just live" note (base.html) and the admin page.

nas/autoupdate.py writes the list (updates.json next to the database) after each update it installs:
newest first, each {sha, from, time, changes: [{title, pr, url, check}]}, where `check` is the page to
look at, taken from a "Check: /path" line in the PR (see .github/pull_request_template.md).
"""
import datetime
import json
import os

RECENT_DAYS = 3   # the note only shows updates this recent, so a new browser isn't shown weeks of them
NOTE_MAX = 8      # updates in the note at most

_cache = {}


def path(db_path):
    return os.environ.get("UPDATES_FILE") or os.path.join(os.path.dirname(os.path.abspath(db_path)), "updates.json")


def load(db_path):
    """All saved updates, newest first; [] when there are none (say, not on the NAS)."""
    p = path(db_path)
    try:
        mtime = os.stat(p).st_mtime
    except OSError:
        return []
    if _cache.get(p, (None,))[0] != mtime:
        try:
            with open(p) as fh:
                data = json.load(fh)
            _cache[p] = (mtime, [u for u in data if isinstance(u, dict) and u.get("sha")])
        except (OSError, ValueError):
            return []
    return _cache[p][1]


STUCK_MINUTES = 10  # an "installing" flag older than this is left over from an update that was cut off


def updating(db_path, now=None):
    """The update being installed right now, as {sha, since, changes}, or None."""
    p = os.path.join(os.path.dirname(path(db_path)), "updating.json")
    try:
        with open(p) as fh:
            u = json.load(fh)
        since = datetime.datetime.fromisoformat(u["since"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return u if now - since <= datetime.timedelta(minutes=STUCK_MINUTES) else None


def recent(db_path, now=None):
    """The updates for the note: from the last RECENT_DAYS days, at most NOTE_MAX."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    out = []
    for u in load(db_path)[:NOTE_MAX]:
        try:
            when = datetime.datetime.fromisoformat(u["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if now - when <= datetime.timedelta(days=RECENT_DAYS):
            out.append(u)
    return out


def when(stamp):
    """"18:42" today, else "14 nov 18:42", in the NAS's local time."""
    try:
        t = datetime.datetime.fromisoformat(stamp).astimezone()
    except (TypeError, ValueError):
        return ""
    today = datetime.datetime.now().astimezone().date()
    return t.strftime("%H:%M") if t.date() == today else t.strftime("%d %b %H:%M").lstrip("0").lower()
