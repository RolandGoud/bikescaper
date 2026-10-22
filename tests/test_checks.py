from datetime import date

import pytest

from webapp import checks, db, seed
from webapp.app import create_app

TODAY = date(2026, 10, 18)


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    conn = db.connect(str(tmp_path_factory.mktemp("db") / "test.sqlite3"))
    seed.load(conn)
    return db.all_models(conn)


def run(models, title, description="", price=None, height=None):
    return checks.run_check(models, {"title": title, "description": description, "asking_price": price,
                                     "rider_height": height}, today=TODAY)


def test_reads_claims_from_dutch_ad():
    c = checks.read_claims("Trek Domane SL6 2022 maat 56 Ultegra, nieuwstaat", "carbon frame, schijfremmen")
    assert c["brand"] == "Trek"
    assert c["year"] == 2022
    assert c["size"] == "56"
    assert c["groupset"]["key"] == "ultegra"
    assert c["material"] == "Carbon"
    assert c["brakes"] == "Disc"
    assert c["condition"] == "like-new"


@pytest.mark.parametrize("text,year,purchase", [
    ("Bouwjaar 2021", 2021, False),
    ("Gekocht in 2024, maat 54", 2024, True),
    ("Vraagprijs €2025", None, False),
    ("Domane uit 2019", 2019, False),
])
def test_year(text, year, purchase):
    assert checks.detect_year(text) == (year, purchase)


@pytest.mark.parametrize("text,size", [("maat 56", "56"), ("Maat: M", "M"), ("frame 54cm", "54"),
                                        ("size XXL", "2XL"), ("voor iemand van 180 cm", None)])
def test_size(text, size):
    assert checks.detect_size(text) == size


def test_105_is_not_a_measurement():
    assert checks.detect_groupset("stuur 105 mm breed") is None
    assert checks.detect_groupset("Shimano 105 Di2")["electronic"] is True


def test_dutch_al_is_not_aluminium():
    assert checks.detect_material("al 2 jaar in gebruik") is None


def test_purchase_year_before_launch_is_a_warning(models):
    r = run(models, "Trek Domane SL6 2022 maat 56 Ultegra, nieuwstaat", "carbon, schijfremmen", 2450, 178)
    assert r["model"]["name"].lower() == "domane sl 6 gen 4"
    assert r["age"]["status"] == checks.WARN
    groupset = next(row for row in r["specs"]["rows"] if row["key"] == "groupset")
    assert groupset["status"] == checks.BAD  # the original has 105, not Ultegra
    assert r["size"]["fit"]["status"] == checks.OK


def test_year_older_than_generation_is_flagged(models):
    r = run(models, "Trek Madone SL 6 gen 8 2020", "maat 56")
    assert r["age"]["status"] == checks.BAD


def test_matching_canyon(models):
    r = run(models, "Canyon Endurace CF 7 Di2 maat M", "Bouwjaar 2023, Shimano 105 Di2, carbon, schijfremmen", 1600)
    assert r["model"]["name"] == "Endurace CF 7 Di2"
    assert r["specs"]["status"] == checks.OK


def test_very_cheap_is_suspicious(models):
    r = run(models, "Trek Madone SLR 7 Gen 8", "bouwjaar 2025", 900)
    assert r["value"]["status"] == checks.BAD


def test_brand_without_data_gives_no_match(models):
    r = run(models, "Orbea Orca M30 maat 53", "2022, 105")
    assert r["claims"]["brand"] == "Orbea"
    assert r["model"] is None


def test_pages_render(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    resp = client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56", "asking_price": "€ 2.450,-"})
    assert resp.status_code == 302
    report = client.get(resp.headers["Location"] + "?lang=en")
    assert report.status_code == 200 and b"Age check" in report.data and "€2.450".encode() in report.data
    for url in ["/", "/listings", "/models", "/models/trek-domane-sl-6-gen-4", "/size?brand=Giant&height=181",
                "/value?model=trek-domane-sl-6-gen-4&year=2023", "/how-it-works", "/check"]:
        assert client.get(url).status_code == 200, url
    assert client.post("/check", data={"title": ""}).status_code == 400


def test_language_switch(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56 Ultegra", "asking_price": "2450"})

    # Dutch by default, English when the browser asks for it
    assert "Advertentie checken".encode() in client.get("/").data
    assert b"Check a listing" in client.get("/", headers={"Accept-Language": "en-GB,en;q=0.9"}).data

    # ?lang= switches and sticks through a cookie, including the check results
    page = client.get("/check/1?lang=en").data
    assert b'<html lang="en">' in page and b"Probably the purchase year" in page
    page = client.get("/check/1").data
    assert b"Probably the purchase year" in page
    page = client.get("/check/1?lang=nl").data
    assert b'<html lang="nl">' in page and b"Waarschijnlijk het aankoopjaar" in page and b"Groep" in page


def test_every_message_has_a_dutch_translation(models):
    from webapp import i18n
    r = run(models, "Trek Domane SL6 2022 maat 56 Ultegra, nieuwstaat", "carbon, schijfremmen", 2450, 178)
    msgs = [r["confidence"]]
    for key in ("age", "specs", "size", "value"):
        msgs += [r[key]["headline"], r[key]["detail"], *r[key].get("notes", [])]
    msgs += [row[f] for row in r["specs"]["rows"] for f in ("part", "result")] + r["questions"]
    for m in msgs:
        if isinstance(m, i18n.Msg) and "{p0}" not in m.text:
            assert m.text in i18n.NL, m.text


def test_model_photos_are_side_views():
    from webapp.seed import pick_image
    # Canyon: the *_FULL_* product shot, not a close-up or an award badge from the same page.
    assert "_FULL_aeroad_cfr-axs_" in pick_image({"brand": "Canyon", "name": "Aeroad CFR AXS"})
    assert "_FULL_aeroad_cf-slx-7-axs_" in pick_image({"brand": "Canyon", "name": "Aeroad CF SLX 7 AXS SPEED"})
    assert "_FULL_ultimate_cf-yh_" in pick_image({"brand": "Canyon", "name": "Ultimate CF Young Hero"})
    # Trek: a file for this exact model, never one for a sibling.
    assert "/DomaneSL6-" in "/" + pick_image({"brand": "Trek", "name": "Domane SL 6 gen 4"}).split("/")[-1]
    assert pick_image({"brand": "Trek", "name": "Domane SL 6 AXS gen 4"}) is None
