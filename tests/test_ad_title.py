from webapp import ad_title, checks


def test_the_title_loses_prices_filler_and_shouting():
    assert ad_title.clean("Giant Defy Advanced 1 Shimano 105 Di2 van €3599 voor € 2450") == "Giant Defy Advanced 1 Shimano 105 Di2"
    assert ad_title.clean("TE KOOP!!! TREK Domane SL6 2022 maat 56 🔥🔥 €2.450,-") == "Trek Domane SL6 2022 maat 56"
    assert ad_title.clean("Cannondale CAAD13 105 1500 euro") == "Cannondale CAAD13 105"
    assert ad_title.clean("Trek Domane AL5") == "Trek Domane AL5"


def test_the_model_words_lead():
    model = {"brand": "Giant", "name": "Defy Advanced 1"}
    assert ad_title.parts("Giant Defy Advanced 1 Shimano 105 Di2 van €3599", model) == ("Giant Defy Advanced 1", "Shimano 105 Di2")
    assert ad_title.parts("Mooie racefiets Giant", model) == ("racefiets Giant", "")  # no model words up front: one part
    assert ad_title.parts("Giant Defy", None) == ("Giant Defy", "")


def test_heading_facts_use_the_catalogue_price_of_the_model_year():
    model = {"brand": "Giant", "name": "Defy Advanced 1", "price_eur": 3399, "seen_on": "2026-10-22",
             "year_specs": {"years": {"2024": {"price": 3599}}}}
    claims = checks.read_claims("Giant Defy Advanced 1 2024 maat L Shimano 105 Di2 van €3999", "")
    facts = [(str(k), v) for k, v in checks.head_facts(model, claims, {"model_year": 2024})]
    assert facts[-1] == ("Nieuw in 2024", "€3.599")  # the catalogue's price that year, not the seller's €3999
    assert ("Groep", "Shimano 105 Di2") in facts
    assert checks.new_price(model, 2026) == 3399 and checks.new_price(model, 2022) is None
