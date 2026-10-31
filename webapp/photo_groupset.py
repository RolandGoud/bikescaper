"""Read the groupset from an ad's photos, for ads whose text doesn't name it.

Sellers often leave the groupset out but photograph the crankset, the rear derailleur or the
shifters, which carry the series name ("105", "ULTEGRA", "FORCE") and a shape that dates the
generation (11-speed R7000 against 12-speed R7100). A vision model reads that from the photos the
check already keeps (webapp/ad_photos.py).

Two sources, the first found wins:

- webapp/photo_groupsets.json: read by eye, keyed like fetch_ad.ad_key. Also the way to correct a
  wrong automatic read.
- The Claude API, when ANTHROPIC_API_KEY is set in the container: once per check, in the background
  after its photos are stored, kept in ad-photos/<check id>/groupset.json. Without a key nothing
  is sent anywhere and the report works as before.

The same read names the crankset on its own (often swapped, or another series than the rest), the
tyres and the frame's material, which fill in those rows when the ad's text doesn't name them, and
reads a purchase receipt when a photo shows one (date, shop, bike, price; never the buyer's details)
for the age check and as proof of purchase.

A read counts for the spec comparison only when it's sure enough (high or medium) and names a
series we know (reference.GROUPSETS); "Shimano, 11-speed" with no series stays "Not stated".
"""
import base64
import io
import json
import os
import sys
import threading
from datetime import date

from PIL import Image

HAND_FILE = os.path.join(os.path.dirname(__file__), "photo_groupsets.json")
CACHE_NAME = "groupset.json"
MODEL = os.environ.get("PHOTO_GROUPSET_MODEL", "claude-opus-5-5")
MAX_PHOTOS = 20       # all of an ad's photos, up to 20: the crankset close-up is often one of the last (check 63: photo 9)
MAX_SIDE = 1024       # px; the series name on a crank arm is still readable at this size
USED = ("high", "medium")

PROMPT = """These are the photos of a second-hand bike ad. Its text often doesn't say which parts the bike has.

Identify the drivetrain groupset from what is visible: the series name printed on the crank arm, \
rear derailleur, front derailleur or shifters, and the shape of those parts (which tells \
generations apart, e.g. Shimano 105 R7000 11-speed against R7100 12-speed, or SRAM AXS against \
mechanical). Wireless shifting shows as no gear cables and a battery on the derailleur (SRAM AXS) \
or no shift cables at the levers (Shimano Di2).

Rules:
- Only name a series you can actually see evidence for. A logo you can read is "high"; a clear \
shape match without a readable logo is "medium"; a guess from a photo of the whole bike is "low". \
If the drivetrain isn't visible at all, use "none" and leave series empty.
- When parts of different series are mixed (a 105 crank with Ultegra derailleurs), name the \
shifters' and rear derailleur's series and say so in the evidence.
- Ignore the bike brand's own parts (wheels, cockpit) and any text that isn't on a drivetrain part.
- The evidence is one or two short sentences saying which photo shows what, in English and in Dutch.

Also identify the crankset on its own, because it is often swapped or of another series than the \
rest: the brand, series and model code printed on the crank arm or the chainrings (e.g. Shimano 105 \
FC-R7000, SRAM Force, Campagnolo Chorus, FSA Gossamer, Rotor Aldhu, Praxis Zayante), or the shape \
when no print is readable. The same confidence rules apply; "none" when no photo shows the crankset. \
Its evidence is about the crankset alone.

Also read the tyres: brand, model and width as printed on the sidewall (e.g. Continental Grand Prix \
5000, 28 mm; Schwalbe One, 25 mm), with the same confidence rules and evidence about the tyres alone.

Also read the frame: its material (carbon, aluminium, steel or titanium) from the print on the frame \
(e.g. "OCLV Carbon", "500 Series OCLV", "ALR", "Columbus", "Ti"), welds and tube shapes, and that print \
as written. "high" when a print names the material, "medium" from clear welds or tube shapes only.

Also say whether one of the photos shows a purchase receipt or invoice for the bike (a till receipt, \
an invoice, an order confirmation). If so, read from it only: the purchase date, the shop, the bike \
as written on it (brand, model, and the model year when printed), and the price paid for the bike. \
Never copy the buyer's name, address, phone, e-mail or a frame number. "high" when you can read it, \
"medium" when partly readable, "none" and shown false when no photo shows one.
Photos are numbered from 1 in the order given."""

# 2: the crankset is read too; 3: and the tyres, the frame and a receipt. An older read is read again for them.
READ_VERSION = 3
NEWER_PARTS = ("crankset", "tyres", "frame", "receipt")  # what a read of an older version doesn't have

SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string", "enum": ["Shimano", "SRAM", "Campagnolo", "other", "unknown"]},
        "series": {"type": ["string", "null"], "description": "e.g. 105, Ultegra, Dura-Ace, Tiagra, GRX, Rival, Force, Chorus"},
        "model_code": {"type": ["string", "null"], "description": "e.g. R7000, R8170, 4700, when the shape or print shows it"},
        "speeds": {"type": ["integer", "null"]},
        "electronic": {"type": ["boolean", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
        "photos": {"type": "array", "items": {"type": "integer"}, "description": "the photos that show it"},
        "evidence_en": {"type": "string"},
        "evidence_nl": {"type": "string"},
        "crankset": {
            "type": "object",
            "properties": {
                "brand": {"type": ["string", "null"], "description": "e.g. Shimano, SRAM, Campagnolo, FSA, Rotor"},
                "series": {"type": ["string", "null"], "description": "e.g. 105, Ultegra, Force, Gossamer"},
                "model_code": {"type": ["string", "null"], "description": "e.g. FC-R7000, FC-R8100"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                "photos": {"type": "array", "items": {"type": "integer"}},
                "evidence_en": {"type": "string"},
                "evidence_nl": {"type": "string"},
            },
            "required": ["brand", "series", "model_code", "confidence", "photos", "evidence_en", "evidence_nl"],
            "additionalProperties": False,
        },
        "tyres": {
            "type": "object",
            "properties": {
                "brand": {"type": ["string", "null"], "description": "e.g. Continental, Schwalbe, Vittoria, Pirelli"},
                "model": {"type": ["string", "null"], "description": "e.g. Grand Prix 5000, Pro One, Corsa"},
                "width_mm": {"type": ["integer", "null"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                "photos": {"type": "array", "items": {"type": "integer"}},
                "evidence_en": {"type": "string"},
                "evidence_nl": {"type": "string"},
            },
            "required": ["brand", "model", "width_mm", "confidence", "photos", "evidence_en", "evidence_nl"],
            "additionalProperties": False,
        },
        "frame": {
            "type": "object",
            "properties": {
                # An enum can't be nullable through "type": the API rejects a string enum on ["string", "null"].
                "material": {"anyOf": [{"type": "string", "enum": ["Carbon", "Aluminium", "Steel", "Titanium"]},
                                       {"type": "null"}]},
                "printed": {"type": ["string", "null"], "description": "the material print on the frame, as written"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                "photos": {"type": "array", "items": {"type": "integer"}},
                "evidence_en": {"type": "string"},
                "evidence_nl": {"type": "string"},
            },
            "required": ["material", "printed", "confidence", "photos", "evidence_en", "evidence_nl"],
            "additionalProperties": False,
        },
        "receipt": {
            "type": "object",
            "properties": {
                "shown": {"type": "boolean"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                "photos": {"type": "array", "items": {"type": "integer"}},
                "date": {"type": ["string", "null"], "description": "purchase date as YYYY-MM-DD, or YYYY-MM or YYYY"},
                "shop": {"type": ["string", "null"]},
                "bike": {"type": ["string", "null"], "description": "the bike as written on the receipt"},
                "model_year": {"type": ["integer", "null"], "description": "only when printed on the receipt"},
                "price": {"type": ["number", "null"], "description": "price paid for the bike, in euros"},
                "evidence_en": {"type": "string"},
                "evidence_nl": {"type": "string"},
            },
            "required": ["shown", "confidence", "photos", "date", "shop", "bike", "model_year", "price",
                         "evidence_en", "evidence_nl"],
            "additionalProperties": False,
        },
    },
    "required": ["brand", "series", "model_code", "speeds", "electronic", "confidence", "photos", "evidence_en",
                 "evidence_nl", "crankset", "tyres", "frame", "receipt"],
    "additionalProperties": False,
}


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def text_of(read):
    """The read as ad text ("Shimano 105 R7000 11-speed Di2"), for checks.detect_groupset."""
    if not read:
        return ""
    parts = [read.get("brand") if read.get("brand") not in ("other", "unknown") else None, read.get("series"),
             read.get("model_code"), f"{read['speeds']}-speed" if read.get("speeds") else None]
    if read.get("electronic"):
        parts.append({"Shimano": "Di2", "SRAM": "AXS", "Campagnolo": "EPS"}.get(read.get("brand"), ""))
    return " ".join(p for p in parts if p)


def usable(read):
    """True when the read is sure enough to compare with the catalogue."""
    return bool(read and read.get("confidence") in USED and read.get("series"))


# Per part of a read: the fields that name it, in the order they read as ad text ("Shimano 105 FC-R7000").
PART_FIELDS = {"crankset": ("brand", "series", "model_code"), "tyres": ("brand", "model", "width_mm"),
               "frame": ("material",)}


def part_of(read, key):
    """A part of a read ("crankset", "tyres", "frame") when it's sure enough and names more than a brand."""
    part = (read or {}).get(key) or {}
    fields = PART_FIELDS[key]
    if part.get("confidence") in USED and any(part.get(f) for f in (fields[1:] or fields)):
        return part
    return None


def part_text(key, part):
    """A part of a read as ad text: "Shimano 105 FC-R7000", "Continental Grand Prix 5000 28 mm", "Carbon"."""
    return " ".join(f"{part[f]} mm" if f == "width_mm" else str(part[f]) for f in PART_FIELDS[key] if part.get(f))


def receipt_of(read):
    """The receipt part of a read when a photo shows one that could be read, else None."""
    receipt = (read or {}).get("receipt") or {}
    if receipt.get("shown") and receipt.get("confidence") in USED:
        return receipt
    return None


# ---------------------------------------------------------------- reading the photos

def _jpeg(path):
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=85)
    return base64.standard_b64encode(out.getvalue()).decode("ascii")


def read_photos(paths, client=None):
    """Ask Claude which groupset the photos show. Returns the read (a dict as SCHEMA), or None when it
    couldn't be read (no photos, an API error, a refusal). Errors are logged, never raised."""
    paths = [p for p in paths if os.path.exists(p)][:MAX_PHOTOS]
    if not paths:
        return None
    import anthropic  # only needed when a key is set
    client = client or anthropic.Anthropic()
    content = []
    for n, path in enumerate(paths, 1):
        try:
            data = _jpeg(path)
        except OSError:
            continue
        content += [{"type": "text", "text": f"Photo {n}:"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}]
    if not content:
        return None
    content.append({"type": "text", "text": PROMPT})
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIStatusError as e:
        print(f"groupset from photos: API error {e.status_code}: {e.message}", file=sys.stderr, flush=True)
        return None
    except anthropic.APIConnectionError as e:
        print(f"groupset from photos: no connection ({e})", file=sys.stderr, flush=True)
        return None
    if response.stop_reason != "end_turn":
        print(f"groupset from photos: stopped ({response.stop_reason})", file=sys.stderr, flush=True)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        print(f"groupset from photos: not JSON: {text[:200]!r}", file=sys.stderr, flush=True)
        return None


# ---------------------------------------------------------------- stored reads

def _cache_path(photo_folder, check_id):
    return os.path.join(photo_folder, str(check_id), CACHE_NAME)


def _hand(listing, _cache={}):
    if "data" not in _cache:
        try:
            with open(HAND_FILE, encoding="utf-8") as fh:
                _cache["data"] = json.load(fh)
        except (OSError, ValueError):
            _cache["data"] = {}
    if not listing.get("title"):
        return None
    from .fetch_ad import ad_key
    entry = _cache["data"].get(ad_key({"listing_url": listing.get("listing_url"), "title": listing["title"],
                                       "asking_price": listing.get("asking_price")}))
    return dict(entry, source="eye") if entry else None


def stored(photo_folder, listing, photo_names):
    """The groupset read for this check: by eye (photo_groupsets.json), else the stored automatic read of its
    photos (possibly of fewer photos than now, until read_later has read them). None when there's neither (yet)."""
    hand = _hand(listing)
    if hand and not outdated(hand):
        return hand
    saved = _saved(photo_folder, listing.get("id"), photo_names)
    if hand:
        # Read by eye before the crankset and receipt were read: the automatic read adds them, once there is one.
        return dict(hand, **{k: saved[k] for k in NEWER_PARTS if k not in hand and saved and k in saved})
    return dict(saved, source="photos") if saved else None


def outdated(read):
    """True when a read is from before the crankset and receipt were read too, so the photos are read again."""
    return read is not None and any(k not in read for k in NEWER_PARTS)


def _saved(photo_folder, check_id, photo_names):
    """The stored automatic read of the check's photos, or None."""
    if check_id is None:
        return None
    try:
        with open(_cache_path(photo_folder, check_id), encoding="utf-8") as fh:
            saved = json.load(fh)
    except (OSError, ValueError):
        return None
    # Of other photos than now is still the best read there is until read_later has read these.
    return saved.get("read") or None


_running = set()
_slots = threading.BoundedSemaphore(2)  # a page listing many old checks starts at most two reads at a time


def read_later(photo_folder, check_id, photo_names, client=None):
    """Read the check's stored photos in the background and keep the result next to them. Does nothing
    without an API key, without photos, or when that check is already being read."""
    if not enabled() or not photo_names or check_id in _running:
        return False
    if os.path.exists(_cache_path(photo_folder, check_id)):
        try:
            with open(_cache_path(photo_folder, check_id), encoding="utf-8") as fh:
                saved = json.load(fh)
            if saved.get("photos") == list(photo_names) and saved.get("version", 1) >= READ_VERSION:
                return False  # read before, also when nothing usable came out
        except (OSError, ValueError):
            pass
    _running.add(check_id)

    def work():
        try:
            with _slots:
                read = read_photos([os.path.join(photo_folder, n) for n in photo_names], client)
            if read is None:
                return  # an error: the next page view tries again
            os.makedirs(os.path.join(photo_folder, str(check_id)), exist_ok=True)
            # Written next to it and then moved in place, so a page view never reads half a file.
            with open(_cache_path(photo_folder, check_id) + ".part", "w", encoding="utf-8") as fh:
                json.dump({"photos": list(photo_names), "version": READ_VERSION, "model": MODEL, "read_on": date.today().isoformat(),
                           "read": read}, fh, ensure_ascii=False, indent=1)
            os.replace(_cache_path(photo_folder, check_id) + ".part", _cache_path(photo_folder, check_id))
        except Exception as e:  # never take the page down
            print(f"groupset from photos of check {check_id} failed: {e!r}", file=sys.stderr, flush=True)
        finally:
            _running.discard(check_id)

    threading.Thread(target=work, name=f"groupset-{check_id}", daemon=True).start()
    return True
