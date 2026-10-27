"""Shared plumbing for the brand adapters: polite fetching, spec labels, photos and output.

Each adapter returns a list of bikes in the shape webapp/seed.py reads:
name, brand, url, sku, price, category, model_year, specifications, color_names,
sizes, image (path under images/) and image_url, and color_image_urls with a photo URL per
colour name (None where the brand shows none), saved as color_images.
"""
import html
import io
import json
import logging
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
log = logging.getLogger("brand_scrapers")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36")


class Fetcher:
    """requests with a browser user agent, a pause between requests per host, and a few retries."""

    def __init__(self, delay=1.5, delays=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        })
        self.delay = delay
        self.delays = delays or {}  # host -> seconds, e.g. a robots.txt crawl-delay
        self._last = {}

    def get(self, url, binary=False):
        host = urlparse(url).netloc
        wait = self.delays.get(host, self.delay) - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=60)
                self._last[host] = time.time()
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                if "charset" not in resp.headers.get("Content-Type", "").lower():
                    resp.encoding = "utf-8"  # requests would guess Latin-1 and mangle names like HANZŌ
                return resp.content if binary else resp.text
            except requests.RequestException as exc:
                log.warning("%s (attempt %d): %s", url, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
        return None


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).replace(" ", " ").strip()


# Brand sites label parts differently. Map the common labels onto the keys the
# Trek and Canyon data use (webapp/reference.py SPEC_LABELS shows them) and keep
# everything else as the brand wrote it.
SPEC_KEYS = {
    "Shifter": ["shifter", "shifters", "shift levers", "schakelhendels", "schakelhendel", "versnellingshendels",
                "shifter/remhendels", "schakel-/remhendels", "shifters/remhendels", "groupset", "groepset",
                "schakelaars"],
    "Shifter_speed": ["speed", "versnellingen"],
    "Achterderailleur": ["achterderailleur", "rear derailleur", "derailleur achter", "derailleur"],
    "Voorderailleur": ["voorderailleur", "front derailleur", "derailleur voor"],
    "Crankstel": ["crankstel", "crankset", "crank", "cranks", "crankset/kettingblad"],
    "Kettingblad": ["kettingblad", "kettingbladen", "chainring"],
    "Bottom bracket": ["bottom bracket", "trapas", "trapaslagers"],
    "Cassette": ["cassette"],
    "Ketting": ["ketting", "chain"],
    "Pedaal": ["pedalen", "pedals", "pedaal"],
    "Frame": ["frame"],
    "Material": ["framemateriaal", "frame material"],
    "Voorvork": ["vork", "fork", "voorvork", "starre vork"],
    "Balhoofdstel": ["balhoofdstel", "balhoofd", "balhoofdlagers", "headset"],
    "As voorwiel": ["front axle", "as voorwiel"],
    "As achterwiel": ["rear axle", "as achterwiel"],
    "Maximale bandenmaat": ["max tire clearance", "maximale bandbreedte", "maximale bandenmaat"],
    "Maximale maat kettingblad": ["max chainring", "max chainring size"],
    "Rem": ["remmen", "rem", "brakes", "voorrem", "front brake", "rem voor", "remset"],
    "Remgreep": ["remhendels", "remgreep", "brake levers"],
    "Remschijf": ["remschijven", "remschijf", "rotors", "rotor", "schijfremrotors", "remschijf voor"],
    "Wiel voor": ["wielen", "wielset", "wheelset", "wheels", "wiel voor", "voorwiel", "front wheel"],
    "Wiel achter": ["achterwiel", "rear wheel", "wiel achter"],
    "Naaf voor": ["voornaaf", "naaf voor", "front hub"],
    "Naaf achter": ["achternaaf", "naaf achter", "rear hub"],
    "Velg": ["velg", "velgen", "rims", "rim"],
    "Spaken": ["spaken", "spokes"],
    "Buitenband": ["banden", "band", "buitenband", "tyres", "tires", "voorband", "front tire", "front tyre",
                   "band voor", "tire", "tyre"],
    "Binnenband": ["binnenband", "binnenbanden", "inner tubes"],
    "Zadel": ["zadel", "saddle"],
    "Zadelpen": ["zadelpen", "seatpost"],
    "Stuur": ["stuur", "handlebar", "handlebars", "stuur/stuurpen"],
    "Stuurpen": ["stuurpen", "stem"],
    "Stuur/stuurpen (geïntegreerd)": ["cockpit", "barstem", "geïntegreerde stuur en -pen"],
    "Stuurlint": ["stuurlint", "tape", "handvat / stuurlint", "bar tape"],
    "Handvatten": ["handvatten", "grips"],
    "Gewicht": ["gewicht", "weight", "fietsgewicht"],
    "Achterband": ["achterband", "rear tire", "rear tyre"],
    "Achterrem": ["achterrem", "rear brake"],
    "Remtype": ["brake type", "remtype"],
    "Naven": ["naven", "hub", "hubs"],
    "Zadelpenklem": ["zadelpenklem", "seat binder", "seat clamp"],
    "Framegewicht": ["framegewicht", "frame weight"],
    "Extra's": ["extra's", "included accessories", "uitrusting", "accessoires"],
    "Wielmaat": ["wielmaat", "wheel size"],
    "Bandenmaat": ["bandenmaat", "recommended tyre size"],
}
# Shop and catalogue details that say nothing about the bike's parts.
SKIP_LABELS = {"product-id", "product id", "model", "model code", "platform", "fietsmaat", "kleur", "kleuren",
               "maat", "maten", "collectie", "configuratie", "manufacturer warranty", "decals", "assembly",
               "astm classification", "finish", "nipples", "bearings", "compatibility", "type interface",
               "gebruik", "weight size", "art. nr.", "prijs*", "compatible components"}
_LABEL_TO_KEY = {label: key for key, labels in SPEC_KEYS.items() for label in labels}


def normalize_specs(pairs):
    """[(label, value)] to a dict with the shared keys filled where a label is known."""
    specs = {}
    for label, value in pairs:
        label, value = clean(label), clean(value)
        if not label or not value or label.lower().rstrip(":") in SKIP_LABELS:
            continue
        key = _LABEL_TO_KEY.get(label.lower().rstrip(":"))
        if key and key not in specs:
            specs[key] = value
        elif label not in specs:
            specs[label] = value
    return specs


def parse_price(text):
    """'€ 6.499,00', '6499', '4699.0' or 13999 to a float."""
    if text is None or text == "":
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = re.sub(r"[^\d,.]", "", str(text))
    if re.search(r",\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{3}$", s) or re.search(r"\.\d{3}\.", s):
        s = s.replace(".", "")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def is_ebike(*texts):
    low = " ".join(t or "" for t in texts).lower()
    return bool(re.search(r"elektrisch|e-bike|ebike|\beplus\b|e\+|\bturbo\b|\bneo\b|hybrid|\bhybride\b", low))


def size_name(text):
    """One way of writing sizes across brands: XXS -> 2XS, Scott's 'XL58' -> 58, 'M-L' -> ML."""
    text = clean(str(text)).upper()
    m = re.match(r"^(?:[2-3]?X*[SML]|X+L)\s*/?\s*(\d\d)$", text)
    if m:
        return m.group(1)
    text = text.replace("-", "").replace("/", "")
    return {"XXS": "2XS", "XXL": "2XL", "XXXS": "3XS", "XXXL": "3XL"}.get(text, text)


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def frame(img, ratio=16 / 9, margin=0.05):
    """Crop a product photo on white to the bike and pad it to the 16:9 tiles, so every brand fills its tile alike."""
    from PIL import Image, ImageOps
    box = ImageOps.invert(img.convert("L")).point(lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        return img
    bike = img.crop(box)
    w = max(bike.width, bike.height * ratio) * (1 + 2 * margin)
    out = Image.new("RGB", (round(w), round(w / ratio)), "white")
    out.paste(bike, ((out.width - bike.width) // 2, (out.height - bike.height) // 2))
    return out


def trim(img):
    """A close-up or other angle: cut off the white bars some brands bake around it, so it fills the frame.
    A bike shot on white (the corners around it are white) is framed like the main photo instead."""
    from PIL import ImageOps, ImageStat
    box = ImageOps.invert(img.convert("L")).point(lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        return img
    shot = img.crop(box)
    w, h, i, n = shot.width, shot.height, 4, 10  # a little in from the corner: past JPEG's halo round the edge
    corners = [shot.crop(b) for b in ((i, i, n, n), (w - n, i, w - i, n), (i, h - n, n, h - i), (w - n, h - n, w - i, h - i))]
    if sum(ImageStat.Stat(c.convert("L")).mean[0] > 235 for c in corners) >= 3:
        return frame(img)
    return shave(shot)


def shave(shot, most=6):
    """Cut the light seam JPEG leaves where a white bar met a dark photo: edge lines much brighter than the photo just inside."""
    from PIL import ImageStat

    def mean(box):
        return ImageStat.Stat(shot.crop(box).convert("L")).mean[0]

    w, h = shot.size
    if min(w, h) < 8 * most:
        return shot
    d = most + 2  # how far in the photo itself is measured
    left_in, right_in = mean((d, 0, d + 1, h)), mean((w - d - 1, 0, w - d, h))
    top_in, bottom_in = mean((0, d, w, d + 1)), mean((0, h - d - 1, w, h - d))
    left = top = 0
    right, bottom = w, h
    while left < most and mean((left, 0, left + 1, h)) > left_in + 20:
        left += 1
    while w - right < most and mean((right - 1, 0, right, h)) > right_in + 20:
        right -= 1
    while top < most and mean((0, top, w, top + 1)) > top_in + 20:
        top += 1
    while h - bottom < most and mean((0, bottom - 1, w, bottom)) > bottom_in + 20:
        bottom -= 1
    return shot.crop((left, top, right, bottom))


def save_image(fetcher, brand, name, url, width=1000):
    """Download one product photo as a JPEG under images/<Brand>/ and return its path under images/."""
    if not url:
        return None
    rel = f"{brand}/{slug(name)}.jpg"
    path = os.path.join(ROOT, "images", rel)
    if os.path.exists(path):
        return rel
    data = fetcher.get(url, binary=True)
    if not data:
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.split()[-1])
            img = bg
        img = frame(img.convert("RGB"))
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception as exc:  # a broken or unsupported image shouldn't stop the run
        log.warning("image %s: %s", url, exc)
        return None
    return rel


def save_colour_images(fetcher, bike):
    """Download the photo of each colour in color_image_urls; color_images lists their paths, None where there is none."""
    urls = bike.get("color_image_urls") or []
    bike["color_images"] = [save_image(fetcher, bike["brand"], f"{bike['name']} colour {colour}", url) if url else None
                            for colour, url in zip(bike.get("color_names") or [], urls)]
    return bike["color_images"]


def dedupe(bikes):
    """One entry per model name: the newest model year, then the first seen."""
    best = {}
    for bike in bikes:
        key = bike["name"].lower()
        if key not in best or (bike.get("model_year") or 0) > (best[key].get("model_year") or 0):
            best[key] = bike
    return list(best.values())


def write_snapshot(brand, bikes, stamp=None):
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(ROOT, "data", brand)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{brand.lower()}_bikes_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bikes, fh, ensure_ascii=False, indent=2)
    return os.path.relpath(path, ROOT)
