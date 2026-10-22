"""Collect each model's own size chart: rider height per frame size, plus stack and reach.

    python -m webapp.seed                    # the site database lists the models to look up
    python -m brand_scrapers.sizing          # all brands
    python -m brand_scrapers.sizing trek --limit 3

Writes webapp/size_charts.json, keyed by model slug. Where a brand publishes rider heights per
model (Trek, Canyon, Cannondale) they are copied as they are. Specialized, Giant, Cube and Factor
only publish geometry: those charts get the model's own sizes, stack and reach, and the site takes
the rider heights from the brand's general size guide. (Stack and reach don't predict a brand's
rider heights well: a fit through the Trek and Canyon charts misses the other brand by 5-8 cm,
while each brand gives the same size the same heights on nearly every model.)
"""
import argparse
import json
import logging
import os
import re
from datetime import date

from .common import ROOT, Fetcher, clean, log

OUT = os.path.join(ROOT, "webapp", "size_charts.json")  # webapp/ is unpacked by every NAS compose file
API_HEADERS = {"Accept": "application/json"}


def size_label(text):
    text = clean(str(text)).upper().replace("CM", "").strip()
    text = {"XXS": "2XS", "XXL": "2XL", "XXXS": "3XS", "M/L": "ML", "SM": "S", "MD": "M", "LG": "L"}.get(text, text)
    return re.sub(r"^(\d\d)(\.0)?$", r"\1", text)


def mm(text):
    m = re.search(r"\d+(?:[.,]\d+)?", str(text))
    return float(m.group(0).replace(",", ".")) if m else None


def heights(text):
    """'176 - 182', '≥ 198' or '≤ 158' (cm) -> (low, high)."""
    nums = [int(float(n)) for n in re.findall(r"\d+(?:\.\d+)?", str(text))]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return (nums[0], nums[0] + 6) if "≥" in text or ">" in text else (nums[0] - 6, nums[0])
    return None


def geometry_table(page):
    """Stack and reach per size from the first HTML table with a Stack row (Specialized, Giant, Cube)."""
    for table in re.findall(r"<table.*?</table>", page, re.S):
        if not re.search(r">\s*(?:<span[^>]*>[A-Z]{1,2}</span>)?\s*Stack\b", table):
            continue
        rows = []
        for row in re.findall(r"<tr.*?</tr>", table, re.S):
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
            # Giant writes each value twice, in mm and inch: keep the mm one.
            cells = [re.sub(r'<span class="value value-inch">.*?</span>', "", c, flags=re.S) for c in cells]
            rows.append([clean(c) for c in cells])
        if not rows:
            continue
        sizes = [size_label(s) for s in rows[0][1:]]
        found = {}
        for row in rows[1:]:
            name = re.sub(r"^[A-Z]{1,2}\s+", "", row[0]).split("(")[0].strip().lower()
            if name in ("stack", "reach"):
                found[name] = [mm(v) for v in row[1:]]
        if "stack" in found and "reach" in found:
            return {s: {"stack": st, "reach": rc} for s, st, rc in zip(sizes, found["stack"], found["reach"])
                    if s and st and rc}
    return {}


def trek(fetcher, model):
    code = re.search(r"/p/(\d+)", model["url"] or "")
    if not code:
        return None
    text = fetcher.get(f"https://api.trekbikes.com/occ/v2/nl/products/{code.group(1)}/sizing")
    if not text:
        return None
    data = json.loads(text)
    sizes = {}
    for group in (data.get("productSizeChart") or {}).get("sizeChartGroups") or []:
        for row in group.get("sizeChartGroups") or []:
            if re.search(r"_(rider)?height_", row.get("id") or "", re.I) and row.get("sizeChartMinCm"):
                sizes[size_label(group["size"].split(" (")[0])] = {"low": round(row["sizeChartMinCm"]),
                                                    "high": round(row["sizeChartMaxCm"])}
    source = "brand" if sizes else "geometry"  # a few models, like the Checkmate, only have geometry
    headers = data.get("geometryDataHeaders") or []
    for entry in data.get("geometryData") or []:
        row = dict(zip(headers, entry.get("geometry") or []))
        size = size_label(row.get("geometryFrameSizeNumber") or row.get("geometryFrameSizeLetter") or "")
        if (size in sizes or source == "geometry") and mm(row.get("geometryFrameStack")) \
                and mm(row.get("geometryFrameReach")):
            sizes.setdefault(size, {}).update(stack=mm(row["geometryFrameStack"]) * 10,
                                              reach=mm(row["geometryFrameReach"]) * 10)
    return sizes and {"source": source, "sizes": sizes}


def canyon(fetcher, model):
    page = model["url"] and fetcher.get(model["url"])
    if not page:
        return None
    sizes = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for variant in data.get("hasVariant") or [] if isinstance(data, dict) else []:
            props = {p.get("name"): p.get("value") for p in variant.get("additionalProperty") or []}
            span = heights(str(props.get("Lichaamslengte") or ""))
            if variant.get("size") and span:
                sizes[size_label(variant["size"])] = {"low": span[0], "high": span[1],
                                                      "stack": mm(props.get("Stack")), "reach": mm(props.get("Reach"))}
    return sizes and {"source": "brand", "sizes": sizes}


def cannondale(fetcher, model):
    page = model["url"] and fetcher.get(model["url"])
    product = page and re.search(r'productSalsifyId\s*=\s*"([^"]+)"', page)
    text = product and fetcher.get(f"https://www.cannondale.com/nl-nl/api/products/{product.group(1)}")
    if not text:
        return None
    sizes = {}
    for item in json.loads(text).get("Data") or []:
        for variant in item.get("Variants") or []:
            if variant.get("IsValid") and variant.get("MinHeight") and variant.get("Size"):
                # Inches, like the size slider on the product page.
                sizes[size_label(variant["Size"].split()[0])] = {"low": round(variant["MinHeight"] * 2.54),
                                                                 "high": round(variant["MaxHeight"] * 2.54)}
    return sizes and {"source": "brand", "sizes": sizes}


def factor(fetcher, model):
    page = model["url"] and fetcher.get(model["url"])
    geo = page and re.search(r'"frameGeometry":\{"geometry":\{"rows":(\[\[.*?\]\]),"headers":(\[.*?\])', page)
    if not geo:
        return None
    rows, headers = json.loads(geo.group(1)), json.loads(geo.group(2))
    found = {r[1].lower(): r[2:] for r in rows if len(r) > 2}
    sizes = {size_label(s): {"stack": mm(st), "reach": mm(rc)}
             for s, st, rc in zip(headers[2:], found.get("stack", []), found.get("reach", [])) if mm(st) and mm(rc)}
    return sizes and {"source": "geometry", "sizes": sizes}


def geometry_page(fetcher, model):
    page = model["url"] and fetcher.get(model["url"])
    sizes = page and geometry_table(page)
    return sizes and {"source": "geometry", "sizes": sizes}


ADAPTERS = {"Trek": trek, "Canyon": canyon, "Cannondale": cannondale, "Factor": factor,
            "Specialized": geometry_page, "Giant": geometry_page, "Cube": geometry_page}


def load_models():
    from webapp import db
    return db.all_models(db.connect())


def run(brands=None, limit=None):
    fetcher = Fetcher()
    try:
        with open(OUT, encoding="utf-8") as fh:
            charts = json.load(fh)["models"]
    except (OSError, ValueError, KeyError):
        charts = {}
    done = {}
    for model in load_models():
        brand = model["brand"]
        if brand not in ADAPTERS or (brands and brand.lower() not in brands):
            continue
        if limit and done.get(brand, 0) >= limit:
            continue
        done[brand] = done.get(brand, 0) + 1
        try:
            chart = ADAPTERS[brand](fetcher, model)
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("%s: %s", model["name"], exc)
            chart = None
        if chart:
            chart.update(brand=brand, name=model["name"], url=model["url"], checked=date.today().isoformat())
            charts[model["slug"]] = chart
            log.info("%s %s: %s sizes (%s)", brand, model["name"], len(chart["sizes"]), chart["source"])
        else:
            log.info("%s %s: no chart", brand, model["name"])
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"models": dict(sorted(charts.items()))}, fh, ensure_ascii=False, indent=1)
    return charts


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("brands", nargs="*", help=", ".join(sorted(ADAPTERS)).lower() + " (default: all)")
    parser.add_argument("--limit", type=int, help="models per brand, for testing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    charts = run([b.lower() for b in args.brands], args.limit)
    print(f"{len(charts)} model charts in {OUT}")


if __name__ == "__main__":
    main()
