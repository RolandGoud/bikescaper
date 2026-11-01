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
                      "evidence_nl": "Foto 9: Rival op de crankarm."},
         "tyres": {"brand": None, "model": None, "width_mm": None, "confidence": "none", "photos": [],
                   "evidence_en": "", "evidence_nl": ""},
         "wheels": {"brand": "", "model": "", "rim_depth_mm": 0, "rim_material": "unknown", "confidence": "none",
                    "photos": [], "evidence_en": "", "evidence_nl": ""},
         "frame": {"material": None, "printed": None, "confidence": "none", "photos": [], "evidence_en": "",
                   "evidence_nl": ""},
         "receipt": {"shown": False, "confidence": "none", "photos": [], "date": None, "shop": None, "bike": None,
                     "model_year": None, "price": None, "evidence_en": "", "evidence_nl": ""}}
RECEIPT = {"shown": True, "confidence": "high", "photos": [11], "date": "2021-03-12", "shop": "Fietsenwinkel De Ronde",
           "bike": "Trek Emonda SL 6 Disc", "model_year": None, "price": 2499.0,
           "evidence_en": "Photo 11: a till receipt dated 12-03-2021 for a Trek Emonda SL 6 Disc.",
           "evidence_nl": "Foto 11: een kassabon van 12-03-2021 voor een Trek Emonda SL 6 Disc."}
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
    # The same photos aren't sent again; more photos are read again, and the last read stands until then.
    assert not photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    assert len(client.calls) == 1
    assert photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg", "45/02.jpg"])["series"] == "Rival"
    photo(str(tmp_path / "45" / "02.jpg"))
    assert photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg", "45/02.jpg"], client)


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
    assert "crankset" in report["specs"]["photo_parts"]


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
    old = {k: v for k, v in RIVAL.items() if k not in ("crankset", "tyres", "wheels", "frame", "receipt")}
    (tmp_path / "45" / "groupset.json").write_text(json.dumps({"photos": ["45/01.jpg"], "read": old}))
    listing = {"id": 45, "title": "Nothing in the hand file", "asking_price": None, "listing_url": None}
    assert photo_groupset.outdated(photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"]))
    client = FakeClient(RIVAL)
    assert photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)
    for _ in range(100):
        if "crankset" in json.loads((tmp_path / "45" / "groupset.json").read_text())["read"]:
            break
        time.sleep(0.05)
    read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
    assert not photo_groupset.outdated(read) and read["crankset"]["series"] == "Rival"
    assert not photo_groupset.read_later(str(tmp_path), 45, ["45/01.jpg"], client)


def test_a_hand_read_without_crankset_takes_it_from_the_automatic_read(tmp_path, monkeypatch):
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps({"marktplaats:m2459123766": {k: v for k, v in RIVAL.items() if k not in ("crankset", "tyres", "wheels", "frame", "receipt")}}))
    monkeypatch.setattr(photo_groupset, "HAND_FILE", str(hand))
    photo_groupset._hand.__defaults__[0].clear()
    try:
        listing = {"id": 45, "title": "Trek Emonda SL6", "asking_price": 1800,
                   "listing_url": "https://www.marktplaats.nl/v/x/y/m2459123766-trek-emonda-sl6"}
        assert photo_groupset.outdated(photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"]))
        os.makedirs(tmp_path / "45")
        (tmp_path / "45" / "groupset.json").write_text(json.dumps({"photos": ["45/01.jpg"], "version": 4,
                                                                   "read": dict(RIVAL, series="Force")}))
        read = photo_groupset.stored(str(tmp_path), listing, ["45/01.jpg"])
        assert read["source"] == "eye" and read["series"] == "Rival" and read["crankset"]["series"] == "Rival"
        assert not photo_groupset.outdated(read)
    finally:
        photo_groupset._hand.__defaults__[0].clear()


def test_a_receipt_in_the_photos_gives_the_year_the_ad_leaves_out(models):
    """Check 61: the ad gives no year, one of its photos is the receipt."""
    report = run(models, "Trek Emonda SL6", "Mooie fiets", dict(RIVAL, receipt=RECEIPT))
    assert report["receipt"]["date"] == "12-03-2021" and report["receipt"]["price"] == 2499.0
    assert report["claims"]["year"] == 2021 and report["claims"]["year_is_purchase"]
    assert "receipt" in en(report["age"]["detail"])


def test_the_receipts_model_year_wins_and_the_ads_own_year_wins_over_both(models):
    report = run(models, "Trek Emonda SL6", "", dict(RIVAL, receipt=dict(RECEIPT, model_year=2020)))
    assert report["claims"]["year"] == 2020 and not report["claims"]["year_is_purchase"]
    report = run(models, "Trek Emonda SL6 2019", "", dict(RIVAL, receipt=RECEIPT))
    assert report["claims"]["year"] == 2019 and report["receipt"]["year"] == 2021


def test_an_unreadable_or_absent_receipt_is_left_out(models):
    assert run(models, "Trek Emonda SL6", "", RIVAL)["receipt"] is None
    assert run(models, "Trek Emonda SL6", "", dict(RIVAL, receipt=dict(RECEIPT, confidence="low")))["receipt"] is None


def test_a_receipt_counts_as_proof_of_purchase(models):
    from webapp import scores
    listing = {"title": "Trek Emonda SL6", "description": ""}
    assert "proof" in scores.missing(run(models, "Trek Emonda SL6", "", RIVAL), listing)
    assert "proof" not in scores.missing(run(models, "Trek Emonda SL6", "", dict(RIVAL, receipt=RECEIPT)), listing)


def test_report_page_shows_the_receipt(tmp_path, monkeypatch):
    from webapp.app import create_app
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (listing_url, title, description, asking_price, photos) VALUES (?,?,?,?,?)",
                 ("https://www.marktplaats.nl/v/x/y/m1234567890-trek-emonda-sl6", "Trek Emonda SL6", "Mooie fiets", 1500,
                  json.dumps(["1/01.jpg"])))
    conn.commit()
    folder = os.path.join(os.path.dirname(app.config["DB_PATH"]), "ad-photos")
    photo(os.path.join(folder, "1", "01.jpg"))
    with open(os.path.join(folder, "1", "groupset.json"), "w") as fh:
        json.dump({"photos": ["1/01.jpg"], "version": photo_groupset.READ_VERSION, "read": dict(RIVAL, receipt=RECEIPT)}, fh)
    page = app.test_client().get("/check/1?lang=nl").data.decode()
    assert "Aankoopbon in de foto&#39;s" in page or "Aankoopbon in de foto's" in page
    assert "gekocht op 12-03-2021" in page and "€2.499" in page and "kassabon" in page


def row(report, key):
    return next(r for r in report["specs"]["rows"] if r["key"] == key)


def test_photos_fill_in_the_tyres_the_ad_leaves_out(models):
    tyres = {"brand": "Continental", "model": "Grand Prix 5000", "width_mm": 28, "confidence": "high", "photos": [6],
             "evidence_en": "Photo 6: GRAND PRIX 5000 28-622 on the sidewall.",
             "evidence_nl": "Foto 6: GRAND PRIX 5000 28-622 op de zijwand."}
    report = run(models, "Trek Emonda SL6", "", dict(RIVAL, tyres=tyres))
    r = row(report, "tyres")
    assert en(r["listing"]) == "Continental Grand Prix 5000 28 mm (inferred from photo analysis)"
    assert r["ad_tier"] and r["photo_why"]["en"].startswith("Photo 6")
    # A tyre we can't rate is still shown, but not compared.
    r = row(run(models, "Trek Emonda SL6", "", dict(RIVAL, tyres=dict(tyres, brand="Noname", model="Road X"))), "tyres")
    assert "Noname" in en(r["listing"]) and r["status"] == checks.UNKNOWN
    # The ad's own words win.
    assert "photo_why" not in row(run(models, "Trek Emonda SL6", "Banden: Schwalbe One 25mm", dict(RIVAL, tyres=tyres)), "tyres")


def test_photos_fill_in_the_frame_material(models):
    """Check 61: photo 8 shows the frame."""
    frame = {"material": "Carbon", "printed": "500 Series OCLV", "confidence": "high", "photos": [8],
             "evidence_en": "Photo 8: 500 SERIES OCLV printed on the top tube.",
             "evidence_nl": "Foto 8: 500 SERIES OCLV op de bovenbuis."}
    without = row(run(models, "Trek Emonda SL6", "", RIVAL), "frame")
    assert en(without["listing"]) == "Not stated"
    r = row(run(models, "Trek Emonda SL6", "", dict(RIVAL, frame=frame)), "frame")
    assert en(r["listing"]) == "Carbon (inferred from photo analysis)" and r["status"] == checks.OK
    r = row(run(models, "Trek Emonda SL6", "", dict(RIVAL, frame=dict(frame, material="Aluminium"))), "frame")
    assert r["status"] == checks.BAD
    assert en(row(run(models, "Trek Emonda SL6", "", dict(RIVAL, frame=dict(frame, confidence="low"))), "frame")["listing"]) == "Not stated"


def test_a_photo_that_failed_to_copy_doesnt_hold_up_the_read(tmp_path, monkeypatch):
    """Bugbot on #254: one photo of the first 20 left as a link must not stop the read for good."""
    from webapp.app import create_app
    calls = []
    monkeypatch.setattr(photo_groupset, "read_later", lambda folder, check_id, names, client=None: calls.append(names))
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (listing_url, title, description, asking_price, photos) VALUES (?,?,?,?,?)",
                 ("https://www.marktplaats.nl/v/x/y/m1234567890-trek-emonda-sl6", "Trek Emonda SL6", "", 1500,
                  json.dumps(["1/01.jpg", "https://images.marktplaats.com/gone.jpg", "1/03.jpg"])))
    conn.commit()
    for n in ("01", "03"):
        photo(os.path.join(os.path.dirname(app.config["DB_PATH"]), "ad-photos", "1", f"{n}.jpg"))
    app.test_client().get("/check/1")
    assert calls and calls[-1] == ["1/01.jpg", "1/03.jpg"]


def test_every_enum_in_the_schema_fits_its_declared_type():
    """The API refused every read when the frame's material enum sat on type ["string", "null"]."""
    def walk(node):
        if isinstance(node, dict):
            if "enum" in node:
                assert node.get("type") == "string" and all(isinstance(v, str) for v in node["enum"]), node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(photo_groupset.SCHEMA)


def test_the_schema_stays_within_the_apis_limit_of_16_union_fields():
    """The API refused every read when 17 fields were nullable (a type list or anyOf)."""
    def unions(node):
        if isinstance(node, dict):
            here = isinstance(node.get("type"), list) or "anyOf" in node
            return here + sum(unions(v) for v in node.values())
        if isinstance(node, list):
            return sum(unions(v) for v in node)
        return 0
    assert unions(photo_groupset.SCHEMA) <= 16


def test_photos_fill_in_the_wheels_the_ad_leaves_out(models):
    """Check 50: Vision Team rims in the photos."""
    wheels = {"brand": "Vision", "model": "Team 30", "rim_depth_mm": 30, "rim_material": "aluminium",
              "confidence": "high", "photos": [3], "evidence_en": "Photo 3: VISION TEAM 30 on the rims.",
              "evidence_nl": "Foto 3: VISION TEAM 30 op de velgen."}
    r = row(run(models, "Trek Emonda SL6", "", dict(RIVAL, wheels=wheels)), "wheels")
    assert en(r["listing"]) == "Vision Team 30 aluminium 30 mm (inferred from photo analysis)"
    assert r["ad_tier"] == 2 and r["photo_why"]["nl"].startswith("Foto 3")
    # A brand alone isn't enough.
    only_brand = dict(wheels, model="", rim_depth_mm=0, rim_material="unknown")
    assert row(run(models, "Trek Emonda SL6", "", dict(RIVAL, wheels=only_brand)), "wheels")["listing"] is None


def test_photo_wheels_name_what_the_ad_only_calls_carbon_wheels(models):
    """Check 71: "De carbonwielen zijn inbegrepen", the photos show Bontrager Aeolus Elite 35."""
    wheels = {"brand": "Bontrager", "model": "Aeolus Elite 35", "rim_depth_mm": 35, "rim_material": "carbon",
              "confidence": "high", "photos": [2], "evidence_en": "Photo 2: AEOLUS ELITE 35 on the rims.",
              "evidence_nl": "Foto 2: AEOLUS ELITE 35 op de velgen."}
    text = "De carbonwielen zijn inbegrepen."
    r = row(run(models, "Trek Emonda SL6", text, dict(RIVAL, wheels=wheels)), "wheels")
    assert "Aeolus Elite 35" in en(r["listing"]) and r["photo_why"]
    # A named wheelset in the ad still wins, and an unratable photo read doesn't replace "carbon".
    r = row(run(models, "Trek Emonda SL6", "Wielen: Zipp 303", dict(RIVAL, wheels=wheels)), "wheels")
    assert "Zipp" in en(r["listing"]) and "photo_why" not in r
    r = row(run(models, "Trek Emonda SL6", text, dict(RIVAL, wheels=dict(wheels, brand="Noname", model="X1",
                                                                        rim_material="unknown"))), "wheels")
    assert "carbonwielen" in en(r["listing"])


def test_a_named_wheelset_outside_the_wheel_names_list_still_wins(models):
    """Bugbot on #281: "Wielen: Fulcrum Racing 5" names its wheels, so the photos don't replace it."""
    wheels = {"brand": "Bontrager", "model": "Aeolus Elite 35", "rim_depth_mm": 35, "rim_material": "carbon",
              "confidence": "high", "photos": [2], "evidence_en": "", "evidence_nl": ""}
    r = row(run(models, "Trek Emonda SL6", "Wielen: Fulcrum Racing 5", dict(RIVAL, wheels=wheels)), "wheels")
    assert "Fulcrum" in en(r["listing"]) and "photo_why" not in r
    # Nor a name from WHEEL_NAMES that the wheel tiers only rate through "carbon".
    assert not checks.part_tier(("wheels",), "fulcrum wind 40")
    r = row(run(models, "Trek Emonda SL6", "Carbon wielen: Fulcrum Wind 40", dict(RIVAL, wheels=wheels)), "wheels")
    assert "photo_why" not in r
