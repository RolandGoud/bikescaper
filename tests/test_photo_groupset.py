"""The groupset read from an ad's photos fills in the spec comparison when the ad's text doesn't name it."""
import json
import os
import time
from datetime import date
from types import SimpleNamespace

import pytest
from PIL import Image

from webapp import checks, db, i18n, photo_groupset, seed

TODAY = date(2026, 10, 31)
RIVAL = {"brand": "SRAM", "series": "Rival", "model_code": "AXS", "speeds": 12, "electronic": True,
         "confidence": "high", "photos": [5], "evidence_en": "Photo 5: RIVAL on the rear derailleur.",
         "evidence_nl": "Foto 5: RIVAL op de achterderailleur.",
         "crankset": {"brand": "SRAM", "series": "Rival", "model_code": None, "confidence": "high", "photos": [9],
                      "evidence_en": "Photo 9: Rival printed on the crank arm.",
                      "evidence_nl": "Foto 9: Rival op de crankarm."}}
NO_CRANK = dict(RIVAL, crankset={"brand": None, "series": None, "model_code": None, "confidence": "none", "photos": [],
                                 "evidence_en": "", "evidence_nl": ""})


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    conn = db.connect(str(tmp_path_factory.mktemp("db") / "test.sqlite3"))
    seed.load(conn)
    return db.all_models(conn)


def en(msg):
    token = i18n.current_language.set("en")
    try:
        return str(msg)
    finally:
        i18n.current_language.reset(token)


def groupset_row(report):
    return next(r for r in report["specs"]["rows"] if r["key"] == "groupset")


def crank_row(report):
    return next(r for r in report["specs"]["rows"] if r["key"] == "crankset")


def run(models, title, description="", read=None):
    return checks.run_check(models, {"title": title, "description": description, "asking_price": 1800,
                                     "listing_url": "https://www.marktplaats.nl/v/x/y/m2459123766-trek-emonda-sl6",
                                     "photo_groupset": read}, today=TODAY)


def test_text_of_a_read_is_detected_like_ad_text():
    assert photo_groupset.text_of(RIVAL) == "SRAM Rival AXS 12-speed AXS"
    found = checks.detect_groupset(photo_groupset.text_of(RIVAL))
    assert found["key"] == "rival" and found["electronic"]


def test_only_sure_reads_with_a_series_count():
    assert photo_groupset.usable(RIVAL)
    assert not photo_groupset.usable(dict(RIVAL, confidence="low"))
    assert not photo_groupset.usable(dict(RIVAL, series=None))
    assert not photo_groupset.usable(None)


def test_photos_fill_in_a_groupset_the_ad_leaves_out(models):
    """Check 45: an Émonda SL 6 whose ad doesn't name the groupset; the photos show SRAM Rival AXS."""
    without = run(models, "Trek Emonda SL6", "Mooie fiets, carbon, maat 56")
    assert en(groupset_row(without)["listing"]) == "Not stated"
    report = run(models, "Trek Emonda SL6", "Mooie fiets, carbon, maat 56", RIVAL)
    row = groupset_row(report)
    assert row["from_photos"]
    assert en(row["listing"]).endswith("(inferred from photo analysis)")
    assert "Rival" in en(row["listing"])
    assert report["specs"]["photo_groupset"] == RIVAL
    assert "read it from the photos" in en(report["specs"]["detail"])
    # What the ad itself says is unchanged: it still doesn't name a groupset.
    assert report["claims"]["groupset"] is None


def test_ad_text_wins_over_the_photos(models):
    report = run(models, "Trek Emonda SL6 Ultegra", "", RIVAL)
    row = groupset_row(report)
    assert not row["from_photos"]
    assert "Ultegra" in en(row["listing"])
    assert report["specs"]["photo_groupset"] is None


def test_unsure_read_leaves_it_not_stated(models):
    report = run(models, "Trek Emonda SL6", "", dict(RIVAL, confidence="low"))
    assert en(groupset_row(report)["listing"]) == "Not stated"
    assert not groupset_row(report)["from_photos"]


def test_hand_read_file_is_used_for_its_ad(tmp_path, monkeypatch):
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps({"marktplaats:m2459123766": RIVAL}))
    monkeypatch.setattr(photo_groupset, "HAND_FILE", str(hand))
    photo_groupset._hand.__defaults__[0].clear()
    try:
        listing = {"id": 45, "title": "Trek Emonda SL6", "asking_price": 1800,
                   "listing_url": "https://www.marktplaats.nl/v/fietsen/racefietsen/m2459123766-trek-emonda-sl6"}
        read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
        assert read["series"] == "Rival" and read["source"] == "eye"
        other = dict(listing, listing_url="https://www.marktplaats.nl/v/x/y/m1111111111-x")
        assert photo_groupset.stored(str(tmp_path), other, ["45/01.jpg"]) is None
    finally:
        photo_groupset._hand.__defaults__[0].clear()


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, answers with a read."""

    def __init__(self, answer, stop="end_turn"):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.answer, self.stop = answer, stop

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def photo(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (2000, 1500), (180, 30, 30)).save(path)


def test_read_photos_sends_the_photos_resized_and_parses_the_answer(tmp_path):
    for n in (1, 2):
        photo(str(tmp_path / f"0{n}.jpg"))
    client = FakeClient(RIVAL)
    read = photo_groupset.read_photos([str(tmp_path / "01.jpg"), str(tmp_path / "02.jpg"), str(tmp_path / "gone.jpg")],
                                      client)
    assert read == RIVAL
    sent = client.calls[0]
    images = [b for b in sent["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 2
    assert sent["output_config"]["format"]["schema"] is photo_groupset.SCHEMA
    import base64, io
    with Image.open(io.BytesIO(base64.b64decode(images[0]["source"]["data"]))) as im:
        assert max(im.size) == photo_groupset.MAX_SIDE


def test_a_refusal_or_cut_off_answer_is_no_read(tmp_path):
    photo(str(tmp_path / "01.jpg"))
    assert photo_groupset.read_photos([str(tmp_path / "01.jpg")], FakeClient(RIVAL, stop="refusal")) is None
    assert photo_groupset.read_photos([], FakeClient(RIVAL)) is None


def test_read_later_stores_the_read_once_per_set_of_photos(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    photo(str(tmp_path / "45" / "01.jpg"))
    client = FakeClient(RIVAL)
    assert photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    for _ in range(100):
        if os.path.exists(tmp_path / "45" / "groupset.json"):
            break
        time.sleep(0.05)
    listing = {"id": 45, "title": "Nothing in the hand file", "asking_price": None, "listing_url": None}
    read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
    assert read["series"] == "Rival" and read["source"] == "photos"
    # The same photos aren't sent again; other photos are read again.
    assert not photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    assert photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg", "45/02.jpg"]) is None
    assert len(client.calls) == 1


def test_nothing_is_sent_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = FakeClient(RIVAL)
    assert not photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    assert client.calls == []


def test_report_page_shows_the_photo_read(tmp_path):
    """Check 45 as the site shows it: stored photos, the hand-read Rival AXS, both languages."""
    from webapp.app import create_app
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (listing_url, title, description, asking_price, photos) VALUES (?,?,?,?,?)",
                 ("https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2459123766-trek-emonda-sl6",
                  "Trek Emonda SL6", "Mooie fiets, maat 56", 1800, json.dumps(["1/01.jpg"])))
    conn.commit()
    photo(os.path.join(os.path.dirname(app.config["DB_PATH"]), "ad-photos", "1", "01.jpg"))
    client = app.test_client()
    page = client.get("/check/1?lang=en").data.decode()
    assert "SRAM Rival AXS (inferred from photo analysis)" in page
    assert "RIVAL" in page  # the evidence line from webapp/photo_groupsets.json
    page = client.get("/check/1?lang=nl").data.decode()
    assert "(afgeleid uit foto-analyse)" in page
    assert "achterderailleur" in page


def test_photos_fill_in_the_crankset_the_ad_leaves_out(models):
    """Check 63: the ad doesn't name the crankset, photo 9 shows it."""
    assert crank_row(run(models, "Trek Emonda SL6", "", None))["listing"] is None
    report = run(models, "Trek Emonda SL6", "", RIVAL)
    row = crank_row(report)
    assert en(row["listing"]) == "SRAM Rival (inferred from photo analysis)"
    assert row["ad_tier"] and row["result"] != "Compare photos"
    assert row["photo_why"]["nl"] == "Foto 9: Rival op de crankarm."
    assert report["specs"]["photo_crankset"]["series"] == "Rival"


def test_crankset_from_photos_when_the_ad_names_only_the_groupset(models):
    report = run(models, "Trek Emonda SL6 Ultegra", "", RIVAL)
    assert not groupset_row(report)["from_photos"]
    assert "Rival" in en(crank_row(report)["listing"])


def test_ad_text_crankset_wins_and_unsure_crank_reads_are_left_out(models):
    report = run(models, "Trek Emonda SL6", "Crankstel Shimano Ultegra", RIVAL)
    assert "Ultegra" in en(crank_row(report)["listing"]) and "photo_why" not in crank_row(report)
    assert crank_row(run(models, "Trek Emonda SL6", "", NO_CRANK))["listing"] is None
    assert crank_row(run(models, "Trek Emonda SL6", "", dict(RIVAL, crankset=dict(RIVAL["crankset"], confidence="low"))))["listing"] is None


def test_all_photos_up_to_20_are_read():
    assert photo_groupset.MAX_PHOTOS >= 9  # check 63's crankset is on photo 9


def test_a_read_from_before_the_crankset_is_read_again(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    photo(str(tmp_path / "45" / "01.jpg"))
    old = {k: v for k, v in RIVAL.items() if k != "crankset"}
    (tmp_path / "45" / "groupset.json").write_text(json.dumps({"photos": ["45/01.jpg"], "read": old}))
    listing = {"id": 45, "title": "Nothing in the hand file", "asking_price": None, "listing_url": None}
    assert photo_groupset.needs_crankset(photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"]))
    client = FakeClient(RIVAL)
    assert photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    for _ in range(100):
        if "crankset" in json.loads((tmp_path / "45" / "groupset.json").read_text())["read"]:
            break
        time.sleep(0.05)
    read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
    assert not photo_groupset.needs_crankset(read) and read["crankset"]["series"] == "Rival"
    assert not photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)


def test_a_hand_read_without_crankset_takes_it_from_the_automatic_read(tmp_path, monkeypatch):
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps({"marktplaats:m2459123766": {k: v for k, v in RIVAL.items() if k != "crankset"}}))
    monkeypatch.setattr(photo_groupset, "HAND_FILE", str(hand))
    photo_groupset._hand.__defaults__[0].clear()
    try:
        listing = {"id": 45, "title": "Trek Emonda SL6", "asking_price": 1800,
                   "listing_url": "https://www.marktplaats.nl/v/x/y/m2459123766-trek-emonda-sl6"}
        assert photo_groupset.needs_crankset(photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"]))
        os.makedirs(tmp_path / "45")
        (tmp_path / "45" / "groupset.json").write_text(json.dumps({"photos": ["45/01.jpg"], "version": 2,
                                                                   "read": dict(RIVAL, series="Force")}))
        read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
        assert read["source"] == "eye" and read["series"] == "Rival" and read["crankset"]["series"] == "Rival"
    finally:
        photo_groupset._hand.__defaults__[0].clear()
