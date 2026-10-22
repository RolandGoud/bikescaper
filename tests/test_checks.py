from datetime import date

import pytest

from webapp import checks, db, i18n, seed
from webapp.app import create_app

TODAY = date(2026, 10, 18)


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
    assert groupset["status"] == checks.OK  # the original has 105, so Ultegra is an upgrade
    assert groupset["step"] == 1
    assert en(r["specs"]["headline"]) == "1 part upgraded"
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


def test_every_catalogue_model_has_a_discipline(models):
    # A new brand's families must be added to reference.FAMILY_DISCIPLINES, not left under "Other".
    unplaced = [f"{m['brand']} {m['name']}" for m in models if checks.discipline_of(m) == "other"]
    assert not unplaced


def test_disciplines_ignore_brand_categories(models):
    by_name = {f"{m['brand']} {m['name']}": checks.discipline_of(m) for m in models}
    assert by_name["Trek Madone SL 6 Gen 8"] == by_name["Canyon Ultimate CF SLX 8 Di2"] == "road"
    assert by_name["Trek Domane+ SLR 7"] == "ebike"
    assert checks.discipline_of({"brand": "Canyon", "name": "Speedmax CF 7", "category": "Aero"}) == "tt"
    assert checks.discipline_of({"brand": "Scott", "name": "Addict Gravel 20", "category": ""}) == "gravel"
    assert checks.discipline_of({"brand": "Specialized", "name": "Turbo Creo 2", "category": ""}) == "ebike"
    assert checks.discipline_of({"brand": "Ridley", "name": "Kanzo Fast", "category": "Gravel"}) == "gravel"


def test_models_page_groups_by_discipline(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models?lang=en").data.decode()
    assert "Time trial &amp; triathlon" in page and "Performance road bikes" not in page
    page = client.get("/models?lang=en&type=tt").data.decode()
    assert "Speedmax" in page and "Madone" not in page
    page = client.get("/models?lang=nl&type=tt&brand=Trek").data.decode()
    assert "Tijdrit &amp; triatlon" in page and "Speedmax" not in page


def test_framesets_have_their_own_discipline(models):
    kits = [m for m in models if "Frame and Brake Kit" in m["name"]]
    assert kits and all(checks.discipline_of(m) == "frames" for m in kits)
    assert checks.discipline_of({"brand": "Trek", "name": "Madone SLR Gen 8 Frameset", "category": ""}) == "frames"


def test_spec_sheet_is_grouped(models):
    trek = next(m for m in models if m["slug"] == "trek-domane-sl-6-gen-4")
    groups = dict(checks.spec_groups(trek))
    assert list(groups)[:4] == ["Frame & fork", "Drivetrain", "Brakes", "Wheels & tyres"]
    assert any(en == "Rear derailleur" for en, _nl, _v in groups["Drivetrain"])
    canyon = next(m for m in models if m["brand"] == "Canyon" and "Weight" in m["specs"])
    weights = [en for _g, rows in checks.spec_groups(canyon) for en, _nl, _v in rows if en == "Weight"]
    assert weights == ["Weight"]  # Canyon's "Gewicht" and "Weight" are shown once
    labels = {raw for m in models for raw in m["specs"]}
    from webapp.reference import SPEC_LABELS
    assert not labels - set(SPEC_LABELS), "map new spec labels in reference.SPEC_LABELS"


def test_model_page_shows_spec_groups(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models/trek-domane-sl-6-gen-4?lang=en").data.decode()
    assert "Drivetrain" in page and "Rear derailleur" in page
    page = client.get("/models/trek-domane-sl-6-gen-4?lang=nl").data.decode()
    assert "Aandrijving" in page and "Achterderailleur" in page


def test_brand_links_open_in_a_new_tab(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models/trek-domane-sl-6-gen-4").data.decode()
    assert 'href="https://www.trekbikes.com' in page and 'target="_blank" rel="noopener"' in page


def test_catalogue_status(models):
    by_name = {f"{m['brand']} {m['name']}": m for m in models}
    assert checks.catalogue_status(by_name["Canyon Endurace CF 7"], TODAY)[0] == "current"
    # Gen 7 was sold until 2024
    assert checks.catalogue_status(by_name["Trek Madone SL 6 Gen 7"], TODAY)[0] == "discontinued"
    # Listed in July 2025, gone from the August 2025 scrape
    gone = by_name["Canyon Endurace 7 RAW"]
    assert checks.catalogue_status(gone, TODAY)[0] == "discontinued"
    assert checks.catalogue_status(dict(gone, missed_scrapes=None), TODAY)[0] == "unknown"


def test_status_on_pages(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models/canyon-endurace-7-raw?lang=en").data.decode()
    assert "Discontinued" in page and "2025-07-18" in page
    page = client.get("/models?lang=nl").data.decode()
    assert "Uit productie" in page and "Endurace 7 RAW" in page
    page = client.get("/models?lang=en&current=1").data.decode()
    assert "Endurace 7 RAW" not in page and "Madone SL 6 Gen 7" not in page and "Domane SL 6 gen 4" in page


def test_old_database_gets_status_columns(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.sqlite3")
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE models (id INTEGER PRIMARY KEY, brand TEXT NOT NULL, name TEXT NOT NULL,"
                " slug TEXT NOT NULL UNIQUE, category TEXT, price_eur REAL, sku TEXT, url TEXT, colors TEXT,"
                " specs TEXT, image TEXT, seen_on TEXT, source_file TEXT)")
    old.execute("INSERT INTO models (brand, name, slug) VALUES ('Canyon', 'Endurace 7 RAW', 'canyon-endurace-7-raw')")
    old.commit()
    conn = db.connect(path)
    seed.refresh_status(conn)
    row = conn.execute("SELECT last_seen, missed_scrapes FROM models").fetchone()
    assert tuple(row) == ("2025-07-18", 1)


def test_colour_swatches(models):
    allroad = next(m for m in models if m["slug"] == "canyon-endurace-allroad")
    assert [c["name"] for c in allroad["colorways"]] == ["Silver Mercury", "Metal Berry"]
    assert all(c["swatch"] and c["image"] and "R138_P0" in c["image"] for c in allroad["colorways"])
    assert seed.swatch("Black/Grey").startswith("linear-gradient(")
    assert seed.swatch("Blue dark") != seed.swatch("Blue") and seed.swatch("Kaze") is None


def test_model_page_colour_selector(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/canyon-endurace-allroad?lang=en").data.decode()
    assert page.count('data-name="') == 2 and 'data-name="Metal Berry"' in page and "R138_P02" in page


def test_model_years(models):
    by_slug = {m["slug"]: m for m in models}
    assert checks.model_years(by_slug["trek-madone-sl-6-gen-7"], TODAY)[:2] == (2023, 2024)
    first, last, _note = checks.model_years(by_slug["canyon-endurace-allroad"], TODAY)
    assert first >= 2024 and last is None  # still sold
    gone = dict(by_slug["canyon-endurace-allroad"], missed_scrapes=2)
    assert checks.model_years(gone, TODAY)[1] == gone["photo_years"][-1]
    assert checks.model_years(dict(gone, photo_years=[]), TODAY) is None


def test_tiles_show_brand_logo_and_discontinued_badge(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models?lang=en&brand=Canyon").data.decode()
    assert '<span class="brand-mark" role="img" aria-label="Canyon" style="--logo: url(\'/static/logos/canyon.svg\')"></span>' in page
    assert 'class="status discontinued overlay"' in page  # Endurace 7 RAW
    assert app.test_client().get("/static/logos/trek.svg").status_code == 200


def test_brand_pills_show_logos(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/models?lang=en").data.decode()
    for name in ("Trek", "Canyon", "Specialized", "Giant", "Cannondale", "Cube", "Factor"):
        assert f'class="pill-logo" role="img" aria-label="{name}"' in page
        assert app.test_client().get(f"/static/logos/{name.lower()}.svg").status_code == 200
    assert ">Scott</span>" in page  # no logo yet, so the name stays


# ---------------------------------------------------------------- brands from brand_scrapers

def test_every_collected_brand_is_loaded(models):
    from webapp.reference import BRANDS
    loaded = {m["brand"] for m in models}
    for brand in BRANDS:
        assert (brand["name"] in loaded) == brand["scraper"], brand["name"]


def test_s_works_names_specialized():
    assert checks.read_claims("S-Works Tarmac SL7 maat 54")["brand"] == "Specialized"


@pytest.mark.parametrize("title,description,brand,family", [
    ("Specialized Tarmac SL9 Expert Ultegra Di2 maat 54", "carbon, schijfremmen", "Specialized", "tarmac"),
    ("Giant TCR Advanced Pro 0 Di2 maat M", "Shimano Ultegra Di2", "Giant", "tcr"),
    ("Cannondale SuperSix EVO 3 maat 56", "SRAM Force AXS", "Cannondale", "supersix"),
    ("Cube Attain C:62 SLX 56 cm", "105 Di2", "Cube", "attain"),
    ("Factor Monza Ultegra maat 54", "", "Factor", "monza"),
])
def test_matching_new_brands(models, title, description, brand, family):
    r = run(models, title, description, height=178)
    assert r["model"] is not None, title
    assert r["model"]["brand"] == brand
    assert checks.family_of(r["model"]["name"]) == family
    assert r["size"]["fit"] is not None


def test_new_brands_have_their_own_size_chart():
    from webapp.reference import SIZE_CHARTS
    for brand in ("Specialized", "Giant", "Cannondale", "Cube", "Factor"):
        assert checks.size_options(brand) is SIZE_CHARTS[brand]


@pytest.mark.parametrize("parts,text,tier", [
    (("groupset",), "Shimano Claris R2000", 1),
    (("groupset",), "Shimano Tiagra 4700", 2),
    (("groupset",), "SRAM Rival eTap AXS", 3),
    (("groupset",), "Shimano Ultegra R8150 Di2", 4),
    (("groupset",), "SRAM RED XPLR eTap AXS", 5),
    (("groupset",), "Shimano GRX RX820", 4),
    (("groupset",), "Shimano GRX RX610", 3),
    (("frame",), "100 Series Alpha Aluminium", 1),
    (("frame",), "500 Series OCLV Carbon", 3),
    (("frame",), "800 Series OCLV-carbon", 4),
    (("frame",), "Carbon Ultimate CF SLX 8 Di2", 4),
    (("frame",), "Carbon Aeroad CFR Di2", 5),
    (("frame",), "Aluminium Endurace AL 7", 2),
    (("wheels",), "Bontrager Aeolus Pro 51, OCLV Carbon, Tubeless Ready", 4),
    (("wheels",), "Bontrager Aeolus RSL 37, OCLV Carbon", 5),
    (("wheels",), "Bontrager Paradigm SL, Tubeless Ready", 2),
    (("tyres", "wheels"), "DT Swiss ARC 1400 DICUT db 55", 5),
    (("tyres",), "Schwalbe G-One Comp K-Guard", 2),
    (("tyres",), "Continental Grand Prix 5000 S TR, 28mm", 4),
    (("tyres",), "Pirelli P ZERO Race TLR RS", 5),
    (("rotors",), "Shimano RT10, centerlock, 160 mm", 1),
    (("rotors",), "SRAM Paceline, afgerond, centerlock, 160 mm", 4),
    (("groupset", "brakes"), "Tektro C550, mechanische schijfrem", 1),
    (("groupset", "brakes"), "Shimano 105 hydraulische schijfrem, flat-mount", 3),
    (("saddle",), "Verse Short Elite, holle roestvaststalen rails", 3),
    (("saddle",), "Bontrager Verse Comp, stalen rails", 1),
    (("seatpost",), "Bontrager lichtmetalen seatmast cap, 10 mm offset", 2),
    (("seatpost",), "KVF aero carbon zadelpen, 20 mm offset", 5),
    (("motor",), "TQ-HPR50, 50 Nm koppel", 5),
    (("stem",), "Bontrager Elite, 31,8 mm", 2),
    (("tyres",), "Bontrager Girona Pro", 4),
    (("tyres",), "Stuurlint", None),
    (("frame",), "Aethos 2 FACT 10r Carbon Aethos 2 Pro", 4),
    (("frame",), "Advanced SL-grade composite Revolt Advanced SL 0", 5),
    (("frame",), "CAAD14, SmartForm C1 Premium Alloy", 2),
    (("frame",), "Agree C:62 SLT Di2", 3),
    (("frame",), "TeXtreme, Toray, Nippon Graphite Pitch-Based Fiber", 5),
    (("wheels",), "Roval Rapide CLX II", 5),
    (("wheels",), "Giant SLR 0 40 Carbon Disc WheelSystem", 4),
    (("tyres",), "S-Works Turbo, 700x30", 5),
])
def test_part_tiers(parts, text, tier):
    assert checks.part_tier(parts, text) == tier


def test_every_model_with_a_spec_sheet_has_an_overall_tier(models):
    for m in models:
        tiers = checks.spec_tiers(m)
        if tiers["groups"].get("Frame & fork") or tiers["groups"].get("Drivetrain"):
            assert tiers["overall"] in range(1, 6), m["name"]


def test_overall_tier_follows_the_price(models):
    by_name = {m["name"]: checks.model_tier(m) for m in models}
    assert by_name["Domane AL 2 Gen 4"] < by_name["Domane SL 5 Gen 4"] < by_name["Domane SLR 9 gen 4"]
    assert by_name["Endurace AllRoad"] < by_name["Ultimate CF SLX 8 Di2"] < by_name["Ultimate CFR Di2"]


def test_tiers_rise_with_price_across_brands(models):
    import statistics
    medians = [statistics.median(m["price_eur"] for m in models if checks.model_tier(m) == t and m["price_eur"])
               for t in range(2, 6)]
    assert medians == sorted(medians)


def test_frame_group_is_rated_on_the_frame_not_the_fork(models):
    m = next(m for m in models if m["name"] == "Domane AL 2 Gen 4")
    tiers = checks.spec_tiers(m)
    assert tiers["rows"]["Fork"] == 4 and tiers["rows"]["Frame"] == 1
    assert tiers["groups"]["Frame & fork"] == 1


def test_weight_tier_depends_on_discipline(models):
    road = next(m for m in models if m["name"] == "Ultimate CFR Di2")
    assert checks.weight_tier(road, "6.78 kg") == 5
    assert checks.weight_tier(road, "56 cm - 10,61 kg (met TLR sealant)") == 1


def test_downgraded_groupset_lowers_the_value(models):
    same = run(models, "Trek Madone SLR 7 Gen 8 2025", "Shimano Ultegra Di2, carbon, schijfremmen", 5000)
    down = run(models, "Trek Madone SLR 7 Gen 8 2025", "Shimano 105 groep, carbon, schijfremmen", 5000)
    groupset = next(row for row in down["specs"]["rows"] if row["key"] == "groupset")
    assert groupset["status"] == checks.BAD and groupset["step"] == -1
    assert en(groupset["result"]) == "Downgrade, tier 4 to 3"
    assert down["specs"]["status"] == checks.BAD
    assert down["value"]["high"] < same["value"]["high"]


def test_wheels_named_in_the_ad_are_compared_by_tier(models):
    r = run(models, "Trek Domane SL 5 Gen 4 2024", "Shimano 105, upgrade: Aeolus RSL 37 wielen, GP5000 banden")
    wheels = next(row for row in r["specs"]["rows"] if row["key"] == "wheels")
    tyres = next(row for row in r["specs"]["rows"] if row["key"] == "tyres")
    assert wheels["step"] == 3 and wheels["status"] == checks.OK
    assert tyres["status"] == checks.OK
    assert "upgraded" in en(r["specs"]["headline"])
    assert any("original Wheels" in en(q) for q in r["questions"])


def test_carbon_frame_is_not_carbon_wheels():
    assert checks.read_claims("Trek Domane", "carbon frame, nieuwe wielen")["wheels"] is None


def test_tiers_on_pages(tmp_path):
    app = create_app(str(tmp_path / "t.sqlite3"))
    with app.app_context():
        seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models/trek-domane-slr-9-gen-4?lang=en").get_data(as_text=True)
    assert "Spec tier" in page and "Top" in page
    listing = client.get("/models?tier=5&lang=en").get_data(as_text=True)
    assert "Domane SLR 9" in listing and "Domane AL 2" not in listing


@pytest.mark.parametrize("text,tier", [("Shimano GRX 400", 2), ("Shimano GRX RX400", 2), ("GRX 600 groep", 3),
                                       ("Shimano GRX 800", 4), ("Shimano GRX Di2", 3)])
def test_grx_series(text, tier):
    assert checks.detect_groupset(text)["tier"] == tier


def test_wheel_names_dont_rate_the_tyres():
    c = checks.read_claims("Trek Domane", "Aeolus RSL 37 wielen en Schwalbe One banden")
    assert c["wheels"]["tier"] == 5 and c["tyres"]["tier"] == 3


def test_rim_brakes_are_not_wheels():
    assert checks.read_claims("Trek Domane", "carbon racefiets met velgremmen")["wheels"] is None


def test_named_wheels_on_a_model_without_wheel_data(models):
    model = next(m for m in models if m["name"] == "Ultimate CF SLX 8 Di2")  # Canyon lists no wheels
    claims = checks.read_claims("Canyon Ultimate CF SLX 8 Di2", "Zipp 404 wielen")
    specs = checks.check_specs(model, claims)
    wheels = next(row for row in specs["rows"] if row["key"] == "wheels")
    assert wheels["status"] == checks.UNKNOWN
    checks.seller_questions(model, claims, {"status": checks.OK}, specs, {"status": checks.OK})


def test_missing_brand_snapshot_is_downloaded(tmp_path, monkeypatch):
    # An older NAS compose file unpacks only data/Trek and data/Canyon; the seed fetches the rest.
    import io
    import json as _json
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    monkeypatch.setattr(seed, "COLLECTED", ["Cube"])
    snapshot = [{"name": "Attain SLX", "price": 1499}]

    def fake_urlopen(url, timeout=None):
        if "api.github.com" in url:
            return io.BytesIO(_json.dumps([{"name": "cube_bikes_20261022_151753.json"}, {"name": "x.csv"}]).encode())
        assert url.endswith("/data/Cube/cube_bikes_20261022_151753.json")
        return io.BytesIO(_json.dumps(snapshot).encode())

    monkeypatch.setattr(seed.urllib.request, "urlopen", fake_urlopen)
    assert seed.fetch_missing_snapshots("main") == 1
    assert seed.latest_snapshot("Cube") == "data/Cube/cube_bikes_20261022_151753.json"
    assert seed.fetch_missing_snapshots("main") == 0  # already there
