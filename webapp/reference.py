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
