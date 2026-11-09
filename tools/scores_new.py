"""Scores for the admin page: how good an ad's photos are and how complete and consistent its text is,
measured against what the improve-your-ad wizard (the Selling page) asks a seller for.

Both start at 10 and lose points per rule, and each lost point comes with its reason, so the admin
page can show why an ad scored what it did."""
import re

from webapp import bike_fit
from webapp.checks import BAD, WARN, split_title

PROOF = re.compile(r"\b(?:aankoopbewijs|factuur|bon|kassabon|bonnetje|invoice|receipt)\b", re.I)
# A generation number in a clash ("Gen 3" against our "Gen 4") rather than a version word (SL against SLR).
GEN = re.compile(r"^(gen|generatie)?\s*\d$", re.I)


def missing(report, listing):
    """What the ad doesn't say: year, size, groupset, condition, colour, proof (of purchase)."""
    claims = report["claims"]
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    return [key for key, gone in (("year", claims["year"] is None), ("size", claims["size"] is None),
                                  ("groupset", claims["groupset"] is None), ("condition", claims["condition"] is None),
                                  ("colour", not (split_title(listing.get("title") or "").get("colour")
                                                 or (not report.get("colour_from_photos")
                                                     and (report.get("colourway") or (report.get("photo_year") or {}).get("colour"))))),
                                  ("proof", not (PROOF.search(text) or report.get("receipt")))) if gone]


def match_problems(report):
    """Why a match is shaky, as keys of PROBLEMS; empty when it's a sure match."""
    claims, name = report["claims"], report.get("name_check") or {}
    if not claims.get("brand"):
        return ["brand"]
    if not report.get("model"):
        return ["catalogue"]
    out = []
    clashes = name.get("conflicts") or []
    if any(GEN.match(str(ours)) or GEN.match(str(theirs)) for ours, theirs in clashes):
        out.append("generation")
    if any(not (GEN.match(str(ours)) or GEN.match(str(theirs))) for ours, theirs in clashes):
        out.append("tier")
    if name.get("extra"):
        out.append("other_word")
    if str(getattr(report.get("confidence"), "text", "")) == "low" and not out:
        out.append("low")
    return out


# What the improve-your-ad wizard (the Selling page) asks a seller for, and what an ad loses without it.
# Year and size are the first things a buyer asks, so they cost the most.
AD_GAPS = (("year", 2), ("size", 2), ("groupset", 1), ("condition", 1), ("proof", 1), ("service", 1))
SERVICE = re.compile(r"onderhoud|onderhouden|service|beurt|\bkm\b|kilometer", re.I)  # seller.SERVICE
SHORT_TEXT = 25  # words of description below which an ad says too little to go on


def ad_score(listing, report):
    """(score out of 10, [(points lost, reason key, detail)]), measured against what the improve-your-ad
    wizard asks for: year, size, groupset, condition, invoice, service and mileage, and an ad that adds up."""
    lost = []
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    gaps = set(missing(report, listing))
    if not SERVICE.search(text):
        gaps.add("service")
    for key, points in AD_GAPS:
        if key in gaps:
            lost.append((points, "no_" + key, None))
    words = len((listing.get("description") or "").split())
    if words < SHORT_TEXT:
        lost.append((1, "short_text", str(words)))
    if not report.get("model"):
        return min(3, max(0, 10 - sum(p for p, _k, _d in lost))), lost + [(0, "no_model", None)]
    clashes = (report.get("name_check") or {}).get("conflicts") or []
    if clashes:
        lost.append((3, "name_clash", " / ".join(f"{ours} ↔ {theirs}" for ours, theirs in clashes[:2])))
    if (report.get("age") or {}).get("status") == BAD or report.get("material_alert"):
        lost.append((3, "impossible", None))
    down = [r for r in (report.get("specs") or {}).get("rows", []) if r.get("step", 0) < 0]
    if down:
        lost.append((min(3, len(down)), "downgraded", ", ".join(str(r["part"]) for r in down[:3])))
    value = report.get("value") or {}
    asking, high = listing.get("asking_price"), value.get("high")
    if value.get("status") == BAD:
        lost.append((2, "price", None))
    elif value.get("status") == WARN and asking and high and asking > 1.25 * high:
        lost.append((1, "price", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


# The wizard's photo step asks for 10 shots: the whole bike from both sides and from the front three-quarter,
# and seven close-ups (derailleur, chainrings, shifters, brakes, frame sticker, rim, tyre).
WANTED_PHOTOS = 10
FEW_PHOTOS = {1: 6, 2: 5, 3: 5, 4: 4, 5: 3, 6: 3, 7: 2, 8: 1, 9: 1}  # points lost for n photos
WANTED_DETAILS = 7


def photo_score(n, paths):
    """(score out of 10, [(points lost, reason key, detail)]) for an ad with n photos, of which paths are the
    files we stored (the others only count), or (None, []) for an ad typed in without photos. Measured
    against the wizard's 10 shots."""
    if not n:
        return None, []
    looks = [(q, p) for q, p in ((bike_fit.photo_quality(p), p) for p in paths) if q]
    lost = []
    if n < WANTED_PHOTOS:
        lost.append((FEW_PHOTOS[min(n, 9)], "few_photos", str(n)))
    if looks:
        sides = {bike_fit.faces_left(p) for q, p in looks if q["side"]} - {None}
        if not any(q["side"] for q, _p in looks):
            lost.append((3, "no_side", None))
        elif False not in sides:  # bars on the right: the drive side, the shot buyers look at first
            lost.append((1, "no_drive_side", None))
        elif True not in sides:
            lost.append((1, "one_side", None))
        details = sum(1 for q, _p in looks if not q["side"])
        if details < 2:
            lost.append((3, "no_details", str(details)))
        elif details < 4:
            lost.append((2, "no_details", str(details)))
        elif details < 6:
            lost.append((1, "no_details", str(details)))
        half = len(looks) / 2
        for key in ("blurry", "dark", "small"):
            bad = sum(1 for q, _p in looks if q[key])
            if bad > half:
                lost.append((2, key, str(bad)))
            elif bad:
                lost.append((1, key, str(bad)))
        if any(q["stock"] for q, _p in looks):
            lost.append((3, "stock", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


MISSING = ("year", "size", "groupset", "condition", "colour", "proof")
PROBLEMS = ("tier", "generation", "catalogue", "other_word", "brand", "low")


def _week(day):
    from datetime import date
    y, w, _d = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


BRAND_LINES = 5  # the chart's colours run out after six lines: the top five brands plus the rest


def summarise(items):
    """The admin page's numbers from one entry per ad: {"day", "brand", "matched", "confidence",
    "missing", "problems", "ad", "photo"}. Totals, plus the same per week and per month for the charts."""
    n = len(items)
    per_brand = {}
    for it in items:
        per_brand[it["brand"] or "?"] = per_brand.get(it["brand"] or "?", 0) + 1
    ranked = sorted(per_brand.items(), key=lambda x: (-x[1], x[0]))
    brand_keys = [b for b, _c in ranked[:BRAND_LINES]] + (["other"] if len(ranked) > BRAND_LINES else [])

    def brand_key(it):
        b = it["brand"] or "?"
        return b if b in brand_keys else "other"

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    def periods(key):
        out = {}
        for it in items:
            out.setdefault(key(it["day"]), []).append(it)
        return [{"label": label,
                 "ads": len(group),
                 "missing": {k: round(100 * sum(k in it["missing"] for it in group) / len(group)) for k in MISSING},
                 "problems": {k: sum(k in it["problems"] for it in group) for k in PROBLEMS},
                 "matched": {"matched": sum(it["matched"] for it in group),
                             "unmatched": sum(not it["matched"] for it in group)},
                 "brands": {k: sum(brand_key(it) == k for it in group) for k in brand_keys}}
                for label, group in sorted(out.items())]

    shaky = [it for it in items if it["problems"]]
    brands = {}
    for it in shaky:
        brands[it["brand"] or "?"] = brands.get(it["brand"] or "?", 0) + 1
    return {
        "ads": n,
        "matched": sum(it["matched"] for it in items),
        "confidence": {lvl: sum(it["confidence"] == lvl for it in items) for lvl in ("high", "medium", "low")},
        "photo": mean(it["photo"] for it in items),
        "ad": mean(it["ad"] for it in items),
        "missing": {k: round(100 * sum(k in it["missing"] for it in items) / n) if n else 0 for k in MISSING},
        "problems": {k: sum(k in it["problems"] for it in items) for k in PROBLEMS},
        "brands": {k: sum(brand_key(it) == k for it in items) for k in brand_keys},
        "shaky_brands": sorted(((b, round(100 * c / len(shaky))) for b, c in brands.items()), key=lambda x: -x[1]),
        "week": periods(_week),
        "month": periods(lambda day: day[:7]),
    }
