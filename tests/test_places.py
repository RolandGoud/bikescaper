import json

from webapp import db, places, seed
from webapp.app import create_app


def test_dutch_and_belgian_towns_are_found_by_any_of_their_names():
    for name in ["Amsterdam", "'s-Hertogenbosch", "Den Bosch", "Den Haag", "Ljouwert", "Texel"]:
        assert places.locate(name)[2] == "NL", name
    for name in ["Antwerpen", "Brussel", "Bruxelles", "Luik", "Liège"]:
        assert places.locate(name)[2] == "BE", name
    assert places.locate("Xyzzy") is None and places.locate(None) is None and places.locate("") is None


def test_a_district_postcode_or_province_still_finds_the_town():
    utrecht = places.locate("Utrecht")
    assert places.locate("Utrecht (3512)") == places.locate("3512 AB Utrecht") == utrecht
    assert places.locate("Gent, Oost-Vlaanderen") == places.locate("Gent")
    assert places.locate("Amsterdam-Noord")[2] == "NL"


def test_the_site_decides_a_name_both_countries_have():
    # Bergen is a Dutch village and the Dutch name of Mons; a typed check counts as Dutch.
    assert places.locate("Bergen")[2] == "NL"
    assert places.locate("Bergen", "https://www.2dehands.be/v/fietsen/m123")[2] == "BE"
    # Gent and Leuven are Dutch hamlets too, but nobody means those.
    assert places.locate("Gent")[2] == places.locate("Leuven")[2] == "BE"
    assert places.locate("Gent", "https://www.marktplaats.nl/v/fietsen/m123")[2] == "BE"
    lat, lng, _ = places.locate("Maastricht")
    assert 50.8 < lat < 50.9 and 5.6 < lng < 5.8


def test_map_page_puts_ads_with_a_known_place_on_pins(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    for title, place in [("Trek Domane SL6 2022 maat 56", "Utrecht"), ("Trek Emonda SL5 2021", "Utrecht"),
                         ("Canyon Endurace CF 7", "Gent"), ("Giant Defy 2020", "Nergenshuizen")]:
        client.post("/check", data={"title": title, "asking_price": "1500", "location": place})
    page = client.get("/listings/map?lang=en").data.decode()
    assert "3 ads in 2 places" in page and "1 without a place we know" in page
    pins = json.loads(page.split("var pins = ", 1)[1].split(";\n", 1)[0])
    by_place = {p["place"]: p for p in pins}
    assert len(by_place["Utrecht"]["ads"]) == 2 and by_place["Gent"]["country"] == "BE"
    assert all(ad["url"].startswith("/check/") for p in pins for ad in p["ads"])
    assert 'href="/listings/map"' in client.get("/listings").data.decode()
