"""The photo review on the Selling page (prototype): a seller's own photos, read by Claude, shot by shot.

The seller fills the shot slots of step 1 (webapp/templates/_sell_photos.html); those photos live in their
browser only. When they ask for the review, the browser sends the filled slots here, each with the shot it was
taken for. Per photo the review says whether it shows that shot, rates light, background, sharpness, angle and
whether the details buyers zoom in on are readable, and gives one concrete tip when it should be retaken. It also
flags a manufacturer or stock photo (buyers distrust those) and personal details in view (a number plate, a house
number, a face).

How it runs:
- Only when ANTHROPIC_API_KEY is set in the container. Without it the offer stays the "Coming soon" sign-up.
- The call takes 10-40 seconds, longer than a request may (gunicorn's 30 s), so it runs in a thread and the
  browser asks for the result (start() and result()). The result is kept in the photo_reviews table, so either
  worker can answer. The photos themselves are never written to disk and are gone when the thread ends.
- At most PER_DAY reviews a day for the whole site (PHOTO_REVIEW_PER_DAY, default 40) and PER_HOUR per visitor,
  so the free prototype can't run up the API bill.
"""
import base64
import io
import json
import os
import secrets
import sys
import threading
import time

from PIL import Image

from . import db

MODEL = os.environ.get("PHOTO_REVIEW_MODEL", "claude-opus-5-5")
MAX_PHOTOS = 10
MAX_SIDE = 1024           # px; a decal or tyre print is still readable at this size
MAX_BYTES = 8 * 1024 * 1024
PER_DAY = int(os.environ.get("PHOTO_REVIEW_PER_DAY", "40"))
PER_HOUR = 3              # per visitor address
STALE_MINUTES = 5         # a review still "running" after this was cut off (the site reloaded): failed

PROMPT = """You review the photos a private seller made for a second-hand bike ad (Marktplaats and similar), \
before they post it. Each photo was taken for one of the shots listed with it; the tips there say what that shot \
should show. Buyers decide on the photos first and zoom in on the details to judge the parts and the wear.

For each photo:
- shows: what the photo actually shows, in a few words.
- matches_shot: whether it shows the shot it was taken for (a reasonable attempt counts).
- light: "good", "ok" or "poor" (too dark, harsh backlight, blown out, strong colour cast).
- background: "good" (plain, calm), "ok", or "busy" (clutter, other bikes, a messy shed that distracts).
- sharpness: "sharp", "soft" or "blurry".
- angle: "good", "ok" or "wrong", judged against the shot's tips (e.g. drive side with the cranks level and the \
chain on the big ring; camera at hub height).
- details: for a detail shot, whether the text buyers need (model name, size, tooth counts, tyre size) is \
readable: "yes", "partly" or "no"; "n/a" for a whole-bike shot.
- stock_photo: true when it looks like a manufacturer, shop or press photo rather than the seller's own \
(studio light, a seamless white background, a retouched bike). Buyers distrust ads that use those.
- privacy: any personal details in view that the seller may want out of the photo (a number plate, a house \
number, a readable letter or label with an address, a face). Empty when there are none.
- verdict: "keep" when it's good as it is, "improve" when it works but one change makes it clearly better, \
"retake" when it misses the shot or buyers can't judge what they need from it.
- tip: one concrete, practical sentence on what to change when retaking (e.g. "Step back so both wheels are in \
the frame and crouch to hub height"). Empty for "keep".
- notes: one short sentence on what is good or what is wrong.

Then a summary: two sentences at most on the set as a whole, starting with the most useful change.

Rules: judge only what you can see; be friendly and direct, like a friend who sells bikes; never comment on the \
bike's value or on the seller. Write every text twice, in English (_en) and in Dutch (_nl, informal "je"). \
Photos are numbered from 1 in the order given."""

SCHEMA = {
    "type": "object",
    "properties": {
        "photos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "photo": {"type": "integer"},
                    "shows_en": {"type": "string"},
                    "shows_nl": {"type": "string"},
                    "matches_shot": {"type": "boolean"},
                    "light": {"type": "string", "enum": ["good", "ok", "poor"]},
                    "background": {"type": "string", "enum": ["good", "ok", "busy"]},
                    "sharpness": {"type": "string", "enum": ["sharp", "soft", "blurry"]},
                    "angle": {"type": "string", "enum": ["good", "ok", "wrong"]},
                    "details": {"type": "string", "enum": ["yes", "partly", "no", "n/a"]},
                    "stock_photo": {"type": "boolean"},
                    "privacy_en": {"type": "string"},
                    "privacy_nl": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["keep", "improve", "retake"]},
                    "tip_en": {"type": "string"},
                    "tip_nl": {"type": "string"},
                    "notes_en": {"type": "string"},
                    "notes_nl": {"type": "string"},
                },
                "required": ["photo", "shows_en", "shows_nl", "matches_shot", "light", "background", "sharpness",
                             "angle", "details", "stock_photo", "privacy_en", "privacy_nl", "verdict", "tip_en",
                             "tip_nl", "notes_en", "notes_nl"],
                "additionalProperties": False,
            },
        },
        "summary_en": {"type": "string"},
        "summary_nl": {"type": "string"},
    },
    "required": ["photos", "summary_en", "summary_nl"],
    "additionalProperties": False,
}

TABLE = """
CREATE TABLE IF NOT EXISTS photo_reviews (
    id INTEGER PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,   -- what the browser asks the result by
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    shots TEXT NOT NULL,          -- JSON list of the shot keys sent, in order (never the photos)
    status TEXT NOT NULL,         -- running, done or failed
    result TEXT,                  -- JSON as SCHEMA, when done
    lang TEXT
);
"""


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _connect(db_path):
    conn = db.connect(db_path)
    conn.executescript(TABLE)
    return conn


def prepare(data):
    """A photo as sent by the browser, checked and made smaller: JPEG bytes as base64, or None when it isn't an
    image we can open."""
    if not data or len(data) > MAX_BYTES:
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=85)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    return base64.standard_b64encode(out.getvalue()).decode("ascii")


def review_photos(photos, shots, client=None):
    """Ask Claude to review the photos. photos: [(shot key, base64 JPEG)]; shots: app.PHOTO_SHOTS. Returns the
    review (a dict as SCHEMA) or None on an API error, a refusal or an answer that isn't JSON. Never raises."""
    if not photos:
        return None
    import anthropic  # only needed when a key is set
    client = client or anthropic.Anthropic()
    by_key = {key: (title, tips) for key, _group, title, tips in shots}
    content = []
    for n, (key, data) in enumerate(photos, 1):
        title, tips = by_key.get(key, ("Any shot", []))
        content += [{"type": "text", "text": f"Photo {n}, taken for the shot \"{title}\". Tips: {'; '.join(tips) or '-'}."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}]
    content.append({"type": "text", "text": PROMPT})
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIStatusError as e:
        print(f"photo review: API error {e.status_code}: {e.message}", file=sys.stderr, flush=True)
        return None
    except anthropic.APIConnectionError as e:
        print(f"photo review: no connection ({e})", file=sys.stderr, flush=True)
        return None
    if response.stop_reason != "end_turn":
        print(f"photo review: stopped ({response.stop_reason})", file=sys.stderr, flush=True)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        print(f"photo review: not JSON: {text[:200]!r}", file=sys.stderr, flush=True)
        return None


_asked = []  # (time, visitor address) of the reviews started by this worker, for PER_HOUR


def allowed(db_path, ip, now=None):
    """True when the site is under its daily number of reviews and this visitor under their hourly one."""
    now = now or time.time()
    _asked[:] = [(t, a) for t, a in _asked if now - t < 3600]
    if sum(1 for _t, a in _asked if a == ip) >= PER_HOUR:
        return False
    conn = _connect(db_path)
    try:
        today = conn.execute("SELECT COUNT(*) FROM photo_reviews WHERE created_at > datetime('now', '-1 day')").fetchone()[0]
    finally:
        conn.close()
    return today < PER_DAY


def start(db_path, photos, shots, lang, ip=None, client=None):
    """Start a review in the background. Returns its token; result(token) has it once done."""
    token = secrets.token_urlsafe(16)
    conn = _connect(db_path)
    try:
        conn.execute("INSERT INTO photo_reviews (token, shots, status, lang) VALUES (?, ?, 'running', ?)",
                     (token, json.dumps([k for k, _ in photos]), lang))
        conn.commit()
    finally:
        conn.close()
    _asked.append((time.time(), ip))

    def work():
        review = None
        try:
            review = review_photos(photos, shots, client)
        except Exception as e:  # never leave it running
            print(f"photo review failed: {e!r}", file=sys.stderr, flush=True)
        conn = _connect(db_path)
        try:
            conn.execute("UPDATE photo_reviews SET status = ?, result = ? WHERE token = ?",
                         ("done" if review else "failed", json.dumps(review, ensure_ascii=False) if review else None,
                          token))
            conn.commit()
        finally:
            conn.close()

    threading.Thread(target=work, name=f"photo-review-{token[:6]}", daemon=True).start()
    return token


def result(db_path, token, lang):
    """{"status": "running" | "done" | "failed" | "unknown", ...}; when done, the review in the page's language:
    {"summary": str, "photos": [{"shot", "verdict", "shows", "notes", "tip", "privacy", "stock_photo", "checks"}]}."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT *, created_at < datetime('now', ?) AS stale FROM photo_reviews WHERE token = ?",
                           (f"-{STALE_MINUTES} minutes", token)).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"status": "unknown"}
    if row["status"] == "running":
        return {"status": "failed" if row["stale"] else "running"}
    if row["status"] != "done":
        return {"status": "failed"}
    return dict(localise(json.loads(row["result"]), json.loads(row["shots"]), lang), status="done")


def localise(review, shot_keys, lang):
    """The review in one language, each photo with the shot key it was sent for."""
    lang = "nl" if lang == "nl" else "en"
    photos = []
    for p in review.get("photos") or []:
        n = p.get("photo")
        if not isinstance(n, int) or not 1 <= n <= len(shot_keys):
            continue
        photos.append({"shot": shot_keys[n - 1], "verdict": p.get("verdict"), "matches_shot": p.get("matches_shot"),
                       "stock_photo": bool(p.get("stock_photo")),
                       "shows": p.get(f"shows_{lang}", ""), "notes": p.get(f"notes_{lang}", ""),
                       "tip": p.get(f"tip_{lang}", "") if p.get("verdict") != "keep" else "",
                       "privacy": p.get(f"privacy_{lang}", ""),
                       "checks": {k: p.get(k) for k in ("light", "background", "sharpness", "angle", "details")}})
    return {"summary": review.get(f"summary_{lang}", ""), "photos": photos}
