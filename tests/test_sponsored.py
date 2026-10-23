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
    assert page.count("Gesponsord") >= 3 and "Advertentie checken" in page
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


def test_listings_and_models_pages_have_their_own_slots(tmp_path):
    path = tmp_path / "sponsored.json"
    path.write_text(json.dumps([offer("card", ["card"]), offer("banner", ["banner"]), offer("side", ["side"])]))
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["SPONSORED_PATH"] = str(path)
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56"})

    listings = client.get("/listings").data.decode()  # a 300×250 among the cards, and the skyscraper
    assert "ad-rect" in listings and "ad-sky" in listings and "ad-banner" not in listings
    models = client.get("/models").data.decode()  # a banner across the grid after eight models, and the skyscraper
    assert "ad-banner" in models and "ad-sky" in models and "ad-rect" not in models
    assert models.count(">AD<") == 2
    grid = models[models.index('class="model-grid"'):models.index("ad-banner")]
    assert grid.count('class="model-card') == 8


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
