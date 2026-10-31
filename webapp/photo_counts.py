"""How many catalogue photos each brand, model and model year has, for the admin page.

A photo counts once per model year, the way the model page can show it: for the year of our own
scrape the main photo, the colour photos and the other angles (data/galleries/), and for an
earlier year the photo, colour photos and angles of that year's archived sheet (data/years/).
Only files that are in images/ count. A model without a scrape date (an archived line) puts its
own photos under None, "year unknown".
"""
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _paths(value):
    """Every photo path in a str, a list or a {colour: path or [paths]} dict."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _paths(v)
    elif isinstance(value, list):
        for v in value:
            yield from _paths(v)


def model_photos(model, galleries, exists=None):
    """{model year or None: set of photo paths under images/} for one model."""
    exists = exists or (lambda p: os.path.isfile(os.path.join(ROOT, "images", p)))
    found = {}
    own = int(model["seen_on"][:4]) if model.get("seen_on") else None
    found[own] = set(_paths(model.get("image"))) | set(
        _paths([c.get("image") for c in model.get("colorways") or []])) | set(
        _paths(galleries.get(model.get("url")) or {}))
    for year, entry in ((model.get("year_specs") or {}).get("years") or {}).items():
        if int(year) == own:
            continue  # the model page shows our own scrape for that year, never the sheet's photos
        found.setdefault(int(year), set()).update(
            _paths([entry.get("image"), entry.get("colour_images") or {}, entry.get("colour_angles") or {}]))
    return {y: {p for p in ps if p and exists(p)} for y, ps in found.items()}


def overview(models, galleries, exists=None):
    """{"years": [...], "brands": [...]} with per brand its totals and its models, each model with
    {name, slug, years: {year: count}, total}; a brand's "shown" are the years any of its models has
    photos for. None (year unknown) sorts last among the years."""
    brands, all_years = {}, set()
    for m in models:
        years = {y: len(ps) for y, ps in model_photos(m, galleries, exists).items() if ps}
        all_years |= set(years)
        brands.setdefault(m["brand"], []).append(
            {"name": m["name"], "slug": m["slug"], "years": years, "total": sum(years.values())})
    order = sorted(all_years, key=lambda y: (y is None, y or 0))
    out = []
    for brand in sorted(brands):
        rows = sorted(brands[brand], key=lambda r: r["name"].lower())
        out.append({
            "brand": brand, "models": rows, "count": len(rows),
            "total": sum(r["total"] for r in rows),
            "years": {y: sum(r["years"].get(y, 0) for r in rows) for y in order},
            "shown": [y for y in order if any(r["years"].get(y) for r in rows)],  # columns of the per-model table
            "none": sum(1 for r in rows if not r["total"]),
            "one": sum(1 for r in rows if r["total"] == 1),
        })
    return {"years": order, "brands": out}
