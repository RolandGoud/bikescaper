"""The blog: articles in webapp/blog/, one Markdown file per article and language.

A file is named `<slug>.<lang>.md` (`used-bike-value.nl.md`, `used-bike-value.en.md`); both languages share the
slug, so /blog/<slug> shows the visitor's language and falls back to the other one. Each file opens with a short
header between `---` lines:

    ---
    title: Hoe snel verliest een racefiets zijn waarde?
    date: 2026-11-15
    category: market
    summary: One or two sentences for the list page and the search snippet.
    ---

An article dated in the future stays hidden until that day, so posts can be written ahead. Optional header
fields: `stat` and `stat_label`, the article's one headline number for the list page, and `hero`, a picture under
webapp/static (default blog/heroes/<slug>.jpg). A model deep-dive can add `model: Trek Domane` (brand, then the
start of the model name): a check report on a matching bike links it first (see `for_report`). The body is a small
Markdown subset (see `render`): `##`/`###` headings, paragraphs, `-` and `1.` lists, `>` call-outs, `|` tables,
**bold**, *italic*, [links](/value), and pictures on a line of their own: `![caption](chart:value-curve)` for a chart. Links to other sites open in a new tab.
"""
import json
import os
import re
from datetime import date

from markupsafe import Markup, escape

from webapp.reference import FIRST_YEAR  # the catalogue's first model year: the value curve goes no further back

FOLDER = os.path.join(os.path.dirname(__file__), "blog")
# The four kinds of article, in the order of the filter on /blog. English is the key, translated in i18n.NL.
CATEGORIES = {"market": "Market data", "guides": "Buying guides", "models": "Model deep-dives", "seasonal": "Seasonal"}
FILE = re.compile(r"^([a-z0-9-]+)\.(nl|en)\.md$")
STATIC = os.path.join(os.path.dirname(__file__), "static")
CHARTS = os.path.join(STATIC, "blog", "charts")  # built by tools/build_blog_charts.py, <name>.<lang>.svg
# What tools/build_blog_heroes.py notes per hero: its focus point (so a cropped tile keeps the subject in view),
# and where the photo comes from (a brand's product photo, or a free photo with its author and licence).
try:
    with open(os.path.join(STATIC, "blog", "heroes", "heroes.json"), encoding="utf-8") as _f:
        HEROES = json.load(_f)
except (OSError, ValueError):
    HEROES = {}
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")


def parse(text):
    """The header fields and the Markdown body of one article file."""
    meta, body = {}, text
    if text.startswith("---"):
        _, head, body = text.split("---", 2)
        for line in head.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    meta["date"] = date.fromisoformat(meta["date"])
    return meta, body.strip()


def load(folder=FOLDER):
    """Every article: {slug: {lang: {slug, lang, title, date, category, summary, body}}}."""
    posts = {}
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        found = FILE.match(name)
        if not found:
            continue
        slug, lang = found.groups()
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            meta, body = parse(f.read())
        # The hero: webapp/static/blog/heroes/<slug>.jpg (tools/build_blog_heroes.py), unless the header names another.
        hero = meta.get("hero") or (f"blog/heroes/{slug}.jpg" if os.path.exists(os.path.join(STATIC, "blog", "heroes", f"{slug}.jpg")) else None)
        about = HEROES.get(slug, {}) if hero == f"blog/heroes/{slug}.jpg" else {}
        focus = about.get("focus") or [50, 50]
        posts.setdefault(slug, {})[lang] = dict(meta, slug=slug, lang=lang, body=body, hero=hero,
                                                hero_focus=f"{focus[0]}% {focus[1]}%", hero_credit=about.get("credit"),
                                                hero_brand=about.get("brand"))
    return posts


def pick(versions, lang):
    """The version in the visitor's language, else the other one."""
    return versions.get(lang) or next(iter(versions.values()))


def published(posts, lang, today=None, category=None):
    """The articles to list, newest first, each in the visitor's language where there is one."""
    today = today or date.today()
    shown = [pick(v, lang) for v in posts.values()]
    shown = [p for p in shown if p["date"] <= today and (category is None or p["category"] == category)]
    return sorted(shown, key=lambda p: (p["date"], p["slug"]), reverse=True)


def reading_minutes(body):
    return max(1, round(len(body.split()) / 220))


INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])"), r"<em>\1</em>"),
]
NUMBER = re.compile(r"^[+−\-<]?€?\d[\d.,]*%?(\s*\(\d{4}\))?$")  # €2.599, +65%, 51, €3.699 (2019)
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


TIER_NAMES = {"nl": {1: "Basis", 2: "Instap", 3: "Midden", 4: "Performance", 5: "Top"},
              "en": {1: "Basic", 2: "Entry", 3: "Mid", 4: "Performance", 5: "Top"}}
TIER_TOKEN = re.compile(r"\{tier:([1-5])\}")
LOGOS = os.path.join(STATIC, "logos")
# Brands with a logo under static/logos/, longest first so "Campagnolo" wins over nothing shorter by accident.
BRAND_FILES = {"Shimano": "shimano", "SRAM": "sram", "Campagnolo": "campagnolo", "Trek": "trek", "Canyon": "canyon",
               "Specialized": "specialized", "Giant": "giant", "Cannondale": "cannondale", "Cube": "cube", "Factor": "factor",
               "Scott": "scott", "Orbea": "orbea", "Lapierre": "lapierre", "Bianchi": "bianchi", "BMC": "bmc",
               "Cervélo": "cervelo", "Ridley": "ridley", "Rose": "rose", "Wilier": "wilier"}
# Groupset series with a logo under static/logos/groupsets/ (what the groupsets page shows). GRX goes by its
# hundreds: GRX 400, GRX 600 and GRX 800 (820, 822, 825) each have their own mark.
SERIES_FILES = {"Dura-Ace": "dura-ace", "Ultegra": "ultegra", "105": "105", "Tiagra": "tiagra", "Sora": "sora",
                "Claris": "claris", "Red": "red", "RED": "red", "Force": "force", "Rival": "rival", "Apex": "apex"}
SERIES = re.compile(r"^(?:(" + "|".join(re.escape(k) for k in SERIES_FILES) + r")|GRX ([468])\d\d)(?=\s|,|$)")


def _viewbox(path):
    with open(path, encoding="utf-8") as f:
        m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', f.read(2000))
    return (float(m.group(1)), float(m.group(2))) if m else (5.0, 1.0)


def logo(rel, name, height):
    """A logo in the text's colour, sized from its own proportions (like brand_label in _macros.html)."""
    path = os.path.join(STATIC, rel)
    if not os.path.exists(path):
        return None
    w, h = _viewbox(path)
    width = min(110, round(height * w / h))
    return (f'<span class="blog-logo" role="img" aria-label="{escape(name)}" title="{escape(name)}" '
            f'style="--logo: url(\'/static/{rel}\'); width: {width}px; height: {height}px"></span>')


def with_logos(text, brand_height=16, series_height=13):
    """A table cell's brand and groupset names as their logos where the site has them: "Shimano 105 Di2" becomes
    the Shimano logo, the 105 logo and "Di2"; "Claris, Sora" both logos; "GRX 825 Di2" the GRX 800 logo and "Di2".
    None when nothing in the cell has a logo, so it stays plain text."""
    pieces, found = [], False
    for piece in text.split(", "):
        out, rest = [], piece
        for brand, file in BRAND_FILES.items():
            if rest == brand or rest.startswith(brand + " "):
                out.append(logo(f"logos/{file}.svg", brand, brand_height))
                rest = rest[len(brand):].strip()
                break
        m = SERIES.match(rest)
        if m:
            name = m.group(0)
            file = SERIES_FILES[m.group(1)] if m.group(1) else f"grx-{m.group(2)}00"
            out.append(logo(f"logos/groupsets/{file}.svg", name, series_height))
            rest = rest[m.end():].strip()
        out = [o for o in out if o]
        found = found or bool(out)
        pieces.append("".join(out) + (f'<span class="blog-logo-rest">{escape(rest)}</span>' if rest else ""))
    return f'<span class="blog-logos">{"".join(pieces)}</span>' if found else None


def inline(text, lang="nl"):
    """Escape a line and apply bold, italic, links and {tier:n} badges."""
    out = str(escape(text))
    out = TIER_TOKEN.sub(lambda m: f'<span class="tier t{m.group(1)} small">{TIER_NAMES.get(lang, TIER_NAMES["en"])[int(m.group(1))]}</span>', out)
    for pattern, html in INLINE:
        out = pattern.sub(html, out)

    def link(m):
        label, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://")):
            return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
        return f'<a href="{url}">{label}</a>'
    return LINK.sub(link, out)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


WORDS = {"nl": {"chart": "Grafiek", "table": "Tabel", "show": "Toon als", "new": "Nieuwprijs", "age": "Leeftijd",
                "years": "jaar", "condition": "Staat", "normal": "Normaal gebruik", "like-new": "Als nieuw",
                "used": "Gebruikt", "damaged": "Beschadigd", "asking": "Vraagprijs"},
         "en": {"chart": "Chart", "table": "Table", "show": "Show as", "new": "New price", "age": "Age",
                "years": "years", "condition": "Condition", "normal": "Normal use", "like-new": "Like new",
                "used": "Used", "damaged": "Damaged", "asking": "Asking price"}}
# Charts you can play with: the reader's own numbers redraw them in the page (static/blog.js).
LIVE = {"value-curve", "price-rises", "tcr-rises", "topstone-falls", "domane-sl6-gen3", "price-zones", "winter-values"}


def live_controls(name, lang):
    """The inputs above a live chart. The value curve: new price, age and condition, as on /value."""
    w = WORDS.get(lang, WORDS["en"])
    if name == "price-zones":
        return ('<div class="blog-live-inputs">'
                f'<label>{w["asking"]}<span class="blog-live-field"><span>€</span><input type="number" name="asking" value="1400" '
                'min="0" max="2600" step="10" inputmode="numeric"></span></label></div>')
    if name == "winter-values":
        return ('<div class="blog-live-inputs">'
                f'<label>{w["age"]}<span class="blog-live-field"><input type="number" name="age" value="4" min="1" max="10" '
                f'step="1" inputmode="numeric"><span>{w["years"]}</span></span></label></div>')
    if name != "value-curve":
        return ""
    conditions = "".join(f'<option value="{k}"{" selected" if k == "" else ""}>{w[k or "normal"]}</option>'
                         for k in ("", "like-new", "used", "damaged"))
    return ('<div class="blog-live-inputs">'
            f'<label>{w["new"]}<span class="blog-live-field"><span>€</span><input type="number" name="new" value="5000" '
            'min="100" max="30000" step="50" inputmode="numeric"></span></label>'
            f'<label>{w["age"]}<span class="blog-live-field"><input type="number" name="age" value="4" min="0" max="{date.today().year - FIRST_YEAR}" '
            f'step="1" inputmode="numeric"><span>{w["years"]}</span></span></label>'
            f'<label>{w["condition"]}<select name="condition">{conditions}</select></label></div>')


def figure(caption, src, lang):
    """A picture in the article: `![caption](chart:name)` puts that chart inline in the article's language, so it
    takes the page's fonts and colours; `![caption](/static/...)` is an ordinary image."""
    cap = f"<figcaption>{inline(caption, lang)}</figcaption>" if caption else ""
    if src.startswith("chart:"):
        name = src[len("chart:"):]
        for code in (lang, "en", "nl"):
            path = os.path.join(CHARTS, f"{name}.{code}.svg")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    if name in LIVE:
                        return (f'<figure class="blog-figure blog-chart blog-live" data-live="{name}" data-lang="{lang}">'
                                f'{live_controls(name, lang)}<div class="blog-live-svg">{f.read()}</div>{cap}</figure>')
                    return f'<figure class="blog-figure blog-chart">{f.read()}{cap}</figure>'
        return ""
    return f'<figure class="blog-figure"><img src="{escape(src)}" alt="{escape(caption)}" loading="lazy">{cap}</figure>'


def switch(key, chart, table, lang):
    """A chart and its table in one place, with a Chart | Table toggle (the site's .toggle); the chart shows first.
    Pure CSS (:has), so without it both simply show."""
    w = WORDS.get(lang, WORDS["en"])
    return (f'<div class="blog-switch">'
            f'<div class="toggle blog-switch-toggle" role="radiogroup" aria-label="{w["show"]}">'
            f'<input type="radio" id="{key}-chart" name="{key}" value="chart" checked><label for="{key}-chart">{w["chart"]}</label>'
            f'<input type="radio" id="{key}-table" name="{key}" value="table"><label for="{key}-table">{w["table"]}</label></div>'
            f'<div class="blog-switch-chart">{chart}</div><div class="blog-switch-table">{table}</div></div>')


def render(body, lang="nl"):
    """The article body as HTML."""
    html, para, lines = [], [], body.splitlines()
    switches = 0

    def flush():
        if para:
            html.append(f"<p>{inline(' '.join(para), lang)}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
        elif IMAGE.match(line.strip()):
            flush()
            caption, src = IMAGE.match(line.strip()).groups()
            fig = figure(caption, src, lang)
            if src.startswith("chart:") and html and html[-1].startswith('<div class="blog-table">') and fig:
                # A table right above a chart of the same numbers: one or the other, the chart first.
                switches += 1
                html[-1] = switch(f"sw{switches}", fig, html[-1], lang)
            else:
                html.append(fig)
            i += 1
        elif line.startswith("### ") or line.startswith("## "):
            flush()
            level = 3 if line.startswith("### ") else 2
            html.append(f"<h{level}>{inline(line[level + 1:], lang)}</h{level}>")
            i += 1
        elif re.match(r"^(- |\d+\. )", line):
            flush()
            ordered = not line.startswith("- ")
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i].rstrip()))
                i += 1
            tag = "ol" if ordered else "ul"
            html.append(f"<{tag}>" + "".join(f"<li>{inline(t, lang)}</li>" for t in items) + f"</{tag}>")
        elif line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            html.append(f'<aside class="blog-callout"><p>{inline(" ".join(quote), lang)}</p></aside>')
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            head, rest = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            rest = [(r + [""] * len(head))[:len(head)] for r in rest]  # every row as wide as the heading
            # a column of numbers (euros, percentages, counts) is right-aligned
            numeric = [bool(rest) and all(NUMBER.match(r[k]) for r in rest if k < len(r) and r[k]) for k in range(len(head))]
            def cell(tag, text, k):
                cls = ' class="num"' if numeric[k] else ""
                logos = None if tag == "th" or numeric[k] or "[" in text else with_logos(text)
                return f"<{tag}{cls}>{logos or inline(text, lang)}</{tag}>"
            table = ("<thead><tr>" + "".join(cell("th", c, k) for k, c in enumerate(head)) + "</tr></thead><tbody>"
                     + "".join("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(r)) + "</tr>" for r in rest)
                     + "</tbody>")
            html.append(f'<div class="blog-table"><table>{table}</table></div>')
        else:
            para.append(line.strip())
            i += 1
    flush()
    return Markup("\n".join(html))


# What a check report links to, after the article on the matched model (an article with `model: Trek Domane` in its
# header goes with every Trek whose name starts with Domane): the guides for the step a reader of a report is at.
REPORT_READS = ["spotting-a-stolen-bike", "reading-a-bike-ad", "how-fast-bikes-lose-value"]


def about_model(post, model):
    """Whether an article is the deep-dive on this catalogue model's family."""
    brand, _, family = (post.get("model") or "").partition(" ")
    return bool(model and brand and family) and model["brand"].lower() == brand.lower() \
        and model["name"].lower().startswith(family.lower())


def for_report(posts, lang, model=None, today=None, n=3):
    """The articles a check report links to: the one on its model if there is one, then REPORT_READS."""
    shown = published(posts, lang, today)
    first = [p for p in shown if about_model(p, model)][:1]
    by_slug = {p["slug"]: p for p in shown}
    return (first + [by_slug[s] for s in REPORT_READS if s in by_slug])[:n]
