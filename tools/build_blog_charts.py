"""Build the charts in the blog articles: webapp/static/blog/charts/<name>.<lang>.svg, one per language.

The SVGs are put inline in the article (webapp/blog.py), so they use the page's fonts and colours (CSS variables);
open on their own they show in plain black. The numbers are the ones in the articles: catalogue new prices, the
archived per-year prices and the value estimator's rules (webapp/checks.py check_value). Run:
python tools/build_blog_charts.py
"""
import json
import os
import sys
from html import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from webapp.blog import with_logos  # noqa: E402  the same logos as the article tables

OUT = os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "blog", "charts")
W = 720
TIER = ["#22252C", "#173A2D", "#1F5A43", "#34D399", "#ECECEF"]  # basic .. top: the .tier t1..t5 badges in style.css
BAR = ["#3A3E48"] + TIER[1:]  # on a card the basic tier's own grey would vanish
SERIES = ["#34D399", "#7AB8FF", "#F2C27A", "#E7A0F0"]  # one colour per line, as the blog categories


def eur(v, lang):
    s = f"{round(v):,}"
    return "€" + (s.replace(",", ".") if lang == "nl" else s)


def t(x, y, text, cls="lbl", anchor="start", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{extra}>{escape(str(text))}</text>'


def svg(h, body, title, data=None):
    extra = f' data-series="{escape(json.dumps(data, ensure_ascii=False))}"' if data is not None else ""
    return (f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{escape(title)}" xmlns="http://www.w3.org/2000/svg"{extra}>'
            f'<title>{escape(title)}</title>{"".join(body)}</svg>\n')


def name_(x_right, y_mid, text, width, brand_height=13, series_height=11):
    """A row label that shows brand and groupset logos where the site has them (HTML inside the SVG, so the logos
    take the text colour like everywhere else), right-aligned to x_right."""
    html = with_logos(text, brand_height, series_height) or escape(text)
    return (f'<foreignObject x="{x_right - width:.1f}" y="{y_mid - 12:.1f}" width="{width}" height="24">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="chart-name">{html}</div></foreignObject>')


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
    x0, x1, top, row = 130, W - 70, 40, 28
    scale = lambda v: x0 + (x1 - x0) * v / 26000
    h = top + row * len(BRANDS) + 40
    b = [t(x0, 18, "Nieuwprijs per merk: goedkoopste tot duurste, stip = mediaan" if lang == "nl"
           else "New price per brand: cheapest to dearest, dot = median", "cap")]
    b += axis(x0, x1, top - 10, h - 34, 25000, 5000, lang, scale)
    for i, (label, n, med, lo, hi) in enumerate(BRANDS):
        y = top + i * row + 8
        b.append(name_(x0 - 14, y, label, x0 - 20, brand_height=13))
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
    x0, x1, top, row = 250, W - 80, 40, 28
    scale = lambda v: x0 + (x1 - x0) * v / 15000
    h = top + row * len(GROUPSETS) + 46
    names = ["Basis", "Instap", "Midden", "Performance", "Top"] if lang == "nl" else ["Basic", "Entry", "Mid", "Performance", "Top"]
    b = [t(x0, 18, "Mediane nieuwprijs van een fiets, per groepset" if lang == "nl" else "Median new price of a bike, per groupset", "cap")]
    for i, (label, med, tier) in enumerate(GROUPSETS):
        y = top + i * row
        b.append(name_(x0 - 12, y + 10, label, x0 - 16, brand_height=10, series_height=10))
        b.append(f'<rect x="{x0}" y="{y + 2}" width="{scale(med) - x0:.1f}" height="17" rx="3" style="fill:{BAR[tier]}"/>')
        b.append(t(scale(med) + 8, y + 15, eur(med, lang), "val"))
    ly = h - 16
    for k, name in enumerate(names):
        lx = 40 + k * 130
        b.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" style="fill:{BAR[k]}"/>')
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


def years_chart(name, lang, series, title):
    """The new price per model year, one line per bike. The article lets the reader pick which lines show
    (static/blog.js redraws it from data-series); this is the drawing without JavaScript, every line."""
    x0, x1, y0, y1 = 70, W - 30, 50, 280
    years = [y for _, pts in series for y, _ in pts]
    lo, hi = min(years), max(years)
    vmax = max(p for _, pts in series for _, p in pts)
    step = 2500 if vmax > 6000 else 1000
    vmax = -(-vmax // step) * step
    sx = lambda y: x0 + (x1 - x0) * (y - lo) / max(1, hi - lo)
    sy = lambda v: y1 - (y1 - y0) * v / vmax
    b = [t(x0, 18, title, "cap")]
    for v in range(0, vmax + 1, step):
        b.append(f'<line x1="{x0}" y1="{sy(v):.1f}" x2="{x1}" y2="{sy(v):.1f}" class="grid"/>')
        b.append(t(x0 - 8, sy(v) + 4, eur(v, lang) if v else "€0", "tick", "end"))
    for y in range(lo, hi + 1):
        b.append(t(sx(y), y1 + 20, str(y), "tick", "middle"))
    for k, (label, pts) in enumerate(series):
        c = SERIES[k % len(SERIES)]
        b.append(f'<polyline points="{" ".join(f"{sx(y):.1f},{sy(p):.1f}" for y, p in pts)}" class="yline" style="stroke:{c}"/>')
        for y, p in pts:
            b.append(f'<circle cx="{sx(y):.1f}" cy="{sy(p):.1f}" r="4.5" class="ydot" style="fill:{c}"/>')
        lx = x0 + (k % 2) * 310
        ly = y1 + 46 + (k // 2) * 20
        b.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="3" style="fill:{c}"/>')
        b.append(t(lx + 18, ly, label, "tick"))
    h = y1 + 46 + ((len(series) + 1) // 2) * 20
    data = {"title": title, "series": [{"label": label, "html": with_logos(label, 13, 11), "points": pts}
                                       for label, pts in series]}
    write(name, lang, svg(h, b, title, data))


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
    data = {"x0": x0, "x1": x1, "y": y, "vmax": vmax,
            "zones": [[a, z, nl if lang == "nl" else en] for a, z, cls, nl, en in zones]}
    write("price-zones", lang, svg(184, b, "Prijsoordelen" if lang == "nl" else "Price verdicts", data))


# 7. Domane line-up today, on one price line
DOMANE = [("AL 2", 999, "AL"), ("AL 4", 1499, "AL"), ("AL 5", 1799, "AL"), ("SL 5 Gen 5", 2499, "SL"), ("SL 5 Gen 4", 2799, "SL"),
          ("SL 6 AXS Gen 5", 3999, "SL"), ("SL 6 Gen 4", 4299, "SL"), ("SL 7 Gen 4", 5499, "SL"), ("SLR 7 Gen 5", 6999, "SLR"),
          ("SLR 9 Gen 5", 9999, "SLR"), ("SLR 9 AXS Gen 5", 10499, "SLR")]


def domane_lineup(lang):
    x0, x1, top, row = 150, W - 90, 40, 26
    scale = lambda v: x0 + (x1 - x0) * v / 11000
    h = top + row * len(DOMANE) + 70
    b = [t(16, 18, "Trek Domane nu: nieuwprijs per uitvoering" if lang == "nl" else "Trek Domane today: new price per build", "cap")]
    b += axis(x0, x1, top - 10, h - 64, 10000, 2500, lang, scale)
    cls = {"AL": "al", "SL": "sl", "SLR": "slr"}
    for i, (name, p, frame) in enumerate(DOMANE):
        y = top + i * row + 8
        b.append(t(x0 - 12, y + 4, "Domane " + name, "lbl", "end"))
        b.append(f'<line x1="{x0}" y1="{y}" x2="{scale(p):.1f}" y2="{y}" class="stem"/>')
        b.append(f'<circle cx="{scale(p):.1f}" cy="{y}" r="7" class="frame {cls[frame]}"/>')
        b.append(t(scale(p) + 12, y + 4, eur(p, lang), "val"))
    ly = h - 12
    for k, (f, label) in enumerate([("al", "AL · aluminium"), ("sl", "SL · OCLV 500 carbon"), ("slr", "SLR · OCLV 800 carbon")]):
        lx = x0 + k * 190
        b.append(f'<circle cx="{lx}" cy="{ly - 4}" r="6" class="frame {f}"/>')
        b.append(t(lx + 12, ly, label, "tick"))
    write("domane-lineup", lang, svg(h, b, "Trek Domane"))


# 8. Used value of a winter bike: new price and the fair range after four years
WINTER = [("Cube Nuroad ONE", 799), ("Trek Domane AL 2", 999), ("Canyon Endurace AllRoad", 999), ("Giant Contend AR 3", 1199),
          ("Trek Checkpoint ALR 3", 1299), ("Cannondale Topstone 3", 1499), ("Giant Revolt 2", 1499)]


def winter_values(lang):
    x0, x1, top, row = 200, W - 40, 44, 30
    scale = lambda v: x0 + (x1 - x0) * v / 1600
    h = top + row * len(WINTER) + 66
    b = [t(16, 18, "Nieuwprijs en eerlijke prijs na vier jaar" if lang == "nl" else "New price and fair price after four years", "cap",
           extra=f' data-tpl="{"Nieuwprijs en eerlijke prijs na {n} jaar" if lang == "nl" else "New price and fair price after {n} years"}"')]
    b += axis(x0, x1, top - 12, h - 60, 1500, 500, lang, scale)
    f = value_factor(4)
    for i, (label, p) in enumerate(WINTER):
        y = top + i * row + 6
        lo, hi = round(p * f * 0.9, -1), round(p * f * 1.1, -1)
        b.append(name_(x0 - 12, y, label, x0 - 16, brand_height=10))
        b.append(f'<rect x="{scale(lo):.1f}" y="{y - 7}" width="{scale(hi) - scale(lo):.1f}" height="14" rx="7" class="band-bar" data-new="{p}"><title>{eur(lo, lang)} – {eur(hi, lang)}</title></rect>')
        b.append(f'<line x1="{scale(hi):.1f}" y1="{y}" x2="{scale(p):.1f}" y2="{y}" class="stem" data-new="{p}"/>')
        b.append(f'<circle cx="{scale(p):.1f}" cy="{y}" r="5" class="then"/>')
        b.append(t(scale(lo) - 6, y + 4, f"{eur(lo, lang)}–{eur(hi, lang)}", "val", "end") if False else "")
    ly = h - 14
    b.append(f'<rect x="{x0}" y="{ly - 10}" width="26" height="12" rx="6" class="band-bar"/>')
    b.append(t(x0 + 34, ly, "eerlijke prijs na 4 jaar" if lang == "nl" else "fair price after 4 years", "tick",
               extra=f' data-tpl="{"eerlijke prijs na {n} jaar" if lang == "nl" else "fair price after {n} years"}"'))
    b.append(f'<circle cx="{x0 + 240}" cy="{ly - 4}" r="5" class="then"/>')
    b.append(t(x0 + 252, ly, "nieuwprijs nu" if lang == "nl" else "new price now", "tick"))
    write("winter-values", lang, svg(h, b, "Winterfietsen" if lang == "nl" else "Winter bikes",
                                     {"x0": x0, "x1": x1, "vmax": 1600, "age": 4}))


# 9. Same groupset, aluminium and carbon frame (carbon-or-aluminium)
CARBON_PAIRS = [("Cube Nuroad · GRX 610", 1299, 1999), ("Trek Domane · 105", 1799, 2499),
                ("Giant Revolt · GRX 610", 1999, 2999), ("Orbea Terra · GRX 610", 1999, 2999),
                ("Specialized Allez / Aethos · 105 Di2", 3950, 3200)]


def carbon_premium(lang):
    x0, x1, top, row = 260, W - 60, 44, 34
    scale = lambda v: x0 + (x1 - x0) * v / 4500
    h = top + row * len(CARBON_PAIRS) + 64
    b = [t(16, 18, "Zelfde groep: nieuwprijs met aluminium en met carbon frame" if lang == "nl"
           else "Same groupset: new price with an aluminium and a carbon frame", "cap")]
    b += axis(x0, x1, top - 14, h - 58, 4000, 1000, lang, scale)
    for i, (label, alu, carbon) in enumerate(CARBON_PAIRS):
        y = top + i * row + 6
        b.append(name_(x0 - 12, y, label, x0 - 16, brand_height=11))
        b.append(f'<line x1="{scale(alu):.1f}" y1="{y}" x2="{scale(carbon):.1f}" y2="{y}" class="stem"/>')
        b.append(f'<circle cx="{scale(alu):.1f}" cy="{y}" r="7" class="frame al"/>')
        b.append(f'<circle cx="{scale(carbon):.1f}" cy="{y}" r="7" class="frame slr"/>')
        diff = carbon - alu
        b.append(t(scale(max(alu, carbon)) + 14, y + 4, ("+" if diff > 0 else "−") + eur(abs(diff), lang), "val"))
    ly = h - 12
    for k, (f, label) in enumerate([("al", "aluminium"), ("slr", "carbon")]):
        lx = x0 + k * 160
        b.append(f'<circle cx="{lx}" cy="{ly - 4}" r="6" class="frame {f}"/>')
        b.append(t(lx + 12, ly, label, "tick"))
    write("carbon-premium", lang, svg(h, b, "Carbon of aluminium" if lang == "nl" else "Carbon or aluminium"))


# 10. The sizes of four bikes by rider height (frame-size-from-an-ad), from webapp/size_charts.json
SIZE_BIKES = [("Trek Domane SL 5", [("XS", 143, 158), ("S", 158, 162), ("M", 162, 173), ("ML", 173, 179),
                                     ("L", 179, 188), ("XL", 188, 199)]),
              ("Canyon Endurace CF 7", [("3XS", 152, 158), ("2XS", 158, 164), ("XS", 164, 170), ("S", 170, 177),
                                        ("M", 177, 184), ("L", 184, 191), ("XL", 191, 197), ("2XL", 197, 203)]),
              ("Rose Backroad AL", [("2XS", 151, 161), ("XS", 162, 167), ("S", 168, 173), ("M", 174, 179),
                                    ("ML", 180, 184), ("L", 185, 191), ("XL", 192, 194), ("2XL", 195, 202)]),
              ("Cannondale CAAD14", [("48", 157, 165), ("51", 165, 175), ("54", 170, 180), ("56", 178, 185),
                                     ("58", 183, 193), ("61", 188, 198)])]
RIDER = 178


def size_by_height(lang):
    x0, x1, top, row = 190, W - 20, 44, 50
    lo, hi = 140, 205
    scale = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
    h = top + row * len(SIZE_BIKES) + 30
    b = [t(16, 18, "Maat per lichaamslengte; groen = de maat voor 1,78 m" if lang == "nl"
           else "Size by rider height; green = the size for 1.78 m", "cap")]
    for v in range(140, 205, 10):
        b.append(f'<line x1="{scale(v):.1f}" y1="{top - 14}" x2="{scale(v):.1f}" y2="{h - 26}" class="grid"/>')
        b.append(t(scale(v), h - 8, f"{v} cm", "tick", "middle"))
    for i, (label, sizes) in enumerate(SIZE_BIKES):
        y = top + i * row + 8
        b.append(name_(x0 - 12, y + 4, label, x0 - 16, brand_height=11))
        for k, (name, a, z) in enumerate(sizes):
            yy = y + (6 if k % 2 else -6) if label.startswith("Cannondale") else y
            fit = a <= RIDER <= z
            b.append(f'<rect x="{scale(a) + 1:.1f}" y="{yy - 7}" width="{scale(z) - scale(a) - 2:.1f}" height="14" rx="4" '
                     f'style="fill:{"var(--accent)" if fit else "var(--line-strong)"};opacity:{1 if fit else 0.6}"/>')
            b.append(t((scale(a) + scale(z)) / 2, yy - 11 if not label.startswith("Cannondale") or k % 2 == 0 else yy + 20,
                       name, "tick", "middle"))
    b.append(f'<line x1="{scale(RIDER):.1f}" y1="{top - 14}" x2="{scale(RIDER):.1f}" y2="{h - 26}" class="ref"/>')
    write("size-by-height", lang, svg(h, b, "Framematen" if lang == "nl" else "Frame sizes"))


# 11. The Endurace today: new price per build, by frame grade (canyon-endurace)
ENDURACE = [("CF 6", 1849, "al"), ("CF 7", 2349, "al"), ("CF 7 Di2", 3049, "al"), ("CF SLX 7 Di2", 4549, "sl"),
            ("CF SLX 8 Di2", 5599, "sl"), ("CF SLX 8 AXS Aero", 5599, "sl"), ("CFR Di2", 9149, "slr"),
            ("CFR AXS", 9149, "slr")]


def endurace_lineup(lang):
    x0, x1, top, row = 190, W - 90, 40, 26
    scale = lambda v: x0 + (x1 - x0) * v / 10000
    h = top + row * len(ENDURACE) + 70
    b = [t(16, 18, "Canyon Endurace nu: nieuwprijs per uitvoering" if lang == "nl" else "Canyon Endurace today: new price per build", "cap")]
    b += axis(x0, x1, top - 10, h - 64, 10000, 2500, lang, scale)
    for i, (name, p, frame) in enumerate(ENDURACE):
        y = top + i * row + 8
        b.append(t(x0 - 12, y + 4, "Endurace " + name, "lbl", "end"))
        b.append(f'<line x1="{x0}" y1="{y}" x2="{scale(p):.1f}" y2="{y}" class="stem"/>')
        b.append(f'<circle cx="{scale(p):.1f}" cy="{y}" r="7" class="frame {frame}"/>')
        b.append(t(scale(p) + 12, y + 4, eur(p, lang), "val"))
    ly = h - 12
    for k, (f, label) in enumerate([("al", "CF"), ("sl", "CF SLX"), ("slr", "CFR")]):
        lx = x0 + k * 150
        b.append(f'<circle cx="{lx}" cy="{ly - 4}" r="6" class="frame {f}"/>')
        b.append(t(lx + 12, ly, label, "tick"))
    write("endurace-lineup", lang, svg(h, b, "Canyon Endurace"))


# 12. What condition does to the fair price (storing-your-bike-over-winter): the value estimator's condition factors
CONDITIONS = [("like-new", 1.05), (None, 1.0), ("used", 0.92), ("damaged", 0.6)]
CONDITION_NAMES = {"nl": {"like-new": "Zo goed als nieuw", None: "Normaal gebruikt", "used": "Gebruikt", "damaged": "Beschadigd"},
                   "en": {"like-new": "Like new", None: "Normal use", "used": "Used", "damaged": "Damaged"}}


def condition_values(lang, new=2499, age=2):
    x0, x1, top, row = 190, W - 40, 44, 34
    scale = lambda v: x0 + (x1 - x0) * v / 2600
    h = top + row * len(CONDITIONS) + 46
    b = [t(16, 18, f"Eerlijke prijs na {age} jaar, nieuw {eur(new, lang)}, per staat" if lang == "nl"
           else f"Fair price after {age} years, {eur(new, lang)} new, by condition", "cap")]
    b += axis(x0, x1, top - 14, h - 40, 2500, 500, lang, scale)
    for i, (key, c) in enumerate(CONDITIONS):
        y = top + i * row + 6
        mid = new * value_factor(age) * c
        lo, hi = round(mid * 0.9, -1), round(mid * 1.1, -1)
        b.append(t(x0 - 12, y + 4, CONDITION_NAMES[lang][key], "lbl", "end"))
        b.append(f'<rect x="{scale(lo):.1f}" y="{y - 8}" width="{scale(hi) - scale(lo):.1f}" height="16" rx="8" class="band-bar"/>')
        b.append(t(scale(hi) + 10, y + 4, f"{eur(lo, lang)} – {eur(hi, lang)}", "val"))
    write("condition-values", lang, svg(h, b, "Staat en prijs" if lang == "nl" else "Condition and price"))


def build(lang):
    nl = lang == "nl"
    brand_prices(lang)
    groupset_prices(lang)
    value_curve(lang)
    # every year with a Dutch price in the catalogue and the archived spec sheets (checks.year_prices)
    years_chart("price-rises", lang, [
        ("Canyon Ultimate CF SLX 8 Di2", [(2019, 3699), (2020, 4199), (2025, 6099)]),
        ("Giant Propel Advanced 1", [(2020, 2299), (2023, 4799), (2024, 4799), (2025, 4399)]),
        ("Giant TCR Advanced 1", [(2021, 2299), (2025, 3499), (2026, 3499)]),
        ("BMC URS ONE", [(2020, 8999), (2021, 2799), (2022, 2999), (2023, 3799), (2026, 4499)])],
        "Dezelfde fiets: nieuwprijs per modeljaar" if nl else "The same bike: new price per model year")
    ad_years(lang)
    price_zones(lang)
    domane_lineup(lang)
    years_chart("domane-sl6-gen3", lang, [
        ("Domane SL 6 Gen 3", [(2020, 3299), (2021, 3999), (2022, 4199)]),
        ("Domane AL 2", [(2021, 729), (2022, 794), (2025, 999)])],
        "Domane: nieuwprijs per modeljaar" if nl else "Domane: new price per model year")
    years_chart("tcr-rises", lang, [
        ("TCR Advanced 2", [(2021, 1899), (2025, 2799), (2026, 2799)]),
        ("TCR Advanced 1", [(2021, 2299), (2025, 3499), (2026, 3499)]),
        ("TCR Advanced 2 Disc", [(2020, 1999), (2021, 2099), (2022, 2549)])],
        "Giant TCR: nieuwprijs per modeljaar" if nl else "Giant TCR: new price per model year")
    years_chart("topstone-falls", lang, [
        ("Topstone 3", [(2023, 1499), (2024, 1499), (2025, 1499)]),
        ("Topstone 1", [(2022, 2449), (2024, 2399), (2025, 2399)]),
        ("Topstone Carbon 2 AXS", [(2024, 3999), (2025, 3099)]),
        ("Topstone Carbon 1 RLE", [(2023, 8999), (2024, 7799), (2025, 7799)])],
        "Topstone: nieuwprijs per modeljaar" if nl else "Topstone: new price per model year")
    winter_values(lang)
    carbon_premium(lang)
    size_by_height(lang)
    endurace_lineup(lang)
    years_chart("endurace-years", lang, [
        ("CF SL 8 Di2", [(2019, 3399), (2020, 3299), (2021, 3599)]),
        ("CF SL 8", [(2020, 2499), (2022, 2799)]),
        ("CF 8", [(2020, 1999), (2021, 1999)])],
        "Endurace: nieuwprijs per modeljaar" if nl else "Endurace: new price per model year")
    condition_values(lang)


if __name__ == "__main__":
    for lang in ("nl", "en"):
        build(lang)
    print(sorted(os.listdir(OUT)))
