"""Build the blog's hero images (webapp/static/blog/heroes/<slug>.jpg) from the catalogue's own product photos.

Each hero is a "night studio": bikes cut out of their white or grey product-shot background, set on a dark
backdrop with a coloured glow and a soft floor reflection, so the twelve launch articles look like one series.
Run it again after changing a layout: python tools/build_blog_heroes.py
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGES = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "webapp", "static", "blog", "heroes")
W, H = 1600, 900
GREEN, BLUE, AMBER, PINK, RED = (52, 211, 153), (122, 184, 255), (242, 194, 122), (231, 160, 240), (255, 110, 100)


def cutout(name):
    """The bike from a product shot, on a transparent background."""
    im = Image.open(os.path.join(IMAGES, name)).convert("RGB")
    a = np.asarray(im).astype(int)
    h, w, _ = a.shape
    corners = np.concatenate([a[:5, :5].reshape(-1, 3), a[:5, -5:].reshape(-1, 3),
                              a[-5:, :5].reshape(-1, 3), a[-5:, -5:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.abs(a - bg).max(axis=2)
    m = Image.fromarray(np.where(dist < 28, 255, 0).astype(np.uint8)).copy()
    for x in range(0, w, 7):  # the background around the bike, reached from the edges
        for y in (0, h - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(0, h, 7):
        for x in (0, w - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    big = w * h * 0.00015  # and the larger pockets inside the frame and between the spokes
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 100)
                arr = np.asarray(m).copy()
                arr[arr == 100] = 128 if (arr == 100).sum() > big else 50
                m = Image.fromarray(arr).copy()
    bgmask = np.asarray(m) == 128
    # Next to the background a pixel is the bike mixed with it: alpha from how far it is from the background,
    # and the colour un-mixed, so thin spokes and cables survive.
    band = np.asarray(Image.fromarray((bgmask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 0
    alpha = np.where(bgmask, 0.0, np.where(band, np.clip(dist / 150.0, 0, 1), 1.0))
    al = np.maximum(alpha, 1e-3)[..., None]
    unmixed = np.clip((a - (1 - al) * bg) / al, 0, 255)
    rgb = np.where((band & ~bgmask)[..., None], unmixed, a)
    out = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")
    return out.crop(out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox())


def backdrop(top=(22, 24, 29), bottom=(8, 9, 11), glow=GREEN, glow_at=(0.5, 0.78), glow_size=(0.55, 0.32), strength=0.35):
    y = np.linspace(0, 1, H)[:, None, None]
    base = np.array(top) * (1 - y) + np.array(bottom) * y
    img = np.broadcast_to(base, (H, W, 3)).astype(float).copy()
    yy, xx = np.mgrid[0:H, 0:W]
    d = ((xx / W - glow_at[0]) / glow_size[0]) ** 2 + ((yy / H - glow_at[1]) / glow_size[1]) ** 2
    img += np.exp(-d * 2.2)[..., None] * np.array(glow) * strength
    # a faint grain keeps the gradient from banding
    img += np.random.default_rng(1).normal(0, 2.0, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


def place(canvas, bike, cx, floor, height, opacity=1.0, reflect=True, tint=None):
    b = bike.resize((int(bike.width * height / bike.height), height), Image.LANCZOS)
    if tint is not None:  # pushed back into the dark
        dark = Image.new("RGBA", b.size, tint + (255,))
        b = Image.composite(Image.blend(b, dark, 0.45), Image.new("RGBA", b.size, (0, 0, 0, 0)), b.getchannel("A"))
    if opacity < 1:
        b.putalpha(b.getchannel("A").point(lambda v: int(v * opacity)))
    x, y = int(cx - b.width / 2), int(floor - b.height)
    if reflect:
        r = b.transpose(Image.FLIP_TOP_BOTTOM)
        fade = Image.linear_gradient("L").resize(r.size).point(lambda v: int(max(0, 255 - v * 2.4) * 0.22))
        r.putalpha(Image.composite(fade, Image.new("L", r.size, 0), r.getchannel("A")))
        canvas.alpha_composite(r, (x, int(floor) + 2))
    canvas.alpha_composite(b, (x, y))
    return x, y, b


def floor_line(canvas, y, colour=GREEN, alpha=70):
    d = ImageDraw.Draw(canvas)
    for i in range(W):
        a = int(alpha * math.sin(math.pi * i / W) ** 2)
        d.point((i, y), fill=colour + (a,))


def save(canvas, slug):
    os.makedirs(OUT, exist_ok=True)
    canvas.convert("RGB").save(os.path.join(OUT, f"{slug}.jpg"), quality=84, optimize=True, progressive=True)
    print("wrote", slug)


def overlay(canvas, draw_fn):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    canvas.alpha_composite(layer)


def hero_brands():
    c = backdrop(glow=GREEN, glow_at=(0.5, 0.72))
    bikes = ["Cube/Nuroad_ONE_colour_spicypapaya_n_black.jpg", "Giant/TCR_Advanced_2_colour_Stealth_Chrome.jpg",
             "Trek/Domane_SL_5_Gen_5_colour_Matte_Deep_Smoke.jpg", "Scott/Addict_RC_10_colour_sunbeam_black.jpg",
             "Factor/ELARA_SRAM_Red_XPLR_w_Power_Meter_colour_Virescent_Blue.jpg"]
    # cheapest to dearest, left to right, each a step bigger: the price ladder across brands
    for i, name in enumerate(bikes):
        place(c, cutout(name), [165, 465, 765, 1060, 1350][i], 660, [175, 195, 215, 230, 225][i])
    floor_line(c, 662)
    save(c, "new-prices-per-brand")


def hero_groupset_prices():
    c = backdrop(glow=GREEN, glow_at=(0.55, 0.7), glow_size=(0.5, 0.5), strength=0.4)
    bike = cutout("Trek/Domane_SL_6_gen_4_colour_Dark_Star_to_Bronze_Age_Fade.jpg")
    # the drivetrain up close: crankset, chain and rear derailleur
    crop = bike.crop((int(bike.width * 0.1), int(bike.height * 0.5), int(bike.width * 0.72), bike.height))
    crop = crop.resize((int(crop.width * 1500 / crop.width), int(crop.height * 1500 / crop.width)), Image.LANCZOS)
    c.alpha_composite(crop, (60, H - crop.height + 60))
    save(c, "groupset-new-prices")


def hero_value():
    c = backdrop(glow=GREEN, glow_at=(0.25, 0.75))
    bike = cutout("Canyon/Ultimate_CF_SLX_8_Di2/2026_FULL_ultimate_cf-slx-8-di2_4066_R100_P08.jpg")
    # the same bike, a little smaller and fainter each step: value fading with the years
    for cx, op, hgt in [(360, 1.0, 420), (820, 0.5, 320), (1170, 0.27, 250), (1430, 0.13, 190)]:
        place(c, bike, cx, 740, hgt, opacity=op, reflect=op == 1.0)
    floor_line(c, 742)
    save(c, "how-fast-bikes-lose-value")


def hero_reading_ad():
    c = backdrop(glow=BLUE, strength=0.3)
    place(c, cutout("Giant/TCR_Advanced_1_colour_Purple_Haze_Ultra_Violet.jpg"), W / 2, 700, 460)
    def draw(d):
        # a viewfinder: corner brackets and one scan line across the bike
        x0, y0, x1, y1, L = 330, 150, 1270, 760, 70
        for (x, y, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            d.line([(x, y + dy * L), (x, y), (x + dx * L, y)], fill=BLUE + (230,), width=6)
        for k in range(26):
            d.line([(x0 + 20, 470 + k), (x1 - 20, 470 + k)], fill=BLUE + (int(60 * (1 - k / 26)),))
        d.line([(x0 + 20, 470), (x1 - 20, 470)], fill=BLUE + (255,), width=3)
    overlay(c, draw)
    save(c, "reading-a-bike-ad")


def hero_stolen():
    c = backdrop(top=(30, 18, 20), bottom=(10, 8, 9), glow=RED, strength=0.32)
    bike = cutout("Specialized/Allez_Shimano_CUES_colour_Obsidian.jpg")
    b = bike.resize((int(bike.width * 470 / bike.height), 470), Image.LANCZOS)
    # only the outline is left where the bike stood
    edge = b.getchannel("A").point(lambda v: 255 if v > 100 else 0).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    outline = Image.new("RGBA", b.size, RED + (0,))
    outline.putalpha(edge.point(lambda v: int(v * 0.85)))
    x, y = int(W / 2 - b.width / 2), 700 - b.height
    glow = outline.filter(ImageFilter.GaussianBlur(8))
    c.alpha_composite(glow, (x, y))
    c.alpha_composite(outline, (x, y))
    floor_line(c, 702, RED)
    save(c, "spotting-a-stolen-bike")


def hero_tiers():
    c = backdrop(glow=BLUE, glow_at=(0.6, 0.85), strength=0.25)
    steps = [(23, 58, 45), (23, 90, 64), (29, 130, 95), (60, 175, 135), (123, 227, 185)]
    def draw(d):
        for i, col in enumerate(steps):
            x = 90 + i * 290
            top = 800 - (i + 1) * 95
            d.rounded_rectangle([x, top, x + 270, 900], radius=10, fill=col + (255,))
    overlay(c, draw)
    for i, name in [(0, "Trek/Domane_AL_2_Gen_4_colour_Matte_Dark_Star_Black.jpg"),
                    (2, "Trek/Domane_SL_5_Gen_5_colour_Matte_Deep_Smoke.jpg"),
                    (4, "Trek/Domane_SLR_9_Gen_5_colour_Matte_Deep_Smoke.jpg")]:
        place(c, cutout(name), 90 + i * 290 + 135, 800 - (i + 1) * 95, 190, reflect=False)
    save(c, "what-a-groupset-tells-you")


def hero_family(slug, front, back_left, back_right, glow):
    c = backdrop(glow=glow, strength=0.33)
    place(c, cutout(back_left), 330, 600, 270, tint=(12, 13, 16))
    place(c, cutout(back_right), 1270, 600, 270, tint=(12, 13, 16))
    place(c, cutout(front), W / 2, 800, 470)
    floor_line(c, 792, glow)
    save(c, slug)


def hero_season(slug, top, bottom, glow, bikes, particles):
    c = backdrop(top=top, bottom=bottom, glow=glow, strength=0.36)
    rnd = random.Random(slug)
    def draw(d):
        for _ in range(particles[0]):
            x, y, r = rnd.uniform(0, W), rnd.uniform(0, H * 0.8), rnd.uniform(*particles[1])
            d.ellipse([x - r, y - r * particles[2], x + r, y + r * particles[2]], fill=particles[3] + (rnd.randint(40, 150),))
    overlay(c, draw)
    for (name, cx, height, tint) in bikes:
        place(c, cutout(name), cx, 760, height, tint=tint)
    floor_line(c, 762, glow)
    save(c, slug)


if __name__ == "__main__":
    hero_brands()
    hero_groupset_prices()
    hero_value()
    hero_reading_ad()
    hero_stolen()
    hero_tiers()
    hero_family("trek-domane", "Trek/Domane_SL_6_gen_4_colour_Dark_Star_to_Bronze_Age_Fade.jpg",
                "Trek/Domane_AL_2_Gen_4_colour_Matte_Dark_Star_Black.jpg", "Trek/Domane_SLR_9_Gen_5_colour_Matte_Deep_Smoke.jpg", AMBER)
    hero_family("giant-tcr-advanced", "Giant/TCR_Advanced_1_colour_Purple_Haze_Ultra_Violet.jpg",
                "Giant/TCR_Advanced_2_colour_Stealth_Chrome.jpg", "Giant/TCR_Advanced_SL_1_colour_Blue_Dragonfly_Iris.jpg", AMBER)
    hero_family("cannondale-topstone", "Cannondale/Topstone_Carbon_2_AXS_1x_colour_Spruce_Green.jpg",
                "Cannondale/Topstone_1_colour_Obsidian.jpg", "Cannondale/Topstone_Carbon_1_Lefty_colour_Rally_Red.jpg", AMBER)
    hero_season("buying-in-autumn", (40, 26, 16), (10, 8, 7), (242, 150, 70),
                [("Trek/Checkpoint_ALR_3_Gen_3_colour_Dark_Carmine.jpg", 800, 470, None)],
                (70, (5, 11), 0.55, (230, 130, 50)))
    hero_season("winter-bike", (20, 30, 44), (7, 9, 13), (140, 190, 255),
                [("Cannondale/Topstone_3_colour_Storm_Cloud.jpg", 560, 380, (12, 13, 16)),
                 ("Cube/Nuroad_ONE_colour_spicypapaya_n_black.jpg", 1000, 460, None)],
                (240, (1.2, 3.5), 1.0, (225, 235, 255)))
    hero_season("selling-in-spring", (22, 34, 28), (8, 10, 9), (120, 230, 170),
                [("Canyon/Endurace_AllRoad/2025_FULL_endurace_all-road-5_4164_R138_P01.jpg", 800, 470, None)],
                (40, (3, 7), 1.0, (231, 160, 240)))
