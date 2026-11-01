"""Bianchi: road, gravel, cyclocross and TT bikes from bianchi.com/en (there is no Dutch site).

The site is WooCommerce: its public Store API (/wp-json/wc/store/v1/products) lists every build
with the recommended retail price in euro, the groupset (short description) and the colours.
The product page adds the spec sheet (grey label, value below), the geometry table (size, A..Y;
X is reach and Y is stack) and each colour's photo (data-product_variations).

Bianchi sells one build of a model under the same name for several seasons ("Oltre Comp",
2024 to 2027), so the build's groupset goes into the name, and the model year is read from the
product code: its second letter steps one a season (YTB23 = 2024, YUB = 2025, YVB = 2026,
YWB = 2027; framesets start with X).
"""
import html
import json
import re

from .common import clean, first_of_each, is_ebike, log, normalize_specs, parse_price, size_name

BRAND = "Bianchi"
BASE = "https://www.bianchi.com/en"
API = BASE + "/wp-json/wc/store/v1/products?per_page=100&page={page}"
CATEGORIES = {  # piece of the product URL -> category; mountain, city, junior and e-bikes are left out
    "/road/aero/": "Aero Race",
    "/road/all-rounder/": "All-Rounder",
    "/road/tt-triathlon/": "Triathlon / TT",
    "/road/cyclocross/": "Cyclocross",
    "/gravel/racing/": "Gravel",
    "/gravel/adventure/": "Gravel",
}
SEASON = {letter: 2021 + i for i, letter in enumerate("QRSTUVWXYZ")}
LABELS = {"grips / extensions": "Stuurlint", "tire": "Buitenband", "rotor": "Remschijf", "shifters": "Shifter",
          "wheels": "Wiel voor", "brake lever": "Remgreep", "brake": "Rem", "seatpost clamp": "Zadelpenklem",
          "seatpost screw": None, "frame kit": "Frame",
          # a few pages are only in Italian
          "telaio": "Frame", "forcella": "Voorvork", "serie sterzo": "Balhoofdstel", "comandi": "Shifter",
          "guarnitura": "Crankstel", "pacco pignoni": "Cassette", "deragliatore posteriore": "Achterderailleur",
          "deragliatore anteriore": "Voorderailleur", "movimento centrale": "Bottom bracket", "catena": "Ketting",
          "freni": "Rem", "dischi": "Remschijf", "leve freno": "Remgreep", "ruote": "Wiel voor",
          "coperture": "Buitenband", "attacco manubrio": "Stuurpen", "piega": "Stuur", "reggisella": "Zadelpen",
          "sella": "Zadel", "morsetto reggisella": "Zadelpenklem"}
WORDS = {"di2": "Di2", "etap": "eTap", "axs": "AXS", "grx": "GRX", "xplr": "XPLR", "sram": "SRAM", "e1": "E1",
         "rc": "RC", "icr": "ICR", "drs": "DRS", "pro": "Pro", "comp": "Comp", "race": "Race", "alu": "AL"}


def model_year(sku):
    m = re.match(r"^[XY]([Q-Z])B", sku or "")
    return SEASON.get(m.group(1)) if m else None


def word_case(text):
    """Bianchi writes the same thing as "Oltre COMP" and "Oltre Comp", "DURA-ACE DI2" and "Dura-Ace Di2"."""
    out = []
    for word in text.split():
        low = word.lower()
        if low in WORDS:
            out.append(WORDS[low])
        elif word.isupper() and len(word) > 3 and word.isalpha():
            out.append(word.title())
        else:
            out.append(word)
    return " ".join(out)


def groupset(short_description, sku):
    """"Ultegra Di2 12sp – 4iiii Power Meter – NEW YWB28" -> "Ultegra Di2"; None for a frameset or an edition."""
    text = clean(short_description).replace(sku or "\0", " ")
    text = re.split(r"\s+[–—-]\s+|\s+\|\s+", text.strip())[0]
    if re.search(r"(?i)frameset|kit telaio|limited edition", text):
        return None
    text = re.sub(r"(?i)\b(?:\d\s*[x×]\s*)?\d{1,2}\s*(?:sp|ps|speed)\b", " ", text)
    text = re.sub(r"(?i)\bnew\b|\bpwm\b|\bpower\s*meter\b|\b4iiii\b|\bquarq\b", " ", text)
    text = re.sub(r"(?i)\bdura[\s-]?ace\b[\s-]*|\bdurace\b\s*", "Dura-Ace ", text)
    text = re.sub(r"(?i)^(?:shimano|sram)\s+", "", text.strip())
    return word_case(re.sub(r"\s+", " ", text).strip(" -–")) or None


def base_name(name):
    """"Oltre Comp – NEW", "Infinito PRO – Frameset", "Oltre RC – Team Replica 2026" -> tidy names."""
    name = clean(html.unescape(name))
    name = re.sub(r"\s+[–—-]\s+NEW$", "", name, flags=re.I)
    name = re.sub(r"\s+[–—-]\s+", " ", name)
    name = re.sub(r"\s+20\d\d$", "", name)
    return word_case(name)


def colour_name(term):
    """"OK – Celeste: Celeste metallico / Logo CK16 [Full Glossy]" -> "Celeste"; "ZN - CK Metallic / Graphite" -> as is
    without the code."""
    text = re.sub(r"^[A-Z0-9]{2}\s*[–—-]\s*", "", clean(html.unescape(term)))
    text = text.split(":")[0] if ":" in text else text
    return re.sub(r"\s*\[[^\]]*\]$", "", text).strip()


def same_colour(a, b):
    return a == b or a.startswith(b + "-") or b.startswith(a + "-")


def category_of(url):
    return next((label for part, label in CATEGORIES.items() if part in url), None)


def products(fetcher):
    found = {}
    for page in range(1, 11):
        try:
            batch = json.loads(fetcher.get(API.format(page=page)) or "[]")
        except ValueError:
            batch = []
        for p in batch if isinstance(batch, list) else []:
            found[p["id"]] = p
        if len(batch) < 100:
            break
    return list(found.values())


def geometry(page):
    """(sizes, {size: {"stack", "reach"}}) from the size table: first column the size (470 = 47), X reach, Y stack."""
    for table in re.findall(r"<table.*?</table>", page or "", re.S):
        rows = [[clean(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
                for row in re.findall(r"<tr.*?</tr>", table, re.S)]
        if not rows or rows[0][:1] != ["SIZE"]:
            continue
        head = rows[0]
        sizes, geo = [], {}
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            size = row[0].upper()
            # 470 is 47; the gravel bikes go XS, SM, MD, LG, XL: Bianchi's five letter sizes, S to L
            size = str(int(size) // 10) if re.fullmatch(r"\d{3}", size) else {"SM": "S", "MD": "M", "LG": "L"}.get(
                size, size_name(size))
            sizes.append(size)
            cells = dict(zip(head, row))
            try:
                stack, reach = float(cells["Y"].replace(",", ".")), float(cells["X"].replace(",", "."))
            except (KeyError, ValueError):
                continue
            if stack > reach:  # the table's letters, checked: stack is always the longer of the two
                geo[size] = {"stack": stack, "reach": reach}
        return sizes, geo
    return [], {}


def parse(page, url, product=None):
    product = product or {}
    pairs = []
    for label, value in re.findall(r'<span style="color: #808080;?">([^<]+)</span>\s*</p>\s*<p>(.*?)</p>', page or "", re.S):
        pairs.append((label, value))
    m = re.search(r'data-product_variations="([^"]+)"', page or "")
    try:
        variations = json.loads(html.unescape(m.group(1))) if m else []
    except ValueError:
        variations = []
    terms = {t["slug"]: t["name"] for a in product.get("attributes") or [] for t in a.get("terms") or []}
    colours, colour_images = [], []
    for slug, name in terms.items():
        # the variation names the colour by the term's slug ("zn") or a longer one ("zn-ck-metallic-graphite")
        image = next(((v.get("image") or {}).get("full_src") or (v.get("image") or {}).get("url") for v in variations
                      if same_colour((v.get("attributes") or {}).get("attribute_pa_color") or "", slug)), None)
        if colour_name(name) not in colours:
            colours.append(colour_name(name))
            colour_images.append(image)
    code = re.search(r"\b[XY][Q-Z]B[0-9A-Z]{2}\b", clean(product.get("short_description")))
    sku = product.get("sku") or (code.group(0) if code else "")
    build = groupset(product.get("short_description"), sku)
    name = base_name(product.get("name") or "")
    sizes, _geo = geometry(page)
    price = parse_price((product.get("prices") or {}).get("price"))
    og = re.search(r'<meta property="og:image" content="([^"]+)"', page or "")
    return {
        "name": f"{name} {build}" if build else name,
        "brand": BRAND,
        "url": url,
        "sku": sku,
        "price": price or None,
        "category": category_of(url) or "",
        "model_year": model_year(sku),
        "specifications": normalize_specs(first_of_each(pairs, LABELS)),
        "color_names": colours,
        "sizes": sizes,
        "image_url": next((i for i in colour_images if i), None) or (og.group(1) if og else None),
        "color_image_urls": colour_images,
    }


def scrape(fetcher, limit=None):
    """Every build on the site, older seasons included (dedupe keeps the newest; history.py the rest)."""
    bikes = []
    for product in products(fetcher):
        if limit is not None and len(bikes) >= limit:
            break
        url = product.get("permalink") or ""
        if not category_of(url) or is_ebike(product.get("name"), url):
            continue
        page = fetcher.get(url)
        if not page:
            log.warning("Bianchi: no page for %s", url)
            continue
        bike = parse(page, url, product)
        bikes.append(bike)
        log.info("Bianchi: %s %s (%s)", bike["name"], bike["model_year"], bike["price"])
    return bikes
