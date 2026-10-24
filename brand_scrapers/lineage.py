"""Earlier models a catalogue model replaced, found in the Wayback Machine listings by family and parts.

Brands rename their bikes with each generation: Cannondale's CAAD14 3 replaced the CAAD13 Disc 105,
Canyon's Aeroad CF SLX 8 Di2 the Aeroad CF SLX 8 Disc Di2, Specialized's Aethos 2 Expert the Aethos
Expert. An archived product page of the same family (the model name's first word without its
generation number) is a predecessor when its name shares the model's groupset and tier words:

    python -m brand_scrapers.lineage <cdx dir> wanted-predecessors.json [site db]

writes, per catalogue model and year without an archived page of its own, the best predecessor's
copy closest to spring in the same shape as archive.match (plus "sheet_name", the predecessor's
URL name), for `wayback.py fetch` and then `archive.py parse`.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

from .archive import FIRST_YEAR, SKIP, SPRING, URL_NAME, catalogue, compact, read_cdx, url_name

BRANDS = ["Canyon", "Cannondale", "Cube", "Specialized"]

# Groupset words, so a model and its predecessor can match on "105", "ultegra di2" or "force axs".
GROUPSETS = {"105", "ultegra", "duraace", "tiagra", "sora", "claris", "grx", "cues", "rival", "force", "red",
             "apex", "di2", "axs", "etap", "ekar", "chorus", "record", "potenza", "centaur", "xplr", "mechanical"}
# The groupset line itself: two names that both name one must name the same (105 is not Ultegra).
LINES = GROUPSETS - {"di2", "axs", "etap", "xplr", "mechanical"}
SYNONYMS = {"etap": "axs", "dura": "duraace", "ace": "duraace", "durace": "duraace"}
# Words that say nothing about which bike it is.
NOISE = {"disc", "smu", "rle", "speed", "shimano", "sram", "campagnolo", "carbon", "bike", "the", "and", "nbsp"}
# Words that must agree when both names have them: the frame material and level (CF SL vs CFR, Hi-Mod
# vs LAB71), the tier word (Comp, Expert, Pro) and the tier number (7 vs 9).
MATERIALS = {"cf", "sl", "slx", "cfr", "al", "alloy", "hi", "mod", "lab71", "sw", "himod", "slt", "c62", "c68x", "c68"}
TIERS = {"sport", "comp", "expert", "pro", "elite", "base", "race", "ex", "one", "slx", "slt", "ltd"}
OTHER_RIDERS = re.compile(r"\b(?:wmn|womens?|dames|women|young|kids?|junior)\b")
FRAMESET = re.compile(r"\b(?:frameset|frame|module)\b")


def words(name):
    """Normalised words of a model name or URL name: "Aeroad CF SLX 8.0 Disc eTap" -> [aeroad, cf, slx, 8, axs]."""
    text = name.lower().replace("dura-ace", "duraace").replace("dura ace", "duraace").replace("+", " plus ")
    text = re.sub(r"\b(\d+)\.0\b", r"\1", text)
    text = text.replace("s-works", "sworks").replace("s works", "sworks")
    text = re.sub(r"\bc\d{5}[a-z]\b|\b(?:19|20)\d\d\b", " ", text)  # Cannondale's article codes, model years
    out = []
    for w in re.findall(r"[a-z0-9:]+", text):
        w = SYNONYMS.get(w, w.replace(":", ""))
        if w and w not in NOISE:
            out.append(w)
    return out


def family(ws):
    ws = [w for w in ws if w != "sworks"]
    return re.sub(r"\d+$", "", ws[0]) if ws else ""


def clash(a, b, group):
    a, b = set(a) & group, set(b) & group
    return bool(a and b and a != b)


def score(model_words, groupset, old_words):
    """How well an earlier model's name fits: shared groupset words count double, a groupset the
    model doesn't have counts against. None when it isn't the same family."""
    if not old_words or family(old_words) != family(model_words) or \
            ("sworks" in old_words) != ("sworks" in model_words):
        return None
    old = set(old_words[1:])
    digits = {w for w in model_words[1:] if re.fullmatch(r"\d", w)}, {w for w in old if re.fullmatch(r"\d", w)}
    if clash(groupset, old, LINES) and not groupset & old & LINES or clash(groupset, old, {"di2", "axs"}) or clash(model_words, old, MATERIALS) or \
            clash(model_words, old, TIERS) or (digits[0] and digits[1] and digits[0] != digits[1]):
        return None
    old_groupset = old & GROUPSETS
    rest = set(model_words[1:]) - GROUPSETS
    return 2 * len(groupset & old_groupset) + len(rest & (old - GROUPSETS)) - len(old_groupset - groupset)


def model_groupset(name, specs):
    text = " ".join([name] + [str(specs.get(k, "")) for k in ("Shifter", "Achterderailleur", "Crankstel")])
    return set(words(text)) & GROUPSETS


def raw_name(brand, url):
    m = re.search(URL_NAME[brand], urlparse(url).path.rstrip("/"))
    return m.group(1) if m else None


def predecessors(cdx_folder, out_path, db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    wanted, report = [], {}
    for brand in BRANDS:
        names = catalogue(db_path)[brand]
        keys = {compact(n) for n in names}
        old = defaultdict(list)  # (year, raw name) -> [(ts, url)]
        own = defaultdict(set)   # catalogue name compacted -> years with a page of its own
        for ts, url in read_cdx(cdx_folder, brand):
            year, raw = int(ts[:4]), raw_name(brand, url)
            if year < FIRST_YEAR or not raw or SKIP.search(urlparse(url).path + "/"):
                continue
            if brand == "Cube" and not re.search(r"cube\.eu/nl(?:-nl)?/", url):
                continue
            key = url_name(brand, url)
            if key in keys:
                own[key].add(year)
            else:
                old[(year, raw)].append((ts, url))
        found = 0
        for name, _sku in names.items():
            row = conn.execute("SELECT specs FROM models WHERE brand = ? AND name = ?", (brand, name)).fetchone()
            specs = json.loads(row[0] or "{}") if row else {}
            mw, groupset = words(name), model_groupset(name, specs)
            for year in range(FIRST_YEAR, datetime.now().year):
                if year in own[compact(name)]:
                    continue
                best = None
                for (y, raw), caps in old.items():
                    if y != year:
                        continue
                    text = raw.replace("-", " ")
                    if bool(OTHER_RIDERS.search(text)) != bool(OTHER_RIDERS.search(name.lower())):
                        continue
                    if bool(FRAMESET.search(text)) != bool(FRAMESET.search(name.lower())):
                        continue
                    s = score(mw, groupset, words(text))
                    if s is not None and s >= 2 and (best is None or s > best[0]):
                        best = (s, raw, caps)
                if best:
                    spring = datetime(year, *SPRING)
                    caps = sorted(best[2], key=lambda c: abs((datetime.strptime(c[0][:8], "%Y%m%d") - spring).days))
                    # Its own folder and photo names (<slug>_pred), next to the model's own archived pages.
                    wanted.append({"brand": brand, "name": name, "slug": compact(name) + "_pred", "year": year,
                                   "ts": caps[0][0], "url": caps[0][1], "sheet_name": best[1],
                                   "alternatives": [{"ts": t, "url": u} for t, u in caps[1:4]]})
                    found += 1
        report[brand] = found
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(wanted, fh, ensure_ascii=False, indent=1)
    return wanted, report


if __name__ == "__main__":
    import os
    from .common import ROOT
    db = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "instance", "bikecompare.sqlite3")
    print(predecessors(sys.argv[1], sys.argv[2], db)[1])
