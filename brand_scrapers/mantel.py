"""Spec sheets of earlier model years from Mantel, a Dutch bike shop, as the Wayback Machine kept them.

Mantel listed each bike with its full spec table, its price, the model year and a photo. The pages are gone, but
the Wayback Machine has copies from 2018 on for Trek, Giant, Cube, BMC, Lapierre (2020 on) and Cannondale (2021 on).
Mantel never sold Canyon, Specialized, Factor or Bianchi online, so those brands get nothing from here.

The archive refuses our cloud machines, so the pages are read on a PC and saved as data/years/mantel/raw.json
({"checked_on", "source", "models": {brand: {Mantel's name: {year: {archived_url, original_url, wayback_timestamp,
model_year, price_eur, weight, frame_sizes, photo_id, photo_url_live, specs: [{label, value}]}}}}}). This turns it into

- data/years/mantel/<Brand>.json ({"checked_on", "years", "source", "models": {name: {year: sheet}}}), under our
  model's name where Mantel's matches one, which webapp/seed.py merges under the brand's own sheets, and
- data/years/mantel/lines/<Brand>.json, the bikes no catalogue model carries (Domane SL 6 Disc, sold 2020 - 2022),
  one per line as a catalogue scrape lists them, which seed.py adds as discontinued lines.

Mantel's photo server still serves each page's photo by its number; the photo goes to
images/<Brand>/years/<slug>_<year>_mantel.jpg.

    python -m brand_scrapers.mantel [--no-photos]
"""
import argparse
import glob
import json
import os
import re
import unicodedata
from datetime import datetime

from .archive import FIRST_YEAR, MIN_SPECS, compact, recognised
from .common import ROOT, Fetcher, clean, first_of_each, log, normalize_specs

SOURCE = "Mantel.com (Dutch bike shop), copies in the Wayback Machine"
RAW = os.path.join(ROOT, "data", "years", "mantel", "raw.json")

# Mantel's labels (Dutch, and French on its Belgian pages) as the labels normalize_specs knows. None drops the row:
# shop details, and facts our own sheets don't carry (geometry kind, frame type, colour in Mantel's words).
LABELS = {
    "derailleur achter": "achterderailleur", "dérailleur arrière": "achterderailleur",
    "voorderailleur": "voorderailleur", "dérailleur avant": "voorderailleur",
    "shifters": "shifters", "leviers de vitesses": "shifters",
    "aantal versnellingen": "versnellingen", "nombre de vitesses": "versnellingen",
    "crankstel": "crankstel", "pédalier": "crankstel", "cassette": "cassette", "ketting": "ketting",
    "bottom bracket": "bottom bracket",
    "frame materiaal": "framemateriaal", "matière du cadre": "framemateriaal",
    "voorvork": "voorvork", "fourche": "voorvork",
    "balhoofdset": "balhoofdstel", "balhoofdlagers": "balhoofdstel", "jeu de direction": "balhoofdstel",
    "remhendels": "remhendels", "remschijfdiameter voorwiel": "remschijf",
    "diamètre du disque de frein avant": "remschijf",
    "wielset": "wielset", "roues": "wielset", "velgen": "velgen", "spaken": "spaken",
    "voornaaf": "voornaaf", "achternaaf": "achternaaf",
    "banden": "banden", "pneus": "banden", "voorband": "voorband", "achterband": "achterband",
    "maximale bandbreedte": "maximale bandbreedte",
    "stuur": "stuur", "guidon": "stuur", "stuurpen": "stuurpen", "potence": "stuurpen", "stuurlint": "stuurlint",
    "zadel": "zadel", "selle": "zadel", "zadelpen": "zadelpen", "tige de selle": "zadelpen",
    "gewicht": "gewicht", "poids": "gewicht",
    "gewichtslimiet": "Gewichtslimiet", "limite de poids": "Gewichtslimiet",
}
BRAKE_KIND = {"remsysteem", "système de freinage"}  # "Hydraulische schijfrem": goes in front of the brake model
BRAKE_MODEL = {"type rem", "type de frein"}
GROUPSET = {"schakelgroep", "groupe de transmission"}  # the shifters' row when the page has none
FRENCH_WORDS = [(r"\bvitesses\b", "versnellingen"), (r"\bCarbone\b", "Carbon")]
FRENCH_BRAKES = {"frein à disque hydraulique": "Hydraulische schijfrem", "freins à disque hydrauliques": "Hydraulische schijfrem",
                 "frein à disque mécanique": "Mechanische schijfrem", "freins sur jante": "Velgremmen"}

# Words in Mantel's names that are the shop's, not the brand's: "Checkpoint ALR 4 Gravel Bike", "Axial WS Dames
# Racefiets", "Vélo de gravel Trek Checkpoint ALR 4 WSD", and the model year some names end with.
SHOP_WORDS = re.compile(r"\b(?:gravel ?bike|racefiets|v[ée]lo de gravel(?: \w+)?)\b|\b20[12]\d\b", re.I)
WOMEN = re.compile(r"\b(?:dames|femmes)\b", re.I)
WOMEN_ALREADY = re.compile(r"\b(?:wsd|women'?s|ws|w|liv)\b", re.I)
# Our spelling of Mantel's: "Emonda" is Trek's Émonda, "Caad13" Cannondale's CAAD13.
SPELLING = [(r"\bEmonda\b", "Émonda"), (r"\bCaad", "CAAD"), (r"\bEvo\b", "EVO"), (r"\bUrs\b", "URS"),
            (r"\bSLR02\b", "SLR 02"), (r"\bdi2\b", "Di2"), (r"\bdisc\b", "Disc"), (r"\bDISC\b", "Disc"), (r"\bgen\b", "Gen")]
GRAVEL = re.compile(r"\b(?:checkpoint|revolt|anyroad|topstone|nuroad|urs|unrestricted|kaius|grail|diverge|crosshill)\b", re.I)
CROSS = re.compile(r"\b(?:cross race|tcx|boone|superx|crossmachine)\b", re.I)


def key(name):
    """'Émonda SL6 Di2' -> 'emonda sl 6 di 2': what two spellings of one name share."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("+", " plus ")
    name = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", name)
    return " ".join(re.findall(r"[a-z]+|\d+", name))


def clean_name(name):
    """Mantel's name without the shop's words, in our spelling: 'Emonda SL 6 2018' -> 'Émonda SL 6'."""
    name = SHOP_WORDS.sub(" ", name)
    if WOMEN.search(name):
        name = WOMEN.sub(" ", name) if WOMEN_ALREADY.search(WOMEN.sub(" ", name)) else WOMEN.sub(" Women's ", name)
    for pattern, ours in SPELLING:
        name = re.sub(pattern, ours, name)
    return re.sub(r"\s+", " ", name).strip(" -")


def specs_of(rows):
    """Mantel's [{label, value}] as our labelled sheet."""
    pairs, kind, model, groupset = [], None, None, None
    for row in rows:
        label, value = clean(row.get("label")).lower().rstrip(":"), clean(row.get("value"))
        if not value:
            continue
        for pattern, dutch in FRENCH_WORDS:
            value = re.sub(pattern, dutch, value)
        if label in BRAKE_KIND:
            kind = FRENCH_BRAKES.get(value.lower(), value)
        elif label in BRAKE_MODEL:
            model = value
        elif label in GROUPSET:
            groupset = value
        elif label in LABELS:
            pairs.append((LABELS[label], value))
    if groupset and not any(label == "shifters" for label, _ in pairs):
        pairs.append(("shifters", groupset))
    if kind and model and kind.lower() in model.lower():  # "C550 Spyre, mechanische schijfrem" says it already
        kind = None
    brake = ", ".join(v for v in (kind, model) if v)
    if brake:
        pairs.append(("rem", brake))
    return normalize_specs(first_of_each(pairs))  # "Balhoofdset" and "Balhoofdlagers" are one row of ours


def sheet(entry, specs):
    ts = str(entry.get("wayback_timestamp") or "")
    return {"captured": datetime.strptime(ts[:8], "%Y%m%d").date().isoformat() if len(ts) >= 8 else None,
            "ts": ts, "url": entry.get("original_url"), "source": "mantel", "specs": specs,
            "price": float(entry["price_eur"]) if entry.get("price_eur") else None, "photo": entry.get("photo_url_live")}


GEN = re.compile(r"\s*\bgen\s*(\d+)\b", re.I)


def generation_years(brand, name):
    """{generation number: (first year, last or None)} for the line our name belongs to, from the hand-entered tables."""
    from webapp.reference import GENERATIONS, LINEAGES
    plain = key(GEN.sub("", name))
    out = {n: span for (b, family, n), span in GENERATIONS.items() if b == brand and plain.startswith(family)}
    for b, pattern, gens in LINEAGES:
        if b == brand and re.search(pattern, plain):
            for first, last, word, _label in gens:
                m = re.fullmatch(r"gen (\d+)", word or "")
                if m:
                    out[int(m.group(1))] = (first, last)
    return out


def with_generation(brand, name, year):
    """The name with the generation its year falls in, as our catalogue names lines that have several:
    Mantel's 2020 "Madone SL 6 Disc" is the "Madone SL 6 Disc Gen 6"."""
    if GEN.search(name):
        return name
    for n, (first, last) in sorted(generation_years(brand, name).items()):
        if first <= year <= (last or 9999):
            return f"{name} Gen {n}"
    return name


def match(brand, name, year, ours):
    """Our name for Mantel's bike of this year, or None. The same name matches; so does ours with a generation
    ("Domane SL 6 Gen 4") when Mantel's year falls in that generation's years."""
    k = key(name)
    exact = ours.get(k)
    if exact:
        return exact
    for theirs in ours.values():
        m = GEN.search(theirs)
        if m and not GEN.search(name) and key(GEN.sub("", theirs)) == k:
            first, last = generation_years(brand, theirs).get(int(m.group(1)), (None, None))
            if first and first <= year <= (last or 9999):
                return theirs
    return None


def catalogue_names(brand):
    """{key: our name} of every model of the brand we know: scrapes, discontinued lines and earlier-year sheets."""
    names = set()
    for path in glob.glob(os.path.join(ROOT, "data", brand, "*.json")) + [
            os.path.join(ROOT, "data", "years", "archived", f"{brand}.json")]:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, list):
            names.update(b["name"].strip() for b in data if b.get("name"))
    for part in ([f"{brand}.json"], ["site", f"{brand}.json"]):
        try:
            with open(os.path.join(ROOT, "data", "years", *part), encoding="utf-8") as fh:
                names.update(json.load(fh).get("models", {}))
        except (OSError, ValueError):
            pass
    return {key(n): n for n in sorted(names)}


def category_of(brand, name, categories):
    """The category our models of the same family carry, else gravel, cyclocross or road by the name."""
    family = key(name).split(" ")[0]
    if family in categories:
        return categories[family]
    if GRAVEL.search(name):
        return "Gravel bikes" if brand == "Trek" else "Gravel"
    if CROSS.search(name):
        return "Cyclocross bikes" if brand == "Trek" else "Cyclocross"
    return "Performance road bikes" if brand == "Trek" else "Race"


def catalogue_categories(brand):
    from collections import Counter
    counts = {}
    for path in glob.glob(os.path.join(ROOT, "data", brand, "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                bikes = json.load(fh)
        except (OSError, ValueError):
            continue
        for b in bikes if isinstance(bikes, list) else []:
            if b.get("name") and b.get("category"):
                counts.setdefault(key(b["name"]).split(" ")[0], Counter())[b["category"]] += 1
    return {family: c.most_common(1)[0][0] for family, c in counts.items()}


def convert(raw, photos=None):
    """{brand: (sheets, lines)} from raw.json's content; photos(brand, slug, year, url) saves one and gives its path."""
    out = {}
    for brand, models in raw.get("models", {}).items():
        ours, categories = catalogue_names(brand), catalogue_categories(brand)
        sheets, new = {}, {}
        for mantel_name, years in models.items():
            for year, entry in years.items():
                year = int(entry.get("model_year") or year)
                specs = specs_of(entry.get("specs") or [])
                if year < FIRST_YEAR or recognised(specs) < MIN_SPECS:
                    continue
                plain = clean_name(mantel_name)
                name = with_generation(brand, plain, year)
                found = ours.get(key(plain)) or match(brand, name, year, ours)
                if not found:  # two spellings of one new name ("Revolt 0 Gravel Bike", "Revolt 0 Gravelbike") share it
                    found = new.setdefault(key(name), name)
                kept = sheets.setdefault(found, {}).get(str(year))
                if kept and len(kept["specs"]) >= len(specs):
                    continue
                sheets[found][str(year)] = sheet(entry, specs)
        for name, years in sheets.items():
            for year, s in years.items():
                url = s.pop("photo")
                s["image"] = photos(brand, compact(name), year, url) if photos and url else None
        lines = []
        for name in sorted(set(new.values())):
            years = sheets[name]
            newest = years[max(years)]
            lines.append({"name": name, "brand": brand, "url": f"https://web.archive.org/web/{newest['ts']}/{newest['url']}",
                          "sku": "", "category": category_of(brand, name, categories), "specifications": newest["specs"],
                          "years": sorted(int(y) for y in years), "model_year": int(max(years)), "price": None,
                          "image": next((years[y]["image"] for y in sorted(years, reverse=True) if years[y].get("image")), None),
                          "source": "mantel"})
        out[brand] = (sheets, lines)
    return out


def save(raw, converted):
    folder = os.path.join(ROOT, "data", "years", "mantel")
    os.makedirs(os.path.join(folder, "lines"), exist_ok=True)
    for brand, (sheets, lines) in converted.items():
        years = sorted({int(y) for entries in sheets.values() for y in entries})
        with open(os.path.join(folder, f"{brand}.json"), "w", encoding="utf-8") as fh:
            json.dump({"checked_on": raw.get("checked_on"), "years": years, "source": SOURCE, "models": sheets},
                      fh, ensure_ascii=False, indent=1, sort_keys=True)
        with open(os.path.join(folder, "lines", f"{brand}.json"), "w", encoding="utf-8") as fh:
            json.dump(lines, fh, ensure_ascii=False, indent=1)
        log.info("%s: %d sheets for %d models, %d of them lines we didn't have", brand,
                 sum(len(e) for e in sheets.values()), len(sheets), len(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw", default=RAW)
    parser.add_argument("--no-photos", action="store_true", help="leave the photos out")
    args = parser.parse_args(argv)
    with open(args.raw, encoding="utf-8") as fh:
        raw = json.load(fh)
    photos = None
    if not args.no_photos:
        from .history import save_photo
        fetcher = Fetcher(delay=2.0)
        photos = lambda brand, slug, year, url: save_photo(fetcher, brand, slug, year, url,
                                                           rel=f"{brand}/years/{slug}_{year}_mantel.jpg")
    save(raw, convert(raw, photos))


if __name__ == "__main__":
    main()
