"""Second-hand asking prices per model, from the ads the site knows about.

For now those are the checked listings: each one counts for the model it was matched to, on the
day it was checked. Only matches the visitor chose or that we're fairly sure of are counted, and
prices under MIN_PRICE (the "€1, bieden" kind) are left out. The median is the headline, because
one silly price can't drag it around; the average is shown next to it.
"""
from datetime import date, timedelta
from statistics import mean, median

from . import checks, fetch_ad

PERIODS = (30, 90, 365)
DEFAULT_PERIOD = 90
MIN_ADS = 5       # fewer ads than this and we don't call it a typical price
MIN_PRICE = 100   # below this an asking price is a placeholder, not a price


def known_ads(conn, models):
    """Every priced ad with the model it belongs to: [{model_id, price, seen, check_id, check_ids}]."""
    by_id = {m["id"]: m for m in models}
    ads, seen_ads, all_checks = [], {}, {}
    # The same ad checked again counts once, at its newest price; all its checks are remembered
    # (also the ones without a usable price) so a report can leave its own ad out whichever of
    # those checks it shows.
    for row in conn.execute("SELECT * FROM checks ORDER BY id DESC"):
        key = fetch_ad.ad_key(row)
        all_checks.setdefault(key, set()).add(row["id"])
        if key in seen_ads or (row["asking_price"] or 0) < MIN_PRICE:
            continue
        model = by_id.get(row["model_id"])
        if model is None:
            ranked = checks.match_models(models, row["title"], row["description"] or "")
            if not ranked or checks.confidence(ranked) not in ("high", "medium"):
                seen_ads[key] = None  # unmatched: its older checks don't count either
                continue
            model = ranked[0][1]
        ad = {"model_id": model["id"], "price": row["asking_price"],
              "seen": date.fromisoformat(row["created_at"][:10]), "check_id": row["id"],
              "check_ids": all_checks[key]}  # the same set, so older checks still get added
        seen_ads[key] = ad
        ads.append(ad)
    return ads


def period_of(value):
    return value if value in PERIODS else DEFAULT_PERIOD


def asking_price(ads, model_id, days, today=None, leave_out=None):
    """Median, average and range of a model's asking prices over the last `days` days."""
    since = (today or date.today()) - timedelta(days=days)
    prices = sorted(a["price"] for a in ads if a["model_id"] == model_id and a["seen"] > since
                    and leave_out not in a.get("check_ids", {a["check_id"]}))
    result = {"days": days, "count": len(prices), "enough": len(prices) >= MIN_ADS, "needed": MIN_ADS,
              "others": leave_out is not None}  # a report counts the other ads, not its own
    if prices:
        result.update(median=median(prices), mean=mean(prices), low=prices[0], high=prices[-1])
    return result
