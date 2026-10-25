"""The check report as a PDF, in the visitor's language: for downloading and for the email."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .i18n import gettext as _

INK, MUTED, ACCENT = colors.HexColor("#111216"), colors.HexColor("#6B6B78"), colors.HexColor("#0E9F6E")
STATUS = {"ok": colors.HexColor("#0E7A5A"), "warn": colors.HexColor("#8A4200"),
          "bad": colors.HexColor("#A3241B"), "unknown": colors.HexColor("#50505E")}


def eur(value):
    return "€{:,.0f}".format(value).replace(",", ".") if value is not None else "–"


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22,
                             textColor=INK, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16,
                             textColor=INK, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=13.5, textColor=INK),
        "muted": ParagraphStyle("muted", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=11.5, textColor=INK),
    }


def _p(text, style, color=None):
    text = escape(str(text))
    if color is not None:
        text = f'<font color="{color.hexval().replace("0x", "#")}">{text}</font>'
    return Paragraph(text, style)


def _table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDE3")),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, INK))
    t.setStyle(TableStyle(style))
    return t


def build(listing, r, height=None, report_url=None):
    """PDF bytes for one check. `listing` is the check row as a dict, `r` the run_check result."""
    s = _styles()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"{_('Check report')}: {listing['title']}", author="Bike Compare")
    width = A4[0] - 36 * mm
    story = [_p("BIKE COMPARE · " + _("Check report").upper(), s["brand"]), Spacer(1, 6)]

    story.append(_p(f"“{listing['title']}”", s["h1"]))
    facts = [_("checked {date}", date=listing["created_at"][:10])]
    if listing.get("asking_price") is not None:
        facts.append(_("Asking {price}", price=eur(listing["asking_price"])))
    if listing.get("location"):
        facts.append(listing["location"])
    if listing.get("removed_at"):
        facts.append(_("Removed from the site on {date}", date=listing["removed_at"][:10]))
    story.append(_p(" · ".join(facts), s["muted"]))
    if listing.get("listing_url"):
        story.append(_p(listing["listing_url"], s["muted"]))

    if not r.get("model"):
        story += [_p(_("No matching model"), s["h2"]),
                  _p(_("We couldn't match this ad to a model in our catalogue."), s["body"])]
        return _finish(doc, story, s, report_url, out)

    m = r["model"]
    label = _("Chosen by you") if r.get("chosen_by_you") else (
        _("{level} confidence", level=r["confidence"]) if r.get("confidence") else "")
    story.append(Spacer(1, 6))
    story.append(_p(f"{_('Matched to')} {m['brand']} {m['name']}" + (f" ({label})" if label else ""), s["body"]))

    alert = r.get("material_alert")
    if alert:
        story += [Spacer(1, 6), _p(alert["headline"], s["h2"], STATUS.get("bad", INK)), _p(alert["detail"], s["body"])]

    story.append(_p(_("Summary"), s["h2"]))
    rows = []
    for key, name in (("age", "AGE"), ("specs", "SPECS"), ("size", "SIZE"), ("value", "VALUE")):
        v = r[key]
        color = STATUS.get(v.get("status"), INK)
        rows.append([_p(_(name), s["cell"], MUTED), _p(v["headline"], s["cell"], color), _p(v["detail"], s["cell"])])
    story.append(_table(rows, [28 * mm, 42 * mm, width - 70 * mm], header=False))

    story.append(_p(_("Size fit"), s["h2"]))
    size = r["size"]
    if height:
        line = _("Your height") + f": {height} cm"
        if size.get("fit"):
            line += " · " + str(size["fit"]["text"])
        story.append(_p(line, s["body"], STATUS.get((size.get("fit") or {}).get("status"), INK)))
    story.append(_p(size["detail"], s["body"]))
    if size.get("rows"):
        cells = [[_p(str(x["size"]), s["cell"]) for x in size["rows"]],
                 [_p(f"{x['low']}–{x['high']}", s["cell"]) for x in size["rows"]]]
        t = Table(cells, colWidths=[min(22 * mm, width / len(size["rows"]))] * len(size["rows"]), hAlign="LEFT")
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDE3"))] +
                              [("BACKGROUND", (i, 0), (i, -1), colors.HexColor("#FFE3D6"))
                               for i, x in enumerate(size["rows"]) if x.get("selected")]))
        story += [Spacer(1, 4), t, _p(_("Rider height in cm."), s["muted"])]

    story.append(_p(_("Age check"), s["h2"]))
    story.append(_p(f"{r['age']['headline']}: {r['age']['detail']}", s["body"]))

    story.append(_p(_("Spec comparison"), s["h2"]))
    original = _("ORIGINAL ({year})", year=r["spec_year"]) if r.get("spec_year") else _("ORIGINAL")
    rows = [[_p(h, s["cell"], MUTED) for h in (_("PART"), original, _("IN THE AD"), _("RESULT"))]]
    for x in r["specs"]["rows"]:
        rows.append([_p(x["part"], s["cell"]), _p(x["original"], s["cell"]), _p(x["listing"] or "", s["cell"]),
                     _p(x["result"], s["cell"], STATUS.get(x.get("status"), INK))])
    story.append(_table(rows, [28 * mm, (width - 58 * mm) / 2, (width - 58 * mm) / 2, 30 * mm]))

    story.append(_p(_("Value estimate"), s["h2"]))
    story.append(_p(r["value"]["detail"], s["body"]))
    for note in r["value"].get("notes") or []:
        story.append(_p(note, s["muted"]))

    if r.get("questions"):
        story.append(_p(_("Ask the seller"), s["h2"]))
        for i, q in enumerate(r["questions"], 1):
            story.append(_p(f"{i}. “{q}”", s["body"]))
    return _finish(doc, story, s, report_url, out)


def _finish(doc, story, s, report_url, out):
    story.append(Spacer(1, 8))
    footer = [_("Bike Compare · not affiliated with Marktplaats or any bike brand.")]
    if report_url:
        footer.insert(0, _("Online report: {url}", url=report_url))
    story.append(_p("  ·  ".join(footer), s["muted"]))
    doc.build(story)
    return out.getvalue()
