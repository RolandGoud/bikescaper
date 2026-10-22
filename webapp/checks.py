"""Read the seller's claims from a listing, match it to a catalogue model, and run the checks.

Everything works on text the user pasted: we never fetch the listing page.
"""
import re
import unicodedata
from datetime import date

from .reference import (BRAND_NAMES, ELECTRONIC, GENERATIONS, GENERATIONS_NOTE, GENERIC_SIZE_CHART, GROUPSETS,
                        SIZE_CHARTS, SIZE_NOTE)

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
    for key, name, pattern, rank in GROUPSETS:
        if re.search(pattern, low):
            # Prefer the highest-ranked match: "105 crankset, Ultegra shifters" reads as Ultegra.
            if found is None or rank > found["rank"]:
                found = {"key": key, "name": name, "rank": rank}
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
    for brand in BRAND_NAMES:
        if re.search(rf"\b{brand.lower()}\b", low):
            return brand
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
        "condition": detect_condition(text),
        "mentions_upgrades": bool(re.search(r"upgrade|geupgrade|vervangen|nieuwe wielen|ander[e]? wielen|omgebouwd",
                                            _plain(text))),
    }


# ---------------------------------------------------------------- matching

def generation_of(model_name):
    m = re.search(r"\bgen\s*(\d+)", _plain(model_name))
    return int(m.group(1)) if m else None


def family_of(model_name):
    toks = _tokens(model_name)
    return toks[0] if toks else ""


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

def check_age(model, claims, today=None):
    today = today or date.today()
    gen = generation_of(model["name"])
    years = GENERATIONS.get((model["brand"], family_of(model["name"]), gen))
    seen = f"On sale in the {model['brand']} NL catalogue on {model['seen_on']}." if model.get("seen_on") else None
    claimed = claims["year"]
    timeline = []
    if years:
        first, last = years
        end = last or today.year
        for y in range(min(first, claimed or first) , max(end, claimed or end) + 1):
            timeline.append({"year": y, "sold": first <= y <= end, "claimed": y == claimed})
    if claimed is None:
        return {"status": WARN, "headline": "Year not stated",
                "detail": "The ad doesn't give a year. Ask for the invoice or the serial number.",
                "timeline": timeline, "notes": [n for n in [seen, years and GENERATIONS_NOTE] if n]}
    if not years:
        return {"status": UNKNOWN, "headline": f"Seller says {claimed}",
                "detail": "We don't have the model years for this bike yet, so we can't confirm the age.",
                "timeline": [], "notes": [n for n in [seen] if n]}
    first, last = years
    gen_label = f"{model['name']}"
    if claimed < first - 1:
        status, headline = BAD, "Older than this model"
        detail = (f"Seller says {claimed}, but this generation was first sold as the {first} model. "
                  "Either the year is wrong or it's an older generation we don't have yet.")
    elif claimed == first - 1:
        status, headline = WARN, "Probably the purchase year"
        detail = (f"This generation went on sale as the {first} model, in {first - 1}. "
                  f"{claimed} is likely when it was bought, not the model year.")
    elif last and claimed > last + 1:
        status, headline = WARN, "After this model was replaced"
        detail = f"This generation was last sold as the {last} model. A {claimed} bike would be leftover stock."
    else:
        status, headline = OK, "Adds up"
        detail = f"{gen_label} was sold as new in {claimed}."
    if claims["year_is_purchase"]:
        detail += " The seller gives this as the purchase year."
    return {"status": status, "headline": headline, "detail": detail, "timeline": timeline,
            "notes": [n for n in [seen, GENERATIONS_NOTE] if n]}


def check_specs(model, claims):
    rows = []
    bad = warn = 0

    ref_group = detect_groupset(groupset_text(model))
    ref_group_label = spec(model, "Shifter") or (ref_group and ref_group["label"]) or "Not in our data"
    claimed = claims["groupset"]
    if not ref_group or not claimed:
        rows.append({"part": "Groupset", "original": ref_group_label,
                     "listing": claimed["label"] if claimed else "Not stated",
                     "status": WARN if ref_group else UNKNOWN,
                     "result": "Ask seller" if ref_group else "Can't compare"})
        warn += 1
    elif claimed["key"] != ref_group["key"]:
        rows.append({"part": "Groupset", "original": ref_group_label, "listing": claimed["label"],
                     "status": BAD, "result": "Differs"})
        bad += 1
    elif claimed["electronic"] != ref_group["electronic"] and claimed["electronic"]:
        rows.append({"part": "Groupset", "original": ref_group_label, "listing": claimed["label"],
                     "status": WARN, "result": "Electronic in ad, mechanical original"})
        warn += 1
    else:
        rows.append({"part": "Groupset", "original": ref_group_label, "listing": claimed["label"],
                     "status": OK, "result": "Matches"})

    for part, ref_val, ad_val in (
        ("Frame", ref_material(model), claims["material"]),
        ("Brakes", ref_brakes(model), claims["brakes"]),
    ):
        shown = spec(model, "Frame", "Material") if part == "Frame" else spec(model, "Rem")
        if not ref_val:
            rows.append({"part": part, "original": shown or "Not in our data", "listing": ad_val or "Not stated",
                         "status": UNKNOWN, "result": "Can't compare"})
        elif not ad_val:
            rows.append({"part": part, "original": shown or ref_val, "listing": "Not stated",
                         "status": WARN, "result": "Ask seller"})
            warn += 1
        elif ad_val == ref_val:
            rows.append({"part": part, "original": shown or ref_val, "listing": ad_val, "status": OK, "result": "Matches"})
        else:
            rows.append({"part": part, "original": shown or ref_val, "listing": ad_val, "status": BAD, "result": "Differs"})
            bad += 1

    for part, keys in (("Wheels", ("Wiel voor", "Velg")), ("Tyres", ("Buitenband",)),
                       ("Crankset", ("Crankstel",)), ("Saddle", ("Zadel",))):
        ref_val = spec(model, *keys)
        if ref_val:
            rows.append({"part": part, "original": ref_val, "listing": "Check photos", "status": UNKNOWN,
                         "result": "Compare photos"})

    if bad:
        status, headline = BAD, f"{bad} part{'s' if bad > 1 else ''} differ{'s' if bad == 1 else ''}"
    elif warn:
        status, headline = WARN, "Not enough detail"
    else:
        status, headline = OK, "Matches the original"
    detail = ("The seller mentions changed parts. " if claims["mentions_upgrades"] else "") + \
        f"Compared with the {model['brand']} spec sheet from {model.get('seen_on') or 'our catalogue'}."
    return {"status": status, "headline": headline, "detail": detail, "rows": rows}


def size_options(brand):
    return SIZE_CHARTS.get(brand, GENERIC_SIZE_CHART)


def check_size(model, claims, rider_height=None):
    chart = size_options(model["brand"])
    size = claims["size"]
    rows = [{"size": k, "low": lo, "high": hi, "selected": k == size}
            for k, (lo, hi) in chart.items() if k.isdigit() == bool(size and size.isdigit())] if size else []
    if not size:
        return {"status": WARN, "headline": "Size not stated", "detail": "Ask the seller for the frame size.",
                "rows": [], "fit": None, "notes": [SIZE_NOTE]}
    if size not in chart:
        return {"status": UNKNOWN, "headline": f"Size {size}",
                "detail": f"{model['brand']} doesn't use size {size} in our chart. Ask the seller to check the frame sticker.",
                "rows": rows, "fit": None, "notes": [SIZE_NOTE]}
    lo, hi = chart[size]
    fit = None
    if rider_height:
        if lo <= rider_height <= hi:
            fit = {"status": OK, "text": "Good fit"}
        elif lo - 4 <= rider_height <= hi + 4:
            fit = {"status": WARN, "text": "Borderline, test ride it"}
        else:
            fit = {"status": BAD, "text": "Wrong size for you"}
    return {"status": fit["status"] if fit else OK, "headline": f"Size {size}",
            "detail": f"Fits riders of about {lo} to {hi} cm.", "rows": rows, "fit": fit, "notes": [SIZE_NOTE]}


CONDITION_FACTOR = {"like-new": 1.05, None: 1.0, "used": 0.92, "damaged": 0.6}


def check_value(model, claims, asking, spec_result, age_result, today=None):
    today = today or date.today()
    original = model.get("price_eur")
    if not original:
        return {"status": UNKNOWN, "headline": "No original price", "detail": "We don't have a new price for this model."}
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
    downgrade = any(r["part"] == "Groupset" and r["status"] == BAD for r in spec_result["rows"])
    if downgrade:
        ref = detect_groupset(groupset_text(model))
        if ref and claims["groupset"] and claims["groupset"]["rank"] < ref["rank"]:
            factor *= 0.9
    mid = original * factor
    low, high = round(mid * 0.9, -1), round(mid * 1.1, -1)
    result = {"original": original, "model_year": model_year, "age": age, "low": low, "high": high,
              "condition": claims["condition"], "asking": asking,
              "notes": ["Rough estimate: new price, age and condition only. Comparable ads aren't used yet.",
                        f"New price is the {model['seen_on'][:4] if model.get('seen_on') else 'catalogue'} Dutch price, "
                        "which can differ from what this bike cost new."]}
    if other_generation:
        result["notes"].append("The claimed year is before this generation, so the bike may be an older generation "
                               "with a different new price.")
    if not asking:
        result.update(status=UNKNOWN, headline=f"Fair €{low:,.0f} to €{high:,.0f}".replace(",", "."),
                      detail="Add the asking price to see how it compares.")
        return result
    if asking > high * 1.05:
        diff = asking - high
        result.update(status=WARN, headline=f"About €{diff:,.0f} high".replace(",", "."))
    elif asking < low * 0.6:
        result.update(status=BAD, headline="Suspiciously cheap")
    elif asking < low * 0.95:
        result.update(status=OK, headline="Below the fair range")
    else:
        result.update(status=OK, headline="Fair price")
    result["detail"] = f"Fair range €{low:,.0f} to €{high:,.0f} for a {model_year} bike".replace(",", ".") + \
        (f" in {claims['condition'].replace('-', ' ')} condition." if claims["condition"] else ".")
    if result["status"] == BAD:
        result["detail"] += " A price this low can mean a stolen bike or a scam. Ask for the invoice and meet in person."
    lo_axis, hi_axis = 0, max(original, asking) * 1.05
    span = hi_axis - lo_axis
    result["bar"] = {"low": 100 * low / span, "width": 100 * (high - low) / span, "asking": min(99.5, 100 * asking / span),
                     "max": hi_axis}
    return result


def seller_questions(model, claims, age, specs, size):
    qs = []
    if age["status"] in (WARN, BAD, UNKNOWN):
        qs.append("Can you send a photo of the serial number under the bottom bracket?")
        qs.append("Do you have the original invoice? Which year did you buy it?")
    for row in specs["rows"]:
        if row["part"] == "Groupset" and row["status"] == BAD:
            qs.append(f"The original came with {row['original']}. Was the groupset changed, and do you still have the original parts?")
        elif row["status"] == BAD:
            qs.append(f"The original has {row['original'].lower()} for the {row['part'].lower()}. Can you explain the difference?")
        elif row["part"] == "Wheels" and row["status"] == UNKNOWN:
            qs.append(f"Are these the original wheels ({row['original'].split(',')[0]})?")
    if size["status"] in (WARN, UNKNOWN):
        qs.append("What frame size is printed on the frame?")
    if claims["condition"] is None:
        qs.append("Has it been in a crash, and are there any cracks or deep scratches on the frame?")
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
    report = {"claims": claims, "candidates": [m for _, m in ranked[:8]],
              "confidence": "chosen by you" if listing.get("model_id") else confidence(ranked), "model": chosen}
    if chosen is None:
        return report
    report["age"] = check_age(chosen, claims, today)
    report["specs"] = check_specs(chosen, claims)
    report["size"] = check_size(chosen, claims, listing.get("rider_height"))
    report["value"] = check_value(chosen, claims, listing.get("asking_price"), report["specs"], report["age"], today)
    report["questions"] = seller_questions(chosen, claims, report["age"], report["specs"], report["size"])
    return report
