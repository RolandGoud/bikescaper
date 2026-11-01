"""Why an ad went off the site: its run ended ("expired") or the seller took it down ("removed").

Marktplaats and 2dehands don't say. A gone ad's link answers a bare 404 "Not Found", the same
for an expired ad, one the seller deleted and one that never existed, and nothing on the site
tells them apart afterwards. What we do know is when the ad was placed: the live ad page carries
it (`stats.since`). A free ad runs RUN_DAYS days and may be extended by the same again, so an ad
that went offline right when one of those runs ended most likely expired; one that went offline
in the middle of a run was taken down by the seller, most likely because it sold.

The re-check looks once a day, so "right when" means between the last time we saw it live and
the moment we found it gone, with a day's slack either side. When that gap is too long (the
re-check didn't run for a while) or we never learnt the placing date, we don't guess.
"""
from datetime import datetime, timedelta

from .i18n import gettext as _

RUN_DAYS = 28
MAX_RUNS = 12        # extended runs looked at; free ads get a few, paid ones may keep going
SLACK = timedelta(days=1)
MAX_GAP = timedelta(days=3)  # a longer gap between the last live sighting and "gone" says too little


def _parse(stamp):
    return datetime.strptime(stamp[:19], "%Y-%m-%d %H:%M:%S") if stamp else None


def reason(posted_at, last_seen_live, found_gone):
    """"expired", "removed", or None when we can't tell. All three are "YYYY-MM-DD HH:MM:SS" UTC."""
    posted, live, gone = _parse(posted_at), _parse(last_seen_live), _parse(found_gone)
    if not (posted and live and gone) or gone - live > MAX_GAP or gone < posted:
        return None
    for run in range(1, MAX_RUNS + 1):
        end = posted + timedelta(days=RUN_DAYS * run)
        if live - SLACK <= end <= gone + SLACK:
            return "expired"
        if end > gone + SLACK:
            break
    return "removed"


def label(row):
    """How a gone ad is shown, or None while it's up:
    {"kind": "expired" | "removed" | "gone", "short", "text", "tip"}, translated for the page."""
    row = dict(row)
    removed_at = row.get("removed_at")
    if not removed_at:
        return None
    date = removed_at[:10]
    kind = row.get("gone_reason") or "gone"
    if kind == "expired":
        return {"kind": kind, "short": _("Expired"), "text": _("Expired on {date}", date=date),
                "tip": _("The ad went offline on {date}, right when its {days}-day run on the site ended, "
                         "so it most likely expired without being sold.", date=date, days=RUN_DAYS)}
    if kind == "removed":
        return {"kind": kind, "short": _("Removed"), "text": _("Removed by the seller on {date}", date=date),
                "tip": _("The ad went offline on {date}, before its run on the site ended, so the seller took it "
                         "down, most likely because it sold.", date=date)}
    return {"kind": "gone", "short": _("Removed"), "text": _("Removed from the site on {date}", date=date),
            "tip": _("We found the ad gone from the site on {date}.", date=date)}
