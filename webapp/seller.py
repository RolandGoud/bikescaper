"""Help a seller improve an ad before they place it.

The seller pastes a draft (title, text, asking price) and answers a few questions. We match the
draft to a catalogue model with the same code that checks buyers' ads, fill in the specs the draft
leaves out, and write a new title and description. Then we run the buyer's check on the new ad, so
what the seller sees is exactly what a buyer pasting it into Bike Compare would see.

What the seller says wins over the catalogue: the catalogue only fills gaps, and where the seller's
words differ from it we say so instead of overwriting them. Drafts are never saved.
"""
import re
from datetime import date

from . import checks
from .i18n import Msg
from .reference import GENERATIONS

CONDITIONS = ("like-new", "used", "damaged")
# What the new ad says for each condition, worded so checks.detect_condition reads it back.
CONDITION_TEXT = {"like-new": "Like new, hardly used.", "used": "Used, with normal signs of wear.",
                  "damaged": "Has a defect: [describe the damage]."}
INVOICE = r"factuur|aankoopbon|kassabon|\bbon\b|invoice|receipt"
SERVICE = r"onderhoud|onderhouden|service|beurt|\bkm\b|kilometer"
ELECTRONIC_NAME = {"Shimano": "Di2", "SRAM": "AXS", "Campagnolo": "EPS"}


def _plain(text):
    return checks._plain(text)


def _first(text):
    """The first part of a spec value: "Bontrager R3, Tubeless Ready, ..." -> "Bontrager R3"."""
    text = re.sub(r"^Maat:\s*[\d, ]+", "", text or "").strip()
    return text.split(",")[0].strip() if text else ""


def display_name(model):
    """The model name for an ad title: without the " - Shimano 105 Di2" build suffix, "gen" as "Gen"."""
    name = model["name"].split(" - ")[0]
    return re.sub(r"\bgen\b", "Gen", name)


def groupset_label(groupset):
    """"Shimano 105" plus Di2/AXS/EPS when it shifts electronically."""
    if not groupset:
        return None
    label = groupset["name"]
    extra = ELECTRONIC_NAME.get(label.split()[0])
    if groupset.get("electronic") and extra and extra.lower() not in _plain(label):
        label += " " + extra
    return label


def speed_count(model):
    text = " ".join(filter(None, [checks.spec(model, "Shifter_speed"), checks.spec(model, "Achterderailleur"),
                                  checks.spec(model, "Cassette")]))
    m = re.search(r"(\d{1,2})\s*-?\s*speed", text, re.I)
    return int(m.group(1)) if m else None


def year_options(model, today=None):
    """Model years the seller can pick: the years this model was sold, newest first."""
    today = today or date.today()
    known = checks.model_years(model, today)
    first, last = (known[0], known[1]) if known else (today.year - 10, None)
    return list(range(last or today.year, first - 1, -1))


def year_hint(model, today=None):
    known = checks.model_years(model, today)
    if not known:
        return None
    return checks._span(known[0], known[1])


def size_options(model):
    return list(checks.model_size_chart(model)["sizes"].items())


def _fact(key, label, value, source, **extra):
    return {"key": key, "label": Msg(label), "value": value, "source": source, **extra}


def catalogue_specs(model):
    """The spec lines a buyer looks for, from the catalogue: [(key, label, value)], missing ones left out."""
    group = checks.detect_groupset(checks.groupset_text(model))
    speeds = speed_count(model)
    groupset = groupset_label(group)
    if groupset and speeds:
        groupset = f"{groupset}, {speeds}-speed"
    brakes = checks.ref_brakes(model)
    disc = checks.spec(model, "Remschijf", "Schijfdiameter")
    rotor = re.search(r"(\d{3})\s*mm", disc or "")
    if brakes == "Disc":
        brakes = Msg("Disc brakes, {size} mm rotors", size=rotor.group(1)) if rotor else Msg("Disc brakes")
    elif brakes == "Rim":
        brakes = Msg("Rim brakes")
    tyre = checks.spec(model, "Buitenband", "Voorband")
    tyre_size = re.search(r"\b\d{3}\s*x\s*\d{2}\s*(?:mm|c)?|\b\d{2}\s*mm\b", tyre or "")
    tyres = _first(tyre)
    if tyres and tyre_size and tyre_size.group(0) not in tyres:
        tyres = f"{tyres}, {tyre_size.group(0)}"
    weight = checks.spec(model, "Gewicht", "Weight")
    sized = re.search(r"(\d{2}|[A-Z]{1,3})\s*(?:cm)?\s*-\s*(\d+(?:[.,]\d+)?)\s*kg", weight or "")
    if sized:
        weight = Msg("about {kg} kg in size {size}", kg=sized.group(2).rstrip("0").rstrip(".,"), size=sized.group(1))
    elif checks.weight_kg(weight):
        weight = Msg("about {kg} kg", kg=f"{checks.weight_kg(weight):g}")
    lines = [("frame", "Frame", _first(checks.spec(model, "Frame", "Material"))),
             ("groupset", "Groupset", groupset),
             ("brakes", "Brakes", brakes),
             ("wheels", "Wheels", _first(checks.spec(model, "Wiel voor", "Velg", "Wheelset"))),
             ("tyres", "Tyres", tyres),
             ("weight", "Weight", weight)]
    return [(k, Msg(label), v) for k, label, v in lines if v]


def improve(models, draft, answers=None, today=None, ads=None):
    """Everything the Selling page shows for a draft.

    draft: {title, description, asking_price, model_id (optional override)}
    answers: {year, size, condition, invoice ("yes"/"no"), service (text), wheels ("original"/"replaced")}
    ads: prices.known_ads(...) to count other ads of the model, or None
    """
    answers = answers or {}
    title, description = draft.get("title") or "", draft.get("description") or ""
    before = checks.run_check(models, {"title": title, "description": description,
                                       "asking_price": draft.get("asking_price"),
                                       "model_id": draft.get("model_id")}, today=today)
    model = before.get("model")
    result = {"before": before, "model": model, "candidates": before["candidates"],
              "confidence": before["confidence"], "chosen_by_you": before["chosen_by_you"]}
    if model is None:
        return result
    claims = before["claims"]
    text = f"{title}\n{description}"
    low = _plain(text)

    # ---- what buyers want to know: from the draft, from the catalogue, from the seller's answers
    facts = [_fact("model", "Brand and model", f"{model['brand']} {display_name(model)}", "draft")]
    ref_group = checks.detect_groupset(checks.groupset_text(model))
    group = claims["groupset"]
    if group and ref_group and group["key"] == ref_group["key"] and group["tier"] == ref_group["tier"] \
            and ref_group["electronic"] and not group["electronic"]:
        group = dict(group, electronic=True)  # "105" on a 105 Di2 bike: name the Di2
        facts.append(_fact("groupset", "Groupset", groupset_label(group), "cat", note=Msg("electronic, added")))
    elif group:
        facts.append(_fact("groupset", "Groupset", groupset_label(group), "draft"))
    elif ref_group:
        group = ref_group
        facts.append(_fact("groupset", "Groupset", groupset_label(group), "cat"))
    material = claims["material"] or checks.ref_material(model)
    if material:
        facts.append(_fact("frame", "Frame", Msg(material), "draft" if claims["material"] else "cat"))
    brakes = claims["brakes"] or checks.ref_brakes(model)
    if brakes:
        facts.append(_fact("brakes", "Brakes", Msg("Disc brakes" if brakes == "Disc" else "Rim brakes"),
                           "draft" if claims["brakes"] else "cat"))
    wheels = checks.spec(model, "Wiel voor", "Velg", "Wheelset")
    wheels_answer = answers.get("wheels") if answers.get("wheels") in ("original", "replaced") else None
    if wheels or claims["wheels"]:
        facts.append(_fact("wheels", "Wheels", claims["wheels"]["label"] if claims["wheels"] else _first(wheels),
                           "draft" if claims["wheels"] else ("you" if wheels_answer else "cat"),
                           answer=wheels_answer, ask=not claims["wheels"]))

    year = claims["year"]
    if not year and answers.get("year"):
        year = answers["year"]
    facts.append(_fact("year", "Model year", year, "draft" if claims["year"] else ("you" if year else "open"),
                       options=year_options(model, today), hint=year_hint(model, today)))
    chart = dict(size_options(model))
    size = claims["size"] or (answers.get("size") if answers.get("size") in chart else None)
    facts.append(_fact("size", "Frame size", size, "draft" if claims["size"] else ("you" if size else "open"),
                       options=list(chart), fits=chart.get(size)))
    condition = claims["condition"] or (answers.get("condition") if answers.get("condition") in CONDITIONS else None)
    facts.append(_fact("condition", "Condition", condition,
                       "draft" if claims["condition"] else ("you" if condition else "open"),
                       options=[(c, Msg(checks.CONDITION_LABEL[c])) for c in CONDITIONS]))
    in_draft = bool(re.search(INVOICE, low))
    invoice = answers.get("invoice") if answers.get("invoice") in ("yes", "no") else None
    facts.append(_fact("invoice", "Invoice", invoice, "draft" if in_draft else ("you" if invoice else "open")))
    service_draft = bool(re.search(SERVICE, low))
    service = (answers.get("service") or "").strip()[:200]
    facts.append(_fact("service", "Service and mileage", service,
                       "draft" if service_draft else ("you" if service else "open")))
    result["facts"] = facts
    counts = {s: sum(1 for f in facts if f["source"] == s) for s in ("draft", "cat", "you", "open")}
    result["counts"] = counts

    # ---- the new ad
    result["title"] = new_title(model, year, size, group, material)
    lines = new_description(model, claims, description, year, size, chart.get(size), condition, wheels_answer,
                            invoice, in_draft, service, service_draft, group)
    result["description"] = lines
    result["copy_text"] = "\n".join("".join(str(t) for t, _ in line) for line in lines
                                    if not any(kind == "todo" for _, kind in line)).strip()
    result["asking"] = draft.get("asking_price")

    # ---- the buyer's check on the new ad, and the price
    after = checks.run_check(models, {"title": result["title"], "description": result["copy_text"],
                                      "asking_price": draft.get("asking_price"), "model_id": model["id"]},
                             today=today)
    result["after"] = after
    value = after["value"]
    if value.get("low"):
        mid = (value["low"] + value["high"]) / 2
        result["suggested"] = round(mid / 50) * 50
        if not value.get("bar"):
            value["bar"] = checks.value_bar(value["low"], value["high"], value["original"])
    result["value"] = value
    if ads is not None:
        from . import prices
        result["others"] = prices.asking_price(ads, model["id"], prices.DEFAULT_PERIOD, today)
    result["flags"] = flags(model, claims, group, after, facts)
    return result


def new_title(model, year, size, group, material):
    parts = [f"{model['brand']} {display_name(model)}"]
    if year:
        parts.append(str(year))
    if size:
        parts.append(Msg("size {size}", size=size))
    label = groupset_label(group)
    if label and _plain(label) not in _plain(model["name"]):
        parts.append(label.replace("Shimano ", "").replace("SRAM ", "SRAM ").strip())
    if material and _plain(material) not in _plain(display_name(model)):
        parts.append(str(Msg(material)).lower())
    return " · ".join(str(p) for p in parts)


def new_description(model, claims, own_text, year, size, fits, condition, wheels, invoice, invoice_in_draft,
                    service, service_in_draft, group):
    """The new description as lines of (text, kind): kind "cat" came from the catalogue, "you" from the
    seller's answers, "draft" from their own text, "todo" is still to fill in (left out of the copy)."""
    name = f"{model['brand']} {display_name(model)}"
    opening = [(name, None)]
    if year:
        opening += [(Msg(" from "), None), (str(year), "you")]
    if size:
        opening += [(Msg(", size "), None), (size, "you")]
        if fits:
            opening += [(Msg(" (fits about "), None), (f"{fits[0]}–{fits[1]} cm", "cat"), (")", None)]
    opening.append((".", None))
    lines = [opening]
    if condition:
        lines.append([(Msg(CONDITION_TEXT[condition]), "you")])
    if own_text.strip():
        lines.append([])
        lines += [[(line, "draft")] for line in own_text.strip().splitlines()]
    specs = catalogue_specs(model)
    if specs:
        lines.append([])
        lines.append([(Msg("Specs, all original:") if wheels == "original" else Msg("Original specs:"), None)])
        ref = checks.detect_groupset(checks.groupset_text(model))
        own_group = bool(claims["groupset"] and ref and (ref["key"], ref["tier"]) != (group["key"], group["tier"]))
        stated = {"groupset": own_group, "frame": claims["material"], "brakes": claims["brakes"]}
        for key, label, value in specs:
            if key == "groupset" and own_group:
                value = groupset_label(group)  # the seller's groupset wins over the catalogue's
            if key == "frame" and claims["material"] and checks.ref_material(model) != claims["material"]:
                value = Msg(claims["material"])
            if key == "wheels" and wheels == "replaced":
                lines.append([("• ", None), (label, None), (": ", None), (Msg("replaced, originally {wheels}",
                                                                              wheels=value), "you")])
                continue
            lines.append([("• ", None), (label, None), (": ", None), (value, "draft" if stated.get(key) else "cat")])
    lines.append([])
    if not invoice_in_draft:
        if invoice:
            lines.append([(Msg("Invoice: "), None), (Msg("yes, available") if invoice == "yes" else Msg("no"), "you")])
        else:
            lines.append([(Msg("Invoice: "), None), (Msg("yes or no"), "todo")])
    if not service_in_draft:
        if service:
            lines.append([(Msg("Service: "), None), (service, "you")])
        else:
            lines.append([(Msg("Service: "), None), (Msg("last service, mileage"), "todo")])
    while lines and not lines[-1]:
        lines.pop()
    return lines


def flags(model, claims, group, after, facts):
    """Where the ad and the catalogue disagree, or where the buyer's check will raise a question."""
    out = []
    ref = checks.detect_groupset(checks.groupset_text(model))
    if group and ref and claims["groupset"] and group["key"] == ref["key"] and ref["electronic"] \
            and not claims["groupset"]["electronic"]:
        extra = ELECTRONIC_NAME.get(ref["name"].split()[0], "")
        out.append({"status": "warn", "title": Msg("We added “{extra}”", extra=extra),
                    "text": Msg("You wrote {yours}, but the {model} comes with {theirs}, which shifts electronically. "
                                "That's a selling point and buyers search for it. Remove it if your bike was changed.",
                                yours=claims["groupset"]["name"], model=display_name(model),
                                theirs=groupset_label(ref))})
    for row in after["specs"]["rows"]:
        if row["key"] in ("groupset", "frame", "brakes", "wheels", "tyres") and \
                (row["status"] == "bad" or row.get("step", 0) != 0):
            out.append({"status": "warn" if row.get("step", 0) > 0 else "bad",
                        "title": Msg("{part}: {result}", part=row["part"], result=row["result"]),
                        "text": Msg("The original has {original}; your ad says {listing}. Say in the ad that it "
                                    "was changed and whether you still have the original part, or buyers will ask.",
                                    original=_first(str(row["original"])), listing=row["listing"])})
    age, est = after["age"], after["year_estimate"]
    if claims["year"] or any(f["key"] == "year" and f["value"] for f in facts):
        if age["status"] in ("bad", "warn") or est.get("status") == "bad":
            bad = est if est.get("status") == "bad" else age
            out.append({"status": "bad" if bad["status"] == "bad" else "warn",
                        "title": Msg("Year: {headline}", headline=bad["headline"]), "text": bad["detail"]})
        elif age["status"] == "ok":
            out.append({"status": "ok", "title": Msg("The year fits this model"), "text": age["detail"]})
    if after.get("name_check") and after["name_check"].get("conflicts"):
        theirs, ours = after["name_check"]["conflicts"][0][1], after["name_check"]["conflicts"][0][0]
        out.append({"status": "bad", "title": Msg("Check the model name"),
                    "text": Msg("Your ad says {theirs}, but the closest model we know is a {ours}. Pick the right "
                                "model above if we got it wrong.", theirs=theirs, ours=ours)})
    return out
