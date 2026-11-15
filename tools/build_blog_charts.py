"""Build the charts in the blog articles: webapp/static/blog/charts/<name>.<lang>.svg, one per language.

The SVGs are put inline in the article (webapp/blog.py), so they use the page's fonts and colours (CSS variables);
open on their own they show in plain black. The numbers are the ones in the articles: catalogue new prices, the
archived per-year prices and the value estimator's rules (webapp/checks.py check_value). Run:
python tools/build_blog_charts.py
"""
import os
from html import escape

OUT = os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "blog", "charts")
W = 720
TIER = ["#3A3E48", "#173A2D", "#1F5A43", "#2E8F67", "#34D399"]  # basic .. top, as the tier badges


def eur(v, lang):
    s = f"{round(v):,}"
    return "€" + (s.replace(",", ".") if lang == "nl" else s)


def t(x, y, text, cls="lbl", anchor="start", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{extra}>{escape(str(text))}</text>'


def svg(h, body, title):
    return (f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{escape(title)}" xmlns="http://www.w3.org/2000/svg">'
            f'<title>{escape(title)}</title>{"".join(body)}</svg>\n')


def write(name, lang, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"{name}.{lang}.svg"), "w", encoding="utf-8") as f:
        f.write(content)


def axis(x0, x1, y_top, y_bot, vmax, step, lang, scale):
    out = []
    v = 0
    while v <= vmax:
        x = scale(v)
        out.append(f'<line x1="{x:.1f}" y1="{y_top}" x2="{x:.1f}" y2="{y_bot}" class="grid"/>')
        out.append(t(x, y_bot + 18, eur(v, lang) if v else "€0", "tick", "middle"))
        v += step
    return out


# 1. New price per brand: cheapest to dearest, the median as a dot
BRANDS = [("Factor", 51, 11399, 4699, 25799), ("Wilier", 48, 8700, 1899, 22800), ("Cervélo", 45, 7999, 2999, 13999),
          ("Specialized", 201, 5999, 999, 17000), ("Orbea", 51, 5699, 1699, 12999), ("Canyon", 43, 5599, 999, 20350),
          ("BMC", 99, 5499, 1999, 23000), ("Bianchi", 65, 5200, 1390, 21885), ("Scott", 54, 4999, 1499, 12999),
          ("Trek", 121, 4899, 699, 14399), ("Cannondale", 56, 4499, 1299, 15799), ("Ridley", 85, 4499, 999, 12499),
          ("Giant", 109, 3899, 749, 12499), ("Lapierre", 31, 3899, 999, 10499), ("Rose", 26, 3410, 1020, 8650),
          ("Cube", 51, 3299, 799, 9999)]


def brand_prices(lang):
    x0, x1, top, row = 120, W - 70, 40, 26
    scale = lambda v: x0 + (x1 - x0) * v / 26000
    h = top + row * len(BRANDS) + 40
    b = [t(x0, 18, "Nieuwprijs per merk: goedkoopste tot duurste, stip = mediaan" if lang == "nl"
           else "New price per brand: cheapest to dearest, dot = median", "cap")]
    b += axis(x0, x1, top - 10, h - 34, 25000, 5000, lang, scale)
    for i, (name, n, med, lo, hi) in enumerate(BRANDS):
        y = top + i * row + 8
        b.append(t(x0 - 12, y + 4, name, "lbl", "end"))
        b.append(f'<line x1="{scale(lo):.1f}" y1="{y}" x2="{scale(hi):.1f}" y2="{y}" class="range"/>')
        b.append(f'<circle cx="{scale(med):.1f}" cy="{y}" r="6" class="dot"/>')
        b.append(t(scale(hi) + 8, y + 4, eur(med, lang), "val"))
    write("brand-prices", lang, svg(h, b, "Nieuwprijs per merk" if lang == "nl" else "New price per brand"))


# 2. Median new price per groupset, coloured by tier
GROUPSETS = [("Shimano Claris", 999, 0), ("Shimano Sora", 1149, 0), ("Shimano Tiagra", 1799, 1), ("Shimano 105", 2599, 2),
             ("Shimano GRX", 2990, 2), ("SRAM Apex", 2999, 1), ("Shimano 105 Di2", 3999, 2), ("SRAM Rival", 4999, 2),
             ("Shimano Ultegra", 4999, 3), ("Shimano Ultegra Di2", 6499, 3), ("SRAM Force", 7499, 3),
             ("Shimano Dura-Ace Di2", 10799, 4), ("SRAM Red", 11999, 4), ("Campagnolo Super Record", 14349, 4)]


def groupset_prices(lang):
    x0, x1, top, row = 190, W - 80, 40, 27
    scale = lambda v: x0 + (x1 - x0) * v / 15000
    h = top + row * len(GROUPSETS) + 46
    names = ["Basis", "Instap", "Midden", "Performance", "Top"] if lang == "nl" else ["Basic", "Entry", "Mid", "Performance", "Top"]
    b = [t(x0, 18, "Mediane nieuwprijs van een fiets, per groepset" if lang == "nl" else "Median new price of a bike, per groupset", "cap")]
    for i, (name, med, tier) in enumerate(GROUPSETS):
        y = top + i * row
        b.append(t(x0 - 12, y + 14, name, "lbl", "end"))
        b.append(f'<rect x="{x0}" y="{y + 2}" width="{scale(med) - x0:.1f}" height="17" rx="3" style="fill:{TIER[tier]}"/>')
        b.append(t(scale(med) + 8, y + 15, eur(med, lang), "val"))
    ly = h - 16
    for k, name in enumerate(names):
        lx = x0 + k * 100
        b.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" style="fill:{TIER[k]}"/>')
        b.append(t(lx + 18, ly, name, "tick"))
    write("groupset-prices", lang, svg(h, b, "Nieuwprijs per groepset" if lang == "nl" else "New price per groupset"))


# 3. The value curve for a €5,000 bike, with the fair range around it
def value_factor(age):
    return 0.80 if age == 0 else 0.75 * 0.88 ** (age - 1)


def value_curve(lang):
    x0, x1, y0, y1 = 70, W - 30, 40, 300
    sx = lambda a: x0 + (x1 - x0) * a / 10
    sy = lambda v: y1 - (y1 - y0) * v / 5000
    h = y1 + 46
    b = [t(x0, 18, "Waarde van een fiets van €5.000 nieuw, normaal gebruik" if lang == "nl"
           else "Value of a bike that cost €5,000 new", "cap")]
    for v in range(0, 5001, 1000):
        b.append(f'<line x1="{x0}" y1="{sy(v):.1f}" x2="{x1}" y2="{sy(v):.1f}" class="grid"/>')
        b.append(t(x0 - 8, sy(v) + 4, eur(v, lang), "tick", "end"))
    pts = [(a, 5000 * value_factor(a)) for a in range(0, 11)]
    band = [(sx(a), sy(v * 1.1)) for a, v in pts] + [(sx(a), sy(v * 0.9)) for a, v in reversed(pts)]
    b.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in band) + '" class="band"/>')
    b.append(f'<line x1="{x0}" y1="{sy(5000):.1f}" x2="{x1}" y2="{sy(5000):.1f}" class="ref"/>')
    b.append(t(x1, sy(5000) - 6, "nieuwprijs" if lang == "nl" else "new price", "tick", "end"))
    b.append('<polyline points="' + " ".join(f"{sx(a):.1f},{sy(v):.1f}" for a, v in pts) + '" class="line"/>')
    for a, v in pts:
        b.append(f'<circle cx="{sx(a):.1f}" cy="{sy(v):.1f}" r="4" class="dot"/>')
        if a in (0, 2, 4, 6, 8, 10):
            b.append(t(sx(a), sy(v) - 12, eur(round(v, -1), lang), "val", "middle"))
        b.append(t(sx(a), y1 + 18, str(a), "tick", "middle"))
    b.append(t((x0 + x1) / 2, y1 + 38, "jaar oud · de band is de eerlijke prijs (±10%)" if lang == "nl"
               else "years old · the band is the fair price (±10%)", "tick", "middle"))
    write("value-curve", lang, svg(h, b, "Waardecurve" if lang == "nl" else "Value curve"))


def dumbbell(name, lang, rows, title, vmax, step, x0=230):
    """then -> now per row: an arrow from the old new price to the current one."""
    x1, top, row = W - 40, 50, 48
    scale = lambda v: x0 + (x1 - x0) * v / vmax
    h = top + row * len(rows) + 30
    b = [t(16, 18, title, "cap")]
    b += axis(x0, x1, top - 14, h - 34, vmax, step, lang, scale)
    for i, (label, (y_then, p_then), (y_now, p_now)) in enumerate(rows):
        y = top + i * row + 6
        up = p_now > p_then
        b.append(t(x0 - 12, y + 4, label, "lbl", "end"))
        b.append(f'<line x1="{scale(p_then):.1f}" y1="{y}" x2="{scale(p_now):.1f}" y2="{y}" class="{"up" if up else "down"}"/>')
        b.append(f'<circle cx="{scale(p_then):.1f}" cy="{y}" r="5" class="then"/>')
        b.append(f'<circle cx="{scale(p_now):.1f}" cy="{y}" r="6" class="{"up-dot" if up else "down-dot"}"/>')
        left, right = sorted([(scale(p_then), f"{y_then}: {eur(p_then, lang)}"), (scale(p_now), f"{y_now}: {eur(p_now, lang)}")])
        if right[0] - left[0] < 1:  # the same price twice: one label
            b.append(t(left[0], y - 12, f"{y_then}–{y_now}: {eur(p_now, lang)}", "val", "middle"))
            continue
        # each label leans away from the other, so close prices don't overlap
        b.append(t(left[0] + 6, y - 12, left[1], "val", "end"))
        b.append(t(right[0] - 6, y - 12, right[1], "val", "start"))
    write(name, lang, svg(h, b, title))


# 4. Ad years: 72 checked ads, as squares
AD_YEARS = [(34, "ok", "Jaar, foto's en onderdelen kloppen", "Year, photos and parts agree"),
            (14, "warn", "Jaar uit de specificaties wijkt af", "Spec year differs"),
            (13, "warn2", "Jaar in de tekst wijkt af van foto en specificaties", "Ad's year differs from photo and spec"),
            (4, "warn3", "Foto wijst op een ander jaar", "Photo points to another year"),
            (1, "bad", "Alle drie verschillend", "All three differ"),
            (5, "unk", "Geen jaar uit de specificaties", "No spec year"),
            (1, "unk2", "Geen model gevonden", "No model matched")]


def ad_years(lang):
    size, gap, cols, x0, y0 = 26, 5, 18, 16, 36
    h = y0 + 4 * (size + gap) + 30 + 22 * len(AD_YEARS)
    b = [t(x0, 18, "72 gecheckte advertenties: klopt het bouwjaar?" if lang == "nl" else "72 checked ads: is the model year right?", "cap")]
    k = 0
    for n, cls, _nl, _en in AD_YEARS:
        for _ in range(n):
            x, y = x0 + (k % cols) * (size + gap), y0 + (k // cols) * (size + gap)
            b.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="4" class="sq {cls}"/>')
            k += 1
    ly = y0 + 4 * (size + gap) + 22
    for i, (n, cls, nl, en) in enumerate(AD_YEARS):
        y = ly + i * 22
        b.append(f'<rect x="{x0}" y="{y - 12}" width="14" height="14" rx="3" class="sq {cls}"/>')
        b.append(t(x0 + 22, y, f"{n} · {nl if lang == 'nl' else en}", "lbl"))
    write("ad-years", lang, svg(h, b, "Bouwjaar in advertenties" if lang == "nl" else "Model year in ads"))


# 5. Price verdicts: where an asking price lands, for a fair range of €1,620 to €1,980
def price_zones(lang):
    low, high = 1620, 1980
    x0, x1, y = 30, W - 30, 70
    vmax = 2600
    s = lambda v: x0 + (x1 - x0) * v / vmax
    zones = [(0, low * 0.6, "bad", "Verdacht goedkoop", "Suspiciously cheap"),
             (low * 0.6, low * 0.95, "okish", "Onder de eerlijke band", "Below the fair range"),
             (low * 0.95, high, "ok", "Eerlijke prijs", "Fair price"),
             (high, vmax, "warn", "Te hoog", "Too high")]
    b = [t(x0, 18, "Waar een vraagprijs landt, bij een eerlijke band van €1.620 tot €1.980" if lang == "nl"
           else "Where an asking price lands, for a fair range of €1,620 to €1,980", "cap")]
    for a, z, cls, nl, en in zones:
        b.append(f'<rect x="{s(a):.1f}" y="{y}" width="{s(z) - s(a):.1f}" height="34" class="zone {cls}"/>')
        b.append(t((s(a) + s(z)) / 2, y + 56, nl if lang == "nl" else en, "lbl", "middle"))
    for v in (round(low * 0.6), round(low * 0.95), high):
        b.append(f'<line x1="{s(v):.1f}" y1="{y - 8}" x2="{s(v):.1f}" y2="{y + 42}" class="tickline"/>')
        b.append(t(s(v), y - 14, eur(v, lang), "val", "middle"))
    write("price-zones", lang, svg(160, b, "Prijsoordelen" if lang == "nl" else "Price verdicts"))


# 6. The tier ladder, and how a groupset slides down with age
def tier_ladder(lang):
    names = ["Basis", "Instap", "Midden", "Performance", "Top"] if lang == "nl" else ["Basic", "Entry", "Mid", "Performance", "Top"]
    groups = ["Claris · Sora", "Tiagra · CUES · Apex", "105 · Rival", "Ultegra · Force", "Dura-Ace · Red"]
    x0, base, step_w, step_h = 20, 300, 136, 46
    b = [t(x0, 18, "De vijf niveaus, en een Ultegra uit 2015 die twee treden zakt" if lang == "nl"
           else "The five tiers, and a 2015 Ultegra sliding down two steps", "cap")]
    for i in range(5):
        x, top = x0 + i * step_w, base - (i + 1) * step_h
        b.append(f'<rect x="{x}" y="{top}" width="{step_w - 6}" height="{base - top}" rx="6" style="fill:{TIER[i]}"/>')
        b.append(t(x + 10, top + 20, f"{i + 1} · {names[i]}", "lbl strong" if i >= 3 else "lbl"))
        b.append(t(x + 10, top + 38, groups[i], "tick"))
    # arrow from Performance (2015) to Entry (now)
    ax1, ay1 = x0 + 3 * step_w + 60, base - 4 * step_h - 22
    ax2, ay2 = x0 + 1 * step_w + 60, base - 2 * step_h - 22
    b.append(f'<path d="M{ax1},{ay1} C{ax1 - 60},{ay1 - 70} {ax2 + 60},{ay2 - 90} {ax2},{ay2}" class="arrow"/>')
    b.append(f'<path d="M{ax2 - 7},{ay2 - 12} L{ax2},{ay2} L{ax2 + 9},{ay2 - 9}" class="arrow"/>')
    b.append(t((ax1 + ax2) / 2, min(ay1, ay2) - 62, "−1 niveau per 5 jaar (max. 2)" if lang == "nl" else "−1 tier per 5 years (max 2)", "val", "middle"))
    write("tier-ladder", lang, svg(base + 14, b, "Groepsetniveaus" if lang == "nl" else "Groupset tiers"))


# 7. Domane line-up today, on one price line
DOMANE = [("AL 2", 999, "AL"), ("AL 4", 1499, "AL"), ("AL 5", 1799, "AL"), ("SL 5 Gen 5", 2499, "SL"), ("SL 5 Gen 4", 2799, "SL"),
          ("SL 6 AXS Gen 5", 3999, "SL"), ("SL 6 Gen 4", 4299, "SL"), ("SL 7 Gen 4", 5499, "SL"), ("SLR 7 Gen 5", 6999, "SLR"),
          ("SLR 9 Gen 5", 9999, "SLR"), ("SLR 9 AXS Gen 5", 10499, "SLR")]


def domane_lineup(lang):
    x0, x1, top, row = 150, W - 90, 40, 26
    scale = lambda v: x0 + (x1 - x0) * v / 11000
    h = top + row * len(DOMANE) + 46
    b = [t(16, 18, "Trek Domane nu: nieuwprijs per uitvoering" if lang == "nl" else "Trek Domane today: new price per build", "cap")]
    b += axis(x0, x1, top - 10, h - 40, 10000, 2500, lang, scale)
    cls = {"AL": "al", "SL": "sl", "SLR": "slr"}
    for i, (name, p, frame) in enumerate(DOMANE):
        y = top + i * row + 8
        b.append(t(x0 - 12, y + 4, "Domane " + name, "lbl", "end"))
        b.append(f'<line x1="{x0}" y1="{y}" x2="{scale(p):.1f}" y2="{y}" class="stem"/>')
        b.append(f'<circle cx="{scale(p):.1f}" cy="{y}" r="7" class="frame {cls[frame]}"/>')
        b.append(t(scale(p) + 12, y + 4, eur(p, lang), "val"))
    ly = h - 12
    for k, (f, label) in enumerate([("al", "AL · aluminium"), ("sl", "SL · OCLV 500 carbon"), ("slr", "SLR · OCLV 800 carbon")]):
        lx = x0 + k * 180
        b.append(f'<circle cx="{lx}" cy="{ly - 4}" r="6" class="frame {f}"/>')
        b.append(t(lx + 12, ly, label, "tick"))
    write("domane-lineup", lang, svg(h, b, "Trek Domane"))


# 8. Used value of a winter bike: new price and the fair range after four years
WINTER = [("Cube Nuroad ONE", 799), ("Trek Domane AL 2", 999), ("Canyon Endurace AllRoad", 999), ("Giant Contend AR 3", 1199),
          ("Trek Checkpoint ALR 3", 1299), ("Cannondale Topstone 3", 1499), ("Giant Revolt 2", 1499)]


def winter_values(lang):
    x0, x1, top, row = 200, W - 40, 44, 30
    scale = lambda v: x0 + (x1 - x0) * v / 1600
    h = top + row * len(WINTER) + 50
    b = [t(16, 18, "Nieuwprijs en eerlijke prijs na vier jaar" if lang == "nl" else "New price and fair price after four years", "cap")]
    b += axis(x0, x1, top - 12, h - 44, 1500, 500, lang, scale)
    f = value_factor(4)
    for i, (name, p) in enumerate(WINTER):
        y = top + i * row + 6
        lo, hi = round(p * f * 0.9, -1), round(p * f * 1.1, -1)
        b.append(t(x0 - 12, y + 4, name, "lbl", "end"))
        b.append(f'<rect x="{scale(lo):.1f}" y="{y - 7}" width="{scale(hi) - scale(lo):.1f}" height="14" rx="7" class="band-bar"/>')
        b.append(f'<line x1="{scale(hi):.1f}" y1="{y}" x2="{scale(p):.1f}" y2="{y}" class="stem"/>')
        b.append(f'<circle cx="{scale(p):.1f}" cy="{y}" r="5" class="then"/>')
        b.append(t(scale(lo) - 6, y + 4, f"{eur(lo, lang)}–{eur(hi, lang)}", "val", "end") if False else "")
    ly = h - 14
    b.append(f'<rect x="{x0}" y="{ly - 10}" width="26" height="12" rx="6" class="band-bar"/>')
    b.append(t(x0 + 34, ly, "eerlijke prijs na 4 jaar" if lang == "nl" else "fair price after 4 years", "tick"))
    b.append(f'<circle cx="{x0 + 240}" cy="{ly - 4}" r="5" class="then"/>')
    b.append(t(x0 + 252, ly, "nieuwprijs nu" if lang == "nl" else "new price now", "tick"))
    write("winter-values", lang, svg(h, b, "Winterfietsen" if lang == "nl" else "Winter bikes"))


# 9. A year of buying and selling: a rough calendar, and the selling plan for spring
def year_ribbon(name, lang, bands, marks, title, note):
    months = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"] if lang == "nl" else \
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    x0, x1, y = 20, W - 20, 70
    mw = (x1 - x0) / 12
    b = [t(x0, 18, title, "cap")]
    for i, m in enumerate(months):
        b.append(f'<rect x="{x0 + i * mw + 1:.1f}" y="{y}" width="{mw - 2:.1f}" height="30" rx="4" class="month"/>')
        b.append(t(x0 + i * mw + mw / 2, y + 20, m, "tick", "middle"))
    for k, (a, z, cls, label) in enumerate(bands):
        by = y + 44 + k * 30
        if z < a:  # wraps over new year
            parts = [(a, 12), (0, z)]
        else:
            parts = [(a, z)]
        for p0, p1 in parts:
            b.append(f'<rect x="{x0 + p0 * mw + 1:.1f}" y="{by}" width="{(p1 - p0) * mw - 2:.1f}" height="22" rx="11" class="season {cls}"/>')
        b.append(t(x0 + parts[0][0] * mw + 12, by + 15, label, "lbl strong-dark" if cls != "now" else "lbl strong-dark"))
    for (mi, label) in marks:
        x = x0 + mi * mw
        b.append(f'<line x1="{x:.1f}" y1="{y - 12}" x2="{x:.1f}" y2="{y + 44 + 30 * len(bands)}" class="nowline"/>')
        b.append(t(x + 4, y - 16, label, "val"))
    h = y + 44 + 30 * len(bands) + 30
    b.append(t(x0, h - 8, note, "tick"))
    write(name, lang, svg(h, b, title))


def build(lang):
    nl = lang == "nl"
    brand_prices(lang)
    groupset_prices(lang)
    value_curve(lang)
    dumbbell("price-rises", lang, [("Canyon Ultimate CF SLX 8 Di2", (2019, 3699), (2025, 6099)),
                                   ("Giant Propel Advanced 1", (2020, 2299), (2025, 4399)),
                                   ("Giant TCR Advanced 1", (2021, 2299), (2026, 3499)),
                                   ("BMC URS ONE", (2020, 8999), (2026, 4499))],
             "Dezelfde fiets, nieuwprijs toen en nu" if nl else "The same bike, new price then and now", 10000, 2500, x0=240)
    ad_years(lang)
    price_zones(lang)
    tier_ladder(lang)
    domane_lineup(lang)
    dumbbell("domane-sl6-gen3", lang, [("Domane SL 6 Gen 3", (2020, 3299), (2022, 4199)),
                                       ("Domane AL 2", (2021, 729), (2025, 999))],
             "Domane: de nieuwprijs liep op" if nl else "Domane: the new price went up", 5000, 1000, x0=170)
    dumbbell("tcr-rises", lang, [("TCR Advanced 2", (2021, 1899), (2025, 2799)),
                                 ("TCR Advanced 1", (2021, 2299), (2026, 3499)),
                                 ("TCR Advanced 2 Disc", (2020, 1999), (2022, 2549))],
             "Giant TCR: nieuwprijs toen en nu" if nl else "Giant TCR: new price then and now", 4000, 1000, x0=190)
    dumbbell("topstone-falls", lang, [("Topstone 3", (2023, 1499), (2025, 1499)),
                                      ("Topstone 1", (2022, 2449), (2024, 2399)),
                                      ("Topstone Carbon 2 AXS", (2024, 3999), (2025, 3099)),
                                      ("Topstone Carbon 1 RLE", (2023, 8999), (2024, 7799))],
             "Topstone: de nieuwprijs zakte of bleef gelijk" if nl else "Topstone: the new price fell or held", 10000, 2500, x0=200)
    winter_values(lang)
    year_ribbon("buying-year", lang,
                [(2, 5, "busy", "Voorjaarsdrukte: veel kopers" if nl else "Spring rush: many buyers"),
                 (7, 10, "mid", "Nieuwe modeljaren in de winkel" if nl else "New model years in the shops"),
                 (10, 2, "now", "Rustig: tijd om te zoeken" if nl else "Quiet: time to look")],
                [(10.5, "nu" if nl else "now")],
                "Een jaar tweedehands kopen, grofweg" if nl else "A year of buying second-hand, roughly",
                "Een grof patroon, niet gemeten in onze data." if nl else "A rough pattern, not measured in our data.")
    year_ribbon("selling-plan", lang,
                [(10, 11, "now", "1 · Model en jaar" if nl else "1 · Model and year"),
                 (11, 1, "mid", "2 · Klaarmaken" if nl else "2 · Get it ready"),
                 (0, 1.5, "mid", "3 · Foto's" if nl else "3 · Photos"),
                 (1, 2, "mid", "4 · Prijs en tekst" if nl else "4 · Price and text"),
                 (1.7, 4, "busy", "5 · Online" if nl else "5 · Online")],
                [(10.5, "nu" if nl else "now")],
                "Je fiets verkopen in het voorjaar: het plan" if nl else "Selling your bike in spring: the plan",
                "Online zodra het eerste mooie weekend in zicht is." if nl else "Online as soon as the first nice weekend is in sight.")


if __name__ == "__main__":
    for lang in ("nl", "en"):
        build(lang)
    print(sorted(os.listdir(OUT)))
