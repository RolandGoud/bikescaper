"""Trek NL: the road and gravel bikes (Trek's category B200) from Trek's own product API.

The search lists each product with its price and model year; the product API (history.trek_product)
gives the spec sheet, the colours and each colour's photo. Like the earlier Trek data this keeps the
Domane+ and FX bikes Trek files under road.
"""
import re

from .common import log

BRAND = "Trek"
SEARCH = ("https://api.trekbikes.com/occ/v2/nl/products/search?query=%3Arelevance%3AallCategories%3AB200"
          "&pageSize=50&currentPage={page}&lang=nl_NL&curr=EUR&fields=FULL")
PRODUCT = "https://www.trekbikes.com/nl/nl_NL/p/{code}/"


def model_years(text):
    """The model years Trek lists a product for: "2027" -> [2027]; a bike it carries over "2026-2027" -> [2026, 2027]."""
    years = [int(y) for y in re.findall(r"\b20\d\d\b", str(text or ""))]
    return list(range(min(years), max(years) + 1)) if years else []


def model_year(text):
    """The model year Trek gives a product now, the last one it lists: "2026-2027" -> 2027."""
    return (model_years(text) or [None])[-1]


def listed(fetcher):
    """[{code, name, price, model_year, model_years}] for every product Trek lists under road bikes."""
    found, page = [], 0
    while True:
        try:  # the search answers in XML unless asked for JSON
            data = fetcher.session.get(SEARCH.format(page=page), headers={"Accept": "application/json"}, timeout=60).json()
        except (ValueError, OSError) as exc:
            log.warning("Trek search page %d: %s", page, exc)
            data = {}
        for p in data.get("products") or []:
            price = (p.get("price") or {}).get("value")
            found.append({"code": p.get("code"), "name": (p.get("name") or "").strip(), "price": price,
                          "model_year": model_year(p.get("marketingModelYear")),
                          "model_years": model_years(p.get("marketingModelYear"))})
        pages = (data.get("pagination") or {}).get("totalPages") or 0
        page += 1
        if page >= pages:
            return [p for p in found if p["code"] and p["name"]]


def scrape(fetcher, limit=None):
    from .history import trek_product
    bikes = []
    # Trek lists a bike's next model year next to the one it still sells (Domane AL 2 Gen 4: 80164 for 2027, 41587
    # for 2026), under the same name: the catalogue takes the newest, the year sheets (history.trek_collect) the other.
    items = listed(fetcher)[:limit]
    newest = {}
    for i in items:
        if (i["model_year"] or 0) > (newest.get(i["name"], {}).get("model_year") or 0) or i["name"] not in newest:
            newest[i["name"]] = i
    for item in (i for i in items if newest[i["name"]] is i):
        product = trek_product(fetcher, item["code"])
        if not product or not product["specs"]:
            log.warning("Trek: no spec sheet for %s %s", item["code"], item["name"])
            continue
        colours = product["colours"]
        bikes.append({
            # the short product URL, as the earlier Trek data, the year sheets and the galleries have it
            "name": item["name"], "brand": BRAND, "url": PRODUCT.format(code=item["code"]), "sku": item["code"],
            "price": item["price"], "category": product["category"], "model_year": item["model_year"],
            "specifications": product["specs"], "color_names": colours,
            "image_url": product["image_url"],
            "color_image_urls": [product["colour_image_urls"].get(c) for c in colours],
        })
        log.info("Trek: %s %s (%s)", item["name"], item["model_year"], item["price"])
    return bikes
