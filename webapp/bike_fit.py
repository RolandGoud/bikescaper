"""Line up the bike in an ad photo with the bike in the catalogue photo, for the merged photo tiles.

The catalogue photos all show the bike from the drive side, handlebars on the right. Ad photos
don't: the bike can face either way, stand small in a corner, or fill the frame. `find` looks for
the catalogue bike's outline in the ad photo and says where the ad's bike is, how big, and whether
it faces left. `placement` turns that into where to draw the ad photo in a 16:9 tile so its bike
sits on top of the catalogue bike, mirrored when it faced left.
"""
import json
import os
import queue
import sys
import threading

import numpy as np
from PIL import Image, ImageFilter, ImageOps

WORK_WIDTH = 160            # the ad photo is searched at this width
FINE_WIDTH = 240            # and the bike looked at this wide to tell which way it faces
SIZES = np.linspace(0.35, 1.0, 14)  # bike width as a share of the ad photo's width
MIN_SCORE = 0.2             # below this the match is a guess; draw the photo as it is
TILE = 16 / 9


def _edges(img, blur=1.2):
    """Soft edge map: where the outline is, not what colour it is, so a red bike finds a black one."""
    grey = ImageOps.grayscale(img).filter(ImageFilter.GaussianBlur(0.8))
    a = np.asarray(grey, dtype=np.float32)
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    e = np.hypot(gx, gy)
    e = Image.fromarray(np.clip(e * (255 / max(e.max(), 1)), 0, 255).astype(np.uint8))
    e = e.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(e, dtype=np.float32)


def bike_box(img):
    """(x, y, w, h) of the bike in a catalogue photo, as shares of the photo: everything that differs
    from the background colour in the corners."""
    small = img.convert("RGB")
    small.thumbnail((400, 400))
    a = np.asarray(small, dtype=np.float32)
    corners = np.concatenate([a[:4, :4].reshape(-1, 3), a[:4, -4:].reshape(-1, 3),
                              a[-4:, :4].reshape(-1, 3), a[-4:, -4:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    mask = np.abs(a - bg).max(axis=2) > 28
    rows, cols = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
    if len(rows) < 4 or len(cols) < 4:
        return None
    h, w = mask.shape
    return cols[0] / w, rows[0] / h, (cols[-1] + 1 - cols[0]) / w, (rows[-1] + 1 - rows[0]) / h


def _match(field, template):
    """Normalised cross-correlation of the template at every position in the field (via FFT).
    Returns (best score, x, y) of the template's top left corner."""
    fh, fw = field.shape
    th, tw = template.shape
    t = template - template.mean()
    tnorm = np.sqrt((t * t).sum())
    if tnorm == 0:
        return -1, 0, 0
    shape = (fh + th, fw + tw)
    corr = np.fft.irfft2(np.fft.rfft2(field, shape) * np.conj(np.fft.rfft2(t, shape)), shape)
    corr = corr[:fh - th + 1, :fw - tw + 1]
    # the field's mean and spread under each window, from summed-area tables
    s = np.pad(field, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    s2 = np.pad(field * field, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    win = lambda a: a[th:, tw:] - a[:-th, tw:] - a[th:, :-tw] + a[:-th, :-tw]
    n = th * tw
    total, total2 = win(s), win(s2)
    spread = np.sqrt(np.maximum(total2 - total * total / n, 1e-6))
    score = corr / (spread * tnorm)
    y, x = np.unravel_index(np.argmax(score), score.shape)
    return float(score[y, x]), int(x), int(y)


def _search(field, bike, blur):
    """Best (score, x, y, w, h) of the bike's outline in the field, at any size in SIZES."""
    fh, fw = field.shape
    best = None
    for size in SIZES:
        tw = round(fw * size)
        th = round(tw * bike.height / bike.width)
        if tw < 16 or th < 8 or th > fh:
            continue
        score, x, y = _match(field, _edges(bike.resize((tw, th), Image.BILINEAR), blur))
        if best is None or score > best[0]:
            best = (score, x, y, tw, th)
    return best


def _ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    norm = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / norm) if norm else -1.0


def _likeness(ad, box, bike):
    """How well the ad photo's part in box matches the bike outline, at its best within a small
    nudge of place and size. Only the top half counts: the wheels look the same either way round,
    the frame, saddle and handlebars don't."""
    aw, ah = ad.size
    x, y, w, h = box
    tw = FINE_WIDTH
    th = round(tw * bike.height / bike.width)
    template = _edges(bike.resize((tw, th), Image.BILINEAR), 0.8)[: th // 2]
    best = -1.0
    for scale in (0.96, 1.0, 1.04):
        for dx in (-0.04, -0.02, 0, 0.02, 0.04):
            for dy in (-0.04, 0, 0.04):
                x0 = (x + dx * w - (scale - 1) / 2 * w) * aw
                y0 = (y + dy * h - (scale - 1) / 2 * h) * ah
                part = ad.crop((round(x0), round(y0), round(x0 + w * scale * aw), round(y0 + h * scale * ah)))
                best = max(best, _ncc(_edges(part.resize((tw, th), Image.BILINEAR), 0.8)[: th // 2], template))
    return best


def find(ad, catalogue):
    """Where the catalogue's bike is in the ad photo: {x, y, w, h (shares of the ad photo), flip,
    score}, flip meaning the ad's bike faces left. None when it can't tell.

    A rough search over the whole photo, both ways round, finds where the bike is and how big; the
    wheels mostly settle that. Then a sharper look at just that spot decides which way it faces."""
    box = bike_box(catalogue)
    if not box:
        return None
    cw, ch = catalogue.size
    bx, by, bw, bh = box
    bike = catalogue.convert("RGB").crop((int(bx * cw), int(by * ch), int((bx + bw) * cw), int((by + bh) * ch)))
    ad = ad.convert("RGB")
    aw, ah = ad.size
    field = _edges(ad.resize((WORK_WIDTH, max(8, round(WORK_WIDTH * ah / aw))), Image.BILINEAR))
    fh, fw = field.shape
    found = [_search(field, b, 1.2) for b in (bike, ImageOps.mirror(bike))]
    score, x, y, tw, th = max((f for f in found if f), default=(-1, 0, 0, 0, 0))
    if score < MIN_SCORE:
        return None
    spot = (x / fw, y / fh, tw / fw, th / fh)
    flip = _likeness(ad, spot, ImageOps.mirror(bike)) > _likeness(ad, spot, bike)
    return {"x": spot[0], "y": spot[1], "w": spot[2], "h": spot[3], "flip": flip, "score": round(score, 3)}


def placement(fit, ad_size, catalogue_size, catalogue_box, zoom=None):
    """Where to draw the ad photo in a 16:9 tile: {left, top, width, height} in % of the tile, and
    flip. The catalogue photo is drawn whole ("contain") and the ad photo must still cover the tile.
    zoom is the catalogue photo's own (scale, shift up as a share of the tile, scaled from the bottom
    centre), for brands whose photos are drawn larger."""
    # the catalogue bike, in tile units: the tile is 1 wide and 1/TILE high
    cw, ch = catalogue_size
    th_ = 1 / TILE
    if cw / ch > TILE:
        dw, dh = 1, ch / cw
    else:
        dw, dh = th_ * cw / ch, th_
    ox, oy = (1 - dw) / 2, (th_ - dh) / 2
    bx, by, bw, bh = catalogue_box
    cx0, cy0, cbw, cbh = ox + bx * dw, oy + by * dh, bw * dw, bh * dh
    if zoom:
        scale, up = zoom
        cx0 = 0.5 + (cx0 - 0.5) * scale
        cy0 = th_ + (cy0 - th_) * scale - up * th_
        cbw, cbh = cbw * scale, cbh * scale
    # size the ad photo so its bike is as big as the catalogue bike, and put it on top of it
    aw, ah = ad_size
    fx = 1 - fit["x"] - fit["w"] if fit["flip"] else fit["x"]
    width = cbw / fit["w"]
    height = width * ah / aw
    centre_x, centre_y = cx0 + cbw / 2, cy0 + cbh / 2
    grow = max(1, 1 / width, th_ / height)  # never leave a gap: grow around the bike if it would
    width, height = width * grow, height * grow
    left = centre_x - (fx + fit["w"] / 2) * width
    top = centre_y - (fit["y"] + fit["h"] / 2) * height
    left = min(0, max(1 - width, left))
    top = min(0, max(th_ - height, top))
    pct = lambda v, of: round(float(100 * v / of), 2)
    return {"left": pct(left, 1), "top": pct(top, th_), "width": pct(width, 1), "height": pct(height, th_),
            "flip": fit["flip"]}


def work_out(ad_path, catalogue_path, zoom=None):
    """The placement for this pair of photo files, or None when the bike can't be found."""
    try:
        with Image.open(ad_path) as ad, Image.open(catalogue_path) as catalogue:
            ad.load()
            catalogue.load()
            fit = find(ad, catalogue)
            box = bike_box(catalogue)
            return placement(fit, ad.size, catalogue.size, box, zoom) if fit and box else None
    except (OSError, ValueError):
        return None


# Working one out takes about half a second, too slow for a page with a dozen tiles, so it's done
# once in the background and kept in a file next to the ad photo ("01.jpg.fit.json"), one entry per
# catalogue photo. Until then the tile shows the ad photo as it is.
_queue = queue.Queue()
_pending = set()
_lock = threading.Lock()
_worker_started = []


def _key(catalogue_path, zoom):
    return f"{os.path.basename(catalogue_path)}@{int(os.path.getmtime(catalogue_path))}@{zoom}"


def _cache_path(ad_path):
    return ad_path + ".fit.json"


def _read(ad_path):
    try:
        with open(_cache_path(ad_path)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _worker():
    while True:
        ad_path, catalogue_path, zoom = _queue.get()
        try:
            key = _key(catalogue_path, zoom)
            result = work_out(ad_path, catalogue_path, zoom)
            with _lock:
                saved = _read(ad_path)
                saved[key] = result
                with open(_cache_path(ad_path) + ".tmp", "w") as f:
                    json.dump(saved, f)
                os.replace(_cache_path(ad_path) + ".tmp", _cache_path(ad_path))
        except Exception as e:  # keep the worker going; the next page view asks again
            print(f"lining up {ad_path} failed: {e}", file=sys.stderr, flush=True)
        finally:
            _pending.discard((ad_path, catalogue_path, zoom))


def style(ad_path, catalogue_path, zoom=None):
    """The placement for this pair of photo files if it's been worked out, else None (draw the ad
    photo as it is) and it's worked out in the background for the next view."""
    try:
        key = _key(catalogue_path, zoom)
    except OSError:
        return None
    saved = _read(ad_path)
    if key in saved:
        return saved[key]
    job = (ad_path, catalogue_path, zoom)
    with _lock:
        if job not in _pending and os.path.exists(ad_path):
            if not _worker_started:
                threading.Thread(target=_worker, name="bike-fit", daemon=True).start()
                _worker_started.append(True)
            _pending.add(job)
            _queue.put(job)
    return None
