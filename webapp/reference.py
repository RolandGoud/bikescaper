"""Hand-entered reference data the scraper does not collect yet.

Everything here is a stop-gap until the reworked scraper stores model years,
size charts and geometry per model. Each table says how sure we are, and the
check report shows that to the user.
"""

# Model years each Trek generation was sold as new (first, last; None = still sold).
# Entered by hand from launch dates, not scraped: verify against Trek's archive
# before relying on them.
GENERATIONS = {
    ("Trek", "domane", 2): (2017, 2019),
    ("Trek", "domane", 3): (2020, 2022),
    ("Trek", "domane", 4): (2023, None),
    ("Trek", "madone", 6): (2019, 2022),
    ("Trek", "madone", 7): (2023, 2024),
    ("Trek", "madone", 8): (2025, None),
    ("Trek", "checkpoint", 1): (2019, 2021),
    ("Trek", "checkpoint", 2): (2022, 2024),
    ("Trek", "checkpoint", 3): (2025, None),
}
GENERATIONS_NOTE = "Model years entered by hand from launch dates; not yet checked against the brand's archive."

# The generations of a model line, oldest first: (first model year, last or None, a word in the model's name that
# says it is this generation or None, name). A model belongs to the generation its name says, else to the one its
# newest catalogue year falls in. Entered by hand from launch dates (a bike launched mid-year is sold as next
# year's model), because our oldest spec sheet is often years after the real launch. Wins over GENERATIONS.
LINEAGES = [
    ("Specialized", r"\btarmac\b", [(2017, 2020, "sl6", "Tarmac SL6"), (2021, 2023, "sl7", "Tarmac SL7"),
                                    (2024, None, "sl8", "Tarmac SL8")]),
    ("Trek", r"\bemonda sl", [(2015, 2017, None, "Émonda (2015–2017)"), (2018, 2020, None, "Émonda (2018–2020)"),
                              (2021, None, None, "Émonda (2021–)")]),
    ("Trek", r"\bdomane al\b", [(2021, 2023, "gen 3", "Domane AL Gen 3"), (2024, None, "gen 4", "Domane AL Gen 4")]),
    ("Giant", r"\btcr advanced\b", [(2016, 2020, None, "TCR Advanced (2016–2020)"),
                                    (2021, 2024, None, "TCR Advanced (2021–2024)"),
                                    (2025, None, None, "TCR Advanced (2025–)")]),
    ("Cannondale", r"\bsupersix evo\b", [(2016, 2019, None, "SuperSix EVO (2016–2019)"),
                                         (2020, 2022, None, "SuperSix EVO (2020–2022)"),
                                         (2023, None, None, "SuperSix EVO (2023–)")]),
    ("Cannondale", r"\bsynapse carbon\b", [(2018, 2021, None, "Synapse Carbon (2018–2021)"),
                                           (2022, None, None, "Synapse Carbon (2022–)")]),
    ("Canyon", r"\baeroad\b", [(2015, 2020, None, "Aeroad (2015–2020)"), (2021, None, None, "Aeroad (2021–)")]),
]
LINEAGES_NOTE = "Launch years of each generation entered by hand; our spec sheets fill in the rest."

# Generic rider-height charts (cm) per brand and size label, used until the
# scraper collects each model's own size chart.
SIZE_CHARTS = {
    "Trek": {
        "47": (152, 158), "49": (155, 161), "50": (158, 163), "52": (163, 168),
        "54": (168, 174), "56": (174, 180), "58": (180, 186), "60": (186, 191),
        "61": (188, 193), "62": (191, 197),
        "XS": (152, 158), "S": (158, 168), "M": (168, 178), "L": (178, 185), "XL": (185, 193),
    },
    "Canyon": {
        "3XS": (150, 158), "2XS": (155, 163), "XS": (163, 170), "S": (170, 176),
        "M": (176, 182), "L": (182, 188), "XL": (188, 194), "2XL": (194, 200),
    },
    # The brands below: entered by hand from each brand's road size guide, for the
    # sizes their 2025-2027 road and gravel bikes use.
    "Specialized": {
        "44": (148, 158), "49": (155, 165), "52": (163, 170), "54": (168, 175), "56": (173, 180),
        "58": (178, 185), "61": (183, 193), "64": (190, 200),
        "XS": (152, 163), "S": (160, 170), "M": (168, 178), "L": (175, 185), "XL": (183, 193),
    },
    "Giant": {
        "XS": (155, 165), "S": (165, 175), "M": (175, 183), "ML": (180, 188), "L": (183, 191), "XL": (188, 196),
    },
    "Cannondale": {
        "44": (150, 157), "48": (155, 163), "50": (158, 166), "51": (160, 168), "52": (163, 170),
        "54": (166, 174), "56": (172, 180), "58": (178, 186), "61": (184, 193),
        "XS": (152, 160), "S": (158, 168), "M": (166, 178), "L": (175, 185), "XL": (183, 193),
    },
    "Cube": {
        "47": (155, 163), "50": (160, 168), "53": (167, 175), "56": (174, 182), "58": (180, 188),
        "60": (186, 194), "62": (192, 200),
        "XS": (155, 163), "S": (160, 168), "M": (167, 175), "L": (174, 182), "XL": (180, 188), "2XL": (186, 194),
    },
    "Scott": {
        "47": (155, 163), "49": (162, 170), "52": (168, 175), "54": (173, 180), "56": (178, 185),
        "58": (183, 190), "61": (188, 198),
        "2XS": (155, 163), "XS": (162, 170), "S": (168, 175), "M": (173, 180), "L": (178, 185),
        "XL": (183, 190), "2XL": (188, 198),
    },
    "Orbea": {
        "47": (150, 158), "49": (156, 164), "51": (162, 169), "53": (167, 175), "55": (173, 181),
        "57": (179, 187), "60": (185, 195),
        "XS": (152, 162), "S": (160, 168), "SM": (164, 172), "M": (167, 176), "ML": (172, 181),
        "L": (175, 184), "XL": (182, 191), "2XL": (189, 198),
    },
    "Factor": {
        "45": (152, 160), "49": (158, 166), "52": (163, 171), "54": (168, 176), "56": (173, 181),
        "58": (178, 186), "61": (183, 193),
    },
}
SIZE_NOTE = "Generic chart for this brand, not this model's own size chart yet."

# Spec tiers, the same five steps for every part and every brand.
TIERS = {1: "Basic", 2: "Entry", 3: "Mid", 4: "Performance", 5: "Top"}
# What a typical road bike part looks like at each tier, for the How it works page.
TIER_EXAMPLES = {
    1: "Shimano Claris or Sora, entry aluminium or steel frame, basic alloy wheels.",
    2: "Shimano Tiagra or CUES, SRAM Apex, aluminium frame, entry alloy wheels.",
    3: "Shimano 105, SRAM Rival, entry carbon frame (Trek OCLV 500, Canyon CF), better alloy or entry carbon wheels.",
    4: "Shimano Ultegra, SRAM Force, performance carbon (OCLV 800, CF SLX), carbon wheels such as Aeolus Pro.",
    5: "Shimano Dura-Ace, SRAM Red, the brand's top carbon (OCLV 900, CFR), flagship wheels such as Aeolus RSL.",
}

# Older groupsets rate lower: Shimano and SRAM bring a new generation about every four to five years, and each one
# passes its features a step down the range (today's 105 shifts like the Ultegra of one generation ago). A bike's
# groupset drops one tier for every GROUPSET_AGE_STEP years of age, at most GROUPSET_AGE_MAX_DROP tiers, never below 1.
GROUPSET_AGE_STEP = 5
GROUPSET_AGE_MAX_DROP = 2

# Groupsets with their tier. Sub-series of one groupset share a key (GRX 600 and GRX 800 are both
# "grx"), so the listing check sees the same groupset but can still tell a step up or down.
GROUPSETS = [
    # (key, display name, regex on lowercased text, tier)
    ("claris", "Shimano Claris", r"\bclaris\b", 1),
    ("sora", "Shimano Sora", r"\bsora\b", 1),
    ("cues", "Shimano CUES", r"\bcues\b", 2),
    ("tiagra", "Shimano Tiagra", r"\btiagra\b", 2),
("grx", "Shimano GRX", r"\b(?:grx\s*)?(?:rd-|fc-|st-|br-)?rx4\d\d\b|\bgrx\s*4\d\d\b", 2),
    ("grx", "Shimano GRX", r"\b(?:grx\s*)?(?:rd-|fc-|st-|br-)?rx[56]\d\d\b|\bgrx\s*[56]\d\d\b", 3),
    ("grx", "Shimano GRX", r"\b(?:grx\s*)?(?:rd-|fc-|st-|br-)?rx8\d\d\b|\bgrx\s*8\d\d\b", 4),
    # GRX without a series code reads as the middle one.
    ("grx", "Shimano GRX", r"\bgrx\b(?!\s*(?:(?:rd-|fc-|st-|br-)?rx)?\s*\d)", 3),
    ("105", "Shimano 105", r"(?<![\d.,x])105(?![\d.,]|\s*(?:mm|kg|cm))", 3),
    ("ultegra", "Shimano Ultegra", r"\bultegra\b", 4),
    ("dura-ace", "Shimano Dura-Ace", r"\bdura[\s-]?ace\b", 5),
    ("apex", "SRAM Apex", r"\bapex\b", 2),
    ("rival", "SRAM Rival", r"\brival\b", 3),
    ("force", "SRAM Force", r"\bforce\b", 4),
    ("red", "SRAM Red", r"\bsram\s+red\b|\bred\s+(?:axs|etap|e1|xplr)\b", 5),
    ("centaur", "Campagnolo Centaur", r"\bcentaur\b", 3),
    ("chorus", "Campagnolo Chorus", r"\bchorus\b", 4),
    ("ekar", "Campagnolo Ekar", r"\bekar\b", 4),
    ("record", "Campagnolo Record", r"\b(?:super\s+)?record\b", 5),
    ("deore", "Shimano Deore", r"\bdeore\b(?!\s*xt)", 2),
    ("slx", "Shimano SLX", r"\bshimano\s+slx\b|\bslx\s*-?m\d{4}", 3),
    ("xt", "Shimano XT", r"\b(?:shimano|deore)\s+xt\b|\bxt\s*-?m\d{4}", 4),
    ("xtr", "Shimano XTR", r"\bxtr\b", 5),
    ("sx", "SRAM SX/NX Eagle", r"\b[sn]x\s+eagle\b", 1),
    ("gx", "SRAM GX", r"\bgx\b", 3),
    ("x0", "SRAM X0", r"\bx0\b|\bxo1\b", 4),
    ("xx", "SRAM XX", r"\bxx(?:1|\s*sl)?\b", 5),
]
ELECTRONIC = r"\bdi2\b|\baxs\b|\betap\b|\beps\b"

# Model years of complete bikes sold with a groupset generation (first, last; None = open).
# Read from the part codes or the speed count in the ad; first match wins, so codes come before
# the looser "12-speed" rules. Entered by hand from launch dates: a bike's model year usually
# follows a groupset's launch by a season, and leftover stock runs a year past its replacement.
SPEED_12 = r"(?:\b12\s*-?\s*(?:speed|sp|v|s|versnellingen|speeds?)\b|\b2\s*x\s*12\b)"
SPEED_11 = r"(?:\b11\s*-?\s*(?:speed|sp|v|s|versnellingen|speeds?)\b|\b2\s*x\s*11\b)"
# The 105 rules read the name, so they only apply when no higher Shimano group is named: "Ultegra Di2 with
# a 105 cassette" is an Ultegra bike.
ONLY_105 = r"(?s:^(?!.*\b(?:ultegra|dura[\s-]?ace)\b))"
GROUPSET_YEARS = [
    # (regex on lowercased text, first, last, name shown in the report)
    (r"\b(?:[a-z]{2}-)?r92[057]\d\b", 2022, None, "Shimano Dura-Ace R9200 (12-speed)"),
    (r"\b(?:[a-z]{2}-)?r81[057]\d\b", 2022, None, "Shimano Ultegra R8100 (12-speed)"),
    (r"\b(?:[a-z]{2}-)?r71[57]\d\b", 2023, None, "Shimano 105 Di2 R7150 (12-speed)"),
    (r"\b(?:[a-z]{2}-)?r71[02]\d\b", 2024, None, "Shimano 105 R7100 (12-speed)"),
    (r"\b(?:[a-z]{2}-)?r91[057]\d\b", 2017, 2022, "Shimano Dura-Ace R9100 (11-speed)"),
    (r"\b(?:[a-z]{2}-)?r80[0257]\d\b", 2017, 2023, "Shimano Ultegra R8000 (11-speed)"),
    (r"\b(?:[a-z]{2}-)?r70[027]\d\b", 2019, 2024, "Shimano 105 R7000 (11-speed)"),
    (r"\bdura[\s-]?ace\s*90[0-7]0\b", 2014, 2017, "Shimano Dura-Ace 9000 (11-speed)"),
    (r"\bultegra\s*68[0-7]0\b", 2015, 2018, "Shimano Ultegra 6800 (11-speed)"),
    (r"\b105\s*58[0-7]0\b", 2015, 2019, "Shimano 105 5800 (11-speed)"),
    (r"\bultegra\s*67[0-7]0\b", 2010, 2014, "Shimano Ultegra 6700 (10-speed)"),
    (r"\b105\s*57[0-7]0\b", 2010, 2015, "Shimano 105 5700 (10-speed)"),
    (r"\b(?:grx\s*)?(?:[a-z]{2}-)?rx(?:82\d|83\d|61\d|62\d)\b|\bgrx\b.{0,40}" + SPEED_12, 2024, None,
     "Shimano GRX (12-speed)"),
    (r"\b(?:grx\s*)?(?:[a-z]{2}-)?rx[468][018]\d\b|\bgrx\b", 2020, None, "Shimano GRX"),
    (ONLY_105 + r"(?s:.*?)(?-s:\b105\b.{0,25}\bdi2\b|\bdi2\b.{0,25}\b105\b)", 2023, None, "Shimano 105 Di2 (12-speed)"),
    (ONLY_105 + r"(?s:.*?)(?-s:\b105\b.{0,40}" + SPEED_12 + r"|" + SPEED_12 + r".{0,40}\b105\b)", 2024, None, "Shimano 105 (12-speed)"),
    (r"\b(?:ultegra|dura[\s-]?ace)\b.{0,40}" + SPEED_12 + r"|" + SPEED_12 + r".{0,40}\b(?:ultegra|dura[\s-]?ace)\b",
     2022, None, "Shimano Ultegra/Dura-Ace (12-speed)"),
    (ONLY_105 + r"(?s:.*?)(?-s:\b105\b.{0,40}" + SPEED_11 + r"|" + SPEED_11 + r".{0,40}\b105\b)", None, 2024, "Shimano 105 (11-speed)"),
    (r"\b(?:ultegra|dura[\s-]?ace)\b.{0,40}" + SPEED_11 + r"|" + SPEED_11 + r".{0,40}\b(?:ultegra|dura[\s-]?ace)\b",
     None, 2023, "Shimano Ultegra/Dura-Ace (11-speed)"),
    (r"\bapex\b.{0,25}\baxs\b|\baxs\b.{0,25}\bapex\b", 2023, None, "SRAM Apex AXS"),
    (r"\brival\b.{0,25}\baxs\b|\baxs\b.{0,25}\brival\b", 2022, None, "SRAM Rival AXS"),
    (r"\bforce\b.{0,25}\baxs\b|\baxs\b.{0,25}\bforce\b", 2020, None, "SRAM Force AXS"),
    (r"\bsram\s+red\b.{0,25}\baxs\b|\bred\s+(?:etap\s+)?axs\b", 2019, None, "SRAM Red AXS"),
]
# Carbon road bikes from the big brands went disc-only around 2021-2022.
RIM_BRAKE_LAST_YEAR = 2022

# Brands the site covers. `site` is the brand's own site the catalogue is read
# from. Trek and Canyon have their own scrapers; the next five are collected by
# brand_scrapers/. Scott and Orbea block requests from servers, so they wait for a
# run from a home connection. `aliases` are other words in an ad that name the brand.
BRANDS = [
    {"name": "Trek", "site": "https://www.trekbikes.com/nl/nl_NL/", "scraper": True, "logo": "logos/trek.svg"},
    {"name": "Canyon", "site": "https://www.canyon.com/nl-nl/", "scraper": True, "logo": "logos/canyon.svg"},
    {"name": "Specialized", "site": "https://www.specialized.com/nl/nl", "scraper": True, "aliases": ["s-works"], "logo": "logos/specialized.svg"},
    {"name": "Giant", "site": "https://www.giant-bicycles.com/nl", "scraper": True, "logo": "logos/giant.svg"},
    {"name": "Cannondale", "site": "https://www.cannondale.com/nl-nl", "scraper": True, "logo": "logos/cannondale.svg"},
    {"name": "Cube", "site": "https://www.cube.eu/nl-nl/", "scraper": True, "logo": "logos/cube.svg"},
    {"name": "Factor", "site": "https://eu.factorbikes.com/", "scraper": True, "logo": "logos/factor.svg"},
    {"name": "Scott", "site": "https://www.scott-sports.com/nl/en/", "scraper": True, "logo": "logos/scott.svg"},
    {"name": "Orbea", "site": "https://www.orbea.com/nl-nl/", "scraper": True, "logo": "logos/orbea.svg"},
]
BRAND_NAMES = [b["name"] for b in BRANDS]
BRAND_ALIASES = {alias: b["name"] for b in BRANDS for alias in [b["name"].lower()] + b.get("aliases", [])}

# Used for brands without their own chart yet.
GENERIC_SIZE_CHART = {**SIZE_CHARTS["Trek"], "2XS": (148, 155), "2XL": (193, 200)}

# The same disciplines for every brand, so the Models page groups bikes alike whatever
# each brand calls its own categories. (key, label); the label is translated on the page.
DISCIPLINES = [
    ("road", "Road"),
    ("gravel", "Gravel & cyclocross"),
    ("tt", "Time trial & triathlon"),
    ("fitness", "Fitness & city"),
    ("mtb", "Mountain"),
    ("ebike", "E-bike"),
    ("frames", "Frames"),
]

# Model families per discipline: the first word of the model name, as checks.family_of reads it.
# Trek and Canyon are checked against their catalogue; the other brands are taken from their
# current line-ups, checked against the brand_scrapers snapshots of October 2026.
FAMILY_DISCIPLINES = {
    "road": {
        "Trek": ["madone", "emonda", "domane"],
        "Canyon": ["aeroad", "ultimate", "endurace"],
        "Specialized": ["tarmac", "aethos", "allez", "roubaix"],
        "Giant": ["propel", "tcr", "defy", "contend"],
        "Cannondale": ["systemsix", "supersix", "caad", "synapse"],
        "Scott": ["foil", "addict", "speedster"],
        "Orbea": ["orca", "avant"],
        "Cube": ["litening", "agree", "attain"],
        "Factor": ["ostro", "o", "monza", "one", "bugatti"],
    },
    "gravel": {
        "Trek": ["checkpoint", "checkmate", "boone"],
        "Canyon": ["grail", "grizl", "inflite"],
        "Specialized": ["diverge", "crux"],
        "Giant": ["revolt", "tcx"],
        "Cannondale": ["topstone", "superx"],
        "Orbea": ["terra"],
        "Cube": ["nuroad", "cross"],
        "Factor": ["explorer", "aluto", "sarana", "elara"],
    },
    "tt": {
        "Trek": ["speed"],
        "Canyon": ["speedmax"],
        "Specialized": ["shiv"],
        "Giant": ["trinity"],
        "Scott": ["plasma"],
        "Orbea": ["ordu"],
        "Cube": ["aerium"],
        "Factor": ["hanzo", "slick"],
        "Cannondale": ["superslice"],
    },
    "fitness": {
        "Trek": ["fx"],
        "Canyon": ["roadlite"],
        "Specialized": ["sirrus"],
        "Giant": ["escape", "fastroad"],
        "Cannondale": ["quick"],
        "Scott": ["sub"],
        "Orbea": ["vector"],
    },
    "mtb": {
        "Trek": ["marlin", "procaliber", "supercaliber", "fuel", "slash"],
        "Canyon": ["exceed", "lux", "neuron", "spectral", "strive"],
        "Specialized": ["epic", "chisel", "stumpjumper", "enduro"],
        "Giant": ["talon", "xtc", "anthem", "trance", "reign"],
        "Cannondale": ["trail", "scalpel", "habit", "jekyll"],
        "Scott": ["scale", "spark", "genius", "ransom"],
        "Orbea": ["alma", "oiz", "occam", "rallon"],
        "Cube": ["reaction", "ams", "stereo"],
    },
}
# Words in a model name that put it in a discipline whatever its family, checked in this order:
# "Aeroad CFR Disc Frame and Brake Kit", "Addict Gravel", "Domane+", "Turbo Creo", "Synapse Neo".
NAME_WORDS = {
    "frames": ["frame", "frameset", "framekit"],
    "ebike": ["plus", "turbo", "neo", "hybrid", "gain"],
    "gravel": ["gravel", "cx", "cyclocross"],
}
# Last resort for a family not listed above: words in the brand's own category name.
CATEGORY_WORDS = {
    "frames": ["frameset", "frames"],
    "ebike": ["electric", "e-bike", "elektrisch"],
    "gravel": ["gravel", "cyclocross", "veldrijden"],
    "tt": ["triathlon", "time trial", "tijdrit"],
    "fitness": ["fitness", "city", "hybrid", "stad"],
    "mtb": ["mountain", "mtb"],
    "road": ["road", "race", "aero", "endurance", "racefiets"],
}

# Spec sheet groups for the model page, in display order. (key, label); the label is translated.
SPEC_GROUPS = [
    ("frame", "Frame & fork"),
    ("drivetrain", "Drivetrain"),
    ("brakes", "Brakes"),
    ("wheels", "Wheels & tyres"),
    ("cockpit", "Cockpit"),
    ("saddle", "Saddle & seatpost"),
    ("electric", "Motor & battery"),
    ("weight", "Weight"),
    ("extras", "Accessories"),
    ("other", "Other"),
]
# Spec labels as the scrapers store them -> (group, English label, Dutch label). Labels that mean
# the same thing (Canyon's "Weight" and "Gewicht") share an English label and are shown once.
SPEC_LABELS = {
    "Frame": ("frame", "Frame", "Frame"),
    "Frame plus vork": ("frame", "Frameset", "Frame plus vork"),
    "Material": ("frame", "Frame material", "Framemateriaal"),
    "Framefit": ("frame", "Frame fit", "Framefit"),
    "Voorvork": ("frame", "Fork", "Voorvork"),
    "Balhoofdstel": ("frame", "Headset", "Balhoofdstel"),
    "As voorwiel": ("frame", "Front axle", "As voorwiel"),
    "As achterwiel": ("frame", "Rear axle", "As achterwiel"),
    "Maximale bandenmaat": ("frame", "Max tyre width", "Maximale bandenmaat"),
    "Maximaal geschikte veerweg": ("frame", "Max suspension travel", "Maximaal geschikte veerweg"),
    "Shifter": ("drivetrain", "Shifters", "Shifters"),
    "Shifter_speed": ("drivetrain", "Speeds", "Versnellingen"),
    "Voorderailleur": ("drivetrain", "Front derailleur", "Voorderailleur"),
    "Achterderailleur": ("drivetrain", "Rear derailleur", "Achterderailleur"),
    "Crankstel": ("drivetrain", "Crankset", "Crankstel"),
    "Kettingblad": ("drivetrain", "Chainring", "Kettingblad"),
    "Maximale maat kettingblad": ("drivetrain", "Max chainring size", "Maximale maat kettingblad"),
    "Bottom bracket": ("drivetrain", "Bottom bracket", "Trapas"),
    "Bottom_bracket": ("drivetrain", "Bottom bracket", "Trapas"),
    "Cassette": ("drivetrain", "Cassette", "Cassette"),
    "Ketting": ("drivetrain", "Chain", "Ketting"),
    "Pedaal": ("drivetrain", "Pedals", "Pedalen"),
    "Rem": ("brakes", "Brakes", "Remmen"),
    "Remgreep": ("brakes", "Brake levers", "Remgrepen"),
    "Remschijf": ("brakes", "Brake rotors", "Remschijven"),
    "Remschijf achter": ("brakes", "Rear rotor", "Remschijf achter"),
    "Schijfdiameter": ("brakes", "Rotor size", "Schijfdiameter"),
    "Wiel voor": ("wheels", "Front wheel", "Wiel voor"),
    "Wiel achter": ("wheels", "Rear wheel", "Wiel achter"),
    "Naaf voor": ("wheels", "Front hub", "Naaf voor"),
    "Naaf achter": ("wheels", "Rear hub", "Naaf achter"),
    "Velg": ("wheels", "Rims", "Velgen"),
    "Velg achter": ("wheels", "Rear rim", "Velg achter"),
    "Spaken": ("wheels", "Spokes", "Spaken"),
    "Velglint": ("wheels", "Rim tape", "Velglint"),
    "Buitenband": ("wheels", "Tyres", "Banden"),
    "Buitenband - onderdelen": ("wheels", "Tyre extras", "Banden - onderdelen"),
    "Binnenband": ("wheels", "Inner tubes", "Binnenbanden"),
    "Stuur": ("cockpit", "Handlebar", "Stuur"),
    "Stuurpen": ("cockpit", "Stem", "Stuurpen"),
    "Stuur/stuurpen (geïntegreerd)": ("cockpit", "Integrated bar & stem", "Stuur/stuurpen (geïntegreerd)"),
    "Stuurlint": ("cockpit", "Bar tape", "Stuurlint"),
    "Handvatten": ("cockpit", "Grips", "Handvatten"),
    "Handlebar Plugs": ("cockpit", "Bar end plugs", "Stuurdopjes"),
    "Extensie": ("cockpit", "Aero extensions", "Opzetstuur"),
    "Stuur - onderdelen": ("cockpit", "Handlebar extras", "Stuur - onderdelen"),
    "Computer": ("cockpit", "Computer", "Computer"),
    "Zadel": ("saddle", "Saddle", "Zadel"),
    "Zadelpen": ("saddle", "Seatpost", "Zadelpen"),
    "Motor": ("electric", "Motor", "Motor"),
    "Accu": ("electric", "Battery", "Accu"),
    "Battery": ("drivetrain", "Shifting battery", "Accu schakeling"),
    "Oplader": ("electric", "Charger", "Oplader"),
    "Gewicht": ("weight", "Weight", "Gewicht"),
    "Weight": ("weight", "Weight", "Gewicht"),
    "Gewichtslimiet": ("weight", "Weight limit", "Gewichtslimiet"),
    "Tas": ("extras", "Bag", "Tas"),
    "Bidonhouder": ("extras", "Bottle cage", "Bidonhouder"),
    "Bidon": ("extras", "Bottle", "Bidon"),
    # Labels from the brand_scrapers brands (Specialized, Giant, Cannondale, Cube, Factor).
    "Frameset": ("frame", "Frameset", "Frame plus vork"),
    "Head Tube Diameter": ("frame", "Head tube diameter", "Diameter balhoofdbuis"),
    "Cable Routing": ("frame", "Cable routing", "Kabelgeleiding"),
    "Axle": ("frame", "Axles", "Assen"),
    "Axle type": ("frame", "Axles", "Assen"),
    "Hub Width": ("wheels", "Hub width", "Naafbreedte"),
    "Demper": ("frame", "Suspension", "Vering"),
    "Vering": ("frame", "Suspension", "Vering"),
    "Opslag": ("frame", "Storage", "Opbergvak"),
    "SWAT": ("frame", "Storage", "Opbergvak"),
    "Aandrijving": ("drivetrain", "Drivetrain", "Aandrijving"),
    "Aandrijving/wielen": ("drivetrain", "Drivetrain", "Aandrijving"),
    "Achterrem": ("brakes", "Rear brake", "Achterrem"),
    "Remtype": ("brakes", "Brake type", "Remtype"),
    "Brake interface": ("brakes", "Rotor mount", "Schijfbevestiging"),
    "Max Rotor Size": ("brakes", "Max rotor size", "Maximale schijfmaat"),
    "Wielen": ("wheels", "Wheels", "Wielen"),
    "Wheelset": ("wheels", "Wheels", "Wielen"),
    "Naven": ("wheels", "Hubs", "Naven"),
    "Rim height": ("wheels", "Rim depth", "Velghoogte"),
    "Rim width": ("wheels", "Rim width", "Velgbreedte"),
    "Wielmaat": ("wheels", "Wheel size", "Wielmaat"),
    "Bandenmaat": ("wheels", "Tyre size", "Bandenmaat"),
    "Voorband": ("wheels", "Front tyre", "Voorband"),
    "Achterband": ("wheels", "Rear tyre", "Achterband"),
    "Weights": ("wheels", "Wheel weight", "Gewicht wielen"),
    "Opzetstuur": ("cockpit", "Aero extensions", "Opzetstuur"),
    "Arm Rest Kit": ("cockpit", "Arm rests", "Armsteunen"),
    "Zadelpenklem": ("saddle", "Seat clamp", "Zadelpenklem"),
    "Saddle Rail Clamps": ("saddle", "Saddle rail clamps", "Zadelklemmen"),
    "Framegewicht": ("weight", "Frame weight", "Framegewicht"),
    "Extra's": ("extras", "Extras", "Extra's"),
    "Uitrusting": ("extras", "Extras", "Extra's"),
    "Extras": ("extras", "Extras", "Extra's"),
    "Accessories": ("extras", "Accessories", "Accessoires"),
    "Storage": ("extras", "Storage", "Opbergvak"),
    "Hydration": ("extras", "Bottle mounts", "Bidonhouders"),
    "Rack": ("extras", "Rack", "Bagagedrager"),
    "Voorlicht": ("extras", "Front light", "Voorlicht"),
    "Achterlicht": ("extras", "Rear light", "Achterlicht"),
    "Spatborden": ("extras", "Mudguards", "Spatborden"),
    "Bagagedrager": ("extras", "Rack", "Bagagedrager"),
    "Standaard": ("extras", "Kickstand", "Standaard"),
    "Bel": ("extras", "Bell", "Bel"),
    # Specialized's and Trek's labels on their own product pages (the current Trek API, older pages)
    "REAR SHOCK": ("frame", "Suspension", "Vering"),
    "CHAINRINGS": ("drivetrain", "Chainring", "Kettingblad"),
    "Chainrings": ("drivetrain", "Chainring", "Kettingblad"),
    "TANDWIELEN": ("drivetrain", "Cassette", "Cassette"),
    "Balhoofdstelonderdeel (zie ook: Lager)": ("frame", "Headset", "Balhoofdstel"),
    "Lager": ("frame", "Bearings", "Lagers"),
    "Spacer": ("cockpit", "Spacers", "Spacers"),
    "Cover": ("cockpit", "Cover", "Afdekkap"),
    "Binder": ("saddle", "Seat clamp", "Zadelpenklem"),
    "Vulring": ("cockpit", "Spacers", "Spacers"),
    "Naafhuis": ("wheels", "Hub shell", "Naafhuis"),
    "Valve": ("wheels", "Valves", "Ventielen"),
    "Ketting - onderdelen": ("drivetrain", "Chain parts", "Kettingonderdelen"),
    "Crankarm": ("drivetrain", "Crank arm", "Crankarm"),
    "Remmenset": ("brakes", "Brakes", "Remmen"),
    "Schokdemper": ("frame", "Shock", "Schokdemper"),
    "E-bikesysteem": ("electric", "E-bike system", "E-bikesysteem"),
    "Controller": ("electric", "Controller", "Bediening"),
    "Controller - onderdelen": ("electric", "Controller parts", "Bedieningsonderdelen"),
    "Motor - onderdelen": ("electric", "Motor parts", "Motoronderdelen"),
    "Stroomkabel": ("electric", "Power cable", "Stroomkabel"),
    "Computer - onderdelen": ("electric", "Display parts", "Displayonderdelen"),
    "Verlichting": ("extras", "Lights", "Verlichting"),
    "Spatbord": ("extras", "Mudguards", "Spatborden"),
    "Armor": ("extras", "Frame protection", "Framebescherming"),
    "Framebeschermers": ("extras", "Frame protection", "Framebescherming"),
    "Beugel": ("extras", "Bracket", "Beugel"),
    "Gereedschap": ("extras", "Tools", "Gereedschap"),
    "Div. fietsonderdelen": ("other", "Other parts", "Overige onderdelen"),
    "Placeholder": ("other", "Other", "Overig"),
}
# Without a motor, a battery and charger belong to electronic shifting (Di2, AXS), not to an e-bike.
NO_MOTOR_GROUP = {"electric": "drivetrain"}

# Tiers for the other parts: (tier, regex on lowercased text without accents). The first pattern that
# matches wins, so specific names come before generic words ("Aeolus Pro ... OCLV Carbon" is an Aeolus
# Pro, not just carbon). Placements come from each brand's own hierarchy and are a first pass: move a
# pattern when a part lands in the wrong tier.
PART_TIERS = {
    # Read with the model name, which carries Canyon's carbon grade ("Ultimate CF SLX 8").
    "frame": [
        (5, r"\b900\s+series\b(?!\s+alpha)|oclv\s*900|\bcfr\b|\bfact\s*12r|s-?works|advanced\s+sl\b|lab\s*71|hmx[\s-]*sl\b"
            r"|pitch-based"),
        (4, r"\b[678]00\s+series\b(?!\s+alpha)|oclv\s*[678]00|\bcf\s*slx\b|\bfact\s*1[01]r|advanced\s+pro\b|hi-?mod|\bhmx\b"
            r"|\bomx\b|c:?68x|titani?um|titaan|pan-based|toray|textreme"),
        (3, r"\b[345]00\s+series\b(?!\s+alpha)|oclv\s*[345]00|\bcf\s*sl\b|\bcf\b|\bfact\s*[89]r|\badvanced\b|ballistec"
            r"|\bhmf\b|\bomr\b|c:?62|carbon|\boclv\b"),
        (1, r"\b[12]00\s+series\s+alpha|\bsteel\b|\bstaal\b|hi-?ten"),
        (2, r"alumini?um|\balloy\b|lichtmetaal|\balr\b|\bal\b|caad|smartform|aluxx|alpha"),
    ],
    "fork": [
        (5, r"\bslr\b|\brsl\b|full foil"),
        (4, r"carbon\s+stuurbuis|carbon\s+steerer|uit een stuk|one-piece|full carbon"),
        (3, r"carbon|\bcf\b"),
        (1, r"\bsteel\b|\bstaal\b"),
        (2, r"alumini?um|\balloy\b|lichtmetaal"),
    ],
    # Cassettes, chains and cranksets that don't name their groupset.
    "drivetrain": [
        (5, r"xg-?1290|xg-?1299|xg-?1391|hg-?901|cs-?r9\d0\d|m9100"),
        (4, r"xg-?1270|xg-?1271|xg-?1371|hg-?701|cs-?r8\d0\d|m8100|rotor|aldhu|\bsrm\b"),
        (3, r"xg-?1250|xg-?1251|xg-?1351|hg-?710|hg-?700|hg-?601|m7100|m7000|praxis.*carbon|carbon"),
        (2, r"pg-?1231|pg-?1130|pc-?1130|hg-?500|hg-?54\b|lg500|lg700|microshift|m6100|miche|praxis"),
        (1, r"hg-?400|hg-?53\b|hg-?71\b|hg-?31\b|lg300|fsa\s+omega|fsa\s+vero|prowheel|rs200"),
    ],
    # Brake calipers and levers that don't name their groupset. Canyon lists rotors here too.
    "brakes": [
        (5, r"cl900|mt900|rt900"),
        (4, r"cl800|mt800|rt800|paceline"),
        (3, r"rt-?70\b|cl700|centerline\s*x"),
        (1, r"mechani|tektro|dual-pivot|velgrem|\bmt20\d\b|rt-?10\b|rt-?26\b"),
        (2, r"hydraul|centerline|rt-?5\d\b|rt-?6\d\b"),
    ],
    "rotors": [
        (5, r"cl900|mt900|rt900"),
        (4, r"cl800|mt800|rt800|paceline"),
        (3, r"rt-?70\b|cl700|centerline\s*x"),
        (2, r"centerline|rt-?5\d\b|rt-?6\d\b"),
        (1, r"rt-?10\b|rt-?26\b|tektro"),
    ],
    "wheels": [
        (5, r"aeolus\s+rsl|\brsl\b|[ae]rc\s*1[14]00|\bclx\b|\bnsw\b|cosmic\s+ultimate|\benve\b|reynolds|princeton"
            r"|black\s+inc|cadex"),
        (4, r"aeolus\s+pro|[ae]rc\s*1[68]00|grc\s*1[14]00|rapide\s+c|\bc38\b|terra\s+cl|alpinist\s+cl|zipp\s*(?:303|353|404|454)"
            r"|firecrest|cosmic\s+slr|racing\s+zero|\bslr\s*[01]\b|reserve|newmen\s+advanced|vision\s+metron"),
        (3, r"aeolus\s+elite|zipp|[pe]r?\s*1600|ksyrium|racing\s+[34]\b|\bslr\s*2\b|grc\s*1[68]00|carbon|\boclv\b"
            r"|vision\s+sc\b"),
        (2, r"paradigm\s+(?:sl|elite|pro)\b|racing\s+[56]\b|aksium|r\s*470|[pe]\s*1800|x\s*1900|g\s*540|newmen"
            r"|vision\s+(?:team|trimax)|\brs\s*(?:171|300|500)\b"),
        (1, r"paradigm|racing\s+7|formula|bontrager\s+tubeless\s+ready|\brs\s*0?10\b|\brs\s*100\b"),
        # A DT Swiss wheelset named by its hubs ("DT swiss wielen met naaf 240"), after the named wheels above.
        (4, r"dt\s*swiss\b.*\b(?:180|240)\b"),
        (3, r"dt\s*swiss\b.*\b350\b"),
    ],
    "hubs": [
        (5, r"dt\s*swiss\s*(?:180|240)"),
        (4, r"dt\s*swiss\s*350|aeolus\s+pro"),
        (3, r"dt\s*swiss\s*370"),
        (1, r"formula|affinity|bontrager\s+lichtmetaal"),
    ],
    "tyres": [
        (5, r"\btt\b|aero\s*111|\brs\b|pro\s+one\s+(?:aero|tt)|corsa\s+pro|aeolus\s+rsl|girona\s+rsl|\brsl\b"
            r"|s-?works\s+turbo|cotton|gavia\s+course\s+0"),
        (4, r"5000|grand\s+prix|pro\s+one|p\s*zero\s+race|\br[34]\b|team\s+issue|girona\s+pro|kwaremont\s+pro|x-one"
            r"|g-one\s+rs?\b|\bcorsa\b|turbo|cadex|gavia\s+course"),
        (3, r"schwalbe\s+one|(?<!-)\bone\b|\br2\b|g-one\s+allround|grand\s+sport\s+race|\bpro\b|gavia\s+fondo|vulpine"),
        (2, r"g-one\s+comp|gr1\s+expert|\bexpert\b|roadsport|gavia\s+ac|rubino"),
        (1, r"\br1\b|lugano|ultra\s+sport|gr1\s+comp|\bcomp\b|\bcity\b"),
    ],
    "handlebar": [
        (5, r"\brsl\b|cp00[1-9]\d|rapide\s+cockpit"),
        (4, r"carbon|\boclv\b|\bcf\b|contact\s+slr"),
        (3, r"\bpro\b|contact\s+sl\b"),
        (1, r"\bcomp\b|satellite"),
        (2, r"\belite\b|lichtmeta|\balloy\b|alumini?um"),
    ],
    "stem": [
        (5, r"\brsl\b"),
        (4, r"rcs\s+pro|carbon"),
        (3, r"\bpro\b"),
        (1, r"\bcomp\b"),
        (2, r"\belite\b|lichtmeta|\balloy\b|alumini?um"),
    ],
    "integrated": [
        (5, r"carbon|\boclv\b|\brsl\b|\bcf\b"),
        (4, r"."),
    ],
    "saddle": [
        (5, r"\b3d\b|mirror|adaptive|\brsl\b"),
        (4, r"carbon|carbonio|\bcf\b|\br1\b|\bpro\b"),
        (3, r"holle|hollow|austenite|titan|\bti\b|\br3\b|\belite\b|\bslr\b|\bflite\b|fleet\s+sl\b"),
        (1, r"stalen|\bsteel\b|selle\s+royal|\bh1\b"),
        (2, r"chromo|\br5\b|\bcomp\b|\bwatt\b|model\s+x|transiro|aliante|montrose"),
    ],
    "seatpost": [
        (5, r"speed\s+concept|^(?=.*carbon)(?=.*(?:aero|seatmast))"),
        (4, r"carbon|\bcf\b"),
        (1, r"\bcomp\b|6061"),
        (2, r"lichtmeta|\balloy\b|alumini?um"),
    ],
    # E-bike motors. A light-assist motor is a choice, not a downgrade, so both classes reach the top.
    "motor": [
        (5, r"hpr\s*50|hpr\s*60|cx\s+race|avinox"),
        (4, r"performance\s+line\s+cx|\bcx\b|ep8|ep801|fazua|ride\s*60|sl\s*1\.\d|mahle\s+x20|\bx20\b"),
        (3, r"performance\s+line|\bep6|ep600|e7000|steps"),
        (2, r"active\s+line|naafmotor|hub\s+motor|\bx35\b|hyena|bafang"),
    ],
}
# Spec labels -> the part tables tried in order; "groupset" reads the groupset name first.
SPEC_PARTS = {
    "Frame": ("frame",), "Frame plus vork": ("frame",), "Material": ("frame",),
    "Voorvork": ("fork",),
    "Shifter": ("groupset",), "Voorderailleur": ("groupset",), "Achterderailleur": ("groupset",),
    "Crankstel": ("groupset", "drivetrain"), "Cassette": ("groupset", "drivetrain"),
    "Ketting": ("groupset", "drivetrain"),
    "Frameset": ("frame",),
    "Aandrijving": ("groupset",), "Aandrijving/wielen": ("groupset",),
    "Rem": ("groupset", "brakes"), "Achterrem": ("groupset", "brakes"), "Remgreep": ("groupset", "brakes"),
    "Remschijf": ("rotors",),
    "Wiel voor": ("wheels",), "Wiel achter": ("wheels",), "Velg": ("wheels",),
    "Wheelset": ("wheels",),
    "Naaf voor": ("hubs",), "Naaf achter": ("hubs",), "Naven": ("hubs",),
    # Canyon sometimes puts the wheels in the tyre field ("DT Swiss ARC 1400 DICUT").
    "Buitenband": ("tyres", "wheels"), "Voorband": ("tyres",), "Achterband": ("tyres",),
    "Stuur": ("handlebar",), "Stuurpen": ("stem",), "Stuur/stuurpen (geïntegreerd)": ("integrated",),
    "Zadel": ("saddle",), "Zadelpen": ("seatpost",),
    "Motor": ("motor",),
}
# Weight tiers by discipline, from the brand's stated weight: the upper limit in kg for tiers 5, 4, 3 and 2;
# anything heavier is tier 1. Frames and mountain bikes aren't rated on weight yet.
WEIGHT_TIERS = {
    "road": (7.0, 7.8, 8.8, 10.0),
    "gravel": (8.0, 8.8, 9.6, 10.5),
    "tt": (8.8, 9.3, 9.8, 10.5),
    "fitness": (9.5, 10.5, 11.5, 13.0),
    "ebike": (12.0, 13.5, 15.0, 17.0),
}
# How much each spec group counts toward the bike's overall tier. The frame group is rated on the frame
# alone when it has one, so a carbon fork doesn't lift an aluminium frame. Groups without a tier are left out
# and the rest re-weighted.
TIER_WEIGHTS = {"frame": 30, "drivetrain": 25, "wheels": 20, "weight": 10, "electric": 10, "brakes": 5,
                "cockpit": 5, "saddle": 5}

# Swatch colours for colour names: the first word found wins; "dark" and "light" shade it.
# Brands' fancy names (Kaze, Aurora, team replicas) have no word here and show as a striped
# swatch, or as a crop of that colour's photo when we have one.
COLOUR_WORDS = [
    ("midnight", "#1f2433"), ("black", "#1b1b1f"), ("stealth", "#26272b"), ("obsidian", "#23232a"),
    ("phantom", "#202024"), ("vapor", "#2a2b30"), ("mirage", "#2b2b30"), ("carbon", "#2e2f33"),
    ("white", "#f4f4f2"), ("crystal", "#eef0f2"), ("silver", "#c3c7cc"), ("mercury", "#b9bdc2"),
    ("chrome", "#c9ccd1"), ("grey", "#8a8d93"), ("gray", "#8a8d93"), ("lillet", "#a7a29a"),
    ("navy", "#1f2f5a"), ("movistar", "#1d3f8f"), ("blue", "#2a5db0"), ("sky", "#6fa3d8"),
    ("teal", "#1f8a8a"), ("cactus", "#6f8f5a"), ("acid", "#a8c62c"), ("green", "#3c8d4a"),
    ("red", "#c0282d"), ("blaze", "#d2452a"), ("berry", "#8e2a54"), ("pink", "#e58aa8"),
    ("coral", "#ea7a6a"), ("orange", "#e36b1e"), ("sugar", "#b4652e"), ("bronze", "#9c6b3f"),
    ("tan", "#c7a77b"), ("champagne", "#d8c7a0"), ("gold", "#c9a13b"), ("purple", "#6b4fa0"),
]
