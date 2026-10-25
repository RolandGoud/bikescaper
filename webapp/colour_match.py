"""Pick the catalogue colour of the matched model that the bike in the ad has.

From the seller's words: a colour in the title ("Addict 30 zwart"), a "kleur: wit" line, or a colour
before "fiets" or "frame" in the description. Brand colour names ("Raptor Blue", "Chalk", "Iron Grey")
are read into the same plain colour families. The photos aren't read: without a vision model the
wall, street or grass around the bike outweighs its paint (tried on Scott's colours pasted onto
street photos: right about half the time).
"""
import colorsys
import re

FAMILIES = ["black", "white", "grey", "silver", "red", "orange", "yellow", "gold", "green", "blue", "purple",
            "pink", "brown", "beige"]

# Plain colour words, as sellers write them: these count in an ad.
PLAIN = {
    "black": "black zwart nero noir", "white": "white wit witte bianco", "grey": "grey gray grijs grijze antraciet anthracite",
    "silver": "silver zilver zilveren", "red": "red rood rode bordeaux", "orange": "orange oranje",
    "yellow": "yellow geel gele", "gold": "gold goud gouden golden", "green": "green groen groene mint olijf olive",
    "blue": "blue blauw blauwe navy turquoise petrol", "purple": "purple paars paarse violet lila",
    "pink": "pink roze rose", "brown": "brown bruin bruine bronze brons", "beige": "beige",
}
# Words in brands' colour names; on top of the plain ones, and only read in catalogue names, since
# "carbon" or "raw" in an ad is about the frame, not its paint.
BRAND = {
    "black": "carbon stealth obsidian phantom panther onyx ink shadow raw",
    "white": "chalk cumulus crystal snow arctic pearl ivory",
    "grey": "iron tungsten agate concrete titanium slate charcoal graphite gunmetal cement storm tempest "
            "stone fog mist lupine supernova smoke",
    "silver": "mercury chrome platinum frost quicksilver",
    "blue": "azurite azure sky ocean cobalt lagoon tide glacier glacial aqua cyan teal marine indigo sapphire denim "
            "midnight dragonfly surf surfblue",
    "red": "crimson cherry ruby scarlet rosso berry",
    "green": "sage moss forest reseda mojito cactus emerald jade lime army pine fern acid",
    "yellow": "lemon sunflower canary sulphur",
    "orange": "tangerine amber tiger papaya blaze",
    "purple": "plum lilac lavender mulberry nebula amethyst aubergine magenta iris grape",
    "pink": "mallow peach salmon coral blush flamingo fuchsia",
    "brown": "cappuccino coffee chocolate mocha copper rust espresso",
    "beige": "sand tan cream khaki champagne desert dune sahara bone oat",
    "gold": "brass",
}
_PLAIN = {w: f for f, words in PLAIN.items() for w in words.split()}
_BRAND = {w: f for f, words in BRAND.items() for w in words.split()}
# Dutch writes shades as one word: donkerblauw, lichtgrijze, matzwart.
_SHADE = re.compile(r"^(?:donker|licht|mat|matte|glans|glanzend|metallic|dark|light)-?")

NEAR = {frozenset(p): 0.5 for p in [("grey", "silver"), ("white", "silver"), ("grey", "black"), ("red", "pink"),
                                     ("red", "orange"), ("purple", "pink"), ("purple", "blue"), ("blue", "green"),
                                     ("yellow", "gold"), ("yellow", "orange"), ("brown", "beige"), ("gold", "beige"),
                                     ("brown", "gold"), ("brown", "orange"), ("white", "beige"), ("red", "purple")]}


def similarity(a, b):
    return 1.0 if a == b else NEAR.get(frozenset((a, b)), 0.0)


def families_in(text, brand_words=False):
    """The colour families named in a text, in order: "Carbon / Red" gives ["black", "red"] with brand
    words. Within one part of a name a plain colour word wins: "Blaze Purple" is purple, not orange."""
    found = []
    for part in re.split(r"[/&,+]| - | 'n' | n | and | en ", (text or "").lower()):
        plain, brand = [], []
        for word in re.findall(r"[a-zà-ÿ-]+", part):
            for w in (word, _SHADE.sub("", word), re.sub(r"e$", "", _SHADE.sub("", word))):
                if w in _PLAIN:
                    plain.append(_PLAIN[w])
                    break
                if brand_words and w in _BRAND:
                    brand.append(_BRAND[w])
                    break
        for family in plain or brand:
            if family not in found:
                found.append(family)
    return found


_AD_COLOUR = r"(?:[a-z]+-?)?(?:%s)e?" % "|".join(sorted(_PLAIN, key=len, reverse=True))


def ad_colours(title, description=""):
    """Colour families the seller names for the bike: in the title, a "kleur" line, or next to fiets/frame."""
    text = (description or "").lower()
    said = [title or ""]
    said += re.findall(r"\b(?:kleur|kleuren|colou?r)\s*(?:is|:|-)?\s*([a-z /&-]{3,40})", text)
    said += re.findall(r"\b(%s(?:\s*[/&-]\s*%s)?)\s+(?:\w+\s+)?(?:race|gravel)?(?:fiets|frame|bike|racer)"
                       % (_AD_COLOUR, _AD_COLOUR), text)
    said += re.findall(r"\bframe\s*(?:is|:)?\s*(?:in\s+)?(?:het\s+)?(%s)" % _AD_COLOUR, text)
    found = []
    for s in said:
        for f in families_in(s):
            if f not in found:
                found.append(f)
    return found


# A plain swatch per family, for a colour dot next to a colour's name.
FAMILY_HEX = {"black": "#1b1c20", "white": "#f4f4f2", "grey": "#8a8f98", "silver": "#c3cad3", "red": "#d8443c",
              "orange": "#f08a2c", "yellow": "#f2d23c", "gold": "#c9a54a", "green": "#3f9c5a", "blue": "#3d6fd0",
              "purple": "#7e57c2", "pink": "#ee88b0", "brown": "#7a5236", "beige": "#d9c7a5"}


def swatch(name):
    """A CSS colour for a colour name like "Frost Silver" or "Carbon / Red", by its first colour; None if unknown."""
    fams = families_in(name, brand_words=True)
    return FAMILY_HEX[fams[0]] if fams else None


def swatch_css(name):
    """A CSS background for a colour name: one swatch colour, or two halves for "Trek Black / Carbon Smoke"."""
    fams = families_in(name, brand_words=True)
    if len(fams) >= 2:
        return f"linear-gradient(135deg, {FAMILY_HEX[fams[0]]} 50%, {FAMILY_HEX[fams[1]]} 50%)"
    return FAMILY_HEX[fams[0]] if fams else None


def hex_family(value):
    """The family of a CSS #rrggbb swatch colour, by its hue, saturation and brightness."""
    m = re.match(r"#([0-9a-f]{6})$", (value or "").lower())
    if not m:
        return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    if v < 0.22:
        return "black"
    if s < 0.18:
        return "white" if v > 0.82 else "grey"
    if h < 50 and v < 0.55:
        return "brown"
    for name, top in [("red", 15), ("orange", 40), ("yellow", 70), ("green", 165), ("blue", 255), ("purple", 290),
                      ("pink", 345), ("red", 361)]:
        if h < top:
            return name


def colourway_families(cw):
    """A colourway's families from its name; when the name is all fancy words ("Satin Solidity Metallic",
    "artline"), from the brand's swatch colour or the frame's colour in its photo."""
    return (families_in(cw.get("name"), brand_words=True)
            or [f for f in [hex_family(cw.get("hex") or cw.get("photo_hex"))] if f])


def by_text(colourways, wanted):
    """The colourways whose names fit the seller's colours best: the first colour said weighs most, and a
    colourway that leads with it wins a tie. More than one when they fit equally; none when nothing fits."""
    weights = [1.0, 0.5, 0.3, 0.2]
    scored = []
    for i, cw in enumerate(colourways):
        fams = colourway_families(cw)
        if not fams:
            continue
        score = sum(w * max(similarity(a, f) for f in fams) for w, a in zip(weights, wanted))
        lead = similarity(wanted[0], fams[0])
        scored.append((score, lead, -i, cw))
    scored.sort(key=lambda s: s[:3], reverse=True)
    if not scored or scored[0][0] < 0.5:
        return []
    return [s[3] for s in scored if s[:2] == scored[0][:2]]


def pick(model, title, description=""):
    """The colourway of the model that the ad's bike has, by the colours the seller names; None when the
    model has one colour, the ad names none, or it fits several colourways equally."""
    colourways = [cw for cw in (model or {}).get("colorways") or [] if cw.get("name")]
    if len(colourways) < 2:
        return None
    wanted = ad_colours(title, description)
    best = by_text(colourways, wanted) if wanted else []
    return best[0] if len(best) == 1 else None
