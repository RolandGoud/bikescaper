"""Hand-entered reference data the scraper does not collect yet.

Everything here is a stop-gap until the reworked scraper stores model years,
size charts and geometry per model. Each table says how sure we are, and the
check report shows that to the user.
"""

# Model years each Trek generation was sold as new (first, last; None = still sold).
# Entered by hand from launch dates, not scraped: verify against Trek's archive
# before relying on them.
GENERATIONS = {
    ("Trek", "domane", 3): (2020, 2022),
    ("Trek", "domane", 4): (2023, None),
    ("Trek", "madone", 7): (2023, 2024),
    ("Trek", "madone", 8): (2025, None),
    ("Trek", "checkpoint", 2): (2022, 2024),
    ("Trek", "checkpoint", 3): (2025, None),
}
GENERATIONS_NOTE = "Model years entered by hand from launch dates; not yet checked against the brand's archive."

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
}
SIZE_NOTE = "Generic chart for this brand, not this model's own size chart yet."

# Groupsets from entry level up. `rank` lets the value check spot a downgrade.
GROUPSETS = [
    # (key, display name, regex on lowercased text, rank)
    ("claris", "Shimano Claris", r"\bclaris\b", 1),
    ("sora", "Shimano Sora", r"\bsora\b", 2),
    ("cues", "Shimano CUES", r"\bcues\b", 2),
    ("tiagra", "Shimano Tiagra", r"\btiagra\b", 3),
    ("grx", "Shimano GRX", r"\bgrx\b", 4),
    ("105", "Shimano 105", r"(?<![\d.,x])105(?![\d.,]|\s*(?:mm|kg|cm))", 4),
    ("ultegra", "Shimano Ultegra", r"\bultegra\b", 5),
    ("dura-ace", "Shimano Dura-Ace", r"\bdura[\s-]?ace\b", 6),
    ("apex", "SRAM Apex", r"\bapex\b", 3),
    ("rival", "SRAM Rival", r"\brival\b", 4),
    ("force", "SRAM Force", r"\bforce\b", 5),
    ("red", "SRAM Red", r"\bsram\s+red\b|\bred\s+(?:axs|etap)\b", 6),
    ("centaur", "Campagnolo Centaur", r"\bcentaur\b", 3),
    ("chorus", "Campagnolo Chorus", r"\bchorus\b", 5),
    ("ekar", "Campagnolo Ekar", r"\bekar\b", 5),
    ("record", "Campagnolo Record", r"\b(?:super\s+)?record\b", 6),
]
ELECTRONIC = r"\bdi2\b|\baxs\b|\betap\b|\beps\b"

# Brands the site covers. `site` is the brand's own Dutch site the catalogue
# collector should read; only Trek and Canyon have a working scraper so far.
# The URLs for the newer brands are unverified starting points.
BRANDS = [
    {"name": "Trek", "site": "https://www.trekbikes.com/nl/nl_NL/", "scraper": True},
    {"name": "Canyon", "site": "https://www.canyon.com/nl-nl/", "scraper": True},
    {"name": "Specialized", "site": "https://www.specialized.com/nl/nl", "scraper": False},
    {"name": "Giant", "site": "https://www.giant-bicycles.com/nl", "scraper": False},
    {"name": "Cannondale", "site": "https://www.cannondale.com/nl-nl", "scraper": False},
    {"name": "Scott", "site": "https://www.scott-sports.com/nl/nl/", "scraper": False},
    {"name": "Orbea", "site": "https://www.orbea.com/nl-nl/", "scraper": False},
    {"name": "Cube", "site": "https://www.cube.eu/nl-nl/", "scraper": False},
    {"name": "Factor", "site": "https://factorbikes.com/", "scraper": False},
]
BRAND_NAMES = [b["name"] for b in BRANDS]

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
# current line-ups and should be confirmed once their scrapers run.
FAMILY_DISCIPLINES = {
    "road": {
        "Trek": ["madone", "emonda", "domane"],
        "Canyon": ["aeroad", "ultimate", "endurace"],
        "Specialized": ["tarmac", "aethos", "allez", "roubaix"],
        "Giant": ["propel", "tcr", "defy"],
        "Cannondale": ["systemsix", "supersix", "caad", "synapse"],
        "Scott": ["foil", "addict", "speedster"],
        "Orbea": ["orca", "avant"],
        "Cube": ["litening", "agree", "attain"],
        "Factor": ["ostro", "o", "monza"],
    },
    "gravel": {
        "Trek": ["checkpoint", "checkmate", "boone"],
        "Canyon": ["grail", "grizl", "inflite"],
        "Specialized": ["diverge", "crux"],
        "Giant": ["revolt", "tcx"],
        "Cannondale": ["topstone", "superx"],
        "Orbea": ["terra"],
        "Cube": ["nuroad", "cross"],
        "Factor": ["explorer"],
    },
    "tt": {
        "Trek": ["speed"],
        "Canyon": ["speedmax"],
        "Specialized": ["shiv"],
        "Giant": ["trinity"],
        "Scott": ["plasma"],
        "Orbea": ["ordu"],
        "Cube": ["aerium"],
        "Factor": ["hanzo"],
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
    "Schijfdiameter": ("brakes", "Rotor size", "Schijfdiameter"),
    "Wiel voor": ("wheels", "Front wheel", "Wiel voor"),
    "Wiel achter": ("wheels", "Rear wheel", "Wiel achter"),
    "Naaf voor": ("wheels", "Front hub", "Naaf voor"),
    "Naaf achter": ("wheels", "Rear hub", "Naaf achter"),
    "Velg": ("wheels", "Rims", "Velgen"),
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
    "Stuur - onderdelen": ("cockpit", "Handlebar extras", "Stuur - onderdelen"),
    "Computer": ("cockpit", "Computer", "Computer"),
    "Zadel": ("saddle", "Saddle", "Zadel"),
    "Zadelpen": ("saddle", "Seatpost", "Zadelpen"),
    "Motor": ("electric", "Motor", "Motor"),
    "Accu": ("electric", "Battery", "Accu"),
    "Oplader": ("electric", "Charger", "Oplader"),
    "Gewicht": ("weight", "Weight", "Gewicht"),
    "Weight": ("weight", "Weight", "Gewicht"),
    "Gewichtslimiet": ("weight", "Weight limit", "Gewichtslimiet"),
    "Tas": ("extras", "Bag", "Tas"),
    "Bidonhouder": ("extras", "Bottle cage", "Bidonhouder"),
    "Bidon": ("extras", "Bottle", "Bidon"),
}
# Without a motor, a battery and charger belong to electronic shifting (Di2, AXS), not to an e-bike.
NO_MOTOR_GROUP = {"electric": "drivetrain"}
