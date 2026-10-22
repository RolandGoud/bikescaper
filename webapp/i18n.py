"""Dutch and English for the site.

English text is the key. `gettext` (`_` in templates) translates it for the current request's
language; `Msg` does the same lazily, so the checks can build messages without knowing the
language and the page renders them in whichever language the visitor picked.
"""
from contextvars import ContextVar

LANGUAGES = {"nl": "Nederlands", "en": "English"}
DEFAULT_LANGUAGE = "nl"

current_language = ContextVar("current_language", default=DEFAULT_LANGUAGE)


def gettext(text, **kwargs):
    if current_language.get() == "nl":
        text = NL.get(text, text)
    return text.format(**kwargs) if kwargs else text


class Msg:
    """A message translated when it is shown, not when it is made."""

    def __init__(self, text, **kwargs):
        self.text = text
        self.kwargs = kwargs

    def __str__(self):
        return gettext(self.text, **self.kwargs)

    def __format__(self, spec):
        return format(str(self), spec)

    def __html__(self):
        from markupsafe import escape
        return str(escape(str(self)))

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.text)

    def __repr__(self):
        return f"Msg({self.text!r})"


def join(*parts):
    """Join messages with a space, dropping empty ones."""
    parts = [p for p in parts if p]
    return Msg(" ".join("{p%d}" % i for i in range(len(parts))), **{f"p{i}": p for i, p in enumerate(parts)})


def join_list(parts):
    """Join messages with a comma, dropping empty ones."""
    parts = [p for p in parts if p]
    return Msg(", ".join("{p%d}" % i for i in range(len(parts))), **{f"p{i}": p for i, p in enumerate(parts)})


NL = {
    # navigation and layout
    "Check a listing": "Advertentie checken",
    "Listings": "Advertenties",
    "Models": "Modellen",
    "Size finder": "Maatzoeker",
    "Value": "Waarde",
    "Main": "Hoofdmenu",
    "Language": "Taal",
    "Bike Compare · prototype": "Bike Compare · prototype",
    "How it works": "Zo werkt het",
    "Data sources": "Bronnen",
    "Not affiliated with Marktplaats or any bike brand.": "Niet verbonden aan Marktplaats of een fietsmerk.",

    # home
    "Second-hand bike check · Netherlands": "Tweedehands fietscheck · Nederland",
    "Is that bike <span>really</span> what the seller says?":
        "Is die fiets <span>echt</span> wat de verkoper zegt?",
    "Paste the ad. We match it to the original model and tell you if the age, specs, size and asking price add up.":
        "Plak de advertentie. Wij zoeken het originele model erbij en vertellen je of de leeftijd, "
        "onderdelen, maat en vraagprijs kloppen.",
    "What a check tells you": "Wat een check je vertelt",
    "01 · AGE": "01 · LEEFTIJD",
    "02 · SPECS": "02 · ONDERDELEN",
    "03 · SIZE": "03 · MAAT",
    "04 · VALUE": "04 · WAARDE",
    "Is it as old as stated?": "Is hij zo oud als gezegd?",
    "We compare the claimed year with the years the model was sold.":
        "We vergelijken het opgegeven jaar met de jaren waarin het model verkocht werd.",
    "Are the parts original?": "Zijn de onderdelen origineel?",
    "Groupset, frame and brakes are checked against the factory spec sheet.":
        "Groep, frame en remmen worden vergeleken met de fabrieksspecificaties.",
    "Will it fit you?": "Past hij bij je?",
    "The frame size is turned into a rider height range.": "We vertalen de framemaat naar een lichaamslengte.",
    "Is the price fair?": "Is de prijs eerlijk?",
    "A fair price range from the new price, age and condition.":
        "Een eerlijke prijs op basis van nieuwprijs, leeftijd en staat.",
    "Recently checked": "Net gecheckt",
    "See all listings": "Alle advertenties",
    "Brands we cover": "Merken",
    "Reference data comes from the brands' own Dutch catalogues. Dashed brands are coming next.":
        "De gegevens komen uit de Nederlandse catalogi van de merken zelf. Gestippelde merken volgen nog.",

    # check form
    "Ad title": "Titel van de advertentie",
    "From the Marktplaats ad": "Uit de Marktplaats-advertentie",
    "Ad text": "Advertentietekst",
    "We read the year, size, groupset and condition from it":
        "Hieruit halen we het jaar, de maat, de groep en de staat",
    "Asking price (€)": "Vraagprijs (€)",
    "Place": "Plaats",
    "Your height (cm)": "Je lengte (cm)",
    "Optional, e.g. 178": "Optioneel, bijv. 178",
    "Link to the ad": "Link naar de advertentie",
    "Optional, saved with the check": "Optioneel, wordt bij de check bewaard",
    "Check this bike": "Check deze fiets",
    "Paste at least the ad's title.": "Plak in elk geval de titel van de advertentie.",
    "How do you want to add the ad?": "Hoe wil je de advertentie toevoegen?",
    "Paste a link": "Plak een link",
    "Enter manually": "Zelf invullen",
    "Marktplaats or 2dehands. We read the title, text, price and photos for you.":
        "Marktplaats of 2dehands. Wij lezen de titel, tekst, prijs en foto's voor je uit.",
    "Paste the link to the ad.": "Plak de link naar de advertentie.",
    "{reason} Fill in the details yourself instead.": "{reason} Vul de gegevens dan zelf in.",
    "We can only read links from Marktplaats and 2dehands for now.":
        "We kunnen voorlopig alleen links van Marktplaats en 2dehands uitlezen.",
    "That ad no longer exists.": "Die advertentie bestaat niet meer.",
    "The site didn't let us read the ad.": "De site liet ons de advertentie niet uitlezen.",
    "The site didn't answer in time.": "De site reageerde niet op tijd.",
    "That link doesn't look like an ad.": "Die link lijkt geen advertentie te zijn.",
    "Photos from the ad": "Foto's uit de advertentie",
    "Photo {n} from the ad": "Foto {n} uit de advertentie",
    "Mooie racefiets, carbon frame, hydraulische schijfremmen...":
        "Mooie racefiets, carbon frame, hydraulische schijfremmen...",

    # listing cards
    "Matched to {name}": "Gekoppeld aan {name}",
    "Not matched": "Niet gekoppeld",
    "Asking {price}": "Vraagprijs {price}",
    "Age: {v}": "Leeftijd: {v}",
    "Specs: {v}": "Onderdelen: {v}",
    "Price: {v}": "Prijs: {v}",
    "No matching model yet": "Nog geen passend model",
    "[no photo yet]": "[nog geen foto]",

    # report
    "Check report": "Checkrapport",
    "PASTED AD": "GEPLAKTE ADVERTENTIE",
    "checked {date}": "gecheckt op {date}",
    "Matched to": "Gekoppeld aan",
    "{level} confidence": "zekerheid: {level}",
    "high": "hoog",
    "medium": "gemiddeld",
    "low": "laag",
    "chosen by you": "door jou gekozen",
    "Change match": "Ander model kiezen",
    "All models": "Alle modellen",
    "Open the ad": "Advertentie openen",
    "No matching model": "Geen passend model",
    "We don't have {brand} models in the catalogue yet. It's on the list of brands to collect next.":
        "We hebben nog geen modellen van {brand} in de catalogus. Dit merk staat op de lijst om toe te voegen.",
    "We couldn't find the brand and model in the title or text. Bike Compare covers {brands} for now; make sure the ad names the model, for example “Trek Domane SL 6”.":
        "We konden merk en model niet vinden in de titel of tekst. Bike Compare kent voorlopig {brands}; "
        "zorg dat het model in de advertentie staat, bijvoorbeeld “Trek Domane SL 6”.",
    "and": "en",
    "Browse the models we have": "Bekijk de modellen die we hebben",
    "AGE": "LEEFTIJD",
    "SPECS": "ONDERDELEN",
    "SIZE": "MAAT",
    "VALUE": "WAARDE",
    "Age check": "Leeftijd",
    "claimed": "opgegeven",
    "sold": "verkocht",
    "Serial number:": "Framenummer:",
    "ask for a photo of the sticker under the bottom bracket.": "vraag om een foto van de sticker onder de trapas.",
    "Spec comparison": "Onderdelen vergeleken",
    "PART": "ONDERDEEL",
    "ORIGINAL": "ORIGINEEL",
    "IN THE AD": "IN DE ADVERTENTIE",
    "RESULT": "RESULTAAT",
    "Size fit": "Maat",
    "Rider height in cm.": "Lichaamslengte in cm.",
    "Your height": "Je lengte",
    "Check fit": "Check pasvorm",
    "Open the size finder": "Open de maatzoeker",
    "Value estimate": "Waardeschatting",
    "Fair {low}–{high}": "Eerlijk {low}–{high}",
    "Asking {asking}": "Vraagprijs {asking}",
    "Scale €0 to {max}": "Schaal €0 tot {max}",
    "Fair range {low} to {high}, asking {asking}": "Eerlijke prijs {low} tot {high}, vraagprijs {asking}",
    "New price": "Nieuwprijs",
    "Model year used": "Gebruikt modeljaar",
    "Condition from the ad": "Staat volgens de advertentie",
    "not stated": "niet vermeld",
    "like new": "als nieuw",
    "used": "gebruikt",
    "damaged": "beschadigd",
    "Similar ads now": "Vergelijkbare advertenties",
    "[coming later]": "[volgt later]",
    "Ask the seller": "Vraag de verkoper",
    "Copy questions": "Vragen kopiëren",
    "Copied": "Gekopieerd",

    # listings page
    "Checked listings": "Gecheckte advertenties",
    "Every ad someone has checked here. Collecting ads automatically comes later, once we know what each site allows.":
        "Alle advertenties die hier gecheckt zijn. Automatisch advertenties verzamelen komt later, "
        "als we weten wat elke site toestaat.",
    "Filter by result": "Filter op resultaat",
    "All": "Alles",
    "Something doesn't add up": "Er klopt iets niet",
    "Needs a question": "Vraag het na",
    "No checks yet.": "Nog geen checks.",
    "Check your first listing": "Check je eerste advertentie",

    # models
    "{count} models from the brands' Dutch catalogues.": "{count} modellen uit de Nederlandse catalogi van de merken.",
    "All brands": "Alle merken",
    "Coming next": "Volgt nog",
    "All types": "Alle soorten",
    "Coming with the next brands": "Volgt met de volgende merken",
    "Road": "Racefiets",
    "Gravel & cyclocross": "Gravel & veldrijden",
    "Time trial & triathlon": "Tijdrit & triatlon",
    "Fitness & city": "Fitness & stad",
    "Mountain": "Mountainbike",
    "E-bike": "E-bike",
    "Other": "Overig",
    "From the model years in {brand}'s own photos; earlier years may be missing.": "Uit de modeljaren in de eigen foto's van {brand}; eerdere jaren kunnen ontbreken.",
    "No photo of this colour yet.": "Nog geen foto van deze kleur.",
    "Status": "Status",
    "Still sold": "Nog te koop",
    "Discontinued": "Uit productie",
    "Status unknown": "Status onbekend",
    "Only bikes still sold": "Alleen nog te koop",
    "Discontinued: this generation was sold until {year}.": "Uit productie: deze generatie werd verkocht tot {year}.",
    "Not checked against the catalogue yet.": "Nog niet gecontroleerd tegen de catalogus.",
    "Discontinued: missing from the last {n} catalogue scrapes, last seen {date}.": "Uit productie: ontbreekt in de laatste {n} catalogusscans, laatst gezien {date}.",
    "Discontinued: missing from the newest catalogue scrape ({latest}), last seen {date}.": "Uit productie: ontbreekt in de nieuwste catalogusscan ({latest}), laatst gezien {date}.",
    "In the {brand} catalogue on {date}.": "In de catalogus van {brand} op {date}.",
    "Frames": "Frames",
    "Frame & fork": "Frame & vork",
    "Drivetrain": "Aandrijving",
    "Wheels & tyres": "Wielen & banden",
    "Cockpit": "Cockpit",
    "Saddle & seatpost": "Zadel & zadelpen",
    "Motor & battery": "Motor & accu",
    "Weight": "Gewicht",
    "Accessories": "Accessoires",
    "Search models": "Modellen zoeken",
    "Search, e.g. Domane": "Zoek, bijv. Domane",
    "Search": "Zoeken",
    "New {price}": "Nieuw {price}",
    "No models match.": "Geen modellen gevonden.",
    "Model years": "Modeljaren",
    "now": "nu",
    "[not collected yet]": "[nog niet verzameld]",
    "Seen in catalogue": "In catalogus gezien",
    "Colours": "Kleuren",
    "{brand} product page": "Productpagina van {brand}",
    "Estimate a used price": "Schat een tweedehands prijs",
    "Spec sheet": "Specificaties",
    "As listed on the {brand} NL site on {date}.": "Zoals vermeld op de Nederlandse site van {brand} op {date}.",
    "Sizes": "Maten",
    "Under each size: stack / reach in mm.": "Onder elke maat: stack / reach in mm.",
    "Other {family} models": "Andere {family}-modellen",

    # size finder
    "Pick a brand and model and enter your height to see which frame sizes fit.":
        "Kies een merk en model en vul je lengte in om te zien welke framematen passen.",
    "Model": "Model",
    "All models (brand chart)": "Alle modellen (tabel van het merk)",
    "brand chart": "tabel van het merk",
    "{model} sizes for {height} cm": "Maten van {model} bij {height} cm",
    "pick a model for its own chart.": "kies een model voor de eigen tabel.",
    "Same chart for {count} models:": "Dezelfde tabel voor {count} modellen:",
    "{own} of {total} {brand} models have their own size chart.":
        "{own} van de {total} modellen van {brand} hebben een eigen maattabel.",
    "{own} of {total} {brand} models have their own sizes and geometry.":
        "{own} van de {total} modellen van {brand} hebben eigen maten en geometrie.",
    "Brand": "Merk",
    "Find my size": "Vind mijn maat",
    "Dark blue fits, light blue is borderline.": "Donkerblauw past, lichtblauw is twijfel.",
    "Generic chart for this brand": "Algemene tabel voor dit merk",
    "Generic chart, not {brand}'s own": "Algemene tabel, niet die van {brand} zelf",

    # value page
    "Value estimator": "Waardeschatter",
    "A rough fair price for a used bike from its new price, age and condition.":
        "Een globale eerlijke prijs voor een gebruikte fiets op basis van nieuwprijs, leeftijd en staat.",
    "Model": "Model",
    "Model year": "Modeljaar",
    "Condition": "Staat",
    "Normal use": "Normaal gebruikt",
    "Like new": "Als nieuw",
    "Visible wear": "Zichtbare gebruikssporen",
    "Damaged": "Beschadigd",
    "Optional": "Optioneel",
    "Estimate": "Schatten",
    "{low} to {high}": "{low} tot {high}",
    "Age": "Leeftijd",
    "{n} year": "{n} jaar",
    "{n} years": "{n} jaar",

    # how it works
    "The check": "De check",
    "You paste an ad's title and text. We read the seller's claims (brand, model, year, size, groupset, frame material, brakes and condition), find the closest model in our catalogue, and compare each claim with the original.":
        "Je plakt de titel en tekst van een advertentie. Wij halen eruit wat de verkoper beweert (merk, model, "
        "jaar, maat, groep, framemateriaal, remmen en staat), zoeken het best passende model in onze catalogus "
        "en vergelijken elke bewering met het origineel.",
    "We never open the ad for you: the check only uses what you paste.":
        "We openen de advertentie nooit zelf: de check gebruikt alleen wat jij plakt.",
    "{count} models from the brands' own sites, collected by the bikescaper. Road, gravel and time trial bikes only; e-bikes and mountain bikes aren't in yet.":
        "{count} modellen van de sites van de merken zelf, verzameld door de bikescaper. Alleen race-, gravel- en "
        "tijdritfietsen; e-bikes en mountainbikes zitten er nog niet in.",
    "Collected on {date}": "Verzameld op {date}",
    "Planned": "Gepland",
    "Limits of this prototype": "Beperkingen van dit prototype",
    "Model years are entered by hand for a few Trek generations only.":
        "Modeljaren zijn alleen voor een paar Trek-generaties met de hand ingevoerd.",
    "Trek, Canyon and Cannondale publish each model's own size chart. Specialized, Giant, Cube and Factor publish the sizes and geometry per model, but rider heights only in a general size guide.":
        "Trek, Canyon en Cannondale publiceren per model een eigen maattabel. Specialized, Giant, Cube en Factor geven per model de maten en geometrie, maar de lichaamslengte alleen in een algemene maattabel.",
    "The value is a simple age and condition curve. Comparable ads aren't used yet.":
        "De waarde is een eenvoudige berekening op leeftijd en staat. Vergelijkbare advertenties tellen nog niet mee.",
    "Only current-catalogue models are covered; older generations come with the reworked scraper.":
        "Alleen modellen uit de huidige catalogus; oudere generaties komen met de nieuwe scraper.",

    # checks: age
    "On sale in the {brand} NL catalogue on {date}.": "Te koop in de Nederlandse catalogus van {brand} op {date}.",
    "Year not stated": "Jaar niet vermeld",
    "The ad doesn't give a year. Ask for the invoice or the serial number.":
        "De advertentie noemt geen jaar. Vraag om de aankoopbon of het framenummer.",
    "Seller says {year}": "Verkoper zegt {year}",
    "We don't have the model years for this bike yet, so we can't confirm the age.":
        "We hebben de modeljaren van deze fiets nog niet, dus we kunnen de leeftijd niet bevestigen.",
    "Older than this model": "Ouder dan dit model",
    "Seller says {claimed}, but this generation was first sold as the {first} model. Either the year is wrong or it's an older generation we don't have yet.":
        "Verkoper zegt {claimed}, maar deze generatie kwam pas uit als model {first}. Het jaar klopt niet, "
        "of het is een oudere generatie die wij nog niet hebben.",
    "Probably the purchase year": "Waarschijnlijk het aankoopjaar",
    "This generation went on sale as the {first} model, in {launch}. {claimed} is likely when it was bought, not the model year.":
        "Deze generatie kwam in {launch} op de markt als model {first}. {claimed} is waarschijnlijk het "
        "aankoopjaar, niet het modeljaar.",
    "After this model was replaced": "Na de opvolger van dit model",
    "This generation was last sold as the {last} model. A {claimed} bike would be leftover stock.":
        "Deze generatie werd voor het laatst verkocht als model {last}. Een fiets uit {claimed} is dan oude voorraad.",
    "Adds up": "Klopt",
    "{name} was sold as new in {claimed}.": "De {name} werd in {claimed} nieuw verkocht.",
    "The seller gives this as the purchase year.": "De verkoper noemt dit het aankoopjaar.",
    "Model years entered by hand from launch dates; not yet checked against the brand's archive.":
        "Modeljaren met de hand ingevoerd op basis van introductiedata; nog niet gecontroleerd in het archief van het merk.",

    # checks: specs
    "Groupset": "Groep",
    "Frame": "Frame",
    "Brakes": "Remmen",
    "Wheels": "Wielen",
    "Tyres": "Banden",
    "Crankset": "Crankstel",
    "Saddle": "Zadel",
    "Not in our data": "Niet in onze gegevens",
    "Not stated": "Niet vermeld",
    "Ask seller": "Vraag verkoper",
    "Can't compare": "Niet te vergelijken",
    "Differs": "Wijkt af",
    "Matches": "Klopt",
    "Electronic in ad, mechanical original": "Elektronisch in advertentie, origineel mechanisch",
    "Check photos": "Bekijk de foto's",
    "Compare photos": "Vergelijk foto's",
    "Carbon": "Carbon",
    "Aluminium": "Aluminium",
    "Steel": "Staal",
    "Disc": "Schijfrem",
    "Rim": "Velgrem",
    "{n} part differs": "{n} onderdeel wijkt af",
    "{n} parts differ": "{n} onderdelen wijken af",
    "Not enough detail": "Te weinig details",
    "Upgrade, tier {a} to {b}": "Upgrade, niveau {a} naar {b}",
    "Downgrade, tier {a} to {b}": "Downgrade, niveau {a} naar {b}",
    "Same tier, different part": "Zelfde niveau, ander onderdeel",
    "Same tier": "Zelfde niveau",
    "{n} part downgraded": "{n} onderdeel lager",
    "{n} parts downgraded": "{n} onderdelen lager",
    "{n} part upgraded": "{n} onderdeel beter",
    "{n} parts upgraded": "{n} onderdelen beter",
    "Lowered for the downgraded parts.": "Verlaagd vanwege de mindere onderdelen.",
    "Do you still have the original {part} ({original})?": "Heb je de originele {part} nog ({original})?",
    "Matches the original": "Klopt met het origineel",
    "The seller mentions changed parts.": "De verkoper noemt vervangen onderdelen.",
    "Compared with the {brand} spec sheet from {date}.": "Vergeleken met de specificaties van {brand} van {date}.",
    "our catalogue": "onze catalogus",

    # spec tiers
    "Basic": "Basis",
    "Entry": "Instap",
    "Mid": "Midden",
    "Performance": "Performance",
    "Top": "Top",
    "Spec tier": "Specniveau",
    "Type": "Type",
    "Show": "Toon",
    "Spec tiers": "Specniveaus",
    "Spec tier {tier} of 5": "Specniveau {tier} van 5",
    "Not rated": "Niet beoordeeld",
    "Lower on": "Lager op",
    "All tiers": "Alle niveaus",
    "Each part is rated from tier 1 (basic) to 5 (top).": "Elk onderdeel krijgt een niveau van 1 (basis) tot 5 (top).",
    "How tiers work": "Zo werken de niveaus",
    "Every part on a model's spec sheet is rated on the same five tiers, whatever the brand. The frame, groupset, wheels, tyres, brakes, rotors, cockpit, saddle, seatpost, motor and weight each get a tier; parts we don't recognise yet are left unrated.":
        "Elk onderdeel op de specificaties van een model krijgt een niveau op dezelfde vijfpuntsschaal, welk merk het ook is. "
        "Frame, groep, wielen, banden, remmen, remschijven, stuur, zadel, zadelpen, motor en gewicht krijgen elk een niveau; "
        "onderdelen die we nog niet herkennen blijven zonder niveau.",
    "The bike's overall tier weighs the frame (30%), drivetrain (25%), wheels and tyres (20%), weight (10%), motor (10%, e-bikes only) and brakes, cockpit and saddle (5% each). In a listing check, a part that differs from the original is shown as an upgrade or a downgrade by comparing tiers.":
        "Het totaalniveau van de fiets weegt het frame (30%), de aandrijving (25%), wielen en banden (20%), gewicht (10%), "
        "motor (10%, alleen e-bikes) en remmen, stuur en zadel (elk 5%). Bij een advertentiecheck zie je aan de niveaus "
        "of een afwijkend onderdeel beter of minder is dan het origineel.",
    "Shimano Claris or Sora, entry aluminium or steel frame, basic alloy wheels.":
        "Shimano Claris of Sora, eenvoudig aluminium of stalen frame, eenvoudige aluminium wielen.",
    "Shimano Tiagra or CUES, SRAM Apex, aluminium frame, entry alloy wheels.":
        "Shimano Tiagra of CUES, SRAM Apex, aluminium frame, instap aluminium wielen.",
    "Shimano 105, SRAM Rival, entry carbon frame (Trek OCLV 500, Canyon CF), better alloy or entry carbon wheels.":
        "Shimano 105, SRAM Rival, instap carbon frame (Trek OCLV 500, Canyon CF), betere aluminium of instap carbon wielen.",
    "Shimano Ultegra, SRAM Force, performance carbon (OCLV 800, CF SLX), carbon wheels such as Aeolus Pro.":
        "Shimano Ultegra, SRAM Force, performance carbon (OCLV 800, CF SLX), carbon wielen zoals Aeolus Pro.",
    "Shimano Dura-Ace, SRAM Red, the brand's top carbon (OCLV 900, CFR), flagship wheels such as Aeolus RSL.":
        "Shimano Dura-Ace, SRAM Red, het beste carbon van het merk (OCLV 900, CFR), topwielen zoals Aeolus RSL.",

    # checks: size
    "Size not stated": "Maat niet vermeld",
    "Ask the seller for the frame size.": "Vraag de verkoper naar de framemaat.",
    "Size {size}": "Maat {size}",
    "{brand} doesn't use size {size} in our chart. Ask the seller to check the frame sticker.":
        "{brand} gebruikt maat {size} niet in onze tabel. Vraag de verkoper de sticker op het frame te checken.",
    "Good fit": "Past goed",
    "Borderline, test ride it": "Twijfelgeval, maak een proefrit",
    "Wrong size for you": "Verkeerde maat voor jou",
    "Fits riders of about {lo} to {hi} cm.": "Past bij een lengte van ongeveer {lo} tot {hi} cm.",
    "Generic chart for this brand, not this model's own size chart yet.":
        "Algemene tabel voor dit merk, nog niet de maattabel van dit model zelf.",
    "{brand}'s own size chart for this model.": "De eigen maattabel van {brand} voor dit model.",
    "This model's own sizes and geometry; {brand} publishes rider heights only in its general size guide.":
        "De eigen maten en geometrie van dit model; {brand} geeft de lichaamslengte alleen in de algemene maattabel.",

    # checks: value
    "No original price": "Geen nieuwprijs",
    "We don't have a new price for this model.": "We hebben geen nieuwprijs voor dit model.",
    "Rough estimate: new price, age and condition only. Comparable ads aren't used yet.":
        "Globale schatting: alleen nieuwprijs, leeftijd en staat. Vergelijkbare advertenties tellen nog niet mee.",
    "New price is the {year} Dutch price, which can differ from what this bike cost new.":
        "De nieuwprijs is de Nederlandse prijs van {year}; die kan afwijken van wat deze fiets nieuw kostte.",
    "The claimed year is before this generation, so the bike may be an older generation with a different new price.":
        "Het opgegeven jaar ligt vóór deze generatie, dus het kan een oudere generatie zijn met een andere nieuwprijs.",
    "Fair {low} to {high}": "Eerlijk {low} tot {high}",
    "Add the asking price to see how it compares.": "Vul de vraagprijs in om te vergelijken.",
    "About {diff} high": "Ongeveer {diff} te hoog",
    "Suspiciously cheap": "Verdacht goedkoop",
    "Below the fair range": "Onder de eerlijke prijs",
    "Fair price": "Eerlijke prijs",
    "Fair range {low} to {high} for a {year} bike.": "Eerlijke prijs {low} tot {high} voor een fiets uit {year}.",
    "Fair range {low} to {high} for a {year} bike in {condition} condition.":
        "Eerlijke prijs {low} tot {high} voor een fiets uit {year} in staat ‘{condition}’.",
    "A price this low can mean a stolen bike or a scam. Ask for the invoice and meet in person.":
        "Zo'n lage prijs kan op een gestolen fiets of oplichting wijzen. Vraag om de aankoopbon en spreek af op locatie.",

    # checks: questions
    "Can you send a photo of the serial number under the bottom bracket?":
        "Kun je een foto sturen van het framenummer onder de trapas?",
    "Do you have the original invoice? Which year did you buy it?":
        "Heb je de originele aankoopbon? In welk jaar heb je hem gekocht?",
    "The original came with {original}. Was the groupset changed, and do you still have the original parts?":
        "Origineel zat er {original} op. Is de groep vervangen, en heb je de originele onderdelen nog?",
    "The original has {original} for the {part}. Can you explain the difference?":
        "Origineel heeft {part}: {original}. Kun je het verschil uitleggen?",
    "Are these the original wheels ({wheels})?": "Zijn dit de originele wielen ({wheels})?",
    "What frame size is printed on the frame?": "Welke framemaat staat er op het frame?",
    "Has it been in a crash, and are there any cracks or deep scratches on the frame?":
        "Is hij gevallen, en zitten er scheuren of diepe krassen in het frame?",
}
