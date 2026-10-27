"""Trek NL: the road and gravel bikes (Trek's category B200) from Trek's own product API.

The search lists each product with its price and model year; the product API (history.trek_product)
gives the spec sheet, the colours and each colour's photo. Like the earlier Trek data this keeps the
Domane+ and FX bikes Trek files under road.
"""
from .common import log

BRAND = "Trek"
SEARCH = ("https://api.trekbikes.com/occ/v2/nl/products/search?query=%3Arelevance%3AallCategories%3AB200"
          "&pageSize=50&currentPage={page}&lang=nl_NL&curr=EUR&fields=FULL")
PRODUCT = "https://www.trekbikes.com/nl/nl_NL/p/{code}/"


def listed(fetcher):
    """[{code, name, price, model_year}] for every product Trek lists under road bikes."""
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
                          "model_year": int(p["marketingModelYear"]) if str(p.get("marketingModelYear") or "").isdigit() else None})
        pages = (data.get("pagination") or {}).get("totalPages") or 0
        page += 1
        if page >= pages:
            return [p for p in found if p["code"] and p["name"]]


def scrape(fetcher, limit=None):
    from .history import trek_product
    bikes = []
    for item in listed(fetcher)[:limit]:
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
