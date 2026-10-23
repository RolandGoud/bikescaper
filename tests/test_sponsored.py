import json
import random

from webapp import db, seed, sponsored
from webapp.app import create_app


def offer(id, slots, url="https://example.com/aff?" + "x"):
    return {"id": id, "slots": slots, "url": url, "advertiser": f"{id}.nl",
            "nl": {"title": f"{id} nl", "text": "tekst", "cta": "Ga"},
            "en": {"title": f"{id} en", "text": "text", "cta": "Go"}}


def test_offers_without_a_link_are_skipped(tmp_path):
    path = tmp_path / "sponsored.json"
    path.write_text(json.dumps([offer("a", ["card"]), offer("b", ["card"], url=""),
                                offer("c", ["card"], url="http://plain.example")]))
    assert [o["id"] for o in sponsored.load(path)] == ["a"]
    assert sponsored.load(tmp_path / "missing.json") == []
    # the shipped file has no links yet, so nothing shows until they're filled in
    assert sponsored.load() == []


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
