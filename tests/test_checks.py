import re
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


def test_unknown_brand_gives_no_match(models):
    r = run(models, "Ridley Noah Fast maat 54", "2022, 105")
    assert r["claims"]["brand"] is None
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


def test_models_filters_animate_without_reload(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/models?lang=en").data.decode()
    # models.js swaps the list in on the form's submit event, which form.submit() would skip
    assert "models.js" in page and "this.form.submit()" not in page and "this.form.requestSubmit()" in page
    assert app.test_client().get("/static/models.js").status_code == 200


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
    for name in ("Trek", "Canyon", "Specialized", "Giant", "Cannondale", "Cube", "Factor", "Scott", "Orbea"):
        assert f'class="pill-logo" role="img" aria-label="{name}"' in page
        assert app.test_client().get(f"/static/logos/{name.lower()}.svg").status_code == 200
    home = app.test_client().get("/?lang=en").data.decode()
    assert 'aria-label="Orbea"' in home and ">Orbea</a>" not in home  # every brand shows its logo


def test_selected_filters_link_back_to_all(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models?lang=en&type=road&brand=Canyon").data.decode()
    assert '<option value="road" selected>' in page
    assert 'class="pill brand on" href="/models?type=road"' in page  # Canyon logo clears the brand
    assert "Mountain" not in page  # no mountain bikes yet


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
    ("Scott Addict RC 30 maat 54", "Shimano 105 Di2", "Scott", "addict"),
    ("Orbea Orca M30 maat 53", "2027, 105", "Orbea", "orca"),
])
def test_matching_new_brands(models, title, description, brand, family):
    r = run(models, title, description, height=178)
    assert r["model"] is not None, title
    assert r["model"]["brand"] == brand
    assert checks.family_of(r["model"]["name"]) == family
    assert r["size"]["fit"] is not None


def test_new_brands_have_their_own_size_chart():
    from webapp.reference import SIZE_CHARTS
    for brand in ("Specialized", "Giant", "Cannondale", "Cube", "Factor", "Scott", "Orbea"):
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


def test_comparison_rows_carry_both_tiers(models):
    r = run(models, "Trek Domane SL 5 Gen 4 2024", "Shimano Ultegra, carbon frame, Schwalbe Lugano banden")
    rows = {row["key"]: row for row in r["specs"]["rows"]}
    assert (rows["groupset"]["ref_tier"], rows["groupset"]["ad_tier"]) == (3, 4)
    assert rows["tyres"]["ad_tier"] == 1 and rows["tyres"]["step"] < 0
    assert rows["frame"]["ref_tier"] and rows["frame"]["ad_tier"] is None
    assert rows["saddle"]["ref_tier"] == 1


def test_report_shows_tiers_and_part_icons(tmp_path):
    app = create_app(str(tmp_path / "t.sqlite3"))
    with app.app_context():
        seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL 5 Gen 4 2023 maat 56 Ultegra", "asking_price": "1900",
                                "description": "carbon frame, Schwalbe Lugano banden"})
    page = client.get("/check/1?lang=en").get_data(as_text=True)
    assert 'class="part-icon"' in page
    assert 'class="tier small t4 up"' in page and 'class="tier small t1 down"' in page
    assert "RESULT" not in page and "Check photos" not in page
    assert page.count('class="arrow check"') >= 1  # the matching carbon frame shows its tier with a check mark...
    assert "<span>Matches</span>" not in page  # ...instead of the word


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


def test_models_use_their_own_size_chart(models):
    by_slug = {m["slug"]: m for m in models}
    own = checks.model_charts()
    assert own, "webapp/size_charts.json is missing"
    for slug, chart in own.items():
        if slug in by_slug and any(s.get("low") for s in chart["sizes"].values()):
            got = checks.model_size_chart(by_slug[slug])
            assert got["source"] == chart["source"] and got["sizes"], slug
    published = [m for m in models if checks.model_size_chart(m)["source"] == "brand"]
    assert {m["brand"] for m in published} >= {"Trek", "Canyon", "Cannondale"}
    unknown = dict(models[0], slug="no-such-model")
    assert checks.model_size_chart(unknown)["source"] == "generic"


def test_size_check_falls_back_to_the_brand_chart_for_unknown_sizes(models):
    model = next(m for m in models if checks.model_size_chart(m)["source"] == "brand" and m["brand"] == "Canyon")
    letters = checks.check_size(model, {"size": "M"}, 180)
    assert letters["fit"] is not None and "own size chart" in en(letters["notes"][0])
    numbers = checks.check_size(model, {"size": "56"}, 180)  # Canyon sizes by letter
    assert "Generic chart" in en(numbers["notes"][0])


def test_size_lines_group_builds_that_share_a_chart(models):
    lines = checks.size_lines(models, "Canyon")
    assert sum(len(l["models"]) for l in lines) == sum(1 for m in models if m["brand"] == "Canyon")
    assert any(len(l["models"]) > 1 for l in lines)
    for line in lines:
        assert len({str(sorted(checks.model_size_chart(m)["sizes"].items())) for m in line["models"]}) == 1 \
            or line["chart"]["source"] == "generic"


def test_size_finder_picks_a_model(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    conn = db.connect(app.config["DB_PATH"])
    model = next(m for m in db.all_models(conn) if checks.model_size_chart(m)["source"] == "brand")
    page = client.get(f"/size?model={model['slug']}&height=180&lang=en").data.decode()
    assert "own size chart for this model" in page and "selected" in page
    page = client.get("/size?brand=Giant&height=181&lang=en").data.decode()
    assert "pick a model for its own chart" in page


def test_checked_ad_shows_its_own_photo_next_to_the_catalogue_photo(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    ad_photo = "https://images.marktplaats.com/api/v1/x/images/aa/1?rule=eps_85.JPG"
    conn.execute("INSERT INTO checks (title, asking_price, photos) VALUES (?, ?, ?)",
                 ("Trek Domane SL 6 Gen 4 2023 maat 56", 3250, f'["{ad_photo}"]'))
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane AL 4 Gen 4 2024", 1050))
    conn.commit()
    client = app.test_client()
    for url in ["/", "/listings"]:
        page = client.get(url + "?lang=en").get_data(as_text=True)
        # Only the check made from a link has a photo of its own, so only that card merges two photos.
        assert page.count('class="photo duo"') == 1, url
        assert ad_photo.replace("&", "&amp;") in page and 'class="duo-range"' in page
    # On the report the merged slider is the first tile of the ad's photo strip.
    report = client.get("/check/1?lang=en").get_data(as_text=True)
    assert 0 < report.index('class="strip-duo"') < report.index('data-photo="0"')
    # ...the ad photo also shows on its own, and the slider opens big in the lightbox, ahead of the photos.
    assert report.count(f'href="{ad_photo}"'.replace("&", "&amp;")) == 1
    assert report.index('<dialog class="lightbox"') < report.index('class="lb-duo"') < report.index('</dialog>')
    # Parts we can only judge from the photos link to them instead of saying "check photos" twice.
    assert '<a class="open-photos" href="#ad-photos">Compare photos' in report and "Check photos" not in report


@pytest.mark.parametrize("title, name, year, size, colour", [
    ("Trek Domane SL 6 Gen 4 2023 maat 56", "Domane SL 6 Gen 4", 2023, "56", None),
    ("Canyon Aeroad CF SLX 8 AXS 2021 maat L", "Aeroad CF SLX 8 AXS", 2021, "L", None),
    ("Giant TCR Advanced Pro 1 zwart/rood 58cm bouwjaar 2021", "TCR Advanced Pro 1", 2021, "58", "zwart/rood"),
    ("S-Works Tarmac SL7 mat zwart size L", "Tarmac SL7", None, "L", "mat zwart"),
    ("Racefiets Trek Emonda ALR 5 - 2019 - 54 cm - blauw", "Racefiets Emonda ALR 5", 2019, "54", "blauw"),
])
def test_ad_title_is_split_into_name_and_facts(title, name, year, size, colour):
    assert checks.split_title(title) == {"name": name, "year": year, "size": size, "colour": colour}


def test_links_off_the_site_open_in_a_new_tab(tmp_path):
    from webapp.app import open_in_new_tab
    assert open_in_new_tab('<a href="https://x.nl/a">') == '<a href="https://x.nl/a" target="_blank" rel="noopener">'
    assert open_in_new_tab('<a href="https://x.nl" rel="nofollow">') == '<a href="https://x.nl" rel="noopener nofollow" target="_blank">'
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    ad = "https://www.marktplaats.nl/v/fietsen/racefietsen/m123-trek-domane"
    conn.execute("INSERT INTO checks (title, asking_price, listing_url, photos) VALUES (?, ?, ?, ?)",
                 ("Trek Domane SL 6 Gen 4 2023 maat 56", 3250, ad, '["https://images.marktplaats.com/x/1.JPG"]'))
    conn.commit()
    client = app.test_client()
    pages = ["/", "/listings", "/models", "/models/trek-domane-sl-6-gen-4", "/check/1", "/how-it-works", "/value", "/size"]
    seen = 0
    for url in pages:
        html = client.get(url + "?lang=en").get_data(as_text=True)
        for tag in re.findall(r'<a\s[^>]*href="https?://[^>]*>', html):
            assert 'target="_blank"' in tag and "noopener" in tag, (url, tag)
            seen += 1
        assert not re.search(r'<a\s[^>]*href="/[^"]*"[^>]*target="_blank"', html), url  # our own links stay in the same tab
    assert seen >= 4  # product page, brand sites, the ad and its photo


def test_certainty_comes_back_when_our_match_is_picked_again(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56 Ultegra", "asking_price": "2450"})
    page = client.get("/check/1?lang=nl").data.decode()
    ours = re.search(r'<option value="(\d+)" selected', page).group(1)
    other = re.search(r'<option value="(\d+)" >', page).group(1)
    level = re.search(r"zekerheid: (\w+)", page).group(1)  # whatever ours is, it must come back

    client.post("/check/1/match", data={"model_id": other})
    page = client.get("/check/1?lang=nl").data.decode()
    assert "Gekozen door jou" in page and "zekerheid" not in page

    client.post("/check/1/match", data={"model_id": ours})
    page = client.get("/check/1?lang=nl").data.decode()
    assert f"zekerheid: {level}" in page and "Gekozen door jou" not in page


def test_size_systems_split_frame_and_letter_sizes(tmp_path):
    assert checks.size_systems(["47", "50", "XS", "M"]) == [("Frame size (cm)", ["47", "50"]), ("Letter sizes", ["XS", "M"])]
    assert checks.size_systems(["S", "M"]) == [("Letter sizes", ["S", "M"])]
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/size?brand=Trek&height=178&lang=en").data.decode()
    assert page.count('class="sizes"') == 2 and "Letter sizes" in page


def test_year_estimate_from_groupset(models):
    r = run(models, "Trek Domane SL 6 gen 4 2021", "Shimano 105 Di2 2x12, schijfremmen")
    e = r["year_estimate"]
    assert e["first"] == 2023 and e["status"] == checks.BAD
    assert en(e["headline"]) == "Doesn't fit 2023 or later"
    r = run(models, "Trek Domane SL 6 gen 4", "Shimano 105 Di2 2x12, schijfremmen")
    assert en(r["year_estimate"]["headline"]) == "Probably 2023 or later"


def test_year_estimate_combines_clues(models):
    r = run(models, "Canyon Ultimate CF SL 8 Di2 2019", "Ultegra Di2 11-speed, velgremmen, carbon")
    e = r["year_estimate"]
    assert (e["first"], e["last"], e["status"]) == (None, 2022, checks.OK)
    r = run(models, "Trek Domane SL 5 gen 4 2022", "Shimano 105 R7000")
    e = r["year_estimate"]
    # The groupset says 2023-2024, and only the 2023 spec sheet has an R7000 groupset.
    assert (e["first"], e["last"], e["status"]) == (2023, 2023, checks.WARN)
    assert any("R7000" in en(x) for x in e["evidence"])


def test_year_estimate_from_named_colourway(models):
    r = run(models, "Canyon Endurace CF 7 Lillet Grey 2020")
    e = r["year_estimate"]
    assert (e["first"], e["last"], e["status"]) == (2025, 2027, checks.BAD)
    assert "Lillet Grey" in en(e["evidence"][0])
    # Plain colour words like "Grey light" date nothing.
    e = run(models, "Trek Domane SL 5 Gen 4 grey light")["year_estimate"]
    assert not any("Colour" in en(x) for x in e["evidence"])


def test_colourway_year():
    assert checks.colourway_year({"image": "Trek/EmondaSL5_23_36974_A_Primary_03.jpg"}) == 2023
    assert checks.colourway_year({"image": "Trek/x/DomaneSL6-26-57639-A-Primary_02.jpg"}) == 2026
    assert checks.colourway_year({"image": "Canyon/E/2026_FULL_endurace_cf-7_4274_R076_P10.jpg"}) == 2026
    assert checks.colourway_year({"image": "Canyon/E/full_2024_3705_endurace-7_P05_P5.jpg"}) == 2024
    assert checks.colourway_year({"image": None}) is None


def test_105_rules_yield_to_a_higher_group(models):
    r = run(models, "Canyon Ultimate CF SL 8 Di2 2019", "Ultegra Di2, 105 cassette")
    assert r["year_estimate"] is None or "105" not in en(r["year_estimate"]["evidence"][0])
    r = run(models, "Canyon Ultimate CF SL 8 Di2 2019", "Ultegra Di2 11-speed, 105 cassette")
    assert "Ultegra" in en(r["year_estimate"]["evidence"][0])


def test_model_page_shows_family_as_tiles(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/canyon-endurace-allroad?lang=nl").data.decode()
    others = page.split("Andere Endurace-modellen")[1]
    assert 'class="model-card" href="/models/canyon-endurace-cf-7"' in others and "brand-mark" in others


def test_models_page_takes_several_brands(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/models?lang=en&brand=Trek&brand=Canyon").data.decode()
    assert "Madone" in page and "Speedmax" in page and "Tarmac" not in page
    # each pill turns its own brand on or off and keeps the others
    assert 'href="/models?brand=Canyon" aria-current="true"' in page
    assert 'href="/models?brand=Trek&amp;brand=Canyon&amp;brand=Specialized"' in page
    assert page.count('name="brand"') == 2 and "brand=Trek&amp;brand=Canyon&amp;lang=nl" in page


def test_value_axis_runs_from_zero_to_the_end_of_the_scale():
    from webapp.checks import axis_ticks
    ticks = axis_ticks(1049)
    assert [round(v) for v, _ in ticks] == [0, 250, 500, 750, 1049]
    assert ticks[0][1] == 0 and ticks[-1][1] == 100


def test_models_page_starts_on_all_brands(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/models?lang=nl").data.decode()
    assert 'class="pill brand all on" href="/models" aria-current="true">Alle merken' in page
    assert page.count('class="pill brand on"') == 0 and 'href="/models?brand=Trek"' in page
    page = app.test_client().get("/models?lang=en&brand=Trek").data.decode()
    assert 'class="pill brand all " href="/models">All brands' in page
    assert page.count('class="pill brand on"') == 1 and 'href="/models" aria-current="true"' in page


def test_seller_named_version_wins(models):
    # An S-Works Tarmac SL7 is not an SL9: the version number the seller names outweighs "S-Works".
    r = run(models, "Specialized S-Works Tarmac SL7", "", 3400)
    assert "SL7" in r["model"]["name"]
    assert r["name_check"]["extra"] == ["S-Works"] and "Sport" in r["name_check"]["missing"]
    # With no SL6 in the catalogue we still compare with a Tarmac, but say we disagree with the seller.
    r = run(models, "Specialized S-Works Tarmac SL6 2019", "", 2500)
    assert r["name_check"]["conflicts"] == [("SL9", "SL6")]
    assert r["confidence"] is not None and str(r["confidence"]) in ("low", "laag")
    # The generation counts too, and an exact name has nothing to say.
    assert run(models, "Trek Domane SL6 gen 3", "", 1500)["name_check"]["conflicts"] == [("Gen 4", "Gen 3")]
    assert run(models, "Trek Domane SL 6 Gen 4 2023 maat 56", "", 2500)["name_check"] is None


def test_report_says_when_we_dispute_the_model(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    resp = client.post("/check", data={"title": "Specialized S-Works Tarmac SL6 2019", "asking_price": "2500"})
    page = client.get(resp.headers["Location"] + "?lang=nl").data.decode()
    assert "Wij denken dat dit een ander model is dan de verkoper zegt" in page
    assert "De advertentie zegt SL6, dit model is een SL9." in page


def test_value_uses_the_oldest_estimated_year(models):
    r = run(models, "Trek Domane SL 6 gen 4", "Shimano 105 Di2 2x12, schijfremmen", price=2000)
    assert r["value"]["model_year"] == 2023
    assert any("probably from 2023 or later" in en(n) for n in r["value"]["notes"])
    # A stated year still wins.
    assert run(models, "Trek Domane SL 6 gen 4 2025", "Shimano 105 Di2 2x12", price=2000)["value"]["model_year"] == 2025
    # No clue in the ad: the first year of the brand's photos, not the catalogue year.
    r = run(models, "Trek Emonda SL 6", price=1500)
    assert r["model"]["photo_years"] == [2024] and r["value"]["model_year"] == 2024


def test_condition_reads_negated_damage_and_the_ads_condition_field():
    assert checks.detect_condition("Hij heeft geen schade en is netjes behandeld") is None
    assert checks.detect_condition("Nooit gevallen, zonder scheurtjes. Zo goed als nieuw") == "like-new"
    assert checks.detect_condition("Kleine schade aan de lak") == "damaged"
    assert checks.detect_condition("Specificaties\nConditie: Gebruikt") == "used"
    assert checks.detect_condition("Conditie: Zo goed als nieuw") == "like-new"


def test_year_is_always_estimated(models):
    # No clue in the ad: the matched model's years, which can't rule out a stated year (it may be an older
    # generation we don't have).
    e = run(models, "Trek Domane SL 6 2019")["year_estimate"]
    assert e["first"] == 2023 and en(e["headline"]) == "Can't check 2019"
    assert run(models, "Trek Domane SL 6 2024")["year_estimate"]["status"] == checks.OK
    e = run(models, "Trek Emonda SL 6 2021")["year_estimate"]
    assert e["status"] == checks.UNKNOWN and en(e["headline"]) == "Can't check 2021"
    assert en(run(models, "Trek Emonda SL 6")["year_estimate"]["headline"]) == "Probably 2024"


def test_value_replaces_a_stated_year_the_details_rule_out(models):
    r = run(models, "Trek Domane SL 6 gen 4 2019", "Shimano 105 Di2 2x12", price=2000)
    assert r["value"]["model_year"] == 2023
    assert any("stated 2019 doesn't fit" in en(n) for n in r["value"]["notes"])
    assert run(models, "Trek Domane SL 6 gen 4 2024", "Shimano 105 Di2 2x12", price=2000)["value"]["model_year"] == 2024


def test_listings_have_no_result_filter(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/listings?lang=nl").data.decode()
    assert "Er klopt iets niet" not in page and "Vraag het na" not in page
    assert "Elke check" in page  # the view switch stays
def test_year_tabs_show_our_scrape_and_archived_years():
    from datetime import date
    model = {"name": "Domane AL 2 Gen 4", "brand": "Trek", "seen_on": "2025-07-18", "price_eur": 999.0, "url": "u",
             "specs": {"Frame": "100 Series Alpha Aluminium", "Rem": "Tektro C550"},
             "year_specs": {"checked": list(range(2020, 2027)), "checked_on": "2026-10-23", "years": {
                 "2024": {"captured": "2024-03-28", "ts": "20240328000000", "url": "a", "price": 949.0,
                          "specs": {"Frame": "100 Series Alpha Aluminium", "Rem": "Tektro MD-C550"}},
                 "2023": {"captured": "2023-04-01", "ts": "20230401000000", "url": "b", "unreadable": True}}}}
    tabs = {t["year"]: t for t in checks.year_tabs(model, today=date(2026, 10, 23))}
    assert list(tabs) == list(range(2018, 2027))
    assert [tabs[y]["state"] for y in (2022, 2023, 2024, 2025)] == ["none", "unreadable", "archive", "scrape"]
    assert tabs[2024]["changed"] == set() and tabs[2025]["changed"] == {"Brakes"}
    # A brand whose archive wasn't searched says so instead of "no copy".
    assert checks.year_tabs(dict(model, year_specs={}), today=date(2026, 1, 1))[0]["state"] == "unchecked"


def test_model_page_has_year_tabs(tmp_path):
    from webapp.app import create_app
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    page = create_app(path).test_client().get("/models/trek-domane-al-2-gen-4?lang=en").get_data(as_text=True)
    assert 'id="tab-2020"' in page and 'id="tab-2025" aria-controls="year-2025"' in page
    # data/years/Trek.json has the 2024 Wayback Machine copy, with its photo
    assert 'class="year-tab archive" id="tab-2024"' in page and "Trek/years/domaneal2gen4_2024.jpg" in page


def test_model_page_photo_carousel_runs_oldest_to_current(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/giant-defy-advanced-2?lang=nl").data.decode()
    years = re.findall(r'class="gallery-thumb[^"]*" aria-pressed="(\w+)" data-year="(\d+)"', page)
    assert len(years) > 2 and [int(y) for _p, y in years] == sorted(int(y) for _p, y in years)
    assert [p for p, _y in years] == ["false"] * (len(years) - 1) + ["true"]  # the current bike is shown first
    assert "year-photo" not in page  # the year photos moved out of the spec tabs
    shown = {int(y) for _p, y in years}
    assert shown == set(range(min(shown), max(shown) + 1))  # a year without a photo gets a placeholder
    assert re.search(r'id="gallery-chip">\d{4}<', page)  # the year only, no colour
    assert "nog niet verzameld" not in page  # model years from the year sheets


def test_sheet_years_skip_predecessor_sheets(models):
    m = dict(models[0], year_specs={"years": {"2019": {"specs": {"Frame": "x"}, "sheet_name": "Old"},
                                              "2021": {"specs": {"Frame": "x"}}, "2022": {"unreadable": True}}})
    assert checks.sheet_years(m, TODAY)[0] == 2021
    assert checks.sheet_years(dict(m, year_specs={}), TODAY) is None


def test_year_clues_from_the_spec_sheets_of_each_year(models):
    m = dict(models[0], seen_on="2026-01-01", colorways=[], colors=[], specs={"Cassette": "Shimano 105, 11-36"},
             year_specs={"years": {"2021": {"specs": {"Achterderailleur": "Shimano GRX RX810", "Cassette": "11-34"}, "colours": ["Carbon", "Matte Pennyflake"]},
                                   "2023": {"specs": {"Achterderailleur": "Shimano GRX RX810", "Cassette": "11-34"}, "colours": ["Crimson"]},
                                   "2025": {"specs": {"Achterderailleur": "Shimano GRX RX820", "Cassette": "11-36"}, "colours": ["Crimson"]}}})
    clues = checks.sheet_clues(m, "Gravelbike met GRX RX810 en een 11-34 cassette, kleur matte pennyflake, carbon")
    # 2022 and 2024 have no sheet, so maybe; the oldest sheet's year leaves the start open
    assert [(a, b) for a, b, _m in clues] == [(None, 2024), (None, 2022)]
    assert "RX810" in en(clues[0][2]) and "Pennyflake" in en(clues[1][2])
    assert checks.sheet_clues(m, "Shimano 105, carbon") == []  # in every year, or a plain colour
    m["year_specs"]["years"]["2023"]["colours"] = ["Blue Dragonfly/Chrome"]
    clues = checks.sheet_clues(m, "Mooie blue dragonfly kleur")
    assert [(a, b) for a, b, _m in clues] == [(2022, 2024)] and "Blue Dragonfly" in en(clues[0][2])


def test_age_from_the_year_sheets_without_a_generation(models):
    m = dict(models[0], name="Defy Advanced 1", brand="Giant", missed_scrapes=0, last_seen="2026-10-01",
             year_specs={"checked": list(range(2018, 2027)), "years": {
                 "2018": {"specs": {"Frame": "x"}}, "2024": {"specs": {"Frame": "x"}}, "2025": {"specs": {"Frame": "x"}}}})
    claims = checks.read_claims("Giant Defy Advanced 1 2025", "")
    assert checks.check_age(m, claims, TODAY)["status"] == checks.OK
    old = checks.check_age(m, checks.read_claims("Giant Defy Advanced 1 2016", ""), TODAY)
    assert old["status"] == checks.UNKNOWN and "2018" in en(old["detail"])  # before the oldest year we looked up
    assert checks.check_age(dict(m, year_specs={}), claims, TODAY)["status"] == checks.UNKNOWN


def test_colour_clue_reads_dutch_colour_words(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[{"name": "Cryo Silver/Chrome"}], specs={"Frame": "x"},
             year_specs={"years": {"2024": {"specs": {"Frame": "x"}, "colours": ["Charcoal/Milky Way"]},
                                   "2025": {"specs": {"Frame": "x"}, "colours": ["Frost Silver/Cordovan"]},
                                   "2026": {"specs": {"Frame": "x"}, "colours": ["Cyber Lime"]}}})
    clues = checks.sheet_clues(m, "Kleur frost zilver, modeljaar 2025")
    assert [(a, b) for a, b, _m in clues] == [(2025, 2025)]
    # Our own scrape in October shows next year's colours: it doesn't replace the 2026 sheet
    assert checks.year_sheets(m)[2026]["colours"] == ["Cyber Lime"]


def test_slider_shows_the_year_photo_that_fits_the_ad(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[], specs={"Frame": "x"},
             year_specs={"years": {"2024": {"specs": {"Frame": "x"}, "colours": ["Charcoal/Milky Way"], "image": "y/2024.jpg"},
                                   "2025": {"specs": {"Frame": "x"}, "colours": ["Frost Silver/Cordovan"], "image": "y/2025.jpg"},
                                   "2026": {"specs": {"Frame": "x"}, "colours": ["Thundercloud", "Cyber Lime"], "image": "y/2026.jpg"}}})
    claims = checks.read_claims("Giant Defy 2024", "kleur frost zilver")
    estimate = {"status": checks.BAD, "first": 2025, "last": 2025}
    assert checks.year_photo(m, claims, estimate, "Giant Defy 2024 kleur frost zilver") == (2025, "y/2025.jpg", "Frost Silver")
    claims = checks.read_claims("Giant Defy 2026", "Cyber lime")
    assert checks.year_photo(m, claims, {"status": checks.OK}, "Giant Defy 2026 cyber lime") == (2026, "y/2026.jpg", None)
    claims = checks.read_claims("Giant Defy 2024", "")
    assert checks.year_photo(m, claims, {"status": checks.OK}, "Giant Defy 2024")[0] == 2024
    claims = checks.read_claims("Giant Defy", "")
    assert checks.year_photo(m, claims, {"status": checks.UNKNOWN, "last": None}, "Giant Defy") is None
