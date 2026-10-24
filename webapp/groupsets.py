"""Groupset upgrade paths: each brand's groupsets from basic to top, their generations, and what it takes
to go from one generation to another.

Entered by hand from the makers' launch notes and compatibility charts. The rules are rules of thumb for
a complete groupset swap, not a parts list: the page says so and points to the bike shop.
"""
import re

from .i18n import Msg
from .reference import GROUPSETS

# The site's own tier per groupset key, so a series here gets the same badge as on the spec sheets.
SITE_TIERS = {}
for _key, _name, _pattern, _tier in GROUPSETS:
    SITE_TIERS.setdefault(_key, _tier)

# The page's types, one pill each. Gravel groupsets follow the road rules (drop-bar levers, road freehubs), so an
# upgrade can still go from one to the other; the page just shows them apart.
DISCIPLINES = [("road", "Road"), ("gravel", "Gravel"), ("mtb", "Mountain bike")]
RULES = {"gravel": "road"}  # type -> the discipline its upgrade rules follow, when it isn't its own
# Logos for the brand pills, as on the models page; a brand without one shows its name.
BRAND_LOGOS = {"Shimano": "logos/shimano.svg", "SRAM": "logos/sram.svg", "Campagnolo": "logos/campagnolo.svg"}

SHIFT_LABELS = {
    "mech": "Mechanical",
    "di2": "Di2, wired",
    "di2-wireless": "Di2, semi-wireless",
    "di2-mtb": "Di2, wireless",
    "etap": "eTap, wireless",
    "axs": "AXS, wireless",
    "eps": "EPS, wired",
    "wrl": "Wireless",
}
# Electronic shifting that needs wires through the frame and a battery inside it.
WIRED = {"di2", "di2-wireless", "eps"}
# Shifters that talk to the derailleurs by radio, fully or semi-wireless.
WIRELESS = {"di2-wireless", "di2-mtb", "etap", "axs", "wrl"}

FREEHUBS = {
    "hg": "Shimano HG (8–10-speed)",
    "hg11": "Shimano HG 11/12-speed road",
    "ms": "Shimano Micro Spline",
    "xd": "SRAM XD",
    "xdr": "SRAM XDR",
    "campa": "Campagnolo",
    "n3w": "Campagnolo N3W",
}


def logo_path(series):
    """Where a series' logo would sit under static/: logos/groupsets/ plus its name as a slug ("Dura-Ace" ->
    dura-ace.svg, "SX / NX Eagle" -> sx-nx-eagle.svg). The page shows the name until the file is there."""
    return "logos/groupsets/" + re.sub(r"[^a-z0-9]+", "-", series["name"].lower()).strip("-") + ".svg"


def gen(key, name, year, speeds, shift, system, freehubs, brakes, note=None, udh=False, shifters_from=(),
        one_by=False):
    """One generation of a groupset. `system` is what has to match for parts to mix: shifters and
    derailleurs of one system work together. `freehubs` lists the bodies its cassettes fit, the usual one
    first. `shifters_from` lists other systems whose shifters drive this one's derailleurs. `one_by` marks
    drop-bar groupsets made for one chainring only."""
    return {"key": key, "name": name, "year": year, "speeds": speeds, "shift": shift, "system": system,
            "freehubs": freehubs, "brakes": brakes, "note": note, "udh": udh, "shifters_from": shifters_from,
            "one_by": one_by}


def series(key, name, gens, tier=None, catalog=None):
    """One groupset from basic to top within its ladder. `catalog` is the key the listing check and the models
    page know it by (all GRX is "grx"), when it differs from `key`."""
    catalog = catalog or key
    gens = sorted(gens, key=lambda g: g["shift"] in WIRELESS)  # wireless generations last, the rest as listed
    return {"key": key, "name": name, "tier": tier or SITE_TIERS.get(catalog), "gens": gens,
            "catalog": catalog if catalog in SITE_TIERS else None}


# brand -> type -> [(ladder label, [series from basic to top])]
LADDERS = {
    "Shimano": {
        "road": [
            ("Road", [
                series("claris", "Claris", [
                    gen("r2000", "Claris R2000", 2016, 8, "mech", "shimano-road-8", ["hg"], ["rim", "disc"],
                        note="Disc versions use cable-pulled brakes."),
                ]),
                series("sora", "Sora", [
                    gen("r3000", "Sora R3000", 2016, 9, "mech", "shimano-road-9", ["hg"], ["rim", "disc"]),
                ]),
                series("tiagra", "Tiagra", [
                    gen("4700", "Tiagra 4700", 2016, 10, "mech", "shimano-road-10-4700", ["hg"], ["rim", "disc"],
                        note="Its rear derailleur doesn't work with older 10-speed road shifters."),
                ]),
                series("105", "105", [
                    gen("5800", "105 5800", 2014, 11, "mech", "shimano-road-11", ["hg11"], ["rim"]),
                    gen("r7000", "105 R7000", 2018, 11, "mech", "shimano-road-11", ["hg11"], ["rim", "disc"]),
                    gen("r7150", "105 Di2 R7150", 2022, 12, "di2-wireless", "shimano-di2-12", ["hg11"], ["disc"]),
                    gen("r7100", "105 R7100", 2023, 12, "mech", "shimano-road-12", ["hg11"], ["disc"]),
                ]),
                series("ultegra", "Ultegra", [
                    gen("6800", "Ultegra 6800", 2014, 11, "mech", "shimano-road-11", ["hg11"], ["rim"]),
                    gen("6870", "Ultegra Di2 6870", 2014, 11, "di2", "shimano-di2-11", ["hg11"], ["rim"]),
                    gen("r8000", "Ultegra R8000", 2017, 11, "mech", "shimano-road-11", ["hg11"], ["rim", "disc"]),
                    gen("r8050", "Ultegra Di2 R8050", 2017, 11, "di2", "shimano-di2-11", ["hg11"], ["rim", "disc"]),
                    gen("r8100", "Ultegra Di2 R8100", 2021, 12, "di2-wireless", "shimano-di2-12", ["hg11"],
                        ["rim", "disc"], note="Electronic only: there is no mechanical 12-speed Ultegra."),
                ]),
                series("dura-ace", "Dura-Ace", [
                    gen("9000", "Dura-Ace 9000", 2013, 11, "mech", "shimano-road-11", ["hg11"], ["rim"]),
                    gen("9070", "Dura-Ace Di2 9070", 2013, 11, "di2", "shimano-di2-11", ["hg11"], ["rim"]),
                    gen("r9100", "Dura-Ace R9100", 2016, 11, "mech", "shimano-road-11", ["hg11"], ["rim", "disc"]),
                    gen("r9150", "Dura-Ace Di2 R9150", 2016, 11, "di2", "shimano-di2-11", ["hg11"], ["rim", "disc"]),
                    gen("r9200", "Dura-Ace Di2 R9200", 2021, 12, "di2-wireless", "shimano-di2-12", ["hg11"],
                        ["rim", "disc"], note="Electronic only: there is no mechanical 12-speed Dura-Ace."),
                ]),
            ]),
        ],
        "gravel": [
            ("Gravel", [
                series("grx-400", "GRX 400", [
                    gen("rx400", "GRX RX400", 2019, 10, "mech", "shimano-road-10-4700", ["hg"], ["disc"]),
                ], tier=2, catalog="grx"),
                series("grx-600", "GRX 600", [
                    gen("rx600", "GRX RX600", 2019, 11, "mech", "shimano-road-11", ["hg11"], ["disc"]),
                    gen("rx610", "GRX RX610", 2023, 12, "mech", "shimano-grx-12", ["hg11", "ms"], ["disc"]),
                ], tier=3, catalog="grx"),
                series("grx-800", "GRX 800", [
                    gen("rx810", "GRX RX810", 2019, 11, "mech", "shimano-road-11", ["hg11"], ["disc"]),
                    gen("rx815", "GRX Di2 RX815", 2019, 11, "di2", "shimano-di2-11", ["hg11"], ["disc"]),
                    gen("rx820", "GRX RX820", 2023, 12, "mech", "shimano-grx-12", ["hg11", "ms"], ["disc"],
                        note="1x with a 10-51 cassette needs a Micro Spline freehub."),
                    gen("rx825", "GRX Di2 RX825", 2024, 12, "di2-wireless", "shimano-di2-12", ["hg11", "ms"], ["disc"]),
                ], tier=4, catalog="grx"),
            ]),
        ],
        "mtb": [
            ("Mountain bike", [
                series("deore", "Deore", [
                    gen("m5100", "Deore M5100", 2020, 11, "mech", "shimano-mtb-11", ["hg"], ["disc"]),
                    gen("m6100", "Deore M6100", 2020, 12, "mech", "shimano-mtb-12", ["ms"], ["disc"]),
                ]),
                series("slx", "SLX", [
                    gen("m7000", "SLX M7000", 2016, 11, "mech", "shimano-mtb-11", ["hg"], ["disc"]),
                    gen("m7100", "SLX M7100", 2019, 12, "mech", "shimano-mtb-12", ["ms"], ["disc"]),
                ]),
                series("xt", "XT", [
                    gen("m8000", "XT M8000", 2015, 11, "mech", "shimano-mtb-11", ["hg"], ["disc"]),
                    gen("m8050", "XT Di2 M8050", 2015, 11, "di2", "shimano-di2-mtb-11", ["hg"], ["disc"]),
                    gen("m8100", "XT M8100", 2018, 12, "mech", "shimano-mtb-12", ["ms"], ["disc"]),
                    gen("m8250", "XT Di2 M8250", 2025, 12, "di2-mtb", "shimano-di2-mtb-12", ["ms"], ["disc"]),
                ]),
                series("xtr", "XTR", [
                    gen("m9000", "XTR M9000", 2014, 11, "mech", "shimano-mtb-11", ["hg"], ["disc"]),
                    gen("m9050", "XTR Di2 M9050", 2014, 11, "di2", "shimano-di2-mtb-11", ["hg"], ["disc"]),
                    gen("m9100", "XTR M9100", 2018, 12, "mech", "shimano-mtb-12", ["ms"], ["disc"]),
                    gen("m9250", "XTR Di2 M9250", 2025, 12, "di2-mtb", "shimano-di2-mtb-12", ["ms"], ["disc"]),
                ]),
            ]),
            ("CUES", [
                series("cues", "CUES", [
                    gen("u4000", "CUES U4000 (9-speed)", 2023, 9, "mech", "shimano-cues-9", ["hg"], ["disc"]),
                    gen("u6000-10", "CUES U6000 (10-speed)", 2023, 10, "mech", "shimano-cues-10", ["hg"], ["disc"]),
                    gen("u6000-11", "CUES U6000/U8000 (11-speed)", 2023, 11, "mech", "shimano-cues-11", ["hg"],
                        ["disc"], note="LinkGlide: doesn't mix with the older 11-speed Deore."),
                ]),
            ]),
        ],
    },
    "SRAM": {
        "road": [
            ("Road", [
                series("apex", "Apex", [
                    gen("apex-11", "Apex 1 (11-speed)", 2015, 11, "mech", "sram-road-11", ["hg11", "xd"], ["rim", "disc"],
                        note="1x only.", one_by=True),
                    gen("apex-12", "Apex (12-speed)", 2023, 12, "mech", "sram-apex-12", ["hg11", "xdr"], ["disc"],
                        note="1x only. The 11-44 cassette fits an HG freehub, the 10-44 needs XDR.", one_by=True),
                    gen("apex-axs", "Apex AXS", 2023, 12, "axs", "sram-axs-12", ["hg11", "xdr"], ["disc"],
                        note="1x only. The 11-44 cassette fits an HG freehub, the 10-44 needs XDR.", one_by=True),
                ]),
                series("rival", "Rival", [
                    gen("rival-22", "Rival 22", 2013, 11, "mech", "sram-road-11", ["hg11"], ["rim", "disc"]),
                    gen("rival-axs", "Rival AXS", 2021, 12, "axs", "sram-axs-12", ["xdr"], ["disc"]),
                ]),
                series("force", "Force", [
                    gen("force-22", "Force 22", 2013, 11, "mech", "sram-road-11", ["hg11"], ["rim", "disc"]),
                    gen("force-axs", "Force AXS", 2019, 12, "axs", "sram-axs-12", ["xdr"], ["rim", "disc"],
                        note="The 2025 generation is disc only and mixes with older AXS parts."),
                    gen("force-xplr-13", "Force XPLR AXS (13-speed)", 2025, 13, "axs", "sram-xplr-13", ["xdr"],
                        ["disc"], udh=True, shifters_from=("sram-axs-12",),
                        note="1x gravel. Needs a wide 1x crank.", one_by=True),
                ]),
                series("red", "Red", [
                    gen("red-22", "Red 22", 2013, 11, "mech", "sram-road-11", ["hg11"], ["rim", "disc"]),
                    gen("red-etap", "Red eTap", 2015, 11, "etap", "sram-etap-11", ["hg11"], ["rim", "disc"]),
                    gen("red-axs", "Red AXS", 2019, 12, "axs", "sram-axs-12", ["xdr"], ["rim", "disc"],
                        note="The 2024 generation is disc only and mixes with older AXS parts."),
                    gen("red-xplr-13", "Red XPLR AXS (13-speed)", 2025, 13, "axs", "sram-xplr-13", ["xdr"], ["disc"],
                        udh=True, shifters_from=("sram-axs-12",), note="1x gravel. Needs a wide 1x crank.", one_by=True),
                ]),
            ]),
        ],
        "mtb": [
            ("Eagle", [
                series("sx", "SX / NX Eagle", [
                    gen("nx-eagle", "SX / NX Eagle", 2018, 12, "mech", "sram-eagle", ["hg"], ["disc"]),
                ]),
                series("gx", "GX Eagle", [
                    gen("gx-eagle", "GX Eagle", 2017, 12, "mech", "sram-eagle", ["xd"], ["disc"]),
                    gen("gx-eagle-axs", "GX Eagle AXS", 2021, 12, "axs", "sram-eagle-axs", ["xd"], ["disc"]),
                ]),
                series("x0", "X01 Eagle", [
                    gen("x01-eagle", "X01 Eagle", 2016, 12, "mech", "sram-eagle", ["xd"], ["disc"]),
                    gen("x01-eagle-axs", "X01 Eagle AXS", 2019, 12, "axs", "sram-eagle-axs", ["xd"], ["disc"]),
                ]),
                series("xx", "XX1 Eagle", [
                    gen("xx1-eagle", "XX1 Eagle", 2016, 12, "mech", "sram-eagle", ["xd"], ["disc"]),
                    gen("xx1-eagle-axs", "XX1 Eagle AXS", 2019, 12, "axs", "sram-eagle-axs", ["xd"], ["disc"]),
                ]),
            ]),
            ("Eagle Transmission (T-Type)", [
                series("gx", "GX Transmission", [
                    gen("gx-t", "GX Eagle Transmission", 2023, 12, "axs", "sram-t-type", ["xd"], ["disc"], udh=True,
                        shifters_from=("sram-eagle-axs",)),
                ]),
                series("x0", "X0 Transmission", [
                    gen("x0-t", "X0 Eagle Transmission", 2023, 12, "axs", "sram-t-type", ["xd"], ["disc"], udh=True,
                        shifters_from=("sram-eagle-axs",)),
                ]),
                series("xx", "XX / XX SL Transmission", [
                    gen("xx-t", "XX / XX SL Eagle Transmission", 2023, 12, "axs", "sram-t-type", ["xd"], ["disc"],
                        udh=True, shifters_from=("sram-eagle-axs",)),
                ]),
            ]),
        ],
    },
    "Campagnolo": {
        "road": [
            ("Road", [
                series("centaur", "Centaur", [
                    gen("centaur-11", "Centaur (11-speed)", 2018, 11, "mech", "campa-11", ["campa", "n3w"], ["rim", "disc"]),
                ]),
                series("chorus", "Chorus", [
                    gen("chorus-12", "Chorus (12-speed)", 2020, 12, "mech", "campa-12", ["campa", "n3w"], ["rim", "disc"]),
                ]),
                series("record", "Record", [
                    gen("record-12", "Record (12-speed)", 2018, 12, "mech", "campa-12", ["campa", "n3w"], ["rim", "disc"]),
                ]),
                series("super-record", "Super Record", [
                    gen("sr-12", "Super Record (12-speed)", 2018, 12, "mech", "campa-12", ["campa", "n3w"], ["rim", "disc"]),
                    gen("sr-eps-12", "Super Record EPS (12-speed)", 2019, 12, "eps", "campa-eps-12", ["campa", "n3w"],
                        ["rim", "disc"]),
                    gen("sr-wrl-12", "Super Record Wireless (12-speed)", 2022, 12, "wrl", "campa-wrl-12",
                        ["campa", "n3w"], ["disc"]),
                    gen("sr-wrl-13", "Super Record 13 Wireless", 2025, 13, "wrl", "campa-wrl-13", ["n3w"], ["disc"]),
                ], catalog="record"),
            ]),
        ],
        "gravel": [
            ("Gravel", [
                series("ekar", "Ekar", [
                    gen("ekar", "Ekar", 2020, 13, "mech", "campa-ekar-13", ["n3w"], ["disc"], note="1x only.", one_by=True),
                    gen("ekar-gt", "Ekar GT", 2023, 13, "mech", "campa-ekar-13", ["n3w"], ["disc"], note="1x only.", one_by=True),
                ]),
            ]),
        ],
    },
}

# Brands we don't rate yet, so they have no ladder and no upgrade paths: a short note each, shown below the
# ladders so a bike with one of these isn't a dead end.
OTHER_BRANDS = [
    ("microSHIFT", "gravel", "Sword: a 10-speed budget gravel groupset with cassettes for a regular Shimano HG freehub."),
    ("FSA", "road", "K-Force WE: semi-wireless electronic road shifting that runs on Shimano-compatible "
                    "cassettes and chains."),
    ("microSHIFT", "mtb", "Advent and Advent X: 9- and 10-speed MTB drivetrains, a budget alternative to "
                          "Deore and CUES."),
]

GENERATIONS = {}
for _brand, _by_kind in LADDERS.items():
    for _kind, _ladders in _by_kind.items():
        for _label, _series in _ladders:
            for _step, _s in enumerate(_series):
                for _g in _s["gens"]:
                    GENERATIONS[_g["key"]] = dict(_g, brand=_brand, kind=_kind, discipline=RULES.get(_kind, _kind),
                                                  series=_s["name"], series_key=_s["key"], tier=_s["tier"],
                                                  ladder=(_brand, _kind, _label), step=_step)

# How much has to change, from least to most, when the new groupset fits the frame.
EFFORT = {
    1: ("Mix and match", "Same system: swap the parts you want and keep the rest."),
    2: ("New shifters and derailleurs", "Cassette, chain and crankset can stay."),
    3: ("New drivetrain", "Shifters, derailleurs, cassette and chain, usually the crankset too."),
    4: ("New freehub body", "The new cassette fits another freehub body: often a swap on the same hub, otherwise a new rear wheel."),
}
# What a whole new drivetrain roughly costs, for the levels where it comes to that: rough figures for a
# mechanical groupset bought online, to weigh against another bike, not a quote.
COST = {
    3: "Roughly €600–900 in parts for a mechanical groupset, more for electronic, plus €100–200 to fit it.",
    4: "Roughly €800–1,300 in all: €600–900 for a mechanical groupset, €100–200 to fit it and €150–300 if the rear "
       "wheel has to change too.",
}
# Said with every upgrade that comes to a whole new drivetrain (level 3 or more).
NOT_WORTH_IT = ("Often not cost-effective: a new or second-hand bike with this groupset usually works out better, "
                "especially if your current bike sells well.")
# Whether the new groupset mounts on the frame you have: "no" when it can't (other brakes), "check" when it
# needs something not every frame has (a UDH dropout, internal routing, a front derailleur mount).
FIT = {
    "no": ("Doesn't fit your frame", "Other brake mounts: the frame and fork would have to change, so this is a "
                                     "new bike rather than an upgrade."),
    "check": ("Check your frame", "Fits only if the frame has the mount or routing it needs."),
}


def path(current, target):
    """What it takes to go from one generation to another: {"effort": 1-4, "steps": [Msg], "fit": "ok", "check"
    or "no", "frame": [Msg]}. Steps are the parts to change; frame lists what the frame must have."""
    steps, frame = [], []
    if current["brand"] != target["brand"]:
        effort = 3
        steps.append(Msg("Brand switch: shifters, derailleurs, cassette and chain all change."))
        if "disc" in current["brakes"] and target["discipline"] == "road":
            steps.append(Msg("Road levers hold the brakes, so the hydraulic calipers and hoses change with them."))
    elif current["system"] == target["system"]:
        effort = 1
    elif current["speeds"] == target["speeds"] or current["system"] in target["shifters_from"]:
        effort = 2
        if current["system"] in target["shifters_from"]:
            steps.append(Msg("Your shifters keep working: change the rear derailleur, cassette and chain."))
        else:
            steps.append(Msg("Change shifters and derailleurs; cassette, chain and crankset stay."))
    else:
        effort = 3
        steps.append(Msg("{speeds}-speed: new shifters, derailleurs, cassette and chain.", speeds=target["speeds"]))
    if current["freehubs"][0] not in target["freehubs"]:
        effort = 4
        steps.append(Msg("Rear wheel needs a {freehub} freehub body.", freehub=Msg(FREEHUBS[target["freehubs"][0]])))
    if target["shift"] in WIRELESS and current["shift"] not in WIRELESS:
        steps.append(Msg("Wireless shifting: no cables or wires from the shifters, and batteries to charge."))
    if target["note"]:
        steps.append(Msg(target["note"]))

    if not set(current["brakes"]) & set(target["brakes"]):
        frame.append(Msg("Disc brakes only: your rim-brake frame and fork have no mounts for them."
                         if target["brakes"] == ["disc"] else "Rim brakes only: your disc frame has no mounts for them."))
    if target["udh"] and not current["udh"]:
        frame.append(Msg("The rear derailleur bolts straight to the frame: needs a UDH (universal derailleur "
                         "hanger) dropout."))
    if target["shift"] in WIRED and current["shift"] not in WIRED:
        frame.append(Msg("The derailleurs still run on wires: needs internal routing for them and a spot for the battery."
                         if target["shift"] in WIRELESS else
                         "Wired electronic shifting: needs internal routing for the wires and a spot for the battery."))
    if current["one_by"] and not target["one_by"] and target["discipline"] == "road":
        frame.append(Msg("Two chainrings need a front derailleur mount; your 1x frame may not have one."))
    fit = "no" if not set(current["brakes"]) & set(target["brakes"]) else ("check" if frame else "ok")
    return {"effort": effort, "steps": steps, "fit": fit, "frame": frame}


def is_upgrade(current, target):
    """A higher tier, or the same series one generation on (more speeds or electronic shifting). Generations
    more than three years older than yours are left out: a 2013 Dura-Ace is no step up from a 2018 105."""
    if target["key"] == current["key"] or target["discipline"] != current["discipline"] \
            or target["year"] < current["year"] - 3:
        return False
    if target["tier"] and current["tier"] and target["tier"] > current["tier"]:
        return True
    if target["brand"] == current["brand"] and target["series_key"] == current["series_key"]:
        return (target["speeds"], target["shift"] != "mech", target["year"]) > \
               (current["speeds"], current["shift"] != "mech", current["year"])
    return False


def upgrades(key):
    """The generations one step or more above `key`, each with its path: [(generation, path)], same brand
    first, the ones that don't fit the frame last, then the least work, then tier and newest first."""
    current = GENERATIONS[key]
    found = [(g, path(current, g)) for g in GENERATIONS.values() if is_upgrade(current, g)]
    return sorted(found, key=lambda item: (item[0]["brand"] != current["brand"], item[1]["fit"] == "no",
                                           item[1]["effort"], item[0]["tier"] or 0, -item[0]["year"]))


def is_downgrade(current, target):
    """The same brand and discipline, a lower tier or an older or simpler generation of the same series, and not
    more than three years older than yours."""
    if target["key"] == current["key"] or target["brand"] != current["brand"] \
            or target["discipline"] != current["discipline"] or target["year"] < current["year"] - 3:
        return False
    if target["tier"] and current["tier"] and target["tier"] < current["tier"]:
        return True
    if target["series_key"] == current["series_key"]:
        return (target["speeds"], target["shift"] != "mech", target["year"]) < \
               (current["speeds"], current["shift"] != "mech", current["year"])
    return False


def downgrades(key):
    """The generations below `key` from the same brand, each with its path, sorted like `upgrades`."""
    current = GENERATIONS[key]
    found = [(g, path(current, g)) for g in GENERATIONS.values() if is_downgrade(current, g)]
    return sorted(found, key=lambda item: (item[1]["fit"] == "no", item[1]["effort"], -(item[0]["tier"] or 0),
                                           -item[0]["year"]))


def route(key):
    """The easiest way up from `key`: in each step above it on its own ladder, the upgrade that fits the frame
    with the least work (no frame check before one, the same kind of shifting, then the newest). [(generation, path)], lowest step first."""
    current = GENERATIONS[key]
    found = [(g, p) for g, p in upgrades(key)
             if g["ladder"] == current["ladder"] and g["step"] > current["step"] and p["fit"] != "no"]

    def rank(item):
        g, p = item
        return p["effort"], p["fit"] == "check", g["shift"] != current["shift"], -g["year"]

    picks = {}
    for g, p in found:
        best = picks.get(g["step"])
        if best is None or rank((g, p)) < rank(best):
            picks[g["step"]] = (g, p)
    return [picks[step] for step in sorted(picks)]


def ladders(kind, brand=None):
    """[(brand, [(ladder label, [series])])] for one type, brands in the order above; only `brand`'s when one is
    given."""
    return [(b, by_kind[kind]) for b, by_kind in LADDERS.items() if kind in by_kind and brand in (None, b)]


def columns(steps):
    """The ladder's series in columns, neighbouring series of the same tier stacked in one: [(tier, [series], up)],
    where `up` is True when some generation in the column is an upgrade from one in the column before it, so the
    page draws an arrow between them (False for the first)."""
    cols = []
    for s in steps:
        if cols and cols[-1][0] == s["tier"]:
            cols[-1][1].append(s)
        else:
            cols.append((s["tier"], [s]))
    gens = [[GENERATIONS[g["key"]] for s in series for g in s["gens"]] for _tier, series in cols]
    ups = [False] + [any(is_upgrade(a, b) for a in lower for b in upper) for lower, upper in zip(gens, gens[1:])]
    return [(tier, series, up) for (tier, series), up in zip(cols, ups)]
