"""Articles on buying a stolen bike, shown as slides on the home page (templates/home.html).

The text is English and goes through `_()` in the template, so each line needs a Dutch translation in
i18n.NL. `site` is what the button says ("Lees op rdw.nl"); `country` is where the article applies.
"""

ARTICLES = [
    {"url": "https://www.rdw.nl/kopen-of-verkopen/controleren-of-een-fiets-gestolen-is",
     "site": "rdw.nl", "country": "NL", "tag": "Official check",
     "title": "Is this bike stolen? Check the frame number",
     "text": "Look up the frame number in the RDW register. Note: “not registered” doesn't mean the bike is clean."},
    {"url": "https://www.stopheling.nl/",
     "site": "stopheling.nl", "country": "NL", "tag": "Police",
     "title": "Stop Heling: check the serial number with the police",
     "text": "See straight away whether a bike or part has been reported stolen."},
    {"url": "https://www.anwb.nl/fiets/fiets-aankooptips/tweedehands-fiets-kopen",
     "site": "anwb.nl", "country": "NL", "tag": "Buying guide",
     "title": "Buying a used bike: what to look out for",
     "text": "Tips for the viewing, the papers and the test ride, so you don't end up with a bad buy."},
    {"url": "https://mybike.belgium.be/nl/",
     "site": "mybike.belgium.be", "country": "BE", "tag": "Official check",
     "title": "MyBike: has the bike been reported stolen?",
     "text": "Belgium's federal bike register, where you can check a bike's frame number."},
    {"url": "https://mobilit.belgium.be/nl/duurzame-mobiliteit/fietsen/fietsdiefstal-en-verzekering",
     "site": "mobilit.belgium.be", "country": "BE", "tag": "Government",
     "title": "Bike theft and insurance",
     "text": "How registering your bike works, and what to do when it's stolen."},
]
