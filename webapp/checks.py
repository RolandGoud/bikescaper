"""Read the seller's claims from a listing, match it to a catalogue model, and run the checks.

Everything works on text the user pasted: we never fetch the listing page.
"""
import html
import re
import unicodedata
from datetime import date

from .i18n import Msg, join, join_list
from .reference import (BRAND_ALIASES, CATEGORY_WORDS, ELECTRONIC, FAMILY_DISCIPLINES, GENERATIONS, GENERATIONS_NOTE,
                        GENERIC_SIZE_CHART, GROUPSETS, NAME_WORDS, NO_MOTOR_GROUP, PART_TIERS, SIZE_CHARTS,
                        SIZE_NOTE, SPEC_GROUPS, SPEC_LABELS, SPEC_PARTS, TIER_WEIGHTS, WEIGHT_TIERS)

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


def detect_material(text, model_name=False):
    low = _plain(text)
    if re.search(r"\bcarbon\b|\boclv\b|\bcf\b", low):
        return "Carbon"
    if re.search(r"alumini?um|\balu\b|lichtmetaal|\balr\b", low) or (model_name and re.search(r"\bal\b", low)):
        return "Aluminium"
    if re.search(r"\bstaal\b|\bsteel\b", low):
        return "Steel"
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


def detect_condition(text):
    low = _plain(text)
    if re.search(r"defect|kapot|schade|scheur|crack", low):
        return "damaged"
    if re.search(r"nieuwstaat|als nieuw|zo goed als nieuw|z\.?g\.?a\.?n|like new|nauwelijks gebruikt", low):
        return "like-new"
    if re.search(r"gebruikssporen|krassen|sporen van gebruik|wear", low):
        return "used"
    return None


def detect_brand(text):
    low = _plain(text)
    for alias, brand in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            return brand
    return None


PART_WORDS = {"wheels": r"wiel|wheel|velg(?!rem)|laufrad", "tyres": r"band|tyre|tire"}


def detect_part(text, part):
    """The first clause of the ad that names this part and a part we can rate: {"label", "tier"} or None.

    Only clauses that mention the part ("Zipp 404 wielen", "GP5000 banden") are read, so "carbon frame"
    doesn't count as carbon wheels.
    """
    # "Zipp 404 wielen en GP5000 banden" is two clauses, so the wheel name doesn't rate the tyres.
    for clause in re.split(r"[\n.,;!?]+|\s(?:en|and|met|with)\s", text or ""):
        if re.search(PART_WORDS[part], _plain(clause)):
            tier = part_tier((part,), clause)
            if tier:
                return {"label": clause.split(":")[-1].strip(), "tier": tier}
    return None


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


def model_years(model, today=None):
    """(first, last or None for still sold, source message), or None when nothing tells us.

    The hand-entered generation table wins; otherwise the model years in the brand's photo file
    names, running to "now" while the newest scrape still lists the model.
    """
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), generation_of(model["name"])))
    if years:
        return years[0], years[1], Msg(GENERATIONS_NOTE)
    seen = model.get("photo_years") or []
    if not seen:
        return None
    still_sold = catalogue_status(model, today)[0] == "current"
    return seen[0], None if still_sold else seen[-1], Msg(
        "From the model years in {brand}'s own photos; earlier years may be missing.", brand=model["brand"])


def catalogue_status(model, today=None):
    """Whether the brand still sells the model: (status, message).

    status is "current", "discontinued" (its generation ended, or the brand's newest scrape no
    longer lists it) or "unknown" (no scrape history).
    """
    today = today or date.today()
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), generation_of(model["name"])))
    missed, last = model.get("missed_scrapes"), model.get("last_seen")
    if years and years[1] and years[1] < today.year:
        return "discontinued", Msg("Discontinued: this generation was sold until {year}.", year=years[1])
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


# ---------------------------------------------------------------- tiers

def part_tier(parts, text):
    """The tier (1-5) of a part from its spec text, trying each part table in turn, or None."""
    low = _plain(html.unescape(text or ""))
    for part in parts:
        if part == "groupset":
            found = detect_groupset(low)
            if found:
                return found["tier"]
            continue
        for tier, pattern in PART_TIERS[part]:
            if re.search(pattern, low):
                return tier
    return None


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


def spec_tiers(model):
    """Tiers for the model's spec sheet: {"rows": {english label: tier}, "groups": {group label: tier},
    "overall": tier or None, "lagging": [group labels two or more tiers below the overall]}.

    A group's tier is the rounded mean of its rated rows; the overall tier weighs the groups by
    TIER_WEIGHTS. The frame group counts the frame itself, not the fork, when the frame is rated.
    Without a rated frame or drivetrain there is no overall tier.
    """
    rows, by_group, frame = {}, {}, []
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
            tier = part_tier(SPEC_PARTS[raw], text)
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
            "lagging": [labels[k] for k, t in groups.items() if overall and t <= overall - 2]}


def model_tier(model):
    return spec_tiers(model)["overall"]


def match_models(models, title, description="", claims=None):
    """Rank catalogue models for a listing. Returns [(score, model)] best first."""
    claims = claims or read_claims(title, description)
    title_toks = set(_tokens(title))
    all_toks = title_toks | set(_tokens(description))
    says_gen = "gen" in all_toks or "generatie" in all_toks
    ranked = []
    for model in models:
        if claims["brand"] and model["brand"] != claims["brand"]:
            continue
        name_toks = _tokens(model["name"])
        if not name_toks or name_toks[0] not in all_toks:
            continue  # the model family (Domane, Ultimate, ...) must be named
        score = 0.0
        skip_next = False
        for i, tok in enumerate(name_toks):
            if skip_next:
                skip_next = False
                continue
            if tok == "gen" and i + 1 < len(name_toks):
                skip_next = True
                if says_gen:
                    score += 1.0 if name_toks[i + 1] in all_toks else -1.0
                continue
            if tok in title_toks:
                score += 1.5
            elif tok in all_toks:
                score += 1.0
            else:
                score -= 0.75
        gen = generation_of(model["name"])
        years = GENERATIONS.get((model["brand"], family_of(model["name"]), gen))
        if years and claims["year"] and not says_gen:
            first, last = years
            if first - 1 <= claims["year"] <= (last or 2100) + 1:
                score += 0.5
        ref_group = detect_groupset(groupset_text(model))
        if ref_group and claims["groupset"] and ref_group["key"] == claims["groupset"]["key"]:
            score += 0.25
        ranked.append((round(score, 2), model))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["price_eur"] or 0))
    return ranked


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


def ref_brakes(model):
    if spec(model, "Remschijf", "Schijfdiameter"):
        return "Disc"
    if re.search(r"\brim\b", _plain(model["name"])):
        return "Rim"
    return detect_brakes(spec(model, "Rem") or "") or ("Disc" if re.search(r"\brt\d|sm-rt", _plain(spec(model, "Rem") or "")) else None)


# ---------------------------------------------------------------- checks

def eur(value):
    return "€{:,.0f}".format(value).replace(",", ".")


def check_age(model, claims, today=None):
    today = today or date.today()
    gen = generation_of(model["name"])
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), gen))
    seen = Msg("On sale in the {brand} NL catalogue on {date}.", brand=model["brand"],
               date=model["seen_on"]) if model.get("seen_on") else None
    claimed = claims["year"]
    timeline = []
    if years:
        first, last = years
        end = last or today.year
        for y in range(min(first, claimed or first), max(end, claimed or end) + 1):
            timeline.append({"year": y, "sold": first <= y <= end, "claimed": y == claimed})
    if claimed is None:
        return {"status": WARN, "headline": Msg("Year not stated"),
                "detail": Msg("The ad doesn't give a year. Ask for the invoice or the serial number."),
                "timeline": timeline, "notes": [n for n in [seen, years and Msg(GENERATIONS_NOTE)] if n]}
    if not years:
        return {"status": UNKNOWN, "headline": Msg("Seller says {year}", year=claimed),
                "detail": Msg("We don't have the model years for this bike yet, so we can't confirm the age."),
                "timeline": [], "notes": [n for n in [seen] if n]}
    first, last = years
    if claimed < first - 1:
        status, headline = BAD, Msg("Older than this model")
        detail = Msg("Seller says {claimed}, but this generation was first sold as the {first} model. "
                     "Either the year is wrong or it's an older generation we don't have yet.",
                     claimed=claimed, first=first)
    elif claimed == first - 1:
        status, headline = WARN, Msg("Probably the purchase year")
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
            "notes": [n for n in [seen, Msg(GENERATIONS_NOTE)] if n]}


def _row(key, part, original, listing, status, result, step=0):
    return {"key": key, "part": Msg(part), "original": original, "listing": listing, "status": status,
            "result": Msg(result) if isinstance(result, str) else result, "step": step}


def _compare_tiers(key, part, original, listing, ref_tier, ad_tier):
    """A row saying whether the ad's part is an upgrade or a downgrade of the original."""
    step = ad_tier - ref_tier
    if step > 0:
        return _row(key, part, original, listing, OK, Msg("Upgrade, tier {a} to {b}", a=ref_tier, b=ad_tier), step)
    if step < 0:
        return _row(key, part, original, listing, BAD, Msg("Downgrade, tier {a} to {b}", a=ref_tier, b=ad_tier), step)
    return _row(key, part, original, listing, WARN, "Same tier, different part")


def check_specs(model, claims):
    rows = []
    not_stated = Msg("Not stated")

    ref_group = detect_groupset(groupset_text(model))
    ref_group_label = spec(model, "Shifter") or (ref_group and ref_group["label"]) or Msg("Not in our data")
    claimed = claims["groupset"]
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
        ("frame", "Frame", ref_material(model), claims["material"]),
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
        else:
            rows.append(_row(key, part, shown or Msg(ref_val), ad_shown, BAD, "Differs"))

    for key, part, keys in (("wheels", "Wheels", ("Wiel voor", "Velg", "Wheelset")),
                              ("tyres", "Tyres", ("Buitenband", "Voorband"))):
        ref_val, ad = spec(model, *keys), claims.get(key)
        ref_tier = part_tier((key,), ref_val) if ref_val else None
        if ad and ref_tier:
            if ad["tier"] == ref_tier:  # often the same wheels or tyres, named differently
                rows.append(_row(key, part, ref_val, ad["label"], OK, "Same tier"))
            else:
                rows.append(_compare_tiers(key, part, ref_val, ad["label"], ref_tier, ad["tier"]))
        elif ad:
            rows.append(_row(key, part, ref_val or Msg("Not in our data"), ad["label"], UNKNOWN, "Can't compare"))
        elif ref_val:
            rows.append(_row(key, part, ref_val, Msg("Check photos"), UNKNOWN, "Compare photos"))
    for key, part, keys in (("crankset", "Crankset", ("Crankstel",)), ("saddle", "Saddle", ("Zadel",))):
        ref_val = spec(model, *keys)
        if ref_val:
            rows.append(_row(key, part, ref_val, Msg("Check photos"), UNKNOWN, "Compare photos"))

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
                  Msg("Compared with the {brand} spec sheet from {date}.", brand=model["brand"],
                      date=model.get("seen_on") or Msg("our catalogue")))
    return {"status": status, "headline": headline, "detail": detail, "rows": rows}


def size_options(brand):
    return SIZE_CHARTS.get(brand, GENERIC_SIZE_CHART)


def check_size(model, claims, rider_height=None):
    chart = size_options(model["brand"])
    size = claims["size"]
    notes = [Msg(SIZE_NOTE)]
    rows = [{"size": k, "low": lo, "high": hi, "selected": k == size}
            for k, (lo, hi) in chart.items() if k.isdigit() == bool(size and size.isdigit())] if size else []
    if not size:
        return {"status": WARN, "headline": Msg("Size not stated"), "detail": Msg("Ask the seller for the frame size."),
                "rows": [], "fit": None, "notes": notes}
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
            "notes": notes}


CONDITION_FACTOR = {"like-new": 1.05, None: 1.0, "used": 0.92, "damaged": 0.6}
CONDITION_LABEL = {"like-new": "like new", "used": "used", "damaged": "damaged"}


def check_value(model, claims, asking, spec_result, age_result, today=None):
    today = today or date.today()
    original = model.get("price_eur")
    if not original:
        return {"status": UNKNOWN, "headline": Msg("No original price"),
                "detail": Msg("We don't have a new price for this model.")}
    gen = generation_of(model["name"])
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), gen))
    model_year = claims["year"]
    other_generation = age_result["status"] == BAD and years and model_year and model_year < years[0]
    if age_result["status"] == WARN and years and model_year and model_year < years[0]:
        model_year = years[0]  # a purchase year just before launch: value it as the launch model year
    if model_year is None:
        model_year = years[0] if years else int((model.get("seen_on") or str(today.year))[:4])
    age = max(0, today.year - model_year)
    # Rough curve: about 25% off in the first year, then about 12% a year.
    factor = 0.80 if age == 0 else 0.75 * (0.88 ** (age - 1))
    factor *= CONDITION_FACTOR.get(claims["condition"], 1.0)
    # Downgraded parts lower the value: 10% for the groupset, 5% for wheels or tyres. Upgrades rarely
    # raise a used bike's price, so they don't count.
    downgraded = [r for r in spec_result["rows"] if r.get("step", 0) < 0]
    for r in downgraded:
        factor *= 0.9 if r["key"] == "groupset" else 0.95
    mid = original * factor
    low, high = round(mid * 0.9, -1), round(mid * 1.1, -1)
    condition = Msg(CONDITION_LABEL[claims["condition"]]) if claims["condition"] else None
    result = {"original": original, "model_year": model_year, "age": age, "low": low, "high": high,
              "condition": condition, "asking": asking,
              "notes": [Msg("Rough estimate: new price, age and condition only. Comparable ads aren't used yet."),
                        Msg("New price is the {year} Dutch price, which can differ from what this bike cost new.",
                            year=model["seen_on"][:4] if model.get("seen_on") else today.year)]}
    if downgraded:
        result["notes"].append(Msg("Lowered for the downgraded parts."))
    if other_generation:
        result["notes"].append(Msg("The claimed year is before this generation, so the bike may be an older "
                                   "generation with a different new price."))
    if not asking:
        result.update(status=UNKNOWN, headline=Msg("Fair {low} to {high}", low=eur(low), high=eur(high)),
                      detail=Msg("Add the asking price to see how it compares."))
        return result
    if asking > high * 1.05:
        result.update(status=WARN, headline=Msg("About {diff} high", diff=eur(asking - high)))
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
    lo_axis, hi_axis = 0, max(original, asking) * 1.05
    span = hi_axis - lo_axis
    result["bar"] = {"low": 100 * low / span, "width": 100 * (high - low) / span, "asking": min(99.5, 100 * asking / span),
                     "max": hi_axis}
    return result


def seller_questions(model, claims, age, specs, size):
    qs = []
    if age["status"] in (WARN, BAD, UNKNOWN):
        qs.append(Msg("Can you send a photo of the serial number under the bottom bracket?"))
        qs.append(Msg("Do you have the original invoice? Which year did you buy it?"))
    for row in specs["rows"]:
        if row["key"] == "groupset" and row["status"] == BAD:
            qs.append(Msg("The original came with {original}. Was the groupset changed, and do you still have the "
                          "original parts?", original=row["original"]))
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
    level = "chosen by you" if listing.get("model_id") else confidence(ranked)
    report = {"claims": claims, "candidates": [m for _, m in ranked[:8]],
              "confidence": Msg(level) if level else None, "model": chosen}
    if chosen is None:
        return report
    report["age"] = check_age(chosen, claims, today)
    report["specs"] = check_specs(chosen, claims)
    report["size"] = check_size(chosen, claims, listing.get("rider_height"))
    report["value"] = check_value(chosen, claims, listing.get("asking_price"), report["specs"], report["age"], today)
    report["questions"] = seller_questions(chosen, claims, report["age"], report["specs"], report["size"])
    return report
