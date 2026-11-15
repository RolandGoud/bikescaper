"""Articles on the risks of buying a stolen bike, shown as slides on the home page (templates/home.html).

The text is English and goes through `_()` in the template, so each line needs a Dutch translation in
i18n.NL. `site` is what the button says ("Lees op rdw.nl"); `country` is where the article applies.
"""

ARTICLES = [
    {"url": "https://www.rdw.nl/kopen-of-verkopen/controleren-of-een-fiets-gestolen-is",
     "site": "rdw.nl", "country": "NL", "tag": "Official check",
     "title": "Is this bike stolen? Check the frame number",
     "text": "Look up the frame number in the RDW register. Note: “not registered” doesn't mean the bike is clean."},
    {"url": "https://www.politie.nl/informatie/hoe-weet-ik-of-de-tweedehands-fiets-die-ik-koop-niet-gestolen-is.html",
     "site": "politie.nl", "country": "NL", "tag": "Police",
     "title": "How to spot a stolen bike",
     "text": "A lock forced off, a dealer sticker torn away, grinding marks where a postcode was: the signs the police look for."},
    {"url": "https://www.politie.nl/informatie/heling-is-strafbaar.html",
     "site": "politie.nl", "country": "NL", "tag": "The law",
     "title": "Buying a stolen bike is a crime",
     "text": "Heling is punishable even if you only could have suspected the bike was stolen: up to a year in prison or a fine."},
    {"url": "https://www.politie.nl/informatie/ik-heb-een-fiets-gekocht-die-toch-gestolen-blijkt-te-zijn.-wat-nu.html",
     "site": "politie.nl", "country": "NL", "tag": "Police",
     "title": "Bought a bike that turns out to be stolen?",
     "text": "A great bike at a giveaway price is a warning sign. What happens if you bought in good faith, and how to play it safe."},
    {"url": "https://www.stopheling.nl/",
     "site": "stopheling.nl", "country": "NL", "tag": "Police",
     "title": "Stop Heling: check the serial number with the police",
     "text": "See straight away whether a bike or part has been reported stolen."},
    {"url": "https://mybike.belgium.be/nl/",
     "site": "mybike.belgium.be", "country": "BE", "tag": "Official check",
     "title": "MyBike: has the bike been reported stolen?",
     "text": "Belgium's federal bike register. Enter the number on the bike's MyBike sticker to see whether it's been reported stolen."},
]
