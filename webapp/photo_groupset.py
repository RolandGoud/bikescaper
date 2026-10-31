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
MAX_PHOTOS = 8        # close-ups of the drivetrain are rarely the first photo, so more than the colour check's 3
MAX_SIDE = 1024       # px; the series name on a crank arm is still readable at this size
USED = ("high", "medium")

PROMPT = """These are the photos of a second-hand bike ad. The ad's text doesn't say which groupset the bike has.

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
Photos are numbered from 1 in the order given."""

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
    },
    "required": ["brand", "series", "model_code", "speeds", "electronic", "confidence", "photos", "evidence_en",
                 "evidence_nl"],
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
    """The groupset read for this check: by eye (photo_groupsets.json), else the stored automatic read of
    these same photos. None when there's neither (yet)."""
    hand = _hand(listing)
    if hand:
        return hand
    if listing.get("id") is None:
        return None
    try:
        with open(_cache_path(photo_folder, listing["id"]), encoding="utf-8") as fh:
            saved = json.load(fh)
    except (OSError, ValueError):
        return None
    if saved.get("photos") != list(photo_names):
        return None  # other photos than were read: read again
    return dict(saved["read"], source="photos") if saved.get("read") else None


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
                if json.load(fh).get("photos") == list(photo_names):
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
            with open(_cache_path(photo_folder, check_id), "w", encoding="utf-8") as fh:
                json.dump({"photos": list(photo_names), "model": MODEL, "read_on": date.today().isoformat(),
                           "read": read}, fh, ensure_ascii=False, indent=1)
        except Exception as e:  # never take the page down
            print(f"groupset from photos of check {check_id} failed: {e!r}", file=sys.stderr, flush=True)
        finally:
            _running.discard(check_id)

    threading.Thread(target=work, name=f"groupset-{check_id}", daemon=True).start()
    return True
