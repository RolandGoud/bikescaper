"""Close matches for a model page without ads of its own ("always be selling"): ads matched to other catalogue
models that are the nearest thing to this one, best first.

The ladder, closest first:
  build   another build of the same model page (Synapse Carbon 3 for the Synapse Carbon 2)
  line    the same model line of the brand: another generation, the SL or the frameset (Synapse Carbon 2 RLE,
          the 2021 Synapse Carbon Ultegra)
  brand   the brand's other bikes of the same kind at about the same new price
  similar another brand's bike of the same kind, new price and spec tier
Within a step the nearest new price comes first, then the newest ad; ads still up go before ones gone from the site.
"""
import math

from . import checks

STEPS = ("build", "line", "brand", "similar")
LIMIT = 8
# How far a new price may be off for the brand and other-brand steps (a factor either way).
BRAND_PRICE = 1.5
SIMILAR_PRICE = 1.33


def _price(model):
    return checks.shown_price(model)[0]


def step_of(model, other, info=None):
    """Which step of the ladder `other` is for `model`, or None when it isn't close enough."""
    info = info or {}
    if other["id"] == model["id"]:
        return None
    same_brand = other["brand"] == model["brand"]
    if same_brand and model["brand"] in checks.SITE_BUILD_BRANDS \
            and checks.site_split(other)[0] == checks.site_split(model)[0]:
        return "build"
    if same_brand and checks.family_of(other["name"]) == checks.family_of(model["name"]):
        return "line"
    kind = info.get("kind") or checks.discipline_of(model)
    if kind == "other" or checks.discipline_of(other) != kind:
        return None
    own, theirs = info.get("price") or _price(model), _price(other)
    if not own or not theirs:
        return None
    ratio = max(own, theirs) / min(own, theirs)
    if same_brand and ratio <= BRAND_PRICE:
        return "brand"
    if not same_brand and ratio <= SIMILAR_PRICE:
        tier, their_tier = info.get("tier") or checks.model_tier(model), checks.model_tier(other)
        if not tier or not their_tier or abs(tier - their_tier) <= 1:
            return "similar"
    return None


def close_ads(model, models, matched, limit=LIMIT):
    """[(row, times checked, other model, step)] for the model page's alternates, best first.

    matched is app.matched_ads: {model_id: [(newest row, times checked)]}."""
    by_id = {m["id"]: m for m in models}
    info = {"kind": checks.discipline_of(model), "price": _price(model), "tier": checks.model_tier(model)}
    own = info["price"]
    found = []
    for model_id, ads in matched.items():
        other = by_id.get(model_id)
        if other is None or model_id == model["id"]:
            continue
        step = step_of(model, other, info)
        if step is None:
            continue
        theirs = _price(other)
        distance = abs(math.log(theirs / own)) if own and theirs else 9
        for row, count in ads:
            found.append(((STEPS.index(step), bool(row["removed_at"]), distance,
                           _desc(row["created_at"])), (row, count, other, step)))
    found.sort(key=lambda f: f[0])
    return [f[1] for f in found[:limit]]


def _desc(created_at):
    """Sorts the newest first in an ascending sort."""
    return tuple(-ord(ch) for ch in created_at or "")
