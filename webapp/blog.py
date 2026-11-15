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

An article dated in the future stays hidden until that day, so posts can be written ahead. The body is a small
Markdown subset (see `render`): `##`/`###` headings, paragraphs, `-` and `1.` lists, `>` call-outs, `|` tables,
**bold**, *italic* and [links](/value). Links to other sites open in a new tab.
"""
import os
import re
from datetime import date

from markupsafe import Markup, escape

FOLDER = os.path.join(os.path.dirname(__file__), "blog")
# The four kinds of article, in the order of the filter on /blog. English is the key, translated in i18n.NL.
CATEGORIES = {"market": "Market data", "guides": "Buying guides", "models": "Model deep-dives", "seasonal": "Seasonal"}
FILE = re.compile(r"^([a-z0-9-]+)\.(nl|en)\.md$")


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
        posts.setdefault(slug, {})[lang] = dict(meta, slug=slug, lang=lang, body=body)
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
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def inline(text):
    """Escape a line and apply bold, italic and links."""
    out = str(escape(text))
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


def render(body):
    """The article body as HTML."""
    html, para, lines = [], [], body.splitlines()

    def flush():
        if para:
            html.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
        elif line.startswith("### ") or line.startswith("## "):
            flush()
            level = 3 if line.startswith("### ") else 2
            html.append(f"<h{level}>{inline(line[level + 1:])}</h{level}>")
            i += 1
        elif re.match(r"^(- |\d+\. )", line):
            flush()
            ordered = not line.startswith("- ")
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i].rstrip()))
                i += 1
            tag = "ol" if ordered else "ul"
            html.append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
        elif line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            html.append(f'<aside class="blog-callout"><p>{inline(" ".join(quote))}</p></aside>')
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            head, rest = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            # a column of numbers (euros, percentages, counts) is right-aligned
            numeric = [all(re.search(r"\d", r[k]) for r in rest if k < len(r)) and bool(rest) for k in range(len(head))]
            def cell(tag, text, k):
                cls = ' class="num"' if numeric[k] else ""
                return f"<{tag}{cls}>{inline(text)}</{tag}>"
            table = ("<thead><tr>" + "".join(cell("th", c, k) for k, c in enumerate(head)) + "</tr></thead><tbody>"
                     + "".join("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(r)) + "</tr>" for r in rest)
                     + "</tbody>")
            html.append(f'<div class="blog-table"><table>{table}</table></div>')
        else:
            para.append(line.strip())
            i += 1
    flush()
    return Markup("\n".join(html))
