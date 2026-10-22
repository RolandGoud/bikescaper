"""Second-hand asking prices per model, from the ads the site knows about.

For now those are the checked listings: each one counts for the model it was matched to, on the
day it was checked. Only matches the visitor chose or that we're fairly sure of are counted, and
prices under MIN_PRICE (the "€1, bieden" kind) are left out. The median is the headline, because
one silly price can't drag it around; the average is shown next to it.
"""
from datetime import date, timedelta
from statistics import mean, median

from . import checks

PERIODS = (30, 90, 365)
DEFAULT_PERIOD = 90
MIN_ADS = 5       # fewer ads than this and we don't call it a typical price
MIN_PRICE = 100   # below this an asking price is a placeholder, not a price


def known_ads(conn, models):
    """Every priced ad with the model it belongs to: [{model_id, price, seen, check_id}]."""
    by_id = {m["id"]: m for m in models}
    ads = []
    for row in conn.execute("SELECT * FROM checks WHERE asking_price >= ?", (MIN_PRICE,)):
        model = by_id.get(row["model_id"])
        if model is None:
            ranked = checks.match_models(models, row["title"], row["description"] or "")
            if not ranked or checks.confidence(ranked) not in ("high", "medium"):
                continue
            model = ranked[0][1]
        ads.append({"model_id": model["id"], "price": row["asking_price"],
                    "seen": date.fromisoformat(row["created_at"][:10]), "check_id": row["id"]})
    return ads


def period_of(value):
    return value if value in PERIODS else DEFAULT_PERIOD


def asking_price(ads, model_id, days, today=None, leave_out=None):
    """Median, average and range of a model's asking prices over the last `days` days."""
    since = (today or date.today()) - timedelta(days=days)
    prices = sorted(a["price"] for a in ads if a["model_id"] == model_id and a["seen"] > since
                    and a["check_id"] != leave_out)
    result = {"days": days, "count": len(prices), "enough": len(prices) >= MIN_ADS, "needed": MIN_ADS}
    if prices:
        result.update(median=median(prices), mean=mean(prices), low=prices[0], high=prices[-1])
    return result
