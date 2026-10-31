import json
import os
import random
import re

from webapp import db, seed, sponsored
from webapp.app import create_app


def offer(id, slots, url="https://example.com/aff?" + "x"):
    return {"id": id, "slots": slots, "url": url, "advertiser": f"{id}.nl",
            "nl": {"title": f"{id} nl", "text": "tekst", "cta": "Ga"},
            "en": {"title": f"{id} en", "text": "text", "cta": "Go"}}


def test_offers_without_a_link_show_as_mock_ups(tmp_path):
    path = tmp_path / "sponsored.json"
    path.write_text(json.dumps([offer("a", ["card"]), offer("b", ["card"], url=""),
                                offer("c", ["card"], url="http://plain.example")]))
    assert [o["url"] for o in sponsored.load(path)] == ["https://example.com/aff?x", "#", "#"]
    assert sponsored.load(tmp_path / "missing.json") == []
    # the shipped file has no links yet, so its offers are mock-ups
    assert sponsored.load() and {o["url"] for o in sponsored.load()} == {"#"}


def test_pick_fills_each_slot_once_and_never_repeats_an_offer():
    offers = [offer("a", ["card", "side"]), offer("b", ["card", "banner", "side"])]
    for seed_ in range(20):
        picked = sponsored.pick(offers, "nl", random.Random(seed_))
        ids = [p["title"] for p in picked.values() if p]
        assert len(ids) == len(set(ids))
        assert picked["banner"] is None or picked["banner"]["title"] == "b nl"
    picked = sponsored.pick([offer("a", ["card"])], "en")
    assert picked["card"]["title"] == "a en" and picked["banner"] is None and picked["side"] is None


def test_home_shows_the_offers_marked_as_sponsored(tmp_path):
    path = tmp_path / "sponsored.json"
    path.write_text(json.dumps([offer("card", ["card"]), offer("banner", ["banner"]), offer("side", ["side"])]))
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["SPONSORED_PATH"] = str(path)
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    for title in ["Trek Domane SL6 2022 maat 56", "Canyon Ultimate CF SL 8 2021", "Giant TCR 2020"]:
        client.post("/check", data={"title": title})

    page = client.get("/").data.decode()
    assert page.count("Gesponsord") >= 3 and "Onze catalogus" in page
    assert page.count('rel="sponsored noopener"') == 3
    for slot in ["card", "banner", "side"]:
        assert f"{slot} nl" in page
    # the card sits third in the row, after two real checks
    row = page[page.index('class="recent-row"'):]
    assert row.index("sponsored-card") > row.index("listing-card", row.index("listing-card") + 1)

    app.config["SPONSORED_PATH"] = str(tmp_path / "none.json")
    assert "sponsored" not in client.get("/").data.decode()

    # the shipped mock-ups fill all three slots
    app.config["SPONSORED_PATH"] = sponsored.PATH
    page = client.get("/").data.decode()
    assert page.count('rel="sponsored noopener"') == 3 and 'href="#"' in page


def test_rotation_gives_every_card_offer_in_the_visitors_language():
    offers = [offer("a", ["card"]), offer("b", ["card", "side"]), offer("c", ["banner"])]
    for seed_ in range(10):
        tiles = sponsored.rotation(offers, "en", rng=random.Random(seed_))
        assert sorted(t["title"] for t in tiles) == ["a en", "b en"]
    assert sponsored.rotation([offer("c", ["banner"])], "nl") == []


def test_listings_and_models_show_ads_as_tiles_5_15_25(tmp_path):
    path = tmp_path / "sponsored.json"
    path.write_text(json.dumps([offer("card1", ["card"]), offer("card2", ["card"]), offer("side", ["side"])]))
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["SPONSORED_PATH"] = str(path)
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    titles = ["Trek Domane SL6 2022 maat 56", "Canyon Ultimate CF SL 8 2021", "Giant TCR 2020",
              "Specialized Tarmac SL7 2021", "Cube Attain 2022", "Scott Addict 2020",
              "Orbea Orca 2021", "Cannondale SuperSix 2019", "Trek Emonda SL5 2021", "Canyon Endurace CF 7 2022",
              "Giant Defy 2021", "Trek Madone SL6 2022", "Canyon Aeroad CF SLX 2021", "Cube Agree C:62 2020"]
    client.post("/check", data={"title": titles[0]})

    listings = client.get("/listings").data.decode()  # fewer than four ads: the ad tile goes last
    assert listings.count("sponsored-card fluid") == 1 and "ad-sky" in listings and "ad-banner" not in listings
    for title in titles[1:]:
        client.post("/check", data={"title": title})
    listings = client.get("/listings").data.decode()
    grid = listings[listings.index('class="grid"'):]
    tiles = re.findall(r'class="(listing-card|sponsored-card fluid)', grid)
    assert tiles == ["listing-card"] * 4 + ["sponsored-card fluid"] + ["listing-card"] * 9 + \
        ["sponsored-card fluid"] + ["listing-card"]
    assert "card1 nl" in grid and "card2 nl" in grid  # the two tiles show different offers

    models = client.get("/models").data.decode()
    assert "ad-banner" not in models and "ad-sky" in models
    grid = models[models.index('class="model-grid"'):]
    grid = grid[:grid.index("</section>")]
    tiles = re.findall(r'class="(model-card|sponsored-card fluid)', grid)
    assert tiles[:15] == ["model-card"] * 4 + ["sponsored-card fluid"] + ["model-card"] * 9 + ["sponsored-card fluid"]
    assert tiles[-1] == "model-card"
    assert all(tiles[i] == ("sponsored-card fluid" if i % 10 == 4 else "model-card") for i in range(len(tiles)))

    app.config["SPONSORED_PATH"] = str(tmp_path / "none.json")  # no offers: no ad tiles
    assert "sponsored-card" not in client.get("/models").data.decode()
    assert "sponsored-card" not in client.get("/listings").data.decode()


def test_stylesheets_and_scripts_carry_a_version(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/").data.decode()
    assert re.search(r'/static/style\.css\?v=\d+"', page) and re.search(r'/static/recent-row\.js\?v=\d+"', page)


def test_stylesheet_braces_balance():
    # an unclosed @media once swallowed every rule after it, so the ads were only styled on phones
    with open(os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "style.css"), encoding="utf-8") as f:
        depth = 0
        for line in f:
            depth += line.count("{") - line.count("}")
            assert depth >= 0
    assert depth == 0
