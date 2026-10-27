"""Scores for the admin page: how good an ad's photos are and how complete and consistent its text is.

Both start at 10 and lose points per rule, and each lost point comes with its reason, so the admin
page can show why an ad scored what it did."""
import re

from . import bike_fit
from .checks import BAD, WARN, split_title

PROOF = re.compile(r"aankoopbewijs|factuur|bon\b|kassabon|invoice|receipt", re.I)
# A generation number in a clash ("Gen 3" against our "Gen 4") rather than a version word (SL against SLR).
GEN = re.compile(r"^(gen|generatie)?\s*\d$", re.I)


def missing(report, listing):
    """What the ad doesn't say: year, size, groupset, condition, colour, proof (of purchase)."""
    claims = report["claims"]
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    return [key for key, gone in (("year", claims["year"] is None), ("size", claims["size"] is None),
                                  ("groupset", claims["groupset"] is None), ("condition", claims["condition"] is None),
                                  ("colour", not (split_title(listing.get("title") or "").get("colour")
                                                 or report.get("colourway") or report.get("photo_year"))), ("proof", not PROOF.search(text))) if gone]


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


def ad_score(listing, report):
    """(score out of 10, [(points lost, reason key, detail)])."""
    lost = []
    gaps = [k for k in missing(report, listing) if k in ("year", "size", "groupset", "condition")]
    for key in gaps[:4]:
        lost.append((1, "no_" + key, None))
    if not report.get("model"):
        return min(4, 10 - len(lost)), lost + [(0, "no_model", None)]
    clashes = (report.get("name_check") or {}).get("conflicts") or []
    if clashes:
        lost.append((3, "name_clash", " / ".join(f"{ours} ↔ {theirs}" for ours, theirs in clashes[:2])))
    if (report.get("age") or {}).get("status") == BAD or report.get("material_alert"):
        lost.append((2, "impossible", None))
    down = [r for r in (report.get("specs") or {}).get("rows", []) if r.get("step", 0) < 0]
    if down:
        lost.append((min(2, len(down)), "downgraded", ", ".join(str(r["part"]) for r in down[:2])))
    value = report.get("value") or {}
    asking, high = listing.get("asking_price"), value.get("high")
    if value.get("status") == BAD or (value.get("status") == WARN and asking and high and asking > 1.25 * high):
        lost.append((1, "price", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


def photo_score(n, paths):
    """(score out of 10, [(points lost, reason key, detail)]) for an ad with n photos, of which paths are the
    files we stored (the others only count), or (None, []) for an ad typed in without photos."""
    if not n:
        return None, []
    looks = [q for q in (bike_fit.photo_quality(p) for p in paths) if q]
    lost = []
    if n < 6:
        lost.append((5 if n == 1 else 3 if n <= 3 else 1, "few_photos", str(n)))
    if looks:
        if not any(q["side"] for q in looks):
            lost.append((2, "no_side", None))
        if sum(1 for q in looks if not q["side"]) < 2:
            lost.append((2, "no_details", None))
        half = len(looks) / 2
        for key in ("blurry", "dark", "small"):
            if sum(1 for q in looks if q[key]) > half:
                lost.append((1, key, None))
        if any(q["stock"] for q in looks):
            lost.append((3, "stock", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


MISSING = ("year", "size", "groupset", "condition", "colour", "proof")
PROBLEMS = ("tier", "generation", "catalogue", "other_word", "brand", "low")


def _week(day):
    from datetime import date
    y, w, _d = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def summarise(items):
    """The admin page's numbers from one entry per ad: {"day", "brand", "matched", "confidence",
    "missing", "problems", "ad", "photo"}. Totals, plus the same per week and per month for the charts."""
    n = len(items)

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
                 "problems": {k: sum(k in it["problems"] for it in group) for k in PROBLEMS}}
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
        "shaky_brands": sorted(((b, round(100 * c / len(shaky))) for b, c in brands.items()), key=lambda x: -x[1]),
        "week": periods(_week),
        "month": periods(lambda day: day[:7]),
    }
