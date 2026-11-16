"""Build the blog's hero images: webapp/static/blog/heroes/<slug>.jpg (1600x900) and heroes.json.

The style is "spotlight": one close-up per article, lit by a single hard beam in a dark room, with haze in the
beam, a shallow depth of field, a vignette and film grain. The sources are the brands' own high-resolution
studio and detail shots (the same photos the catalogue shows) and, for the street scenes, freely licensed photos
from Wikimedia Commons, credited in heroes.json and under the picture. Sources are downloaded once to
~/.cache/bikecheck-heroes. Run: python tools/build_blog_heroes.py [slug ...]

heroes.json also holds each picture's focus point, so a tile that crops it (the /blog wall, "Read next") keeps
the subject in view (object-position).
"""
import json
import math
import os
import random
import sys
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "webapp", "static", "blog", "heroes")
CACHE = os.path.expanduser("~/.cache/bikecheck-heroes")
W, H = 1600, 900
UA = {"User-Agent": "BikecheckBlog/1.0 (hero images)"}

GIANT = "https://images2.giant-bicycles.com/b_white%2Cc_pad%2Ch_2250%2Cq_90%2Cw_3000/"
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"
SOURCES = {
    "trek-domane-slr9": "https://media.trekbikes.com/image/upload/f_jpg,w_4000/DomaneSLR9-27-79926-A-Primary",
    "trek-domane-sl6": "https://media.trekbikes.com/image/upload/f_jpg,w_4000/DomaneSL6-26-57639-A-Primary",
    "tcr-sl1": GIANT + "zzgqf9xwbjkjdjmev8ix/MY25TCRAdvancedSL1_ColorABlueDragonfly_Iris.jpg",
    "topstone-c2": "https://embed.widencdn.net/img/dorelrl/oj336v4hm2/3000px@1x/C25_C15335U_Topstone_Crb_2_AXS_1x_SGR_PD.jpg",
    "tcr-sl-crank": GIANT + "ccpgyga8zcnnwol24ocq/MY25TCRAdvancedSL1_ColorABlueDragonfly_Iris-D3.jpg",
    "tcr-sl-cockpit": GIANT + "kq1quuacyutfdpuwybeh/MY25TCRAdvancedSL1_ColorABlueDragonfly_Iris-D6.jpg",
    "tcr-head": GIANT + "jhwgz5cae08mwmsmrvtc/MY26TCRAdvanced1-PC_ColorADreamyBlue-D1.jpg",
    "tcr-105": GIANT + "z3qz1wnrva7qwxz6mrfs/MY26TCRAdvanced1-PC_ColorADreamyBlue-D3.jpg",
    "defy-bars": GIANT + "j7tc8hwx7i80dsjrsy23/MY27DefyAdvanced2_ColorAPearlWhite-D4.jpg",
    "defy-fork": GIANT + "d9kfyvsxfjkie9y46uip/MY27DefyAdvanced2_ColorAPearlWhite-D2.jpg",
    "revolt-badge": GIANT + "laiphrr9bgoc2a5u75qh/MY25Revolt2_ColorAAsphaltGreen-D5.jpg",
    "lock": COMMONS + "Manchester_-_bicycle_lock.jpg?width=3000",
    "snow": COMMONS + "Bike_on_a_snowy_street_in_Quebec_City_at_night.jpg?width=3000",
}
CREDITS = {
    "lock": {"author": "Jorge Franganillo", "license": "CC BY 4.0",
             "url": "https://commons.wikimedia.org/wiki/File:Manchester_-_bicycle_lock.jpg"},
    "snow": {"author": "Wilfredor", "license": "CC0",
             "url": "https://commons.wikimedia.org/wiki/File:Bike_on_a_snowy_street_in_Quebec_City_at_night.jpg"},
}
BRAND = {"trek-domane-slr9": "Trek", "trek-domane-sl6": "Trek", "topstone-c2": "Cannondale"}  # else Giant

WARM, COOL, MINT, AMBER, ICE = (255, 226, 186), (190, 214, 255), (170, 255, 214), (255, 178, 104), (200, 225, 255)


UNSPLASH = "https://api.unsplash.com"


def unsplash(path, **params):
    """A call to the Unsplash API with the key from UNSPLASH_ACCESS_KEY (never in the repo; see docs/going-public.md)."""
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        raise SystemExit("Set UNSPLASH_ACCESS_KEY to search or fetch Unsplash photos.")
    url = UNSPLASH + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1", **UA})
    return json.load(urllib.request.urlopen(req, timeout=30))


def search(query):
    """Landscape Unsplash photos for a query, to pick hero sources from: python tools/build_blog_heroes.py --search ..."""
    for p in unsplash("/search/photos", query=query, orientation="landscape", per_page=20)["results"]:
        print(f"unsplash:{p['id']}  {p['width']}x{p['height']}  {p['user']['name']}  {(p.get('alt_description') or '')[:60]}")
        print(f"    {p['urls']['small']}")


def source(key):
    """A hero source, downloaded once. `unsplash:<id>` fetches that Unsplash photo through the API, which counts the
    download as Unsplash's API guidelines ask, and notes the photographer for the credit."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, key.replace(":", "-") + ".jpg")
    if not os.path.exists(path) and key.startswith("unsplash:"):
        photo = unsplash(f"/photos/{key.split(':', 1)[1]}")
        unsplash(urllib.parse.urlparse(photo["links"]["download_location"]).path)  # the download, counted
        CREDITS[key] = {"author": photo["user"]["name"], "license": "Unsplash License",
                        "url": photo["links"]["html"] + "?utm_source=bikecheck&utm_medium=referral"}
        SOURCES[key] = photo["urls"]["raw"] + "&w=3000&q=90&fm=jpg"
        with open(path + ".json", "w", encoding="utf-8") as f:
            json.dump(CREDITS[key], f)
    elif key.startswith("unsplash:") and os.path.exists(path + ".json"):
        with open(path + ".json", encoding="utf-8") as f:
            CREDITS[key] = json.load(f)
    if not os.path.exists(path):
        data = urllib.request.urlopen(urllib.request.Request(SOURCES[key], headers=UA), timeout=90).read()
        with open(path, "wb") as f:
            f.write(data)
    return Image.open(path).convert("RGB")


def frame(im, cx, cy, width, studio):
    """A 16:9 crop centred on (cx, cy) (fractions of the source), `width` of the source wide; a studio shot is
    padded with its white background where the crop runs past the edge."""
    sw, sh = im.size
    cw = width * sw
    ch = cw * H / W
    box = (cx * sw - cw / 2, cy * sh - ch / 2, cx * sw + cw / 2, cy * sh + ch / 2)
    canvas = Image.new("RGB", (round(cw), round(ch)), (255, 255, 255) if studio else (0, 0, 0))
    canvas.paste(im, (-round(box[0]), -round(box[1])))
    return canvas.resize((W, H), Image.LANCZOS)


def studio_alpha(im):
    """How much of each pixel is bike rather than the white studio background: 0 on the background (reached from
    the edges and in the larger pockets), soft at the edge so spokes and cables keep their shape."""
    a = np.asarray(im).astype(float)
    dist = (255 - a).max(axis=2)
    m = Image.fromarray(np.where(dist < 22, 255, 0).astype(np.uint8)).copy()
    for x in range(0, W, 9):
        for y in (0, H - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(0, H, 9):
        for x in (0, W - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    arr = np.asarray(m).copy()
    # larger white pockets inside the frame are background too
    rest = Image.fromarray(np.where(arr == 255, 255, 0).astype(np.uint8)).copy()
    big = W * H * 0.0004
    for y in range(0, H, 6):
        for x in range(0, W, 6):
            if rest.getpixel((x, y)) == 255:
                ImageDraw.floodfill(rest, (x, y), 100)
                r = np.asarray(rest)
                hit = r == 100
                if hit.sum() > big:
                    arr[hit] = 128
                rest = Image.fromarray(np.where(hit, 50, r).astype(np.uint8)).copy()
    bg = arr == 128
    band = np.asarray(Image.fromarray((bg * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    alpha = np.where(bg, 0.0, np.where(band, np.clip(dist / 120.0, 0, 1), 1.0))
    return Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


def cone(origin, target, spread, soft=0.35, reach=1.6):
    """A beam from `origin` towards `target` (pixels), `spread` its half-angle in degrees: 1 in its core, fading
    over `soft` of its width to the sides and with distance."""
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    dx, dy = xx - origin[0], yy - origin[1]
    ax, ay = target[0] - origin[0], target[1] - origin[1]
    length = math.hypot(ax, ay)
    ax, ay = ax / length, ay / length
    along = dx * ax + dy * ay
    across = np.abs(dx * -ay + dy * ax)
    half = np.maximum(along, 1) * math.tan(math.radians(spread))
    side = np.clip((1 - across / half) / soft, 0, 1)
    side = side * side * (3 - 2 * side)
    fall = np.clip(1.15 - along / (length * reach), 0, 1)
    return np.where(along > 0, side * fall, 0)


def noise(scale, seed):
    rng = np.random.default_rng(seed)
    small = Image.fromarray((rng.random((H // scale + 2, W // scale + 2)) * 255).astype(np.uint8))
    return np.asarray(small.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(scale / 3))) / 255.0


def spotlight(slug, key, cx, cy, width, light, target, spread=16, colour=WARM, focus=None, blur=7.0,
              ambient=0.05, haze=0.16, dust=140, tint=(1.0, 1.0, 1.0), bg=(7, 8, 10), gain=2.0, sat=1.0, seed=1):
    """One hero: the crop of source `key`, lit by a beam from `light` towards `target`."""
    photo = source(key)  # first, so an Unsplash photo's credit is known
    studio = key not in CREDITS
    im = frame(photo, cx, cy, width, studio)
    a = np.asarray(im).astype(float) / 255
    focus = focus or target
    beam = cone(light, target, spread)
    wide = cone(light, target, spread * 2.2, soft=0.9) * 0.35
    col = np.array(colour, float) / 255
    if studio:
        alpha = np.asarray(studio_alpha(im)).astype(float)[..., None] / 255
        # the white studio light becomes a dark room: the bike's own shading, darker overall
        subject = np.clip(a ** 1.35, 0, 1)
    else:
        alpha = np.ones((H, W, 1))
        grey = a.mean(axis=2, keepdims=True)
        subject = np.clip((grey + (a - grey) * sat) ** 1.2, 0, 1)
    # light on the subject: the beam, a little spill and a little ambient
    lit = ambient + gain * (beam + 0.6 * wide)[..., None]
    subject = subject * lit * (0.55 + 0.45 * col) * np.array(tint)
    # the room: near black, with haze inside the beam
    room = np.ones((H, W, 3)) * (np.array(bg, float) / 255)
    swirl = 0.55 + 0.45 * noise(90, seed) * noise(35, seed + 1)
    # haze is thickest near the lamp and thins out downwards
    thin = np.clip(1.25 - np.mgrid[0:H, 0:W][0] / H, 0.3, 1)
    mist = ((beam * 0.9 + wide * 0.4) * thin * swirl)[..., None] * col * haze
    img = subject * alpha + room * (1 - alpha) + mist * (1 - 0.6 * alpha)
    # depth of field: sharp around the focus, softer away from it
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    d = np.hypot((xx - focus[0]) / W, (yy - focus[1]) / H * 0.8)
    depth = np.clip((d - 0.14) / 0.30, 0, 1)[..., None]
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    soft = np.asarray(pil.filter(ImageFilter.GaussianBlur(blur))).astype(float) / 255
    img = img * (1 - depth) + soft * depth
    # dust in the beam: small sharp specks and a few big soft ones
    rnd = random.Random(seed)
    specks = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(specks)
    for _ in range(dust):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        if beam[int(y), int(x)] < 0.25:
            continue
        r = rnd.choice([1, 1, 1, 1.5, 2, 2.5]) if rnd.random() < 0.93 else rnd.uniform(5, 11)
        dr.ellipse((x - r, y - r, x + r, y + r), fill=int(rnd.uniform(60, 200) if r < 4 else rnd.uniform(12, 30)))
    specks = np.asarray(specks.filter(ImageFilter.GaussianBlur(0.8))).astype(float)[..., None] / 255
    img = img + specks * col * 0.9
    # vignette, a filmic curve, then grain
    v = np.hypot((xx - W * 0.5) / (W * 0.62), (yy - H * 0.5) / (H * 0.66))
    img = img * np.clip(1.08 - v ** 2.2 * 0.75, 0.12, 1)[..., None]
    img = 1 - np.exp(-img * 1.9)
    img = img / (1 - math.exp(-1.9))
    grain = np.random.default_rng(seed).normal(0, 0.022, (H, W, 1))
    img = np.clip(img + grain, 0, 1)
    out = Image.fromarray((img * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, f"{slug}.jpg"), quality=86, optimize=True, progressive=True)
    meta = {"focus": [round(focus[0] / W * 100), round(focus[1] / H * 100)], "source": key}
    if key in CREDITS:
        meta["credit"] = CREDITS[key]
    else:
        meta["brand"] = BRAND.get(key, "Giant")
    return meta


def mood(slug, key, cx, cy, width, light, target, spread=24, colour=WARM, focus=None, base=0.55, gain=0.75,
         gamma=1.15, sat=0.85, tint=(1.0, 1.0, 1.0), haze=0.10, dust=90, vignette=0.8, seed=1):
    """One hero from an atmospheric photo (Unsplash): the photo keeps its own light and feeling, graded darker and
    warmer or cooler, with the same spotlight signature as the studio heroes: a soft beam lifting the subject,
    haze and dust in that beam, a deep vignette and film grain."""
    photo = source(key)
    im = frame(photo, cx, cy, width, False)
    a = np.asarray(im).astype(float) / 255
    focus = focus or target
    col = np.array(colour, float) / 255
    grey = a.mean(axis=2, keepdims=True)
    img = np.clip(grey + (a - grey) * sat, 0, 1) ** gamma * np.array(tint)
    beam = cone(light, target, spread, soft=0.8)
    wide = cone(light, target, spread * 2.0, soft=1.0)
    img = img * (base + gain * (0.7 * beam + 0.5 * wide))[..., None] * (0.75 + 0.25 * col)
    swirl = 0.55 + 0.45 * noise(90, seed) * noise(35, seed + 1)
    thin = np.clip(1.25 - np.mgrid[0:H, 0:W][0] / H, 0.3, 1)
    img = img + ((beam * 0.8 + wide * 0.3) * thin * swirl)[..., None] * col * haze
    rnd = random.Random(seed)
    specks = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(specks)
    for _ in range(dust):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        if beam[int(y), int(x)] < 0.3:
            continue
        r = rnd.choice([1, 1, 1.5, 2]) if rnd.random() < 0.93 else rnd.uniform(5, 10)
        dr.ellipse((x - r, y - r, x + r, y + r), fill=int(rnd.uniform(50, 160) if r < 4 else rnd.uniform(10, 24)))
    specks = np.asarray(specks.filter(ImageFilter.GaussianBlur(0.8))).astype(float)[..., None] / 255
    img = img + specks * col * 0.8
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    v = np.hypot((xx - W * 0.5) / (W * 0.62), (yy - H * 0.5) / (H * 0.66))
    img = img * np.clip(1.08 - v ** 2.2 * vignette, 0.10, 1)[..., None]
    img = 1 - np.exp(-img * 1.9)
    img = img / (1 - math.exp(-1.9))
    grain = np.random.default_rng(seed).normal(0, 0.018, (H, W, 1))
    img = np.clip(img + grain, 0, 1)
    out = Image.fromarray((img * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, f"{slug}.jpg"), quality=86, optimize=True, progressive=True)
    return {"focus": [round(focus[0] / W * 100), round(focus[1] / H * 100)], "source": key, "credit": CREDITS[key]}


def stage(slug, key, cx, cy, width, scene, streak, rim, seed=1):
    """A model article's hero: the brand's own studio photo of the bike, cut out and set on a dark stage. A beam
    lights it from the upper right, a thin rim light traces it, long-exposure light streaks in the bike's colour run
    behind it, and a wet floor reflects it. The backdrop is the article's Unsplash scene (`scene`: key, cx, cy,
    width), blurred and dark, credited as the background."""
    im = frame(source(key), cx, cy, width, True)
    alpha = np.asarray(studio_alpha(im)).astype(float) / 255
    a = np.asarray(im).astype(float) / 255
    # take the white studio background out of the soft edge pixels (spokes, cables), so no white fringe is left
    k = np.maximum(alpha, 0.05)[..., None]
    a = np.clip((a - (1 - k)) / k, 0, 1)
    beam = cone((1300, -300), (800, 450), 26, soft=0.9)
    bike = np.clip(a ** 1.5, 0, 1) * (0.25 + 1.0 * beam)[..., None]
    inner = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))) / 255
    edge = Image.fromarray((np.clip(alpha - inner, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    bike = bike + (np.asarray(edge).astype(float) / 255)[..., None] * (np.array(rim, float) / 255) * 0.45
    back = frame(source(scene[0]), *scene[1:], False).filter(ImageFilter.GaussianBlur(14))
    bg = (np.asarray(back).astype(float) / 255) ** 1.6 * 0.35
    rnd = random.Random(seed)
    lines = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(lines)
    for _ in range(26):
        y, x0, length = rnd.gauss(H * 0.52, H * 0.13), rnd.uniform(-200, W * 0.5), rnd.uniform(400, 1300)
        dr.line((x0, y, x0 + length, y - length * rnd.uniform(0.02, 0.06)), fill=int(rnd.uniform(60, 255)),
                width=rnd.choice([1, 2, 2, 3, 5]))
    lines = lines.filter(ImageFilter.GaussianBlur(2.5))
    glow = np.asarray(lines.filter(ImageFilter.GaussianBlur(18))).astype(float)[..., None] / 255
    lines = np.asarray(lines).astype(float)[..., None] / 255
    bg = bg + (lines * 0.9 + glow * 1.3) * (np.array(streak, float) / 255)
    bg = bg + (cone((1300, -300), (800, 450), 30, soft=1.0) * 0.10)[..., None] * np.array((1, 0.95, 0.9))
    # the wet floor: the bike mirrored under its wheels, fading out
    rows = np.where(alpha.max(axis=1) > 0.5)[0]
    bottom = int(rows.max())
    n = min(H - bottom, bottom)
    mirror = np.zeros((H, W, 3))
    mirror[bottom:bottom + n] = bike[bottom - n:bottom][::-1]
    mirror_a = np.zeros((H, W))
    mirror_a[bottom:bottom + n] = alpha[bottom - n:bottom][::-1] * np.linspace(0.35, 0, n)[:, None]
    mirror = np.asarray(Image.fromarray((np.clip(mirror, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)))
    bg = bg * (1 - mirror_a[..., None]) + mirror.astype(float) / 255 * mirror_a[..., None]
    img = bike * alpha[..., None] + bg * (1 - alpha[..., None])
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    v = np.hypot((xx - W * 0.5) / (W * 0.62), (yy - H * 0.5) / (H * 0.66))
    img = img * np.clip(1.08 - v ** 2.2 * 0.8, 0.10, 1)[..., None]
    img = 1 - np.exp(-img * 1.9)
    img = img / (1 - math.exp(-1.9))
    img = np.clip(img + np.random.default_rng(seed).normal(0, 0.018, (H, W, 1)), 0, 1)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((img * 255).astype(np.uint8)).save(os.path.join(OUT, f"{slug}.jpg"), quality=86, optimize=True,
                                                       progressive=True)
    ys, xs = np.where(alpha > 0.5)
    return {"focus": [round(xs.mean() / W * 100), round(ys.mean() / H * 100)], "source": key,
            "brand": BRAND.get(key, "Giant"), "credit": CREDITS[scene[0]]}


# The first heroes, built from the brands' studio shots (python tools/build_blog_heroes.py --studio [slug ...]).
# slug: source, crop centre x/y and width (fractions), the beam (from, to, half-angle), its colour, and extras
STUDIO = {
    "new-prices-per-brand": dict(key="trek-domane-slr9", cx=0.56, cy=0.52, width=0.46, light=(1250, -260), target=(1050, 560),
                                 spread=19, colour=WARM),
    "groupset-new-prices": dict(key="tcr-sl-crank", cx=0.66, cy=0.62, width=0.62, light=(1350, -250), target=(900, 560),
                                spread=17, colour=WARM, gain=2.4),
    "how-fast-bikes-lose-value": dict(key="tcr-head", cx=0.60, cy=0.42, width=0.58, light=(300, -300), target=(760, 420),
                                      spread=17, colour=COOL, tint=(0.95, 1.0, 1.08)),
    "reading-a-bike-ad": dict(key="defy-bars", cx=0.50, cy=0.42, width=0.62, light=(800, -420), target=(800, 330),
                              spread=20, colour=WARM),
    "spotting-a-stolen-bike": dict(key="lock", cx=0.42, cy=0.60, width=0.62, light=(1100, -300), target=(640, 560),
                                   spread=13, colour=(255, 214, 170), ambient=0.05, haze=0.10, blur=5,
                                   tint=(1.0, 0.94, 0.88), sat=0.45, gain=1.25),
    "what-a-groupset-tells-you": dict(key="tcr-105", cx=0.62, cy=0.62, width=0.62, light=(300, -260), target=(930, 560),
                                      spread=15, colour=MINT),
    "trek-domane": dict(key="trek-domane-sl6", cx=0.52, cy=0.50, width=0.55, light=(1250, -300), target=(980, 620),
                        spread=19, colour=AMBER),
    "giant-tcr-advanced": dict(key="tcr-sl-cockpit", cx=0.50, cy=0.50, width=0.72, light=(1350, -300), target=(1000, 560),
                               spread=17, colour=(230, 205, 255)),
    "cannondale-topstone": dict(key="topstone-c2", cx=0.46, cy=0.50, width=0.55, light=(400, -300), target=(760, 470),
                                spread=20, colour=(220, 255, 200)),
    "buying-in-autumn": dict(key="defy-fork", cx=0.50, cy=0.55, width=0.80, light=(1350, -250), target=(760, 520),
                             spread=17, colour=AMBER, tint=(1.05, 0.92, 0.80), dust=260),
    "winter-bike": dict(key="snow", cx=0.62, cy=0.56, width=0.62, light=(1100, -300), target=(820, 520), spread=22,
                        colour=ICE, ambient=0.08, haze=0.12, blur=5, tint=(0.92, 0.98, 1.08), dust=420, bg=(8, 10, 14),
                        gain=0.95, sat=0.7),
    "selling-in-spring": dict(key="revolt-badge", cx=0.50, cy=0.52, width=0.80, light=(350, -280), target=(840, 450),
                              spread=16, colour=MINT),
}


# The heroes now on the site: atmospheric Unsplash photos, graded in the spotlight style by mood().
# slug: source, crop centre x/y and width (fractions of the photo), the beam (from, to; pixels of the 1600x900 hero),
# the focus point that tiles keep in view, and the grade.
HEROES = {
    "new-prices-per-brand": dict(key="unsplash:vj4Qi9ToRXQ", cx=0.48, cy=0.55, width=0.95, light=(1100, -300),
                                 target=(750, 450), focus=(750, 450), base=0.55, gain=0.8, colour=WARM, sat=0.85),
    "groupset-new-prices": dict(key="unsplash:itzedAcA6zc", cx=0.45, cy=0.55, width=0.9, light=(1250, -260),
                                target=(620, 480), focus=(620, 480), base=0.30, gain=1.0, gamma=1.35, colour=WARM),
    "how-fast-bikes-lose-value": dict(key="unsplash:jSjbkyJAmIo", cx=0.5, cy=0.6, width=0.95, light=(300, -300),
                                      target=(715, 450), focus=(715, 450), base=0.45, gain=0.8, gamma=1.3,
                                      colour=AMBER, sat=0.8),
    "reading-a-bike-ad": dict(key="unsplash:9phJzNSAEW4", cx=0.55, cy=0.45, width=0.95, light=(1050, -320),
                              target=(1050, 380), focus=(1050, 360), base=0.75, gain=0.7, colour=COOL, sat=0.9),
    "spotting-a-stolen-bike": dict(key="unsplash:gaeP0enIkiQ", cx=0.5, cy=0.55, width=0.95, light=(1150, -300),
                                   target=(834, 360), focus=(834, 340), base=0.32, gain=0.9, gamma=1.4,
                                   colour=(255, 214, 170), tint=(0.88, 0.95, 1.08), sat=0.7),
    "what-a-groupset-tells-you": dict(key="unsplash:9mZVRcC9rN4", cx=0.5, cy=0.5, width=0.9, light=(400, -300),
                                      target=(800, 420), focus=(800, 400), base=0.7, gain=0.7, colour=MINT, sat=0.85),
    "trek-domane": dict(key="unsplash:nIdWCuL-61M", cx=0.5, cy=0.5, width=0.88, light=(1350, -300), target=(1160, 620),
                        focus=(1160, 640), base=0.55, gain=0.75, colour=AMBER, tint=(1.06, 1.0, 0.9)),
    "giant-tcr-advanced": dict(key="unsplash:ZZay7O20jgc", cx=0.55, cy=0.55, width=0.95, light=(1450, -250),
                               target=(1050, 450), focus=(1050, 450), base=0.6, gain=0.7, colour=(230, 205, 255),
                               sat=0.85),
    "cannondale-topstone": dict(key="unsplash:zEdh7yYIwBU", cx=0.45, cy=0.5, width=0.95, light=(1500, -150),
                                target=(600, 450), focus=(560, 560), base=0.6, gain=0.6, colour=(220, 255, 200),
                                gamma=1.3),
    "buying-in-autumn": dict(key="unsplash:fkb2fVN2pkI", cx=0.6, cy=0.6, width=0.8, light=(850, -300),
                             target=(860, 480), focus=(860, 480), base=0.55, gain=0.75, colour=AMBER,
                             tint=(1.05, 0.95, 0.85), dust=160),
    "winter-bike": dict(key="unsplash:HPpj2190tGs", cx=0.5, cy=0.58, width=0.95, light=(1100, -300), target=(800, 495),
                        focus=(800, 495), base=0.45, gain=0.8, gamma=1.3, colour=ICE, tint=(0.9, 0.96, 1.08), sat=0.75,
                        dust=300),
    "selling-in-spring": dict(key="unsplash:oZUT7x06YvY", cx=0.55, cy=0.55, width=0.9, light=(500, -250),
                              target=(1150, 600), focus=(1170, 600), base=0.6, gain=0.6, colour=WARM, gamma=1.25),
}


# The model articles: the brand's own photo of that bike, staged by stage() in front of the article's scene.
MODELS = {
    "trek-domane": dict(key="trek-domane-sl6", cx=0.5, cy=0.54, width=1.45, scene=("unsplash:nIdWCuL-61M", 0.5, 0.5, 0.88),
                        streak=(255, 170, 90), rim=(255, 200, 150)),
    "giant-tcr-advanced": dict(key="tcr-sl1", cx=0.5, cy=0.54, width=1.4, scene=("unsplash:ZZay7O20jgc", 0.55, 0.55, 0.95),
                               streak=(120, 170, 255), rim=(200, 220, 255)),
    "cannondale-topstone": dict(key="topstone-c2", cx=0.5, cy=0.54, width=1.4,
                                scene=("unsplash:zEdh7yYIwBU", 0.45, 0.5, 0.95), streak=(190, 255, 150),
                                rim=(230, 255, 200)),
}


if __name__ == "__main__":
    if sys.argv[1:2] == ["--search"]:
        search(" ".join(sys.argv[2:]))
        sys.exit()
    studio = sys.argv[1:2] == ["--studio"]
    only = sys.argv[2:] if studio else sys.argv[1:]
    path = os.path.join(OUT, "heroes.json")
    meta = json.load(open(path)) if os.path.exists(path) else {}
    for slug, spec in (STUDIO if studio else HEROES).items():
        if only and slug not in only:
            continue
        if not studio and slug in MODELS:
            meta[slug] = stage(slug, seed=sum(map(ord, slug)), **MODELS[slug])
        else:
            meta[slug] = (spotlight if studio else mood)(slug, seed=sum(map(ord, slug)), **spec)
        print("built", slug)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(meta.items())), f, indent=1)
