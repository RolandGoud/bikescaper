"""Read the seller's claims from a listing, match it to a catalogue model, and run the checks.

Everything works on text the user pasted: we never fetch the listing page.
"""
import html
import json
import os
import re
import unicodedata
from datetime import date

from . import colour_match
from .i18n import Msg, join, join_list
from .reference import (BRAND_ALIASES, CATEGORY_WORDS, ELECTRONIC, FAMILY_DISCIPLINES, GENERATIONS, GENERATIONS_NOTE,
                        LINEAGES, LINEAGES_NOTE,
                        GENERIC_SIZE_CHART, GROUPSET_AGE_MAX_DROP, GROUPSET_AGE_STEP, GROUPSET_YEARS, GROUPSETS, NAME_WORDS, NO_MOTOR_GROUP, PART_TIERS, SIZE_CHARTS,
                        RIM_BRAKE_LAST_YEAR, SIZE_NOTE, SPEC_GROUPS, SPEC_LABELS, SPEC_PARTS, TIER_WEIGHTS,
                        WEIGHT_TIERS)

OK, WARN, BAD, UNKNOWN = "ok", "warn", "bad", "unknown"


def _plain(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _tokens(text):
    """Lowercase word tokens, splitting 'sl6' into 'sl 6' and 'domane+' into 'domane plus'."""
    text = _plain(text).replace("+", " plus ")
    text = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", text)
    return re.findall(r"[a-z]+|\d+", text)


# ---------------------------------------------------------------- claims

SIZE_LABELS = r"3xs|2xs|xxs|xs|s|m|l|xl|xxl|2xl"


def detect_groupset(text):
    low = _plain(text)
    found = None
    for key, name, pattern, tier in GROUPSETS:
        if re.search(pattern, low):
            # Prefer the highest tier: "105 crankset, Ultegra shifters" reads as Ultegra.
            if found is None or tier > found["tier"]:
                found = {"key": key, "name": name, "tier": tier}
    if found:
        found["electronic"] = bool(re.search(ELECTRONIC, low))
        found["label"] = found["name"] + (" (electronic)" if found["electronic"] else "")
    return found


# Parts that come in carbon on an aluminium or steel frame: "carbon vork", "zadelpen: carbon" is no frame claim.
NON_FRAME_PARTS = (r"vork|voorvork|fork|zadelpen|zadelpi[jg]p|seat\s*post|stuur|stuurpen|handlebars?|bars?|stem|"
                   r"wiel(?:en|set)?|wheels?(?:et)?|velgen|rims?(?![\s-]*brakes?)|cranks?(?:et|stel)?|crankarmen|"
                   r"zadel|saddle|kooitjes|bidonhouders?|cages?|spacers?")
NON_FRAME_CARBON = re.compile(rf"\b(?:full\s+)?carbon[\s-]+(?:{NON_FRAME_PARTS})\b"
                              rf"|\b(?:{NON_FRAME_PARTS})\b\s*(?::|=|-|van|in|uit|of|is|zijn|made of)?\s*(?:volledig\s+)?carbon\b")


MATERIAL_WORDS = {"Carbon": r"\bcarbon\b|\boclv\b|\bcf\b", "Aluminium": r"alumini?um|\balu\b|lichtmetaal|\balr\b",
                  "Steel": r"\bstaal\b|\bsteel\b"}


def detect_material(text, model_name=False):
    low = NON_FRAME_CARBON.sub(" ", _plain(text))
    for material, pattern in MATERIAL_WORDS.items():
        if re.search(pattern, low) or (material == "Aluminium" and model_name and re.search(r"\bal\b", low)):
            return material
    return None


def detect_brakes(text):
    low = _plain(text)
    if re.search(r"schijf|\bdisc\b|hydraulisch|hydraulic", low):
        return "Disc"
    if re.search(r"velgrem|\brim\b|rim brake", low):
        return "Rim"
    return None


def detect_year(text):
    """The model year the seller claims, and whether it reads as a purchase year instead."""
    low = _plain(text)
    keyed = re.search(
        r"(bouwjaar|modeljaar|model\s*jaar|model|jaar|year|uit|van|gekocht\s+in|aangeschaft\s+in|aankoop)\D{0,12}"
        r"((?:19[89]|20[0-3])\d)\b",
        low,
    )
    if keyed:
        purchase = keyed.group(1).startswith(("gekocht", "aangeschaft", "aankoop"))
        return int(keyed.group(2)), purchase
    for m in re.finditer(r"(?<![€\d.,])\b((?:19[89]|20[0-3])\d)\b(?![.,]\d)", low):
        return int(m.group(1)), False
    return None, False


def detect_size(text):
    low = _plain(text)
    m = re.search(r"(?:maat|size|framemaat|frame\s*maat|frame)\s*:?\s*(\d{2})(?:\s*cm)?\b", low)
    if m and 44 <= int(m.group(1)) <= 64:
        return m.group(1)
    m = re.search(rf"(?:maat|size|framemaat|frame)\s*:?\s*({SIZE_LABELS})\b", low)
    if m:
        return m.group(1).upper().replace("XXS", "2XS").replace("XXL", "2XL")
    m = re.search(r"\b(4[4-9]|5\d|6[0-4])\s*cm\b", low)
    if m:
        return m.group(1)
    return None


# The condition the seller picked on Marktplaats or 2dehands, which fetch_ad appends as "Conditie: ...".
SITE_CONDITION = (("damaged", r"defect|kapot|niet werkend|beschadigd|damaged"),
                  ("like-new", r"nieuw|new"),
                  ("used", r"gebruikt|used"))


def detect_condition(text):
    low = _plain(text)
    # The seller's own pick wins over words in the text, so "Conditie: Zo goed als nieuw" with a
    # "geen valschade" or "schadeverzekering" in the description still reads as like new.
    field = re.search(r"^\s*(?:conditie|staat|condition)\s*:\s*(.+)$", low, re.M)
    if field:
        for condition, pattern in SITE_CONDITION:
            if re.search(pattern, field.group(1)):
                return condition
    # "Geen schade" and "no cracks" say the opposite of damaged, also as one word ("geen valschade").
    damage = re.sub(r"\b(?:geen|zonder|no|without|nooit|never)\s+(?:\w+\s+){0,2}?\w*(?:schade|scheur\w*|crack\w*|defect\w*)"
                    r"|schadevrij|crash-?vrij", " ", low)
    if re.search(r"defect|kapot|schade|scheur|crack|niet werkend", damage):
        return "damaged"
    if re.search(r"nieuwstaat|als nieuw|zo goed als nieuw|z\.?g\.?a\.?n|like new|nauwelijks gebruikt"
                 r"|conditie:\s*nieuw", low):
        return "like-new"
    if re.search(r"gebruikssporen|krassen|sporen van gebruik|wear|conditie:\s*gebruikt", low):
        return "used"
    return None


def detect_brand(text):
    low = _plain(text)
    for alias, brand in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            return brand
    return None


PART_WORDS = {"wheels": r"wiel|wheel|velg(?!rem)|laufrad", "tyres": r"band|tyre|tire", "crankset": r"crank"}
# The part tables a claim is rated with: a crankset by its groupset ("crankstel Ultegra") or its own name.
PART_TABLES = {"crankset": ("groupset", "drivetrain")}
# Wheelset names that say "wheels" on their own, so "Bontrager Aeolus Pro 37" counts without the word "wielen".
# Each needs its model or rim depth: a bare "Aeolus" can be a saddle or handlebar.
WHEEL_NAMES = (r"aeolus\s+(?:rsl|pro|elite|comp)\s*\d{2}\b|zipp\s*\d{3}\b|\b[aepg]rc\s*\d{4}\b"
               r"|roval\s+(?:rapide|alpinist|terra|c38|clx)|ksyrium|mavic\s+cosmic|campagnolo\s+(?:bora|shamal)"
               r"|fulcrum\s+(?:racing|speed|wind)|reynolds\s+\w*\s*\d{2}\b|enve\s+(?:ses\s+)?\d\.\d|cadex\s+\d{2}\b"
               r"|princeton\s+(?:carbon\s*works\s+)?\w*\s*\d{4}\b|black\s+inc\s+\d{2}\b|newmen\s+(?:advanced|evolution)")


def detect_part(text, part):
    """The first clause of the ad that names this part and a part we can rate: {"label", "tier"} or None.

    Only clauses that mention the part ("Zipp 404 wielen", "GP5000 banden") are read, so "carbon frame"
    doesn't count as carbon wheels.
    """
    # "Zipp 404 wielen en GP5000 banden" is two clauses, so the wheel name doesn't rate the tyres.
    words = PART_WORDS[part] + (f"|{WHEEL_NAMES}" if part == "wheels" else "")
    tables = PART_TABLES.get(part, (part,))
    found = []
    for sentence in re.split(r"[\n.,;!?]+", text or ""):
        for clause in re.split(r"\s(?:en|and|met|with)\s", sentence):
            if re.search(words, _plain(clause)):
                tier = part_tier(tables, clause)
                label = clause
                if not tier:
                    # "DT swiss wielen met naaf 240": the clause names the wheels, the rest of the sentence rates them.
                    tier, label = part_tier(tables, sentence), sentence
                if tier:
                    found.append({"label": label.split(":")[-1].strip(" \t-•*"), "tier": tier})
    # A named wheelset ("Wielen: Bontrager Aeolus Pro 37") says more than an earlier "carbon wielen".
    named = [f for f in found if part == "wheels" and re.search(WHEEL_NAMES, _plain(f["label"]))]
    return (named or found or [None])[0]


def read_claims(title, description=""):
    text = f"{title}\n{description or ''}"
    year, purchase = detect_year(text)
    return {
        "brand": detect_brand(text),
        "year": year,
        "year_is_purchase": purchase,
        "size": detect_size(text),
        "groupset": detect_groupset(text),
        "material": detect_material(title) or detect_material(description),
        "brakes": detect_brakes(text),
        "wheels": detect_part(text, "wheels"),
        "tyres": detect_part(text, "tyres"),
        "crankset": detect_part(text, "crankset"),
        "condition": detect_condition(text),
        "mentions_upgrades": bool(re.search(r"upgrade|geupgrade|vervangen|nieuwe wielen|ander[e]? wielen|omgebouwd",
                                            _plain(text))),
    }


# Colour words sellers use in titles, Dutch and English, with the Dutch -e forms.
AD_COLOURS = (r"zwart|wit|grijs|grijze|blauw|rood|rode|groen|geel|gele|oranje|paars|roze|zilver|goud|brons|bruin|beige"
              r"|antraciet|black|white|grey|gray|blue|red|green|yellow|orange|purple|pink|silver|gold|bronze|brown")
AD_COLOUR = rf"(?:(?:mat|matte?|glans|glossy|donker|licht|dark|light)[\s-]?)?(?:{AD_COLOURS})e?"


def split_title(title):
    """An ad title split into the bike's name and the year, size and colour the seller put in it.

    "Trek Domane SL 6 Gen 4 2023 maat 56 zwart/rood" gives name "Domane SL 6 Gen 4", year 2023, size "56",
    colour "zwart/rood". The brand is left out of the name; the card shows it as a logo.
    """
    year, _purchase = detect_year(title)
    size = detect_size(title)
    colour = re.search(rf"\b{AD_COLOUR}(?:\s*[/&-]\s*{AD_COLOUR})?\b", title, re.I)
    name = title
    for alias in BRAND_ALIASES:
        name = re.sub(rf"\b{re.escape(alias)}\b", " ", name, flags=re.I)
    if year:
        name = re.sub(rf"\b(?:bouwjaar|modeljaar|model\s*jaar|jaar|year|uit)?\s*:?\s*\b{year}\b", " ", name, flags=re.I)
    if size:
        name = re.sub(rf"\b(?:maat|size|framemaat|frame\s*maat|frame)\s*:?\s*{re.escape(size)}(?:\s*cm)?\b"
                      rf"|\b{re.escape(size)}\s*cm\b", " ", name, flags=re.I)
    if colour:
        name = name.replace(colour.group(0), " ")
    name = re.sub(r"\s+([,;])", r"\1", re.sub(r"\s{2,}", " ", name))
    name = re.sub(r"^[\s,;:|/-]+|[\s,;:|/-]+$", "", re.sub(r"([,;:|/-]\s*){2,}", ", ", name))
    return {"name": name or title, "year": year, "size": size,
            "colour": colour.group(0).lower() if colour else None}


# ---------------------------------------------------------------- matching

def generation_of(model_name):
    m = re.search(r"\bgen\s*(\d+)", _plain(model_name))
    return int(m.group(1)) if m else None


def family_of(model_name):
    toks = _tokens(model_name)
    return toks[0] if toks else ""


def scrape_year(model):
    """The model year of our own catalogue scrape: the year the brand gives the bike (Giant, Trek and others list
    next year's bikes from the autumn on), else the year of the scrape date. None without a scrape (an archived line)."""
    if not model.get("seen_on"):
        return None
    return int(model.get("model_year") or model["seen_on"][:4])


def newest_year(model, today):
    """The newest model year a model still on sale can have: this year, or next year's that the brand already lists."""
    return max(today.year, scrape_year(model) or 0)


def generation(model):
    """The generation the model belongs to: {"first", "last" (None = still sold), "name", "earlier": [(first, last,
    name)], "note"}, from the hand-entered lineages (LINEAGES), else the generation table (GENERATIONS), else None.
    The years are model years; first is the real launch, which can be before our oldest spec sheet."""
    plain = _plain(model["name"])
    for brand, pattern, gens in LINEAGES:
        if brand != model["brand"] or not re.search(pattern, plain):
            continue
        named = [g for g in gens if g[2] and re.search(r"\b" + g[2].replace(" ", r"\s*") + r"\b", plain)]
        if named:
            mine = named[-1]
        else:
            # The newest model year we have under this very name (a predecessor's sheet has a sheet_name).
            own = [int(y) for y, e in ((model.get("year_specs") or {}).get("years") or {}).items()
                   if e.get("specs") and not e.get("sheet_name")] + [int(y) for y in model.get("photo_years") or []]
            if scrape_year(model):
                own.append(scrape_year(model))
            newest = max(own) if own else None
            mine = next((g for g in reversed(gens) if newest and g[0] <= newest), gens[-1])
        at = gens.index(mine)
        return {"first": mine[0], "last": mine[1], "name": mine[3], "note": Msg(LINEAGES_NOTE), "source": "lineage",
                "earlier": [(g[0], g[1], g[3]) for g in gens[:at]]}
    gen = generation_of(model["name"])
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), gen))
    if not years:
        return None
    earlier = sorted((y[0], y[1], f"{model['name'].split()[0]} Gen {g}") for (b, f, g), y in GENERATIONS.items()
                     if b == model["brand"] and f == family_of(model["name"]) and g < gen)
    return {"first": years[0], "last": years[1], "name": None, "note": Msg(GENERATIONS_NOTE), "earlier": earlier,
            "source": "table"}


def model_years(model, today=None):
    """(first, last or None for still sold, source message), or None when nothing tells us.

    The hand-entered generation table wins; otherwise the model years in the brand's photo file
    names, running to "now" while the newest scrape still lists the model.
    """
    gen = generation(model)
    if gen:
        return gen["first"], gen["last"], gen["note"]
    seen = model.get("photo_years") or []
    if not seen:
        return None
    still_sold = catalogue_status(model, today)[0] == "current"
    return seen[0], None if still_sold else seen[-1], Msg(
        "From the model years in {brand}'s own photos; earlier years may be missing.", brand=model["brand"])


def sheet_years(model, today=None):
    """Like model_years, from the years with a spec sheet sold under this very name (a predecessor's
    sheet has a sheet_name), for the model page when nothing else tells us. Not used for the price
    and age checks."""
    sheets = sorted(int(y) for y, e in ((model.get("year_specs") or {}).get("years") or {}).items()
                    if e.get("specs") and not e.get("sheet_name"))
    if not sheets:
        return None
    still_sold = catalogue_status(model, today)[0] == "current"
    return sheets[0], None if still_sold else sheets[-1], Msg(
        "From the spec sheets of earlier model years that {brand} or the Wayback Machine still has;"
        " earlier years may be missing.", brand=model["brand"])


def catalogue_status(model, today=None):
    """Whether the brand still sells the model: (status, message).

    status is "current", "discontinued" (its generation ended, or the brand's newest scrape no
    longer lists it) or "unknown" (no scrape history).
    """
    today = today or date.today()
    gen = generation(model)
    missed, last = model.get("missed_scrapes"), model.get("last_seen")
    # A hand-entered lineage's end only counts once the brand stops listing the model: a version can outlive its
    # generation (the Tarmac SL7 Sport after the SL8 came).
    if gen and gen["last"] and gen["last"] < today.year and (gen["source"] == "table" or missed):
        return "discontinued", Msg("Discontinued: this generation was sold until {year}.", year=gen["last"])
    if "years/archived/" in (model.get("source_file") or ""):  # a line the brand no longer sells (seed.add_archived)
        sheets = [int(y) for y in ((model.get("year_specs") or {}).get("years") or {})]
        if sheets:
            return "discontinued", Msg("Discontinued: this generation was sold until {year}.", year=max(sheets))
        return "discontinued", Msg("Discontinued: no longer in the {brand} catalogue.", brand=model["brand"])
    if missed is None:
        return "unknown", Msg("Not checked against the catalogue yet.")
    if missed:
        return "discontinued", Msg("Discontinued: missing from the newest catalogue scrape ({latest}),"
                                   " last seen {date}.", latest=model["latest_scrape"], date=last)
    return "current", Msg("In the {brand} catalogue on {date}.", brand=model["brand"], date=last)


def discipline_of(model):
    """The brand-independent discipline key (reference.DISCIPLINES) for a catalogue model, or "other"."""
    toks = set(_tokens(model["name"]))
    for key, words in NAME_WORDS.items():
        if toks & set(words):
            return key
    family = family_of(model["name"])
    for key, brands in FAMILY_DISCIPLINES.items():
        if family in brands.get(model["brand"], []):
            return key
    category = _plain(model.get("category"))
    for key, words in CATEGORY_WORDS.items():
        if any(w in category for w in words):
            return key
    return "other"


def spec_groups(model):
    """The model's spec sheet as [(group label, [(english label, dutch label, value)])], in SPEC_GROUPS order."""
    rows, seen = {}, set()
    for raw, value in model["specs"].items():
        group, en, nl = SPEC_LABELS.get(raw, ("other", raw.replace("_", " "), raw.replace("_", " ")))
        if "Motor" not in model["specs"]:
            group = NO_MOTOR_GROUP.get(group, group)
        if en in seen or not str(value).strip():
            continue
        seen.add(en)
        rows.setdefault(group, []).append((en, nl, html.unescape(str(value))))
    return [(label, rows[key]) for key, label in SPEC_GROUPS if key in rows]


FIRST_SPEC_YEAR = 2018  # the specs-per-year table on the model page starts here


def _same(a, b):
    return re.sub(r"\s+", " ", _plain(html.unescape(str(a)))).strip(" .") == \
        re.sub(r"\s+", " ", _plain(html.unescape(str(b)))).strip(" .")


def year_tabs(model, today=None):
    """One tab per catalogue year from FIRST_SPEC_YEAR (or the model's earliest sheet) to this year, for
    the spec sheet on the model page.

    Each tab is {year, state, captured, ts, url, price, specs, tiers, changed, moves, earlier, generation}. state is
    "scrape" (our own catalogue scrape), "archive" (a Wayback Machine copy of the brand's page),
    "unreadable" (a copy without a spec list), "none" (no copy of the model's page that year) or
    "unchecked" (the archive wasn't searched for this brand). specs and tiers are as spec_groups()
    and spec_tiers() give them, and changed holds the English labels whose value differs from the
    previous year with specs; moves maps those that are rated both years to "up" or "down". Rows
    keep one order across the years. earlier is true for a year of an earlier generation, as the
    age check has it (catalogue_years); generation is then what year_generations knows of it, else None.
    """
    today = today or date.today()
    found = model.get("year_specs") or {}
    archived, checked = found.get("years") or {}, set(found.get("checked") or [])
    own_year = scrape_year(model)
    tabs, before, before_tiers = [], None, None
    catalogue = catalogue_years(model)  # the same generations the age check marks
    generations = year_generations(model)
    # Earlier years only show for a model that has a sheet from then (Giant keeps some 2017 pages).
    first = min([FIRST_SPEC_YEAR] + [int(y) for y, e in archived.items() if e.get("specs")])
    for year in range(first, max(today.year, own_year or 0) + 1):
        entry = archived.get(str(year))
        if year == own_year:
            tab = {"state": "scrape", "captured": model["seen_on"], "url": model.get("url"), "price": model.get("price_eur")}
            sheet = model["specs"]
        elif entry:
            tab = dict(entry, state="archive" if entry.get("specs") else "unreadable")
            sheet = entry.get("specs")
        else:
            tab, sheet = {"state": "none" if year in checked else "unchecked"}, None
        tab["year"] = year
        listed = (found.get("list_prices") or {}).get(str(year))
        if not tab.get("price") and listed:
            tab.update(price=listed["price"], price_german=True, price_url=listed["url"])
        tab["earlier"] = catalogue.get(year, (None, False))[1]
        tab["generation"] = generations.get(year)
        if sheet:
            this = dict(model, specs=sheet)
            tab["specs"], tab["tiers"] = spec_groups(this), spec_tiers(this, year, today)
            values = {en: v for _g, rows in tab["specs"] for en, _nl, v in rows}
            tab["changed"] = set() if before is None else {
                en for en in values.keys() | before.keys() if not _same(values.get(en, ""), before.get(en, ""))}
            # A changed part rated both years is an upgrade or a downgrade on the year before. Parts are compared
            # as new: the age drop differs between the years and says nothing about the part itself.
            as_new = dict(tab["tiers"]["rows"], **{en: a["new"] for en, a in tab["tiers"]["aged"].items()})
            tab["moves"] = {en: "up" if as_new[en] > before_tiers[en] else "down"
                            for en in tab["changed"] if en in as_new and en in (before_tiers or {})
                            and as_new[en] != before_tiers[en]}
            before, before_tiers = values, as_new
        tabs.append(tab)
    _same_order(tabs)
    return tabs


def _same_order(tabs):
    """Put every year's rows in one order, so a part sits on the same line in each year: the order of
    our own scrape first, then labels only older sheets have, where they first turn up."""
    sheets = [t for t in tabs if t.get("specs")]
    sheets.sort(key=lambda t: t["state"] != "scrape")  # stable: the rest stay oldest first
    order = {}
    for t in sheets:
        for _group, rows in t["specs"]:
            for en, _nl, _v in rows:
                order.setdefault(en, len(order))
    for t in sheets:
        t["specs"] = [(group, sorted(rows, key=lambda r: order[r[0]])) for group, rows in t["specs"]]


# ---------------------------------------------------------------- tiers

def part_tier(parts, text):
    """The tier (1-5) of a part from its spec text, trying each part table in turn, or None."""
    return _part_tier(parts, text)[0]


def _part_tier(parts, text):
    """(tier, the part table that rated it) or (None, None)."""
    low = _plain(html.unescape(text or ""))
    for part in parts:
        if part == "groupset":
            found = detect_groupset(low)
            if found:
                return found["tier"], part
            continue
        for tier, pattern in PART_TIERS[part]:
            if re.search(pattern, low):
                return tier, part
    return None, None


def groupset_age_drop(year, today=None):
    """How many tiers a groupset on a bike of model `year` drops for its age: one per GROUPSET_AGE_STEP years,
    at most GROUPSET_AGE_MAX_DROP. 0 without a year."""
    if not year:
        return 0
    age = (today or date.today()).year - int(year)
    return max(0, min(GROUPSET_AGE_MAX_DROP, age // GROUPSET_AGE_STEP))


def sheet_year(model):
    """The model year of the model's own spec sheet: its newest archived sheet for a line the brand no longer
    sells, otherwise the year we scraped it. None when nothing tells us."""
    if "years/archived/" in (model.get("source_file") or ""):
        sheets = [int(y) for y, e in ((model.get("year_specs") or {}).get("years") or {}).items() if e.get("specs")]
        if sheets:
            return max(sheets)
    return scrape_year(model)


def weight_kg(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg", text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def weight_tier(model, text):
    limits, kg = WEIGHT_TIERS.get(discipline_of(model)), weight_kg(text)
    if not limits or not kg:
        return None
    return 5 - sum(kg > limit for limit in limits)


def _round(x):
    return int(x + 0.5)


# The parts the model page header lists beside the photo: (label, spec rows to try in order).
KEY_PARTS = (("Frame", ("Frame", "Frame material")),
             ("Groupset", ("Rear derailleur", "Drivetrain", "Shifters", "Crankset")),
             ("Wheels", ("Front wheel", "Rims", "Rear wheel")),
             ("Brakes", ("Brakes", "Rear brake", "Brake type")),
             ("Weight", ("Weight",)))


def key_parts(specs, tier_rows=None, limit=4):
    """The main parts of a spec sheet (from spec_groups) for the model page header:
    [(label, short value, tier or None)], at most `limit`, weight only when a part is missing.
    The short value is the part's name, the text before its first comma."""
    values = {en: value for _group, rows in specs or [] for en, _nl, value in rows}
    parts = []
    for label, keys in KEY_PARTS:
        key = next((k for k in keys if str(values.get(k) or "").strip()), None)
        if key:
            short = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(values[key]))).split(",")[0].strip(" .;")
            if label == "Groupset":  # "SRAM Rival Rear Derailleur" names the groupset as "SRAM Rival"
                short = re.sub(r"\s+(rear derailleur|achterderailleur)$", "", short, flags=re.I) or short
            parts.append((label, short, (tier_rows or {}).get(key)))
    return parts[:limit]


def spec_tiers(model, year=None, today=None):
    """Tiers for the model's spec sheet: {"rows": {english label: tier}, "groups": {group label: tier},
    "overall": tier or None, "lagging": [group labels two or more tiers below the overall],
    "aged": {english label: {"new": tier when new, "age": years}}, "age": years or None}.

    A group's tier is the rounded mean of its rated rows; the overall tier weighs the groups by
    TIER_WEIGHTS. The frame group counts the frame itself, not the fork, when the frame is rated.
    Without a rated frame or drivetrain there is no overall tier.

    `year` is the sheet's model year (sheet_year of the model when not given). Rows rated by their groupset
    name drop a tier or two for the bike's age (groupset_age_drop); "aged" lists them with their tier new.
    """
    year = year or sheet_year(model)
    drop = groupset_age_drop(year, today)
    age = (today or date.today()).year - year if year else None
    rows, by_group, frame, aged = {}, {}, [], {}
    for raw, value in model["specs"].items():
        group, en, _nl = SPEC_LABELS.get(raw, ("other", raw, raw))
        if "Motor" not in model["specs"]:
            group = NO_MOTOR_GROUP.get(group, group)
        if en in rows:
            continue
        if group == "weight" and en == "Weight":
            tier = weight_tier(model, str(value))
        elif raw in SPEC_PARTS:
            text = f"{value} {model['name']}" if SPEC_PARTS[raw] == ("frame",) else str(value)
            tier, part = _part_tier(SPEC_PARTS[raw], text)
            if tier and part == "groupset" and drop and tier > 1:
                aged[en] = {"new": tier, "age": age}
                tier = max(1, tier - drop)
        else:
            tier = None
        if tier:
            rows[en] = tier
            by_group.setdefault(group, []).append(tier)
            if SPEC_PARTS.get(raw) == ("frame",):
                frame.append(tier)
    if frame:
        by_group["frame"] = frame
    groups = {key: _round(sum(ts) / len(ts)) for key, ts in by_group.items()}
    weighted = [(TIER_WEIGHTS[k], t) for k, t in groups.items() if k in TIER_WEIGHTS]
    overall = None
    if "frame" in groups or "drivetrain" in groups:
        overall = _round(sum(w * t for w, t in weighted) / sum(w for w, _t in weighted))
    labels = dict(SPEC_GROUPS)
    return {"rows": rows, "groups": {labels[k]: t for k, t in groups.items()}, "overall": overall,
            "lagging": [labels[k] for k, t in groups.items() if overall and t <= overall - 2],
            "aged": aged, "age": age}


def model_tier(model):
    return spec_tiers(model)["overall"]


def _numbered(tokens):
    """The (word, number) pairs in a token list: "Tarmac SL 7 Gen 4" gives {("sl", "7"), ("gen", "4")}."""
    return {(a, b) for a, b in zip(tokens, tokens[1:]) if a.isalpha() and b.isdigit()}


def conflicts(model, text):
    """Where the ad names another version of a numbered part of this model's name: [("SL9", "SL7")] when the
    model is an SL9 and the ad says SL7. Only the name before the " - " counts, so "Shimano 105" in the build
    can't clash with "Shimano 11 speed"."""
    ad_toks = _tokens(text)
    ad_pairs = _numbered(ad_toks)
    name_toks = _tokens(model["name"].split(" - ")[0])
    found = []
    for part, number in sorted(_numbered(name_toks)):
        said = sorted({n for w, n in ad_pairs if w == part})
        if said and number not in said:
            label = "Gen " if part == "gen" else part.upper() if len(part) <= 3 else part.title()
            found.append((f"{label}{number}", "/".join(f"{label}{n}" for n in said)))
    # A tier one letter off: the ad says SLR and this model is an SL (or AL for ALR, CF for CFR).
    for tok in dict.fromkeys(t for t in name_toks if t.isalpha() and 2 <= len(t) <= 4 and t not in ad_toks):
        said = sorted({t for t in ad_toks if t.isalpha() and t not in name_toks and abs(len(t) - len(tok)) == 1
                       and (t.startswith(tok) or tok.startswith(t))})
        if said:
            found.append((tok.upper(), "/".join(t.upper() for t in said)))
    return found


def _colour_named(model, text):
    """Whether the ad names one of this model's colourways in full ("Navy Carbon Smoke/Viper Red"); a plain
    colour ("zwart") says little, so a name needs two words or more."""
    ad = " ".join(re.findall(r"[a-z]+", _plain(text)))
    names = set(model.get("colors") or [])
    names |= {c for e in (model.get("year_specs") or {}).values() if isinstance(e, dict) for c in e.get("colours") or []}
    for name in names:
        words = re.findall(r"[a-z]+", _plain(name))
        if len(words) >= 2 and f" {' '.join(words)} " in f" {ad} ":
            return True
    return False


def match_models(models, title, description="", claims=None):
    """Rank catalogue models for a listing. Returns [(score, model)] best first."""
    claims = claims or read_claims(title, description)
    title_toks = set(_tokens(title))
    all_toks = title_toks | set(_tokens(description))
    says_gen = "gen" in all_toks or "generatie" in all_toks
    # The generation numbers the ad names ("gen 4", "generatie 3"): a Domane SL 5 Gen 5 must not count the
    # "5" of "SL 5" as its generation.
    ad_gens = set(re.findall(r"\bgen(?:eratie)?\.?\s*(\d+)\b", f"{title} {description}".lower()))
    # The words this brand uses in its model names (SLR, Expert, Pro), for the title words a model lacks.
    brand_toks = {}
    for m in models:
        brand_toks.setdefault(m["brand"], set()).update(_tokens(m["name"].split(" - ")[0]))
    title_words = {t for w in title.split() if not re.fullmatch(ELECTRONIC, w.lower()) for t in _tokens(w)
                   if not t.isdigit()}
    ranked = []
    for model in models:
        if claims["brand"] and model["brand"] != claims["brand"]:
            continue
        name_toks = _tokens(model["name"])
        family = [t for t in name_toks if t not in ("s", "works")][:1]
        if not family or family[0] not in all_toks:
            continue  # the model family (Domane, Ultimate, Tarmac in "S-Works Tarmac") must be named
        # The seller names another version: an SL7 is not an SL9 (Gen has its own rule below).
        # A tier one letter off (SL for SLR) weighs half: the ad's own model may simply not be in the catalogue.
        clashes = sum(1 if any(c.isdigit() for c in ours) else 0.5
                      for ours, _ in conflicts(model, title) if not ours.startswith("Gen"))
        score = 0.0
        skip_next = False
        for i, tok in enumerate(name_toks):
            if skip_next:
                skip_next = False
                continue
            if tok == "gen" and i + 1 < len(name_toks):
                skip_next = True
                if ad_gens:
                    score += 1.0 if name_toks[i + 1] in ad_gens else -1.0
                continue
            if tok in title_toks:
                score += 1.5
            elif tok in all_toks:
                score += 1.0
            else:
                score -= 0.75
        gen = generation(model)
        if gen and claims["year"] and not says_gen:
            if gen["first"] - 1 <= claims["year"] <= (gen["last"] or 2100) + 1:
                score += 0.5
        ref_group = detect_groupset(groupset_text(model))
        if ref_group and claims["groupset"] and ref_group["key"] == claims["groupset"]["key"]:
            score += 0.25
        score -= 3 * clashes  # still a candidate when we have nothing closer, but a weak one
        # A model word in the title this model hasn't (Defy Advanced SL 1 for a Defy Advanced 1): another model.
        score -= 0.75 * len((title_words & brand_toks.get(model["brand"], set())) - set(name_toks))
        if _colour_named(model, f"{title} {description}"):
            score += 1.0  # the seller copied the brand's colour name: that colourway's model
        ranked.append((round(score, 2), model))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["price_eur"] or 0))
    return ranked


def name_check(model, models, title, description=""):
    """How the seller's name for the bike compares with the model we matched, or None when they agree.

    {"conflicts": [(our word, the ad's word)] like ("SL9", "SL7"), "found": our model's words the ad names,
    "missing": our model's words the ad doesn't name, "extra": words in the title that are model words for
    this brand (S-Works, Expert, ...) but aren't in our model}.
    """
    ad_toks = set(_tokens(f"{title} {description or ''}"))
    clashes = conflicts(model, title)
    words = model["name"].split(" - ")[0].split()
    clash_toks = {t for pair in clashes for side in pair for t in _tokens(side)}
    found = [w for w in words if all(t in ad_toks for t in _tokens(w)) and not set(_tokens(w)) <= clash_toks]
    missing = [w for w in words if w not in found and not set(_tokens(w)) <= clash_toks]
    model_toks = set(_tokens(model["name"]))
    brand_toks = {t for m in models if m["brand"] == model["brand"] for t in _tokens(m["name"].split(" - ")[0])}
    # "Di2", "AXS", "eTap", "EPS" say how it shifts, not which model it is: match_rate weighs that on its own.
    extra = []
    for w in title.split():
        toks = _tokens(w)
        if re.fullmatch(ELECTRONIC, w.lower()):
            continue
        if (toks and w not in extra and not all(t in model_toks for t in toks) and all(t in brand_toks for t in toks)
                and not all(t in clash_toks or t.isdigit() for t in toks)):
            extra.append(w)
    if not clashes and not missing and not extra:
        return None
    return {"conflicts": clashes, "found": found, "missing": missing, "extra": extra}


def confidence(ranked):
    if not ranked:
        return None
    top = ranked[0][0]
    gap = top - ranked[1][0] if len(ranked) > 1 else top
    if top >= 3 and gap >= 1:
        return "high"
    if top >= 2 and gap > 0:
        return "medium"
    return "low"


def match_confidence(pct, others=(), not_exact=False):
    """The confidence the report shows, from the same fit it shows next to it: high from 90% with no
    other model within 15 points, medium from 70%, low below that or when the ad names a version we don't have."""
    runner = max(others, default=0)
    if not_exact or pct < 70:
        return "low"
    if pct >= 90 and pct - runner >= 15:
        return "high"
    return "medium"


def name_parts(model):
    """The model's name split into its family and its version: "Defy Advanced Pro 1" gives ("Defy Advanced Pro",
    "1"), "Domane SL 6 Gen 4" gives ("Domane SL", "6 Gen 4"). The version starts at the first word with a number."""
    words = re.split(r"[\s-]+", model["name"].split(" - ")[0].strip())
    at = next((i for i, w in enumerate(words) if i and re.search(r"\d", w)), len(words))
    return " ".join(words[:at]), " ".join(words[at:])


def _share(part, ad_toks, clash_toks=()):
    toks = _tokens(part)
    if not toks:
        return None
    return round(100 * sum(t in ad_toks and t not in clash_toks for t in toks) / len(toks))


def shifting(model, title, description=""):
    """How the ad's shifting compares with the model's: {"ad", "model"} as "electronic" or "mechanical", and
    "same"; None when the ad doesn't say or we don't know the model's groupset."""
    text = f"{title} {description or ''}".lower()
    if re.search(ELECTRONIC + r"|elektronis|electronic", text):
        ad = "electronic"
    elif re.search(r"mechanis|mechanical", text):
        ad = "mechanical"
    else:
        return None
    group = detect_groupset(groupset_text(model))
    if not group:
        return None
    ours = "electronic" if group.get("electronic") else "mechanical"
    return {"ad": ad, "model": ours, "same": ad == ours}


def match_rate(model, models, title, description=""):
    """How well the ad's words fit a model, in percent, with the part scores it's made of:
    {"pct", "brand", "family", "version" (each {"name", "pct"}, version None for a model without one), "extra"}.
    The brand counts a fifth, the family and the version two fifths each; every model word the title has that
    this model hasn't (Pro, Expert) takes 15 off, a tier one letter off (SL for SLR) 25, shifting the ad says otherwise (Di2 for a mechanical groupset) 10,
    and a version the ad names otherwise (an SL7 for an SL9) scores 0."""
    ad_toks = set(_tokens(f"{title} {description or ''}"))
    family, version = name_parts(model)
    clash_toks = {t for ours, _ in conflicts(model, title) for t in _tokens(ours)}
    brand_pct = 100 if set(_tokens(model["brand"])) <= ad_toks else 50
    family_pct = _share(family, ad_toks)
    version_pct = _share(version, ad_toks, clash_toks)
    check = name_check(model, models, title, description) or {}
    extra = check.get("extra", [])
    if version_pct is None:
        pct = 0.2 * brand_pct + 0.8 * family_pct
    else:
        pct = 0.2 * brand_pct + 0.4 * family_pct + 0.4 * version_pct
    shift = shifting(model, title, description)
    if shift and not shift["same"]:
        pct -= 10
    pct -= 25 * sum(not any(c.isdigit() for c in ours) for ours, _ in check.get("conflicts", []))  # SL for SLR
    return {"pct": max(0, min(100, round(pct - 15 * len(extra)))), "shifting": shift,
            "brand": {"name": model["brand"], "pct": brand_pct},
            "family": {"name": family, "pct": family_pct},
            "version": {"name": version, "pct": version_pct} if version else None,
            "found": check.get("found") if check else model["name"].split(" - ")[0].split(),
            "missing": check.get("missing", []), "extra": extra, "conflicts": check.get("conflicts", [])}


# ---------------------------------------------------------------- reference helpers

def spec(model, *keys):
    specs = model["specs"]
    for key in keys:
        if specs.get(key):
            return specs[key]
    return None


def groupset_text(model):
    return " ".join(filter(None, [spec(model, "Shifter"), spec(model, "Achterderailleur"), spec(model, "Crankstel")]))


def ref_material(model):
    return detect_material(spec(model, "Material", "Frame") or "") or detect_material(model["name"], model_name=True)


def model_materials(model):
    """{material: [model years]} for the frame materials the model came in, from the spec sheet of each model
    year we have; years whose sheet doesn't say are left out. The current spec sheet and the model's name
    count too (under None: we don't know its year), only for a material no year's sheet gives."""
    out = {}
    for year, sheet in sorted(year_sheets(model).items()):
        material = detect_material(spec(dict(model, specs=sheet["specs"]), "Material", "Frame") or "")
        if material:
            out.setdefault(material, []).append(year)
    current = ref_material(model)
    if current and current not in out:
        out[current] = [None]
    return out


MATERIAL_LOWER = {"Carbon": "carbon", "Aluminium": "aluminium", "Steel": "steel"}


def impossible_material(model, claims, text=""):
    """When the ad claims a frame material the model was never made in: {"claimed", "made_in", "years"}.

    Only when every model year we know says the same thing, and the ad doesn't also name the material the
    model really is ("alu frame, carbon vork"): then it's a wrong claim or a different model, not a
    bike that came in both."""
    claimed = claims.get("material")
    made = model_materials(model)
    if not claimed or not made or claimed in made:
        return None
    low = NON_FRAME_CARBON.sub(" ", _plain(text))
    if any(re.search(MATERIAL_WORDS[m], low) for m in made):
        return None
    years = sorted(y for ys in made.values() for y in ys if y)
    span = _span(years[0], years[-1]) if years else None
    lower = {k: Msg(v) for k, v in MATERIAL_LOWER.items()}
    kw = {"name": model["name"], "brand": model["brand"], "claimed": lower[claimed],
          "made": join_list([lower[m] for m in sorted(made)]), "years": span}
    detail = (Msg("The ad says the frame is {claimed}, but every {brand} spec sheet we have of it ({years}) says "
                  "{made}. Either the ad gets the material wrong, or the bike is another model than it says.", **kw)
              if span else
              Msg("The ad says the frame is {claimed}, but {brand}'s spec sheet says {made}. Either the ad gets the "
                  "material wrong, or the bike is another model than it says.", **kw))
    return {"claimed": claimed, "made_in": sorted(made), "years": span,
            "headline": Msg("Impossible claim: the {name} was never made in {claimed}", **kw), "detail": detail,
            "question": Msg("The {name} was only ever made in {made}. Why does the ad say {claimed}?", **kw)}



def ref_brakes(model):
    if spec(model, "Remschijf", "Schijfdiameter"):
        return "Disc"
    if re.search(r"\brim\b", _plain(model["name"])):
        return "Rim"
    return detect_brakes(spec(model, "Rem") or "") or ("Disc" if re.search(r"\brt\d|sm-rt", _plain(spec(model, "Rem") or "")) else None)


# ---------------------------------------------------------------- checks

def eur(value):
    return "€{:,.0f}".format(value).replace(",", ".")


SHEETS_NOTE = "From the spec sheets of each model year that {brand} or the Wayback Machine still has."
PHOTOS_NOTE = "From our own catalogue scrape and the model years in {brand}'s photos; earlier years may be missing."
EARLIER_NOTE = "Earlier generations in our catalogue: {years}."


def catalogue_years(model):
    """{year: (sheet name or None, earlier generation)} for every model year our catalogue has of this model: its
    spec sheets (a predecessor's under its own name), our own scrape and the model years in the brand's photos.

    A year is an earlier generation when its sheet names another generation number, or when it comes before the
    generation's launch (generation), even under this very name: brands keep a name across generations.
    """
    number, gen = generation_of(model["name"]), generation(model)

    def earlier(year, name):
        if name and number is not None and generation_of(name) is not None:
            return generation_of(name) != number
        return bool(gen and year < gen["first"])

    archived = (model.get("year_specs") or {}).get("years") or {}
    out = {}
    for y in model.get("photo_years") or []:
        out[int(y)] = (None, earlier(int(y), "photo"))
    for y, e in archived.items():
        if e.get("specs"):
            name = e.get("sheet_name")
            out[int(y)] = (name, earlier(int(y), name))
    # Our own scrape, for a year without a sheet of this generation (Giant lists next year's bikes from the
    # autumn on, so the scrape date isn't the model year when a sheet has it).
    if scrape_year(model) and model.get("specs"):
        own = scrape_year(model)
        if own not in out or out[own][1]:
            out[own] = (None, False)
    return out


SAME_FRAME, OTHER_FRAME = 0.8, 0.5  # how alike two years' frame descriptions read (words in common), see _frame_likeness


def _frame(model, year):
    """The frame line of the model's spec sheet for that year (our own scrape for its own year), or None."""
    sheet = (((model.get("year_specs") or {}).get("years") or {}).get(str(year)) or {}).get("specs")
    if not sheet and scrape_year(model) == year:
        sheet = model.get("specs")
    return next((v for k, v in (sheet or {}).items() if k.lower() in ("frame", "frameset")), None)


def _frame_likeness(a, b):
    """The share of words two frame descriptions have in common (0-1), or None without both. Within a generation
    Trek's frame line mostly barely changes (0.86-1.0 on the Madone SL and Domane SL sheets), but a mid-generation
    update can score 0.64 (the 2021 Madone SLR's 800 Series frame) and a new generation 0.71 (Madone Gen 7), so only
    a frame that has little in common (the 2019-2020 rim-brake Domane AL against its Gen 3: 0.44) counts as new."""
    a, b = (set(re.findall(r"\w+", (t or "").lower())) for t in (a, b))
    return len(a & b) / len(a | b) if a and b else None


def without_generation(name):
    """"Domane AL 2 Gen 4" -> "Domane AL 2": the model's name without the generation the brand puts in it."""
    return re.sub(r"\s*\bgen\s*\d+\b", "", name or "", flags=re.I).strip() or name


def _sheet_span(text):
    """"2021 - 2023" (the model years a brand's own archive sheet covers) -> (2021, 2023), else None."""
    found = [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", text or "")]
    return (min(found), max(found)) if found else None


def year_generations(model):
    """{year: generation} for each year of an earlier generation in our catalogue (catalogue_years), so the model
    page can show that bike when its year is picked: {"name" (as it was sold, or None), "title" (the name to
    show), "first", "last" (the model years that generation was sold, or None when nothing tells us), "number"
    (its generation number or None),
    "counted" (None when the name gives the number, "same" when the frame matches the next generation's, "before"
    when the frame changed right before it), "source"}.

    The years come from the hand-entered launch years ("lineage": LINEAGES or GENERATIONS), else the brand's own
    archive sheet ("sheet", e.g. Trek's "2021 - 2023"), else the run of following years whose sheets carry the
    same name ("sheets"); "frame" when unnumbered years joined a generation because their frame reads the same
    (see below). A generation
    without a number in its name gets one from the frame of the numbered generation right after it: Trek's
    2019–2020 Domane AL 2 had a rim-brake frame, the Gen 3 from 2021 a new one, so it was gen 2."""
    gen = generation(model)
    archived = (model.get("year_specs") or {}).get("years") or {}
    lineage = (gen or {}).get("earlier") or []
    catalogue = catalogue_years(model)
    old = {y: name for y, (name, earlier) in catalogue.items() if earlier}
    out = {}
    for y, name in old.items():
        name = re.sub(r"\bgen\s*(\d+)", r"Gen \1", name) if name else None
        line = next(((f, l, n) for f, l, n in lineage if f <= y <= (l or f)), None)
        number = generation_of(name) if name else None
        # The hand-entered launch years are of the whole generation; a sheet's years only of that one page. They
        # count unless the sheet names another generation.
        if line and generation_of(line[2]) not in (None, number) and number is not None:
            line = None
        if line:
            span, source, number = (line[0], line[1]), "lineage", number or generation_of(line[2])
        else:
            span, source = _sheet_span((archived.get(str(y)) or {}).get("sheet_years")), "sheet"
        if not span and name:
            first = last = y
            while old.get(first - 1) == old[y]:
                first -= 1
            while old.get(last + 1) == old[y]:
                last += 1
            span, source = (first, last), "sheets"
        out[y] = {"name": name, "first": span[0] if span else None, "last": span[1] if span else None,
                  "number": number, "counted": None,
                  "source": source if span else None}
    # Count back from the newest generation. Trek's archive often names a generation only on its last sheets (the
    # 2020-2021 Domane SL 5 sheet is the same bike as the 2022 "Domane SL 5 gen 3"), so the frame decides: a run
    # of years without a number right before a numbered generation is that generation when its frame reads the
    # same, and the one before it when the frame changed. In between, or without both frames, we don't guess.
    own_first = min([y for y, (_n, earlier) in catalogue.items() if not earlier] + ([gen["first"]] if gen else []),
                    default=None)
    groups = {}
    for e in out.values():
        if e["first"]:
            groups.setdefault((e["first"], e["last"]), []).append(e)
    newer = (own_first, generation_of(model["name"]), None)  # (first year, number, its entries; None = ours)
    for span in sorted(groups, reverse=True):
        mine = groups[span]
        number = mine[0]["number"]
        if number is None and newer[1] and newer[0] == span[1] + 1:
            same = _frame_likeness(_frame(model, span[1]), _frame(model, newer[0]))
            if same is not None and same >= SAME_FRAME and newer[2] is not None:
                number, last = newer[1], newer[2][0]["last"]
                for e in mine:
                    e.update(number=number, counted="same", last=last)
                for e in mine + newer[2]:
                    e.update(first=span[0], source="frame")
                mine = mine + newer[2]
            elif same is not None and same <= OTHER_FRAME and newer[1] > 1:
                number = newer[1] - 1
                for e in mine:
                    e.update(number=number, counted="before")
        newer = (span[0], number, mine)
    # The name to show: as it was sold, else ours with the generation number swapped ("Domane AL 2 Gen 4" -> "Gen 3").
    for e in out.values():
        e["title"] = e["name"] or (re.sub(r"\b(gen\s*)\d+", lambda m: m.group(1) + str(e["number"]), model["name"],
                                          flags=re.I) if e["number"] else model["name"])
    return out


def sold_years(model, today=None):
    """(first, last or None for still sold, note, open start, catalogue years) for the age check, or None when
    nothing tells us. The years this generation was sold come from every year in our catalogue (catalogue_years),
    stretched to the hand-entered generation table where it has one. The start is open when nothing older is
    known: no table, no earlier generation and no sheet from before the oldest year we looked up."""
    gen = generation(model)
    years = catalogue_years(model)
    own = {y for y, (_name, old) in years.items() if not old} | (
        set(range(gen["first"], (gen["last"] or gen["first"]) + 1)) if gen else set())
    if not own:
        return None
    still_sold = catalogue_status(model, today)[0] == "current"
    first, last = min(own), None if still_sold else max(own)
    year_specs = model.get("year_specs") or {}
    archived = any(e.get("specs") for e in (year_specs.get("years") or {}).values())
    checked = year_specs.get("checked") or []
    open_start = (not gen and not any(old and y < first for y, (_n, old) in years.items())
                  and (not archived or not checked or first <= min(checked)))
    note = gen["note"] if gen and not archived else Msg(SHEETS_NOTE if archived else PHOTOS_NOTE, brand=model["brand"])
    return first, last, note, open_start, years


def check_age(model, claims, today=None):
    today = today or date.today()
    known = sold_years(model, today)
    years, note, open_start, catalogue = (known[:2], known[2], known[3], known[4]) if known else (None, None, False, {})
    seen = Msg("On sale in the {brand} NL catalogue on {date}.", brand=model["brand"],
               date=model["seen_on"]) if model.get("seen_on") else None
    earlier = {y: name for y, (name, old) in catalogue.items() if old}
    notes = [n for n in [seen, note, earlier and Msg(EARLIER_NOTE, years=_years_list(earlier))] if n]
    # The earlier generations we know the launch years of, under their own name where we have no sheet of that year.
    sheets = dict(earlier)
    gen = generation(model)
    lineage = {y: name for f, l, name in (gen or {}).get("earlier") or [] for y in range(f, (l or f) + 1)}
    for y, name in lineage.items():
        if not earlier.get(y):
            earlier[y] = name
    claimed = claims["year"]
    timeline = []
    photos = {int(y): e["image"] for y, e in ((model.get("year_specs") or {}).get("years") or {}).items()
              if e.get("image")}
    if scrape_year(model) and model.get("image") and scrape_year(model) not in photos:
        photos[scrape_year(model)] = model["image"]
    if years:
        first, last = years
        end = last or newest_year(model, today)
        for y in range(min([first, claimed or first] + list(catalogue)), max([end, claimed or end] + list(catalogue)) + 1):
            sold = first <= y <= end
            timeline.append({"year": y, "sold": sold, "claimed": y == claimed, "photo": photos.get(y),
                             "earlier": not sold and y in earlier, "sheet_name": sheets.get(y),
                             "generation": None if sold else lineage.get(y)})
    if claimed is None:
        return {"status": WARN, "headline": Msg("Year not stated"),
                "detail": Msg("The ad doesn't give a year. Ask for the invoice or the serial number."),
                "timeline": timeline, "generations": timeline_groups(model, timeline), "notes": notes}
    if not years:
        return {"status": UNKNOWN, "headline": Msg("Seller says {year}", year=claimed),
                "detail": Msg("We don't have the model years for this bike yet, so we can't confirm the age."),
                "timeline": [], "notes": [n for n in [seen] if n]}
    first, last = years
    older = purchase = False
    # The year before launch is more likely the purchase year than the previous generation, unless we have a sheet
    # of that generation in that year.
    other = claimed < first and (claimed in earlier or (earlier and min(earlier) < claimed)) and (
        claimed != first - 1 or claimed in sheets)
    if other:
        status, headline = WARN, Msg("Earlier generation")
        name = earlier.get(claimed)
        detail = (Msg("In {claimed} {brand} sold the {sheet}, an earlier generation than {name}. Check which one the "
                      "ad's bike is.", claimed=claimed, brand=model["brand"], sheet=name, name=model["name"]) if name else
                  Msg("{claimed} is before {name} went on sale as the {first} model, when {brand} sold an earlier "
                      "generation. Check which one the ad's bike is.", claimed=claimed, name=model["name"],
                      first=first, brand=model["brand"]))
        if claimed == first - 1:
            detail = join(detail, Msg("{claimed} may also be when it was bought.", claimed=claimed))
    elif open_start and claimed < first:
        status, headline = UNKNOWN, Msg("Seller says {year}", year=claimed)
        detail = Msg("Our oldest model year of {name} is {first}, so we can't confirm {claimed}.",
                     name=model["name"], first=first, claimed=claimed)
    elif claimed < first - 1:
        # We can't disprove the seller: the bike is probably an older generation than any we have, so the
        # check goes by the year in the ad.
        status, headline, older = UNKNOWN, Msg("Probably older than we can check"), True
        detail = Msg("Seller says {claimed}. The oldest {name} we know is the {first} model, so this is probably "
                     "an earlier generation we don't have yet. We go by {claimed}, the year in the ad.",
                     claimed=claimed, name=model["name"], first=first)
    elif claimed == first - 1:
        status, headline, purchase = WARN, Msg("Probably the purchase year"), True
        detail = Msg("This generation went on sale as the {first} model, in {launch}. "
                     "{claimed} is likely when it was bought, not the model year.",
                     first=first, launch=first - 1, claimed=claimed)
    elif last and claimed > last + 1:
        status, headline = WARN, Msg("After this model was replaced")
        detail = Msg("This generation was last sold as the {last} model. A {claimed} bike would be leftover stock.",
                     last=last, claimed=claimed)
    else:
        status, headline = OK, Msg("Adds up")
        detail = Msg("{name} was sold as new in {claimed}.", name=model["name"], claimed=claimed)
    if claims["year_is_purchase"]:
        detail = join(detail, Msg("The seller gives this as the purchase year."))
    return {"status": status, "headline": headline, "detail": detail, "timeline": timeline,
            "generations": timeline_groups(model, timeline), "notes": notes, "year": claimed,
            "earlier": bool(other), "earlier_sheet": bool(other) and claimed in year_sheets(model), "older": older,
            "purchase": purchase}


def timeline_groups(model, timeline):
    """The age timeline as blocks of years in a row that belong together, for the age tab: this model's own
    years, each earlier generation's (named after its newest spec sheet, else the generation's name) and years we
    know nothing of. Each block: {"kind": "own" | "earlier" | "unknown", "name", "first", "last", "years"}."""
    def key(y):
        if y["sold"]:
            return "own"
        if y["earlier"]:
            return ("earlier", y["generation"] or y["sheet_name"])
        return "unknown"

    groups = []
    for y in timeline:
        if groups and groups[-1]["key"] == key(y):
            groups[-1]["years"].append(y)
        else:
            groups.append({"key": key(y), "kind": key(y) if isinstance(key(y), str) else "earlier", "years": [y]})
    for g in groups:
        g["first"], g["last"] = g["years"][0]["year"], g["years"][-1]["year"]
        named = [y["sheet_name"] for y in g["years"] if y["sheet_name"]]
        g["name"] = (model["name"] if g["kind"] == "own" else
                     (named[-1] if named else g["years"][0]["generation"]) if g["kind"] == "earlier" else None)
        del g["key"]
    return groups


def colourway_year(colourway):
    """The model year in a colourway photo's file name (Trek "-26-" or "_23_", Canyon "2026_FULL_" or "full_2025_"),
    or None."""
    name = os.path.basename(colourway.get("image") or "")
    m = (re.search(r"(20[1-3]\d)_full_|^full_(20[1-3]\d)_", name.lower())
         or re.search(r"[-_]([1-3]\d)[-_]\d{4,}", name))
    if not m:
        return None
    year = int(next(g for g in m.groups() if g))
    return year if year > 2000 else 2000 + year


GENERIC_COLOUR = re.compile(rf"^(?:{AD_COLOURS}|mat|matte?|gloss|glossy|satin|metallic|dark|light|donker|licht"
                            r"|deep|bright|and|en)$")


def _named_colourways(model, models):
    """Colourways of this model and its siblings (same brand and family) whose name is more than plain colour words."""
    found = {}
    for m in [model] + [m for m in models if m["brand"] == model["brand"] and family_of(m["name"]) == family_of(model["name"])]:
        for cw in m.get("colorways") or []:
            words = re.findall(r"[a-z]+", _plain(cw.get("name")))
            year = colourway_year(cw)
            if year and words and not all(GENERIC_COLOUR.match(w) for w in words):
                found.setdefault(" ".join(words), (cw["name"], year))
    return found.values()


# Part numbers that change between model years: RX810, M7100, FC-R510, CL800, cassettes 11-34 or 11x34.
PART_CODE = re.compile(r"\b(?:[a-z]{1,3}-?\d{3,4}[a-z]?|\d{2}[-x]\d{2})\b")
YEAR_PARTS = ("Achterderailleur", "Voorderailleur", "Shifter", "Crankstel", "Cassette", "Ketting", "Rem", "Remgreep",
              "Remschijf", "Wiel voor", "Wiel achter", "Velg", "Naven", "Buitenband", "Wheelset", "Aandrijving")


def _part_codes(text):
    return {c.replace("x", "-") if re.fullmatch(r"\d{2}[-x]\d{2}", c) else c.replace("-", "")
            for c in PART_CODE.findall(_plain(text))
            if not re.fullmatch(r"(?:19|20)\d\d", c)}


def year_sheets(model):
    """{year: {"specs", "colours"}} for every model year we have a spec sheet of, our own scrape included."""
    out = {int(y): {"specs": e["specs"], "colours": e.get("colours") or []}
           for y, e in ((model.get("year_specs") or {}).get("years") or {}).items() if e.get("specs")}
    # Only for a year without a sheet: the scrape date isn't the model year (Giant lists next year's bikes
    # from the autumn on).
    if scrape_year(model) and model.get("specs") and scrape_year(model) not in out:
        out[scrape_year(model)] = {"specs": model["specs"],
                                          "colours": [c["name"] for c in model.get("colorways") or []] or model.get("colors") or []}
    return out


def year_prices(model):
    """{year: (new price, German?)}: the Dutch price from that year's spec sheet, else the German list price
    from the TOUR/BIKE database (see webapp/seed.py year_specs)."""
    found = model.get("year_specs") or {}
    prices = {int(y): (e["price"], True) for y, e in (found.get("list_prices") or {}).items() if e.get("price")}
    prices.update({int(y): (e["price"], False) for y, e in (found.get("years") or {}).items() if e.get("price")})
    return prices


def new_price(model, year):
    """The model's new price in that model year, from that year's spec sheet or our own scrape, else the German
    list price; None when we don't have that year's price."""
    if not year:
        return None
    entry = ((model.get("year_specs") or {}).get("years") or {}).get(str(year)) or {}
    if entry.get("price"):
        return entry["price"]
    if scrape_year(model) == year and model.get("price_eur"):
        return model["price_eur"]
    return year_prices(model).get(year, (None, False))[0]


def _widen(years, sheets):
    """(first, last) of years, stretched over neighbouring years we have no sheet of: those may have had the same.
    An end that reaches the oldest or newest sheet stays open (None): we don't know the years beyond."""
    first, last = min(years), max(years)
    while first - 1 >= min(sheets) and first - 1 not in sheets:
        first -= 1
    while last + 1 <= max(sheets) and last + 1 not in sheets:
        last += 1
    return (None if first <= min(sheets) else first), (None if last >= max(sheets) else last)


# Colour names that say nothing about the year: the frame material and plain finishes.
PLAIN_COLOURS = re.compile(r"^(?:carbon|raw|chrome|unpainted|black|zwart|gravel)$")  # Trek has a colour called Gravel
# Dutch colour words, so "frost zilver" in an ad finds Giant's "Frost Silver".
NL_COLOURS = {"zwart": "black", "wit": "white", "witte": "white", "grijs": "grey", "grijze": "grey", "zilver": "silver",
              "zilveren": "silver", "rood": "red", "rode": "red", "oranje": "orange", "geel": "yellow", "gele": "yellow",
              "goud": "gold", "gouden": "gold", "groen": "green", "groene": "green", "blauw": "blue", "blauwe": "blue",
              "paars": "purple", "paarse": "purple", "roze": "pink", "bruin": "brown", "bruine": "brown"}


def colour_years(sheets, low):
    """(colour name, {years}) for the longest colour name in the ad that only some years came in, or None.
    Only the years we know the colours of count: a sheet without them says nothing about a colour."""
    dated = {y: s for y, s in sheets.items() if s["colours"]}
    colours = {}
    for y, s in dated.items() if len(dated) > 1 else ():
        # Each part of a two-tone name on its own ("Blue Dragonfly/Chrome"): an ad names the colour, not the finish.
        for name in s["colours"]:
            first = True  # the colourway's lead colour: its first part that isn't "Carbon" or plain black
            for c in (part.strip() for part in name.split("/")):
                words = re.findall(r"[a-z]+", _plain(c))
                if words and not all(GENERIC_COLOUR.match(w) or PLAIN_COLOURS.match(w) for w in words):
                    entry = colours.setdefault(" ".join(words), (c, set(), set()))
                    entry[1].add(y)
                    if first:
                        entry[2].add(y)
                    first = False
    words = re.findall(r"[a-z]+", low)
    ad_text = " ".join(words) + " | " + " ".join(NL_COLOURS.get(w, w) for w in words)
    for key, (name, years, lead) in sorted(colours.items(), key=lambda kv: -len(kv[0])):  # the longest name first
        if len(years) < len(dated) and re.search(rf"\b{re.escape(key)}\b", ad_text):
            # "kleur charcoal" is a Charcoal bike: "Charcoal / Iris" (2019), not "Carbon Smoke / Neon Red / Charcoal"
            # (2018), where charcoal is only the trim. The years whose colourway leads with it, when only some do.
            return name, (lead if lead and lead != years else years)
    return None


def colour_family_years(sheets, text):
    """({years}, [colourway names]) of the model years that came in the plain colours the seller names
    ("zwart/rood", "kleur: blauw"), when only some years did; else None. The first colour said must be in
    the colourway, a second one at least close (grey for silver). Only years we know the colours of count."""
    dated = {y: s for y, s in sheets.items() if s["colours"]}
    title, _nl, description = (text or "").partition("\n")
    wanted = colour_match.ad_colours(title, description)[:2]
    if len(dated) < 2 or not wanted:
        return None
    fits = {}
    for y, s in dated.items():
        for name in s["colours"]:
            fams = colour_match.families_in(name, brand_words=True)
            if wanted[0] in fams and all(max((colour_match.similarity(w, f) for f in fams), default=0) >= 0.5
                                         for w in wanted[1:]):
                fits.setdefault(y, []).append(name)
    if not fits or len(fits) == len(dated):
        return None
    return set(fits), [n for y in sorted(fits) for n in fits[y] if n][:4]


PHOTO_COLOURS_FILE = os.path.join(os.path.dirname(__file__), "photo_colours.json")


def photo_colour(model, listing, _cache={}):
    """The colourway name someone read from the ad's photos for this model (webapp/photo_colours.json), or None."""
    if "data" not in _cache:
        try:
            with open(PHOTO_COLOURS_FILE, encoding="utf-8") as fh:
                _cache["data"] = json.load(fh)
        except (OSError, ValueError):
            _cache["data"] = {}
    from .fetch_ad import ad_key
    if not listing.get("title"):
        return None
    entry = _cache["data"].get(ad_key({"listing_url": listing.get("listing_url"), "title": listing["title"],
                                       "asking_price": listing.get("asking_price")}))
    return entry["colour"] if entry and entry.get("model") == model.get("slug") else None


def seen_colour_years(sheets, colour):
    """(colour, {years}) of the years whose colourways include exactly this name, or None: a colour read from
    the photos is a whole colourway, so "Matte Trek Black" isn't the matte black half of a two-tone."""
    want = " ".join(re.findall(r"[a-z]+", _plain(colour)))
    years = {y for y, s in sheets.items() for c in s["colours"] if " ".join(re.findall(r"[a-z]+", _plain(c))) == want}
    dated = [y for y, s in sheets.items() if s["colours"]]
    return (colour, years) if years and len(years) < len(dated) else None


def _sheet_speed(sheet):
    """How many sprockets a spec sheet's cassette, rear derailleur or shifters say: 11 for "11-28, 11 speed"."""
    for key, value in sheet["specs"].items():
        if re.search(r"cassette|tandwiel|achterderailleur|shifter|schakel", key, re.I):
            found = re.search(r"\b(1[0-3]|[7-9])\s*-?\s*(?:speed|sp|versnellingen)\b", str(value), re.I)
            if found:
                return int(found.group(1))
    return None


def sheet_clues(model, text, seen_colour=None):
    """Year windows from the spec sheets of each model year: the part numbers the ad names that only some
    years' sheets have, and a colour name the ad uses that only some years came in. [(first, last, Msg)]."""
    sheets = year_sheets(model)
    if len(sheets) < 2:
        return []
    low, clues = _plain(text), []
    codes = {y: set().union(*(_part_codes(v) for k, v in s["specs"].items() if k in YEAR_PARTS)) for y, s in sheets.items()}
    every = set.intersection(*codes.values())
    named = _part_codes(low) - every
    hits = {y: c & named for y, c in codes.items() if c & named}
    if hits:
        best = max(len(c) for c in hits.values())
        years = sorted(y for y, c in hits.items() if len(c) == best)
        parts = sorted(set().union(*(hits[y] for y in years)))
        # A sheet that gives no part number for those parts (just "Shimano 105 Di2") doesn't rule its year out.
        labels = {k for s in sheets.values() for k, v in s["specs"].items() if k in YEAR_PARTS and _part_codes(v) & named}
        known = {y for y, s in sheets.items() if any(_part_codes(v) for k, v in s["specs"].items() if k in labels)}
        first, last = _widen(years, known | set(years))
        if first or last:
            clues.append((first, last, Msg("Parts {parts} are on the {years} spec sheets.",
                                           parts=", ".join(p.upper() for p in parts), years=_span(years[0], years[-1]))))
    # "2x12", "12-speed", "12 versnellingen": the years whose sheets have that many sprockets.
    said = re.search(r"\b[12]\s*x\s*(1[0-3]|[7-9])\b|\b(1[0-3]|[7-9])\s*-?\s*(?:speed|sp|versnellingen|voudig)\b", low)
    if said:
        speeds = {y: _sheet_speed(s) for y, s in sheets.items()}
        known = {y for y, n in speeds.items() if n}
        years = sorted(y for y in known if speeds[y] == int(said.group(1) or said.group(2)))
        if years and len(years) < len(known):
            first, last = _widen(years, known)
            if first or last:
                clues.append((first, last, Msg("{n}-speed: the {years} spec sheets.", n=int(said.group(1) or said.group(2)),
                                               years=_span(years[0], years[-1]))))
    dated = {y: s for y, s in sheets.items() if s["colours"]}
    # The colour in the ad's photos goes before the colour the seller writes: sellers name it loosely.
    seen = seen_colour and seen_colour_years(sheets, seen_colour)
    hit = None if seen else colour_years(sheets, low)
    if seen:
        first, last = _widen(seen[1], dated)
        if first or last:
            clues.append((first, last, Msg("The photos show colour '{colour}', sold in {years}.", colour=seen_colour,
                                           years=_years_list(seen[1]))))
    elif hit:
        first, last = _widen(hit[1], dated)
        if first or last:
            clues.append((first, last, Msg("Colour '{colour}' was sold in {years}.", colour=hit[0],
                                           years=_span(min(hit[1]), max(hit[1])))))
    else:
        # No brand colour name in the ad: the plain colours the seller gives still rule out years without them.
        fit = colour_family_years(sheets, text)
        if fit:
            first, last = _widen(fit[0], dated)
            if first or last:
                clues.append((first, last, Msg("In the ad's colours it was sold in {years}: {colourways}.",
                                               years=_years_list(fit[0]), colourways=", ".join(dict.fromkeys(fit[1])))))
    return clues


def _years_list(years):
    """2019, 2021–2023: the years, with runs of following years as a span."""
    years, runs = sorted(years), []
    for y in years:
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    return ", ".join(str(a) if a == b else f"{a}\u2013{b}" for a, b in runs)


def middle_year(years):
    """The year in the middle of the ones that fit, the earlier of the two middle ones for an even count: an ad
    without a year is as likely from the start of the run as from the end."""
    years = sorted(years)
    return years[(len(years) - 1) // 2] if years else None


def resolve_year(model, claims, age, estimate, today=None, photo=None):
    """The one model year the report goes by, for the price and the spec comparison alike:
    {"year", "how", "reliable", "first", "last"}, how being

    - "ad": the year in the ad, which nothing disproves;
    - "older": the year in the ad, for a bike older than any generation we know;
    - "purchase": the ad's purchase year, as the model year that fits it: that year, or the generation's first
      (bought just before launch), or the newest year the ad's details allow (bought later, second-hand);
    - "details": the ad's year doesn't fit its details, so the middle of the years they allow;
    - "photo": no year in the ad, the year of the catalogue photo in the ad's colour (year_photo: year, image, colour);
    - "estimate": no year in the ad, the middle of the years its details allow within the generation's years;
    - "generation": no year and no year clues, the middle of the years the generation was sold;
    - "catalogue": nothing tells us, the year of our catalogue scrape.

    reliable is False when the bike is probably another generation than the model we matched, whose new price
    and specs we don't have: the ad's year, or its details, fall outside the generation."""
    today = today or date.today()
    known = sold_years(model, today)
    gen_first, gen_last = (known[0], known[1] or newest_year(model, today)) if known else (None, None)
    est = estimate or {}
    e_first, e_last = (est.get("first"), est.get("last")) if est.get("status") != WARN and not est.get("fallback") else (None, None)

    def window(lo, hi):
        """(first, last, inside): the years from lo to hi (None = open) within the generation's years. When they miss
        it: the details' own years if they have both ends (the bike is probably another generation, so inside is
        False), else the generation's."""
        first = max([y for y in (lo, gen_first) if y] or [None], key=lambda y: y or 0)
        last = min([y for y in (hi, gen_last) if y] or [None], key=lambda y: y or 9999)
        if first and last and first > last:
            return (lo, hi, False) if lo and hi else (gen_first, gen_last, True)
        return first, last, True

    def middle(first, last):
        if first and last:
            return middle_year(range(first, last + 1))
        return first or last

    claimed = claims["year"]
    other = bool(age.get("earlier") or age.get("older"))
    # A generation we know of comes with another new price; one older than any we know we can't disprove, so we
    # go by the year in the ad (check_age's "probably older").
    if claimed and est.get("status") == BAD and (e_first or e_last):
        first, last, inside = window(e_first, e_last)
        return {"year": middle(first, last), "how": "details", "reliable": inside, "first": first, "last": last}
    if claimed and not other and (claims.get("year_is_purchase") or age.get("purchase")):
        first, last, _inside = window(e_first, e_last)
        year = min(max(claimed, first or claimed), last or claimed)
        return {"year": year, "how": "purchase" if year != claimed else "ad", "reliable": True, "first": first, "last": last}
    if claimed:
        # An earlier generation we have a sheet of is this model's predecessor; one we only know the launch years of
        # may be another model altogether.
        return {"year": claimed, "how": "older" if age.get("older") else "ad",
                "reliable": not age.get("earlier") or bool(age.get("earlier_sheet")),
                "first": claimed, "last": claimed}
    first, last, inside = window(e_first, e_last)
    if photo and photo[2] and (not first or photo[0] >= first) and (not last or photo[0] <= last):
        # The colour in the ad dates it more closely than the window.
        return {"year": photo[0], "how": "photo", "reliable": inside, "first": photo[0], "last": photo[0]}
    if e_first or e_last:
        return {"year": middle(first, last), "how": "estimate", "reliable": inside, "first": first, "last": last}
    if gen_first:
        return {"year": middle(gen_first, gen_last), "how": "generation", "reliable": True, "first": gen_first,
                "last": gen_last}
    year = scrape_year(model) or today.year
    return {"year": year, "how": "catalogue", "reliable": True, "first": year, "last": year}


def comparison_year(model, claims, estimate):
    """The model year whose spec sheet the ad is compared with: the stated year when the year estimate allows it
    and we have its sheet, else the sheet year the estimate allows closest to the stated year. Without a stated
    year: None (our own scrape) when the estimate allows its year, else the newest sheet year it allows. None
    too when no sheet year fits."""
    sheets = year_sheets(model)
    claimed = claims["year"]
    first, last = (estimate or {}).get("first"), (estimate or {}).get("last")
    allowed = [y for y in sheets if (first is None or y >= first) and (last is None or y <= last)]
    if not first and not last and (estimate or {}).get("status") == WARN:
        allowed = list(sheets)  # the details disagree: they don't rule out any year
    if claimed in allowed:
        return claimed
    own = scrape_year(model)
    if not allowed or not claimed and own and (first is None or own >= first) and (last is None or own <= last):
        return None  # our own scrape fits
    return min(allowed, key=lambda y: (abs(y - claimed), -y)) if claimed else middle_year(allowed)


def year_model(model, year):
    """The model as its spec sheet of that year describes it, for the spec comparison; the model itself for None."""
    sheet = year_sheets(model).get(year) if year else None
    if not sheet:
        return model
    return dict(model, specs=sheet["specs"], spec_year=year)


def year_photo(model, claims, estimate, text, seen_colour=None):
    """(year, image, colour or None) of the model-year photo that fits the ad best, or None to keep the
    current one: the year of the colour the ad names, else the year the spec comparison uses
    (comparison_year), else the stated year unless the details rule it out, else the newest year they allow."""
    photos = {int(y): e["image"] for y, e in ((model.get("year_specs") or {}).get("years") or {}).items()
              if e.get("image")}
    if not photos:
        return None
    claimed = claims["year"]
    first, last = (estimate or {}).get("first"), (estimate or {}).get("last")

    def allowed(years):
        """The years the other clues (groupset, speeds, generation) leave, of these; all of them when none are left."""
        return [y for y in years if (first is None or y >= first) and (last is None or y <= last)] or list(years)

    hit = (seen_colour and seen_colour_years(year_sheets(model), seen_colour)) or colour_years(year_sheets(model), _plain(text))
    if hit:
        year = claimed if claimed in hit[1] else middle_year(allowed(hit[1]))
        # That colour's own photo of that year, when we have one: the colourway with that name, or with that part,
        # the one whose other part the ad also names first ("Navy Carbon Smoke / Viper Red", not ".../Blue").
        own = ((model.get("year_specs") or {}).get("years") or {}).get(str(year), {}).get("colour_images") or {}
        key = " ".join(re.findall(r"[a-z]+", _plain(hit[0])))
        ad_words = set(re.findall(r"[a-z]+", _plain(text)))
        ad_words |= {NL_COLOURS.get(w, w) for w in ad_words}

        def named(name):
            parts = [" ".join(re.findall(r"[a-z]+", _plain(p))) for p in name.split("/")]
            return key == " ".join(re.findall(r"[a-z]+", _plain(name))) or key in parts

        def also_said(name):
            return sum(1 for w in re.findall(r"[a-z]+", _plain(name)) if w in ad_words)

        for name in sorted((n for n in own if named(n)), key=also_said, reverse=True)[:1]:
            return year, own[name], name
        # A year that came in more colours has one photo, maybe of another colour: then don't name it.
        one = len(year_sheets(model).get(year, {}).get("colours") or []) == 1
        return (year, photos[year], hit[0] if one else None) if year in photos else None
    fit = colour_family_years(year_sheets(model), text)
    if fit:
        # The newest year in the seller's colours with a photo, unless the stated year is one of them.
        shown = sorted(y for y in fit[0] if y in photos)
        if shown:
            year = claimed if claimed in shown else middle_year(allowed(shown))
            # The photo of the colourway in the seller's colours, when that year has one.
            own = ((model.get("year_specs") or {}).get("years") or {}).get(str(year), {}).get("colour_images") or {}
            name = next((n for n in fit[1] if n in own), None)
            if name:
                return year, own[name], name
            colours = year_sheets(model)[year]["colours"]
            return year, photos[year], colours[0] if len(colours) == 1 else None
    year = comparison_year(model, claims, estimate)
    if year is None:
        year = claimed if claimed and estimate.get("status") != BAD else estimate.get("last")
    return (year, photos[year], None) if year in photos else None


# The year clues that come from parts a bike can be given later (estimate_year), by the start of their message.
PART_CLUES = ("{part}: bikes from", "Parts {parts}", "{n}-speed")


def ringed_years(years, estimate, claimed=None):
    """The years on the age timeline marked "estimated": the estimate's years, kept close to the year in the ad.

    With a year in the ad, only the estimated years right next to it (one before, one after, and the year itself)
    are marked, not every year the estimate leaves open. When none of those are estimated, the estimate rules
    the ad's year out and it makes sense to show where it points: its year closest to the ad's and the one next
    to that. Without a year in the ad, all of it."""
    if not estimate:
        return set()
    first, last = estimate.get("first"), estimate.get("last")
    inside = [y for y in years if (not first or y >= first) and (not last or y <= last)]
    if not claimed or not inside:
        return set(inside)
    near = {y for y in inside if abs(y - claimed) <= 1}
    if near:
        return near
    closest = min(inside, key=lambda y: (abs(y - claimed), y))
    return {y for y in inside if abs(y - closest) <= 1}


def estimate_year(model, models, claims, text, seen_colour=None):
    """The model years the ad's own details allow, and whether the claimed year fits them.

    Each clue gives a window (first, last; None = open): the groupset generation, a frame generation the
    seller names, rim brakes, and a named colourway we have a dated photo of. The estimate is where they
    overlap. Photos aren't read: without a vision model their colours are mostly the background.
    """
    low = _plain(text)
    clues = []
    for pattern, first, last, name in GROUPSET_YEARS:
        if re.search(pattern, low):
            clues.append((first, last, Msg("{part}: bikes from {years}.", part=name, years=_span(first, last))))
            break
    gen = re.search(r"\bgen(?:eratie|eration)?\s*(\d)\b", low)
    line = next((gens for brand, pattern, gens in LINEAGES
                 if brand == model["brand"] and re.search(pattern, _plain(model["name"]))), None)
    years = gen and (next(((g[0], g[1]) for g in line or [] if g[2] == f"gen {gen.group(1)}"), None) if line else
                     GENERATIONS.get((model["brand"], family_of(model["name"]), int(gen.group(1)))))
    if years:
        clues.append((years[0], years[1], Msg("{family} gen {gen}: sold from {years}.", family=model["name"].split()[0],
                                              gen=gen.group(1), years=_span(*years))))
    if claims["brakes"] == "Rim" and (claims["material"] == "Carbon" or ref_material(model) == "Carbon"):
        clues.append((None, RIM_BRAKE_LAST_YEAR, Msg("Rim brakes on a carbon road bike: {year} or older.",
                                                     year=RIM_BRAKE_LAST_YEAR)))
    sheet = sheet_clues(model, text, seen_colour)
    clues += sheet
    for name, year in [] if any(c[2].text.startswith(("Colour", "The photos")) for c in sheet) else _named_colourways(model, models):
        if re.search(rf"\b{re.escape(_plain(name))}\b", low):
            clues.append((year - 1, year + 1, Msg("Colour '{colour}' is in {brand}'s {year} photos.",
                                                  colour=name, brand=model["brand"], year=year)))
            break
    # Nothing in the ad: fall back on the years we know the matched model was sold. That only dates the
    # model we matched, which may be a newer generation than the bike, so it never overrules a stated year.
    fallback = not clues
    if fallback:
        known = model_years(model)
        if not known:
            return {"status": UNKNOWN, "first": None, "last": None, "evidence": [], "headline": Msg("Can't tell"),
                    "detail": Msg("Nothing in the ad or in our catalogue dates this bike yet.")}
        clues += [(known[0], known[1], Msg("{name} was sold from {years}.", name=model["name"],
                                           years=_span(known[0], known[1]))), (None, None, known[2])]
    # Paint can't be swapped like a cassette: a clue that leaves out every year of the colour in the photos
    # is kept as a note, not used.
    seen = next((c for c in sheet if c[2].text.startswith("The photos")), None)
    notes = []
    if seen:
        years = seen_colour_years(year_sheets(model), seen_colour)[1]
        for c in [c for c in clues if c is not seen]:
            if not any((c[0] or 0) <= y <= (c[1] or 9999) for y in years):
                clues.remove(c)
                notes.append(join(c[2], Msg("That part may have been swapped: the frame's colour goes first.")))
    # Parts can be swapped, the frame can't: when the stated year only clashes with parts (a groupset, the
    # number of speeds, part numbers), go by the year in the ad and take those parts as upgrades.
    claimed = claims["year"]

    def fits(c):
        return (c[0] or 0) <= claimed <= (c[1] or 9999)

    swappable = [c for c in clues if c[2].text.startswith(PART_CLUES)]
    if claimed and any(not fits(c) for c in swappable) and all(fits(c) for c in clues if c not in swappable):
        for c in [c for c in swappable if not fits(c)]:
            clues.remove(c)
            notes.append(join(c[2], Msg("We go by the year in the ad: that part was probably upgraded.")))
    first = max([c[0] for c in clues if c[0]] or [None], key=lambda y: y or 0)
    last = min([c[1] for c in clues if c[1]] or [None], key=lambda y: y or 9999)
    evidence = [c[2] for c in clues] + notes
    if first and last and first > last:
        return {"status": WARN, "first": None, "last": None, "evidence": evidence,
                "headline": Msg("Details disagree"),
                "detail": Msg("The parts and colour point to different years; some parts may have been swapped.")}
    claimed = claims["year"]
    span = _span(first, last)
    inside = claimed and (first is None or claimed >= first) and (last is None or claimed <= last)
    if fallback and claimed and not inside:
        return {"status": UNKNOWN, "first": first, "last": last, "evidence": evidence, "fallback": True,
                "headline": Msg("Can't check {claimed}", claimed=claimed),
                "detail": Msg("The ad has no year clues, and we only know {name} from {years}: "
                              "it may be an older generation.", name=model["name"], years=span)}
    if claimed is None:
        status, headline = UNKNOWN, Msg("Probably {years}", years=span)
        detail = (Msg("The ad gives no year and no year clues; we know {name} from {years}.", name=model["name"],
                      years=span) if fallback else
                  Msg("The ad doesn't give a year, but its details point to {years}.", years=span))
    elif inside:
        # No window left when the only clues were parts the stated year overrules (estimate's swappable clues).
        status, headline = OK, Msg("Fits {years}", years=span) if first or last else Msg("{claimed} fits", claimed=claimed)
        detail = (Msg("{claimed} fits the years we know {name} from.", claimed=claimed, name=model["name"])
                  if fallback else Msg("{claimed} fits the ad's details.", claimed=claimed))
    elif claims["year_is_purchase"] and last and claimed > last:
        # Bought later than the details allow is normal for a second-hand bike, not a wrong year.
        status, headline = OK, Msg("Probably {years}", years=span)
        detail = Msg("{claimed} is when it was bought; the ad's details point to model year {years}.",
                     claimed=claimed, years=span)
    elif (first and claimed == first - 1) or (last and claimed == last + 1):
        status, headline = WARN, Msg("Just outside {years}", years=span)
        detail = Msg("{claimed} is one year off what the details allow: maybe the purchase year.", claimed=claimed)
    else:
        status, headline = BAD, Msg("Doesn't fit {years}", years=span)
        detail = Msg("The seller says {claimed}, but the ad's details point to {years}.", claimed=claimed, years=span)
    if claims["mentions_upgrades"]:
        evidence.append(Msg("The ad mentions upgrades, so a part may be newer than the bike."))
    return {"status": status, "first": first, "last": last, "headline": headline, "detail": detail,
            "evidence": evidence, "fallback": fallback}


STATUS_RANK = {BAD: 3, WARN: 2, OK: 1, UNKNOWN: 0}


def age_summary(age, estimate, resolved=None):
    """The age tab's verdict, in line with its section: the age check and the year estimate together.
    The worse of the two leads; when one can't tell, the other speaks."""
    # The tab's OK / watch out / not OK pill gives the verdict, so a check that adds up shows its year.
    adds_up = Msg("Model year {year}", year=age["year"]) if age["status"] == OK and age.get("year") else None
    if adds_up and resolved and resolved["how"] == "purchase":
        adds_up = Msg("Model year {year}, bought in {claimed}", year=resolved["year"], claimed=age["year"])
    if not age.get("year") and resolved:
        # No year in the ad: the tab gives the year we go by (resolve_year), not "Year not stated".
        return {"status": WARN, "headline": Msg("Probably {years}", years=resolved["year"]),
                "detail": join(year_note(resolved, {"year": None}) or (estimate or {}).get("detail"),
                               Msg("Ask for the invoice or the serial number."))}
    if not estimate or estimate["status"] == UNKNOWN and age["status"] != UNKNOWN or age.get("older"):
        # A bike older than any generation we know: say so, even when the parts fit the year.
        return {"status": age["status"], "headline": adds_up or age["headline"], "detail": age["detail"],
                "tab_headline": Msg("Older than we know") if age.get("older") and not adds_up else None}
    if age["status"] == UNKNOWN or STATUS_RANK[estimate["status"]] > STATUS_RANK[age["status"]]:
        # The tab sits under AGE, so it leaves out "Year estimate:" to keep to one line.
        return {"status": estimate["status"], "headline": Msg("Year estimate: {verdict}", verdict=estimate["headline"]),
                "tab_headline": estimate["headline"], "detail": estimate["detail"]}
    if adds_up:
        # Both agree: the year leads ("Fits 2024 or earlier" next to a green pill reads like a warning).
        return {"status": age["status"], "headline": adds_up, "detail": join(age["detail"], estimate["detail"])}
    return {"status": age["status"], "headline": Msg("{age} · {estimate}", age=age["headline"], estimate=estimate["headline"]),
            "detail": age["detail"]}


def _span(first, last):
    if first and last:
        return str(first) if first == last else f"{first}\u2013{last}"
    if first:
        return Msg("{year} or later", year=first)
    return Msg("{year} or earlier", year=last)


def _row(key, part, original, listing, status, result, step=0, ad_tier=None):
    return {"key": key, "part": Msg(part), "original": original, "listing": listing, "status": status,
            "result": Msg(result) if isinstance(result, str) else result, "step": step,
            "ref_tier": None, "ad_tier": ad_tier}


# The spec sheet labels a comparison row's original part is rated from, first found wins.
ROW_SPECS = {"frame": ("Frame", "Frameset", "Material"), "brakes": ("Rem",), "wheels": ("Wiel voor", "Velg", "Wheelset"),
             "tyres": ("Buitenband", "Voorband"), "crankset": ("Crankstel",), "saddle": ("Zadel",)}


def _ref_tier(model, key):
    """The tier of the matched model's original part for a comparison row, or None."""
    for label in ROW_SPECS.get(key, ()):
        value = spec(model, label)
        if value and label in SPEC_PARTS:
            text = f"{value} {model['name']}" if SPEC_PARTS[label] == ("frame",) else str(value)
            return part_tier(SPEC_PARTS[label], text)
    return None


def _compare_tiers(key, part, original, listing, ref_tier, ad_tier):
    """A row saying whether the ad's part is an upgrade or a downgrade of the original."""
    step = ad_tier - ref_tier
    if step > 0:
        return _row(key, part, original, listing, OK, Msg("Upgrade, tier {a} to {b}", a=ref_tier, b=ad_tier), step,
                    ad_tier)
    if step < 0:
        return _row(key, part, original, listing, BAD, Msg("Downgrade, tier {a} to {b}", a=ref_tier, b=ad_tier), step,
                    ad_tier)
    return _row(key, part, original, listing, WARN, "Same tier, different part", ad_tier=ad_tier)


def photo_group(read):
    """The groupset a read of the ad's photos shows (webapp/photo_groupset.py), as detect_groupset gives it, or
    None when the read isn't sure enough or names no series we know."""
    from . import photo_groupset
    if not photo_groupset.usable(read):
        return None
    found = detect_groupset(photo_groupset.text_of(read))
    if found:
        extra = ELECTRONIC_NAME.get(found["name"].split()[0]) if found["electronic"] else None
        found["label"] = Msg("{label} (inferred from photo analysis)", label=f"{found['name']} {extra}" if extra else found["name"])
    return found


def check_specs(model, claims, impossible=None, photo_read=None, bike_year=None, no_sheet=False, today=None):
    """The ad's parts against the model's spec sheet. `bike_year` is the model year the report goes by: the ad's
    groupset drops a tier or two for its age (groupset_age_drop), as the original's does for its sheet's year;
    up- and downgrades still compare the tiers when new. With `no_sheet` the bike is older than any generation we
    know (resolve_year's "older"): we have no spec sheet of its year, so its parts aren't compared with another
    generation's sheet."""
    rows = []
    not_stated = Msg("Not stated")
    if no_sheet:
        # Nothing of a later generation stands in for the original, not even the frame its name implies.
        model, impossible = dict(model, specs={}, spec_year=None), None

    ref_group = detect_groupset(groupset_text(model))
    ref_group_label = spec(model, "Shifter") or (ref_group and ref_group["label"]) or Msg("Not in our data")
    # The ad's words first; when they don't name it, what its photos show.
    seen = None if claims["groupset"] else photo_group(photo_read)
    claimed = claims["groupset"] or seen
    if not ref_group or not claimed:
        rows.append(_row("groupset", "Groupset", ref_group_label, claimed["label"] if claimed else not_stated,
                         WARN if ref_group else UNKNOWN, "Ask seller" if ref_group else "Can't compare"))
    elif claimed["key"] != ref_group["key"] or claimed["tier"] != ref_group["tier"]:
        rows.append(_compare_tiers("groupset", "Groupset", ref_group_label, claimed["label"], ref_group["tier"],
                                   claimed["tier"]))
    elif claimed["electronic"] != ref_group["electronic"] and claimed["electronic"]:
        rows.append(_row("groupset", "Groupset", ref_group_label, claimed["label"], WARN,
                         "Electronic in ad, mechanical original"))
    else:
        rows.append(_row("groupset", "Groupset", ref_group_label, claimed["label"], OK, "Matches"))

    for key, part, ref_val, ad_val in (
        ("frame", "Frame", None if no_sheet else ref_material(model) or (impossible and impossible["made_in"][0]),
         claims["material"]),
        ("brakes", "Brakes", ref_brakes(model), claims["brakes"]),
    ):
        shown = spec(model, "Frame", "Material") if key == "frame" else spec(model, "Rem")
        ad_shown = Msg(ad_val) if ad_val else not_stated
        if not ref_val:
            rows.append(_row(key, part, shown or Msg("Not in our data"), ad_shown, UNKNOWN, "Can't compare"))
        elif not ad_val:
            rows.append(_row(key, part, shown or Msg(ref_val), not_stated, WARN, "Ask seller"))
        elif ad_val == ref_val:
            rows.append(_row(key, part, shown or Msg(ref_val), ad_shown, OK, "Matches"))
        elif key == "frame" and impossible:
            rows.append(_row(key, part, shown or Msg(ref_val), ad_shown, BAD,
                             f"Never made in {MATERIAL_LOWER[ad_val]}"))
        else:
            rows.append(_row(key, part, shown or Msg(ref_val), ad_shown, BAD, "Differs"))

    for key, part, keys in (("wheels", "Wheels", ("Wiel voor", "Velg", "Wheelset")),
                              ("tyres", "Tyres", ("Buitenband", "Voorband")), ("crankset", "Crankset", ("Crankstel",))):
        ref_val, ad = spec(model, *keys), claims.get(key)
        ref_tier = part_tier(PART_TABLES.get(key, (key,)), ref_val) if ref_val else None
        if ad and ref_tier:
            if ad["tier"] == ref_tier:  # often the same wheels or tyres, named differently
                rows.append(_row(key, part, ref_val, ad["label"], OK, "Same tier", ad_tier=ad["tier"]))
            else:
                rows.append(_compare_tiers(key, part, ref_val, ad["label"], ref_tier, ad["tier"]))
        elif ad:
            rows.append(_row(key, part, ref_val or Msg("Not in our data"), ad["label"], UNKNOWN, "Can't compare"))
        elif ref_val:
            rows.append(_row(key, part, ref_val, None, UNKNOWN, "Compare photos"))
    for key, part, keys in (("saddle", "Saddle", ("Zadel",)),):
        ref_val = spec(model, *keys)
        if ref_val:
            rows.append(_row(key, part, ref_val, None, UNKNOWN, "Compare photos"))

    for row in rows:
        row["ref_tier"] = ref_group["tier"] if row["key"] == "groupset" and ref_group else _ref_tier(model, row["key"])
    if claimed:
        rows[0]["ad_tier"] = claimed["tier"]
    rows[0]["from_photos"] = bool(seen)
    # An older groupset rates lower, the ad's by the bike's year and the original's by its sheet's year.
    for side, year in (("ad", bike_year), ("ref", None if no_sheet else model.get("spec_year") or sheet_year(model))):
        rows[0][f"{side}_aged"] = None
        tier, drop = rows[0][f"{side}_tier"], groupset_age_drop(year, today)
        if tier and drop and tier > 1:
            rows[0][f"{side}_aged"] = {"new": tier, "age": (today or date.today()).year - int(year)}
            rows[0][f"{side}_tier"] = max(1, tier - drop)

    down = sum(1 for r in rows if r["step"] < 0)
    up = sum(1 for r in rows if r["step"] > 0)
    differ = sum(1 for r in rows if r["status"] == BAD and not r["step"])
    warn = sum(1 for r in rows if r["status"] == WARN)
    counts = [Msg("{n} part differs" if differ == 1 else "{n} parts differ", n=differ) if differ else None,
              Msg("{n} part downgraded" if down == 1 else "{n} parts downgraded", n=down) if down else None,
              Msg("{n} part upgraded" if up == 1 else "{n} parts upgraded", n=up) if up else None]
    if differ or down:
        status, headline = BAD, join_list(counts)
    elif up:
        status, headline = OK, join_list(counts)
    elif warn:
        status, headline = WARN, Msg("Not enough detail")
    else:
        status, headline = OK, Msg("Matches the original")
    detail = join(claims["mentions_upgrades"] and Msg("The seller mentions changed parts."),
                  seen and Msg("The ad doesn't name the groupset; we read it from the photos.") or None,
                  Msg("Compared with the {brand} spec sheet of the {year} model.", brand=model["brand"],
                      year=model["spec_year"]) if model.get("spec_year") else
                  Msg("Compared with the {brand} spec sheet from {date}.", brand=model["brand"],
                      date=model.get("seen_on") or Msg("our catalogue")))
    # The report tab's pill says whether it matches; the tab's headline says what was compared.
    # The tab keeps to one line: with more than one count, the counts without "part(s)".
    short = [Msg("{n} differs" if differ == 1 else "{n} differ", n=differ) if differ else None,
             Msg("{n} lower", n=down) if down else None, Msg("{n} better", n=up) if up else None]
    tab = (Msg("Original parts") if status == OK and not up else
           join_list(short) if sum(map(bool, short)) > 1 else headline)
    if no_sheet:
        status, headline, tab = UNKNOWN, Msg("No spec sheet for {year}", year=bike_year), Msg("No spec sheet")
        detail = join(Msg("The oldest {name} we know is a later generation, and we don't have the spec sheet of the "
                          "{year} bike, so we can't compare its parts with the original.", name=model["name"],
                          year=bike_year),
                      claims["mentions_upgrades"] and Msg("The seller mentions changed parts."))
    return {"status": status, "headline": headline, "tab_headline": tab, "detail": detail, "rows": rows,
            "photo_groupset": photo_read if seen else None}


def size_options(brand):
    return SIZE_CHARTS.get(brand, GENERIC_SIZE_CHART)


MODEL_CHARTS_FILE = os.path.join(os.path.dirname(__file__), "size_charts.json")
_model_charts = {}


def model_charts():
    """Each model's own size chart by slug, as brand_scrapers/sizing.py collected them."""
    try:
        mtime = os.path.getmtime(MODEL_CHARTS_FILE)
    except OSError:
        return {}
    if _model_charts.get("mtime") != mtime:
        try:
            with open(MODEL_CHARTS_FILE, encoding="utf-8") as fh:
                charts = json.load(fh).get("models") or {}
        except (OSError, ValueError):
            charts = {}
        _model_charts.update(mtime=mtime, charts=charts)
    return _model_charts["charts"]


SIZE_SOURCE_NOTES = {
    "brand": "{brand}'s own size chart for this model.",
    "geometry": "This model's own sizes and geometry; {brand} publishes rider heights only in its general size guide.",
    "generic": SIZE_NOTE,
}


LETTER_SIZES = ["3XS", "2XS", "XS", "S", "SM", "M", "ML", "L", "XL", "2XL", "3XL"]


def _size_order(label):
    if label.isdigit():
        return 0, int(label)
    return 1, LETTER_SIZES.index(label) if label in LETTER_SIZES else len(LETTER_SIZES)


def size_systems(labels):
    """Split size labels into frame sizes in cm and letter sizes: [(heading, labels)], empty groups left out."""
    labels = list(labels)
    groups = [("Frame size (cm)", [k for k in labels if k.isdigit()]),
              ("Letter sizes", [k for k in labels if not k.isdigit()])]
    return [g for g in groups if g[1]]


def model_size_chart(model):
    """The model's own chart when we have it, else the brand chart.

    {"sizes": {label: (low, high)}, "geometry": {label: (stack, reach)}, "source": brand|geometry|generic, "url"}
    """
    own = model_charts().get(model.get("slug") or "")
    brand_chart = size_options(model["brand"])
    if own and own["source"] == "geometry":
        # Only geometry published: the model's own sizes, with the rider heights of the brand's size guide.
        sizes = {k: brand_chart[k] for k in own["sizes"] if k in brand_chart}
    else:
        sizes = {k: (v["low"], v["high"]) for k, v in (own or {}).get("sizes", {}).items() if v.get("low")}
    sizes = dict(sorted(sizes.items(), key=lambda kv: _size_order(kv[0])))
    if not sizes:
        return {"sizes": brand_chart, "geometry": {}, "source": "generic", "url": None}
    return {"sizes": sizes, "source": own["source"], "url": own.get("url"),
            "geometry": {k: (v["stack"], v["reach"]) for k, v in own["sizes"].items()
                         if v.get("stack") and v.get("reach")}}


def size_note(chart, brand):
    return Msg(SIZE_SOURCE_NOTES[chart["source"]], brand=brand)


def _line_label(names):
    """The words all names share, in order: 'Domane SL 5 Gen 4' + 'Domane SL 6 Gen 4' -> 'Domane SL Gen 4'."""
    words = [n.replace(" - ", " ").split() for n in names]
    common = [w for w in words[0] if all(w.lower() in map(str.lower, other) for other in words[1:])]
    return " ".join(common) or names[0]


def size_lines(models, brand):
    """A brand's models grouped by family and size chart, for the size finder's model picker.

    Builds that share a frame share a chart, so 'Madone SLR 7' and 'Madone SLR 9' become one line.
    Models without their own chart are grouped per family on the brand chart.
    """
    groups = {}
    for m in models:
        if m["brand"] != brand:
            continue
        chart = model_size_chart(m)
        own = {k: chart["sizes"][k] + chart["geometry"].get(k, ()) for k in chart["sizes"]}
        key = (family_of(m["name"]), json.dumps(own, sort_keys=True) if chart["source"] != "generic" else "")
        groups.setdefault(key, {"family": key[0], "chart": chart, "models": []})["models"].append(m)
    lines = []
    for group in groups.values():
        names = sorted(m["name"] for m in group["models"])
        group["models"].sort(key=lambda m: m["name"])
        group["key"] = group["models"][0]["slug"]
        group["label"] = _line_label(names) if len(names) > 1 else names[0]
        lines.append(group)
    seen, per_family = {}, {}
    for line in lines:
        seen[line["label"]] = seen.get(line["label"], 0) + 1
        per_family[line["family"]] = per_family.get(line["family"], 0) + 1
    for line in lines:
        sizes = list(line["chart"]["sizes"])
        bare = " " not in line["label"] and per_family[line["family"]] > 1  # just 'Madone' next to other Madones
        if (seen[line["label"]] > 1 or bare) and line["chart"]["source"] != "generic":
            line["label"] += f" ({sizes[0]}–{sizes[-1]})" if len(sizes) > 1 else f" ({sizes[0]})"
    return sorted(lines, key=lambda l: (l["family"], l["chart"]["source"] == "generic", l["label"]))


def _cm_between(chart, cm):
    """Rider heights for frame size cm, drawn between the chart's own cm sizes either side of it, or None."""
    numeric = sorted((int(k), v) for k, v in chart.items() if k.isdigit())
    below = [(k, v) for k, v in numeric if k <= cm]
    above = [(k, v) for k, v in numeric if k >= cm]
    if not below or not above:
        return None
    (k0, (lo0, hi0)), (k1, (lo1, hi1)) = below[-1], above[0]
    share = (cm - k0) / (k1 - k0) if k1 != k0 else 0
    return round(lo0 + (lo1 - lo0) * share), round(hi0 + (hi1 - hi0) * share)


def estimate_size(chart, size):
    """((low, high), how) rider heights for a frame size in cm the chart doesn't list, or None.

    "between": drawn between the chart's own cm sizes either side of it; "general": from the general chart
    (its own row, or between its rows: it has 56 and 58, not 57), for a chart without cm sizes around it, such
    as Canyon's and Giant's letter sizes. Letter sizes aren't guessed."""
    if not size.isdigit():
        return None
    own = _cm_between(chart, int(size))
    if own:
        return own, "between"
    general = _cm_between(GENERIC_SIZE_CHART, int(size))
    return (general, "general") if general else None


def check_size(model, claims, rider_height=None):
    own = model_size_chart(model)
    size = claims["size"]
    if size and size not in own["sizes"] and own["source"] != "generic":
        own = {"sizes": size_options(model["brand"]), "geometry": {}, "source": "generic", "url": None}
    chart = own["sizes"]
    notes = [size_note(own, model["brand"])]
    rows = [{"size": k, "low": lo, "high": hi, "selected": k == size}
            for k, (lo, hi) in chart.items() if k.isdigit() == bool(size and size.isdigit())] if size else []
    if not size:
        return {"status": WARN, "headline": Msg("Size not stated"), "detail": Msg("Ask the seller for the frame size."),
                "rows": [], "fit": None, "notes": notes}
    estimated = None if size in chart else estimate_size(chart, size)
    if estimated:
        # A cm size the chart skips (Cube and Orbea go 50, 53; Canyon and Giant size by letter): a rider-height
        # estimate still beats none, flagged as such.
        (lo, hi), how = estimated
        chart = {**chart, size: (lo, hi)}
        notes.append(Msg("{brand}'s chart has no size {size}; these heights are estimated from its neighbouring sizes."
                         if how == "between" else
                         "{brand}'s chart has no size {size}; these heights come from a general road bike chart.",
                         brand=model["brand"], size=size))
        rows = sorted(rows + [{"size": size, "low": lo, "high": hi, "selected": True, "estimated": True}],
                      key=lambda r: _size_order(r["size"]))
    if size not in chart:
        return {"status": UNKNOWN, "headline": Msg("Size {size}", size=size),
                "detail": Msg("{brand} doesn't use size {size} in our chart. Ask the seller to check the frame sticker.",
                              brand=model["brand"], size=size),
                "rows": rows, "fit": None, "notes": notes}
    lo, hi = chart[size]
    fit = None
    if rider_height:
        if lo <= rider_height <= hi:
            fit = {"status": OK, "text": Msg("Good fit")}
        elif lo - 4 <= rider_height <= hi + 4:
            fit = {"status": WARN, "text": Msg("Borderline, test ride it")}
        else:
            fit = {"status": BAD, "text": Msg("Wrong size for you")}
    return {"status": fit["status"] if fit else OK, "headline": Msg("Size {size}", size=size),
            "detail": Msg("Fits riders of about {lo} to {hi} cm.", lo=lo, hi=hi), "rows": rows, "fit": fit,
            "fits": (lo, hi), "notes": notes}


CONDITION_FACTOR = {"like-new": 1.05, None: 1.0, "used": 0.92, "damaged": 0.6}
CONDITION_LABEL = {"like-new": "like new", "used": "used", "damaged": "damaged"}
# A bike this many years old isn't like new, whatever the ad says: rubber, bearings and the frame have aged.
LIKE_NEW_MAX_AGE = 10


def year_note(resolved, claims):
    """Which year the report goes by and why, or None when it's simply the year in the ad."""
    year, how = resolved["year"], resolved["how"]
    span = _span(resolved["first"], resolved["last"])
    if how == "purchase":
        return Msg("The ad gives {claimed} as the purchase year; we go by model year {year}.", claimed=claims["year"], year=year)
    if how == "details":
        return Msg("The stated {claimed} doesn't fit the ad's details ({years}), so we go by {year}.",
                   claimed=claims["year"], years=span, year=year)
    if how == "photo":
        return Msg("The ad gives no year; its colour is in the {year} photos, so we go by {year}.", year=year)
    if how == "estimate":
        return Msg("The ad gives no year; its details point to {years}, so we go by {year}, the middle.", years=span, year=year)
    if how == "generation":
        return Msg("The ad gives no year; this generation was sold {years}, so we go by {year}, the middle.",
                   years=span, year=year)
    if how == "older":
        return Msg("Probably older than any generation we know, so its new price may have been different; we go by "
                   "{year}, the year in the ad.", year=year)
    if how == "catalogue":
        return Msg("The ad gives no year; we go by {year}, the year in our catalogue.", year=year)
    return None


def check_value(model, claims, asking, spec_result, age_result, today=None, year_estimate=None, resolved=None):
    today = today or date.today()
    resolved = resolved or resolve_year(model, claims, age_result, year_estimate, today)
    model_year = resolved["year"]
    # Our catalogue's new price; for a line no longer sold, the price on the sheet of that year or the closest one
    # (the archived sheets' prices are less sure: a sheet can list another version's price).
    prices = year_prices(model)
    german = False
    if model.get("price_eur"):
        original = model["price_eur"]
        price_year = scrape_year(model)
    else:
        price_year = min(prices, key=lambda y: (abs(y - model_year), -y)) if prices else None
        original, german = prices.get(price_year, (None, False))
    if not original:
        return {"status": UNKNOWN, "headline": Msg("No original price"),
                "detail": Msg("We don't have a new price for this model.")}
    age = max(0, today.year - model_year)
    # Rough curve: about 25% off in the first year, then about 12% a year.
    factor = 0.80 if age == 0 else 0.75 * (0.88 ** (age - 1))
    condition_key = claims["condition"]
    aged_out = condition_key == "like-new" and age >= LIKE_NEW_MAX_AGE
    if aged_out:
        condition_key = None  # counted as normal use
    factor *= CONDITION_FACTOR.get(condition_key, 1.0)
    # Downgraded parts lower the value: 10% for the groupset, 5% for wheels or tyres. Upgrades rarely
    # raise a used bike's price, so they don't count.
    downgraded = [r for r in spec_result["rows"] if r.get("step", 0) < 0]
    for r in downgraded:
        factor *= 0.9 if r["key"] == "groupset" else 0.95
    mid = original * factor
    low, high = round(mid * 0.9, -1), round(mid * 1.1, -1)
    condition = (Msg("Normal use") if aged_out else
                 Msg(CONDITION_LABEL[claims["condition"]]) if claims["condition"] else None)
    result = {"original": original, "model_year": model_year, "age": age, "low": low, "high": high,
              "condition": condition, "asking": asking,
              "notes": [Msg("Rough estimate: new price, age and condition only. Comparable ads aren't used yet."),
                        Msg("New price is the {year} German list price (TOUR/BIKE database), which can differ "
                            "from the Dutch price and from what this bike cost new.", year=price_year) if german else
                        Msg("New price is the {year} Dutch price, which can differ from what this bike cost new.",
                            year=price_year or today.year)]}
    why = year_note(resolved, claims)
    if why:
        result["notes"].append(why)
    if aged_out:
        result["notes"].append(Msg("The ad says like new, but a bike {age} years old isn't, so we count it as "
                                   "normal use.", age=age))
    if not resolved["reliable"]:
        # We can't disprove the ad's year, so we go by it, but the price is this generation's.
        result["notes"].append(Msg("The bike is probably an earlier generation than {name}, whose new price we don't "
                                   "have; an older generation is usually worth less.", name=model["name"]))
    if downgraded:
        result["notes"].append(Msg("Lowered for the downgraded parts."))
    if not asking:
        result.update(status=UNKNOWN, headline=Msg("Fair {low} to {high}", low=eur(low), high=eur(high)),
                      detail=Msg("Add the asking price to see how it compares."))
        return result
    # Anything above the fair range is too high, even by a few euros: a price over the range is never called fair.
    if asking > high:
        result.update(status=WARN, headline=Msg("ca. {diff} too high", diff=eur(asking - high)))
    elif asking < low * 0.6:
        result.update(status=BAD, headline=Msg("Suspiciously cheap"))
    elif asking < low * 0.95:
        result.update(status=OK, headline=Msg("Below the fair range"))
    else:
        result.update(status=OK, headline=Msg("Fair price"))
    if condition:
        detail = Msg("Fair range {low} to {high} for a {year} bike in {condition} condition.",
                     low=eur(low), high=eur(high), year=model_year, condition=condition)
    else:
        detail = Msg("Fair range {low} to {high} for a {year} bike.", low=eur(low), high=eur(high), year=model_year)
    if result["status"] == BAD:
        detail = join(detail, Msg("A price this low can mean a stolen bike or a scam. "
                                  "Ask for the invoice and meet in person."))
    result["detail"] = detail
    result["bar"] = value_bar(low, high, original, asking)
    return result


def value_bar(low, high, original, asking=None):
    """Where the fair range (and the asking price, if any) sit on a bar from €0 to a bit past the new price."""
    hi_axis = max(original, asking or 0) * 1.05
    return {"low": 100 * low / hi_axis, "width": 100 * (high - low) / hi_axis,
            "asking": min(99.5, 100 * asking / hi_axis) if asking else None,
            "max": hi_axis, "ticks": axis_ticks(hi_axis)}


def axis_ticks(top):
    """Round euro steps from €0 to the axis end, as (value, % along the bar); the end itself is always the last tick."""
    raw = top / 5
    magnitude = 10 ** (len(str(int(raw))) - 1)
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks, value = [], 0
    while value < top * 0.9:  # a round tick too close to the end would collide with its label
        ticks.append((value, 100 * value / top))
        value += step
    return ticks + [(top, 100.0)]


def seller_questions(model, claims, age, specs, size, material_alert=None):
    # The frame number, always: it dates the bike and shows whether it was reported stolen.
    qs = [Msg("Can you send a photo of the serial number under the bottom bracket?")]
    if material_alert:
        qs.append(material_alert["question"])
    if age["status"] in (WARN, BAD, UNKNOWN):
        qs.append(Msg("Do you have the original invoice? Which year did you buy it?"))
    for row in specs["rows"]:
        if row["key"] == "groupset" and row["status"] == BAD:
            qs.append(Msg("The original came with {original}. Was the groupset changed, and do you still have the "
                          "original parts?", original=row["original"]))
        elif row["key"] == "frame" and material_alert:
            continue
        elif row["status"] == BAD:
            qs.append(Msg("The original has {original} for the {part}. Can you explain the difference?",
                          original=row["original"], part=row["part"]))
        elif row.get("step", 0) > 0:
            qs.append(Msg("Do you still have the original {part} ({original})?", part=row["part"],
                          original=str(row["original"]).split(",")[0]))
        elif row["key"] == "wheels" and row["status"] == UNKNOWN:
            qs.append(Msg("Are these the original wheels ({wheels})?", wheels=str(row["original"]).split(",")[0]))
    if size["status"] in (WARN, UNKNOWN):
        qs.append(Msg("What frame size is printed on the frame?"))
    if claims["condition"] is None:
        qs.append(Msg("Has it been in a crash, and are there any cracks or deep scratches on the frame?"))
    return qs[:6]


def run_check(models, listing, today=None):
    """listing: dict with title, description, asking_price, rider_height, model_id (optional override)."""
    claims = read_claims(listing["title"], listing.get("description"))
    ranked = match_models(models, listing["title"], listing.get("description") or "", claims)
    chosen = None
    if listing.get("model_id"):
        chosen = next((m for m in models if m["id"] == listing["model_id"]), None)
    if chosen is None and ranked:
        chosen = ranked[0][1]
    # Picking our own suggestion again brings back our confidence; another model is the visitor's call.
    chosen_by_you = bool(chosen and ranked and listing.get("model_id") and chosen["id"] != ranked[0][1]["id"])
    level = confidence(ranked) if not chosen_by_you else None
    report = {"claims": claims, "candidates": [m for _, m in ranked[:8]],
              "confidence": Msg(level) if level else None, "chosen_by_you": chosen_by_you, "model": chosen}
    if chosen is None:
        return report
    if not chosen_by_you:
        report["name_check"] = name_check(chosen, models, listing["title"], listing.get("description"))
        # The ad names another version or a model word ours hasn't: the closest bike we have, not the ad's.
        if report["name_check"] and (report["name_check"]["conflicts"] or report["name_check"]["extra"]):
            report["confidence"] = Msg("low")
            report["not_exact"] = True
    # The candidates with how well the ad's words fit each, best fit first; our pick is marked in the list.
    rates = [(match_rate(m, models, listing["title"], listing.get("description")), score, m) for score, m in ranked[:8]]
    rates.sort(key=lambda r: (-r[0]["pct"], -r[1]))
    report["matches"] = [dict(rate, model=m) for rate, _, m in rates]
    report["match"] = next((r for r in report["matches"] if r["model"]["id"] == chosen["id"]), None)
    if report["confidence"] and report["match"]:
        report["confidence"] = Msg(match_confidence(report["match"]["pct"],
                                                    [r["pct"] for r in report["matches"] if r is not report["match"]],
                                                    report.get("not_exact")))
    # Show the catalogue bike in the colour of the ad's bike, in every photo of the report.
    report["colourway"] = colour_match.pick(chosen, listing["title"], listing.get("description") or "")
    report["colour_from_photos"] = False
    if not report["colourway"] and (name := colour_match.by_photos(
            [(w["name"], w.get("image")) for w in chosen.get("colorways") or []], listing.get("photo_paths"))):
        # The ad doesn't name its colour: the colourway its photos show.
        report["colourway"] = next(w for w in chosen["colorways"] if w["name"] == name)
        report["colour_from_photos"] = True
    if report["colourway"] and report["colourway"].get("image"):
        report["model"] = dict(chosen, image=report["colourway"]["image"])
    report["age"] = check_age(chosen, claims, today)
    seen = photo_colour(chosen, listing)
    report["year_estimate"] = estimate_year(chosen, models, claims,
                                            f"{listing['title']}\n{listing.get('description') or ''}", seen)
    # The photo of the model year the ad's bike is, rather than of today's model, when we have one.
    found = year_photo(chosen, claims, report["year_estimate"], f"{listing['title']}\n{listing.get('description') or ''}", seen)
    # One model year for the price and the spec comparison, so they can't disagree.
    report["year"] = resolve_year(chosen, claims, report["age"], report["year_estimate"], today, found)
    report["year"]["note"] = year_note(report["year"], claims)
    if found and found[2] is None:
        # The ad doesn't name its colour and that year came in several: the colourway its photos show.
        own = ((chosen.get("year_specs") or {}).get("years") or {}).get(str(found[0]), {}).get("colour_images") or {}
        name = colour_match.by_photos(list(own.items()), listing.get("photo_paths"))
        report["colour_from_photos"] = bool(name)
        if name:
            found = (found[0], own[name], name)
    if found:
        report["photo_year"] = {"year": found[0], "colour": found[2]}
        report["colourway"] = None
        report["model"] = dict(chosen, image=found[1], year_photo=True)
    report["age_tab"] = age_summary(report["age"], report["year_estimate"], report["year"])
    if report["year"]["how"] == "older" and report["match"] and (report["match"].get("shifting") or {}).get("same") is False:
        # A generation older than any we know may well shift otherwise than today's: that's no mismatch.
        report["match"] = dict(report["match"], shifting=None)
    report["material_alert"] = impossible_material(chosen, claims,
                                                   f"{listing['title']}\n{listing.get('description') or ''}")
    # The spec comparison uses the resolved year's sheet, else the sheet year the estimate allows closest to it.
    # A bike older than any generation we know has no sheet to compare with: not the oldest one we have.
    no_sheet = report["year"]["how"] == "older"
    year = None if no_sheet else comparison_year(
        chosen, dict(claims, year=report["year"]["year"]) if report["year"]["how"] != "catalogue" else claims,
        report["year_estimate"])
    report["spec_year"] = None if no_sheet else year or scrape_year(chosen)
    report["specs"] = check_specs(year_model(chosen, year), claims, report["material_alert"],
                                  listing.get("photo_groupset"), report["year"]["year"], no_sheet, today)
    report["size"] = check_size(chosen, claims, listing.get("rider_height"))
    report["value"] = check_value(chosen, claims, listing.get("asking_price"), report["specs"], report["age"], today,
                                  report["year_estimate"], report["year"])
    report["questions"] = seller_questions(chosen, claims, report["age"], report["specs"], report["size"],
                                           report["material_alert"])
    report["facts"] = head_facts(chosen, claims, report["value"])
    return report


ELECTRONIC_NAME = {"Shimano": "Di2", "SRAM": "AXS", "Campagnolo": "EPS"}


def head_facts(model, claims, value):
    """The few facts for the report's heading: [(label, value)] for the year, size and groupset the ad gives,
    and the model's new price in the year it's valued as, which is our catalogue's, never the seller's."""
    facts = []
    if claims["year"]:
        facts.append((Msg("Year"), str(claims["year"])))
    if claims["size"]:
        facts.append((Msg("Size"), str(claims["size"])))
    group = claims["groupset"]
    if group:
        brand = group["name"].split()[0]
        extra = ELECTRONIC_NAME.get(brand) if group.get("electronic") else None
        facts.append((Msg("Groupset"), f"{group['name']} {extra}" if extra else group["name"]))
    year = value.get("model_year")
    price = new_price(model, year)
    if price:
        facts.append((Msg("New in {year}", year=year), eur(price)))
    return facts
