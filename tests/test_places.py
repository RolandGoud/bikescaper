import json
import os

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


def test_towns_link_to_the_map_opened_there(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56", "asking_price": "1500", "location": "Gent"})
    client.post("/check", data={"title": "Giant Defy 2020", "asking_price": "900", "location": "Nergenshuizen"})
    link = "/listings/map?place=Gent&amp;cc=BE"
    for page in ["/listings", "/checks", "/check/1", "/"]:
        html = client.get(page).data.decode()
        assert link in html, page
        assert "place=Nergenshuizen" not in html, page  # a town the map doesn't know stays plain text
    page = client.get("/listings/map?place=Gent&cc=BE").data.decode()
    assert "var selected = 0;" in page  # Gent is the first (only) town on the map
    assert 'href="/listings/map"' in client.get("/size").data.decode()  # in the Tools menu


def test_map_lists_the_ads_per_town_busiest_first(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    for title, place in [("Canyon Endurace CF 7", "Gent"), ("Trek Domane SL6 2022", "Utrecht"),
                         ("Trek Emonda SL5 2021", "Utrecht")]:
        client.post("/check", data={"title": title, "asking_price": "1500", "location": place})
    page = client.get("/listings/map?lang=en").data.decode()
    # Nothing picked: the towns, most ads first, each linking to its own address; no town's ads open yet.
    index = page.split('<nav class="map-index"', 1)[1].split("</nav>", 1)[0]
    assert index.index("Utrecht") < index.index("Gent") and 'href="/listings/map?place=Utrecht&amp;cc=NL"' in index
    assert page.count('<section class="map-town" data-pin="0" hidden>') == 1
    assert page.count('class="map-ad"') == 3 and 'href="/check/1"' in page
    # A town's address: only that town's ads shown, the town list hidden.
    page = client.get("/listings/map?place=Gent&cc=BE&lang=en").data.decode()
    assert '<nav class="map-index" aria-label="Places" hidden>' in page
    assert '<section class="map-town" data-pin="1">' in page and '<section class="map-town" data-pin="0" hidden>' in page


def test_benelux_shapes_have_the_lakes_and_the_border():
    with open(os.path.join(os.path.dirname(places.__file__), "static", "benelux.json"), encoding="utf-8") as f:
        kinds = [x["properties"]["kind"] for x in json.load(f)["features"]]
    assert kinds.count("country") == 2 and "border" in kinds and "lake" in kinds
