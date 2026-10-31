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
    ("Emonda SL 6 2023 groep\nframe ca. 2010", 2010, False),
    ("Nieuwe banden 2024, circa 2012", 2012, False),
    ("Tarmac 2023, ongeveer 2000 km gereden", 2023, False),
    ("Tarmac 2023, vraagprijs ca. 2100 euro", 2023, False),
    ("Tarmac 2023, frame ca. €2100", 2023, False),
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
    # 2020 is in our catalogue as the earlier Madone SL 6, so it's flagged as that generation
    assert r["age"]["status"] == checks.WARN and r["age"]["earlier"]
    assert "Madone SL 6," in en(r["age"]["detail"])
    r = run(models, "Trek Madone SL 6 gen 8 2015", "maat 56")
    # Older than any generation in our catalogue: we can't disprove the seller, so the check goes by 2015.
    assert r["age"]["status"] == checks.UNKNOWN and r["age"]["older"]
    assert "Probably older than we can check" == en(r["age"]["headline"]) and "We go by 2015" in en(r["age"]["detail"])


def test_bike_older_than_our_catalogue_has_no_spec_sheet(models):
    # 2011 is before any Ultimate CF SLX 8 AXS we know: don't compare it with the oldest sheet we have (2020).
    r = run(models, "Canyon Ultimate CF SLX 8 AXS 2011", "Campagnolo Record, carbon, velgremmen, maat 56", 1500)
    assert r["year"]["how"] == "older" and r["spec_year"] is None
    assert r["specs"]["status"] == checks.UNKNOWN
    assert en(r["specs"]["headline"]) == "No spec sheet for 2011" and en(r["specs"]["tab_headline"]) == "No spec sheet"
    assert "2020" not in en(r["specs"]["detail"])
    groupset = r["specs"]["rows"][0]
    assert groupset["step"] == 0 and groupset["ref_tier"] is None
    assert all(row["status"] == checks.UNKNOWN for row in r["specs"]["rows"])  # not even the frame its name implies
    # A 2011 Record is no longer top tier: two tiers down for its age.
    assert groupset["ad_tier"] == 3 and groupset["ad_aged"] == {"new": 5, "age": TODAY.year - 2011}


def test_old_bike_is_not_like_new_and_shifting_isnt_held_against_it(models):
    r = run(models, "Canyon Ultimate CF SLX 8 2011", "Campagnolo Record mechanisch, velgremmen\nConditie: Zo goed als nieuw", 1500)
    assert r["claims"]["condition"] == "like-new"
    assert en(r["value"]["condition"]) == "Normal use"
    assert any("isn't, so we count it as normal use" in en(n) for n in r["value"]["notes"])
    assert r["model"]["name"] == "Ultimate CF SLX 8 AXS" and r["year"]["how"] == "older"
    assert r["match"]["shifting"] is None  # an older generation may shift otherwise than today's AXS
    recent = run(models, "Canyon Ultimate CF SLX 8 AXS 2022", "Conditie: Zo goed als nieuw", 4000)
    assert en(recent["value"]["condition"]) == "like new"


def test_spec_comparison_ages_both_groupsets(models):
    model = dict(next(m for m in models if m["name"] == "Ultimate CF SLX 8 Di2"), spec_year=2015)
    claims = checks.read_claims("Canyon Ultimate", "Shimano Dura-Ace")
    row = checks.check_specs(model, claims, bike_year=2015, today=TODAY)["rows"][0]
    assert row["ad_aged"]["new"] == 5 and row["ad_tier"] == 3
    assert row["ref_aged"]["age"] == TODAY.year - 2015
    assert row["step"] == row["ad_aged"]["new"] - row["ref_aged"]["new"]  # up/downgrades compare the tiers new
    new = checks.check_specs(model, claims, bike_year=TODAY.year, today=TODAY)["rows"][0]
    assert new["ad_tier"] == 5 and new["ad_aged"] is None


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
    assert "Onze catalogus".encode() in client.get("/").data
    assert b"Our catalogue" in client.get("/", headers={"Accept-Language": "en-GB,en;q=0.9"}).data

    # ?lang= switches and sticks through a cookie, including the check results
    page = client.get("/check/1?lang=en").data
    assert b'<html lang="en">' in page and b"Earlier generation" in page
    page = client.get("/check/1").data
    assert b"Earlier generation" in page
    page = client.get("/check/1?lang=nl").data
    assert b'<html lang="nl">' in page and b"Eerdere generatie" in page and b"Groep" in page


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


def test_key_parts_name_the_main_parts_with_their_tiers():
    specs = [("Frame & fork", [("Frame", "Frame", "800 Series OCLV Carbon, tapered head tube")]),
             ("Drivetrain", [("Rear derailleur", "Achterderailleur", "SRAM Rival Rear Derailleur")]),
             ("Brakes", [("Brakes", "Remmen", "Shimano Ultegra hydraulic disc, flat mount")]),
             ("Weight", [("Weight", "Gewicht", "7.9 kg")])]
    parts = checks.key_parts(specs, {"Frame": 5, "Rear derailleur": 3})
    # No wheels on this sheet, so the weight takes the fourth place.
    assert parts == [("Frame", "800 Series OCLV Carbon", 5), ("Groupset", "SRAM Rival", 3),
                     ("Brakes", "Shimano Ultegra hydraulic disc", None), ("Weight", "7.9 kg", None)]
    assert checks.key_parts([]) == []


def test_model_page_header_lists_main_parts_and_second_hand_price(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/trek-domane-sl-6-gen-4?lang=nl").data.decode()
    assert 'class="key-parts" data-fact="parts"' in page and '<span class="kp-k">Groep</span>' in page
    assert "Tweedehands" in page and 'href="#asking"' in page


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
    # "Only bikes still sold" is on by default; current=0 (the form's hidden field when unticked) turns it off
    page = client.get("/models?lang=nl&current=0").data.decode()
    assert "Uit productie" in page and "Endurace 7 RAW" in page
    for url in ["/models?lang=en", "/models?lang=en&current=1", "/models?lang=en&current=1&current=0"]:
        page = client.get(url).data.decode()
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
    page = app.test_client().get("/models?lang=en&brand=Canyon&current=0").data.decode()
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
    assert 'value="road" selected>' in page
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
    assert by_name["Domane AL 2 Gen 4"] < by_name["Domane SL 5 Gen 4"] < by_name["Domane SLR 9 Gen 5"]
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


@pytest.mark.parametrize("year,drop", [(None, 0), (2026, 0), (2022, 0), (2021, 1), (2017, 1), (2016, 2), (2005, 2)])
def test_groupsets_drop_a_tier_for_every_five_years(year, drop):
    assert checks.groupset_age_drop(year, date(2026, 10, 31)) == drop


def test_an_old_bike_rates_its_groupset_lower_and_says_why():
    bike = {"name": "Test SL", "brand": "Trek", "specs": {"Achterderailleur": "Shimano Ultegra R8000",
                                                          "Shifter": "Shimano Ultegra R8000", "Zadel": "Bontrager"}}
    new = checks.spec_tiers(bike, 2026, date(2026, 10, 31))
    old = checks.spec_tiers(bike, 2015, date(2026, 10, 31))
    assert new["rows"]["Rear derailleur"] == 4 and not new["aged"]
    assert old["rows"]["Rear derailleur"] == 2
    assert old["aged"]["Rear derailleur"] == {"new": 4, "age": 11}
    # Sora is already Basic: nothing to drop, nothing to explain.
    sora = dict(bike, specs={"Achterderailleur": "Shimano Sora R3000"})
    assert checks.spec_tiers(sora, 2015, date(2026, 10, 31))["aged"] == {}


def test_year_moves_compare_groupsets_as_new():
    # 2021 drops a tier for age and 2022 doesn't: an Ultegra reworded is no upgrade, a 105 is still a downgrade.
    sheets = {"2021": {"specs": {"Achterderailleur": "Shimano Ultegra R8000", "Shifter": "Shimano Ultegra R8000"}}}
    bike = {"name": "Test SL", "brand": "Trek", "seen_on": "2022-05-01", "year_specs": {"years": sheets},
            "specs": {"Achterderailleur": "Shimano Ultegra R8000 11-speed", "Shifter": "Shimano 105 R7000"}}
    tab = next(t for t in checks.year_tabs(bike, date(2026, 10, 31)) if t["year"] == 2022)
    assert tab["moves"] == {"Shifters": "down"}


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


def test_check_63_aeolus_carbon_wheels_match_the_aeolus_pro(models):
    model = next(m for m in models if "Aeolus Pro 37" in (checks.spec(m, "Wiel voor", "Velg", "Wheelset") or ""))
    claims = checks.read_claims(model["name"], "Bontrager Aeolus Carbon wielen")
    wheels = next(row for row in checks.check_specs(model, claims)["rows"] if row["key"] == "wheels")
    assert wheels["status"] == checks.OK and not wheels["step"]


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


def test_size_check_estimates_cm_sizes_the_chart_skips(models):
    # Cube's chart goes 50, 53: a 52 is drawn between them, not left without rider heights.
    cube = dict(next(m for m in models if m["brand"] == "Cube"), slug="no-own-chart")
    between = checks.check_size(cube, {"size": "52"})
    assert between["fits"] == (165, 173) and between["status"] == checks.OK
    assert "neighbouring sizes" in en(between["notes"][-1])
    assert [r for r in between["rows"] if r["selected"]] == [{"size": "52", "low": 165, "high": 173,
                                                               "selected": True, "estimated": True}]
    # Canyon sizes by letter: the general chart gives the heights, and a fit can be judged.
    canyon = dict(next(m for m in models if m["brand"] == "Canyon"), slug="no-own-chart")
    general = checks.check_size(canyon, {"size": "52"}, 165)
    assert general["fits"] == checks.GENERIC_SIZE_CHART["52"] and general["fit"]["status"] == checks.OK
    assert "general road bike chart" in en(general["notes"][-1])
    # A size the general chart skips too (it has 56 and 58) is drawn between its rows.
    assert checks.check_size(canyon, {"size": "57"})["fits"] == (177, 183)
    giant = dict(next(m for m in models if m["brand"] == "Giant"), slug="no-own-chart")
    assert checks.check_size(giant, {"size": "57"})["fits"] == (177, 183)
    # Letter sizes aren't guessed.
    assert checks.check_size(dict(canyon, brand="Factor"), {"size": "M"})["status"] == checks.UNKNOWN


def test_tab_headlines_are_short(models):
    older = checks.age_summary({"status": checks.UNKNOWN, "headline": checks.Msg("Probably older than we can check"),
                                "detail": None, "older": True}, None)
    assert en(older["tab_headline"]) == "Older than we know"


def test_size_lines_group_builds_that_share_a_chart(models):
    lines = checks.size_lines(models, "Canyon")
    assert sum(len(l["models"]) for l in lines) == sum(1 for m in models if m["brand"] == "Canyon")
    assert any(len(l["models"]) > 1 for l in lines)
    for line in lines:
        assert len({str(sorted(checks.model_size_chart(m)["sizes"].items())) for m in line["models"]}) == 1 \
            or line["chart"]["source"] == "generic"


def test_size_picker_groups_families_under_their_discipline(models):
    picker = checks.size_picker(checks.size_lines(models, "Trek"))
    kinds = dict(picker)
    names = {f["name"]: f for fs in kinds.values() for f in fs}
    assert [k for k, _ in picker][0] == "road"
    assert "Domane" in [f["name"] for f in kinds["road"]] and "Domane+" in [f["name"] for f in kinds["ebike"]]
    assert "Speed Concept" in names and "FX Sport" in names
    domane = dict((line["label"], short) for line, short in names["Domane"]["lines"])
    assert domane["Domane AL 2 Gen 4"] == "AL 2 Gen 4"
    assert None in domane.values()  # the family's brand chart line, shown as 'Other Domane'
    # every line of the brand shows up once
    assert sum(len(f["lines"]) for f in names.values()) == len(checks.size_lines(models, "Trek"))


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
    assert 'data-type="Road"' in page and "data-short=" in page


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
    # On the report the merged slider is the main photo at the top, ahead of the ad's photo strip.
    report = client.get("/check/1?lang=en").get_data(as_text=True)
    assert 0 < report.index('class="head-duo"') < report.index('data-photo="0"')
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
    ad = "https://www.marktplaats.nl/v/fietsen/racefietsen-racefietsen/m2435934805-trek-domane"
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
    level = re.search(r"ZEKERHEID: (\w+)", page).group(1)  # whatever ours is, it must come back

    client.post("/check/1/match", data={"model_id": other})
    page = client.get("/check/1?lang=nl").data.decode()
    assert "Gekozen door jou" in page and "ZEKERHEID" not in page

    client.post("/check/1/match", data={"model_id": ours})
    page = client.get("/check/1?lang=nl").data.decode()
    assert f"ZEKERHEID: {level}" in page and "Gekozen door jou" not in page


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


def nl(msg):
    token = i18n.current_language.set("nl")
    try:
        return str(msg)
    finally:
        i18n.current_language.reset(token)


def test_a_price_above_the_fair_range_is_never_fair(models):
    m = {"brand": "Trek", "name": "Trek Emonda SL 6", "price_eur": 4000, "seen_on": "2026-01-01"}
    claims = checks.read_claims("Trek Emonda SL 6 2026", "")
    high = checks.check_value(m, claims, None, {"rows": []}, {"status": checks.OK}, TODAY)["high"]
    just_over = checks.check_value(m, claims, high + 10, {"rows": []}, {"status": checks.OK}, TODAY)
    assert just_over["status"] == checks.WARN
    assert en(just_over["headline"]) == "ca. €10 too high" and nl(just_over["headline"]) == "± €10 te hoog"
    at_top = checks.check_value(m, claims, high, {"rows": []}, {"status": checks.OK}, TODAY)
    assert at_top["status"] == checks.OK and en(at_top["headline"]) == "Fair price"


def test_value_axis_runs_from_zero_to_the_end_of_the_scale():
    from webapp.checks import axis_ticks
    ticks = axis_ticks(1049)
    assert [round(v) for v, _ in ticks] == [0, 250, 500, 750, 1049]
    assert ticks[0][1] == 0 and ticks[-1][1] == 100


def test_price_slider_runs_from_zero_to_the_new_price():
    from webapp.checks import price_slider
    s = price_slider(3720, 4550, 7700, 3499)
    assert s["ticks"][0][:2] == (0, 0) and s["ticks"][-1][:2] == (7700, 100.0)
    assert sum(not minor for _, _, minor in s["ticks"]) == 3  # the ends and the middle, on a phone
    assert 0 < s["asking"] < s["low"] < s["high"] < 100 and s["align"] == "middle" and not s["beyond"]
    over = price_slider(950, 1160, 2349, 2950)
    assert over["asking"] == 100.0 and over["beyond"] and over["align"] == "end"
    assert not over["label"]  # a narrow band leaves out its label
    assert "asking" not in price_slider(950, 1160, 2349)
    inside = price_slider(3720, 4550, 7700, 4000)
    assert not inside["label"]  # the knob would sit on it


def test_value_says_how_far_the_asking_price_is_from_the_range(models):
    m = {"brand": "Trek", "name": "Trek Emonda SL 6", "price_eur": 4000, "seen_on": "2026-01-01"}
    claims = checks.read_claims("Trek Emonda SL 6 2026", "")
    v = checks.check_value(m, claims, None, {"rows": []}, {"status": checks.OK}, TODAY)
    low, high = v["low"], v["high"]
    over = checks.check_value(m, claims, high + 100, {"rows": []}, {"status": checks.OK}, TODAY)
    assert en(over["verdict"]).startswith("The asking price is €100 above the fair range")
    under = checks.check_value(m, claims, low - 50, {"rows": []}, {"status": checks.OK}, TODAY)
    assert nl(under["verdict"]).startswith("De vraagprijs ligt €50 onder de eerlijke prijs")
    inside = checks.check_value(m, claims, low + 10, {"rows": []}, {"status": checks.OK}, TODAY)
    assert en(inside["verdict"]) == "The asking price is within the fair range."
    assert [round(s["value"]) for s in v["steps"]][0] == 4000 and len(v["steps"]) == 2  # new price, age


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
    assert r["model"]["name"].startswith("S-Works Tarmac SL7")  # a discontinued line we keep
    # With no SL5 at all we still compare with a Tarmac, but say it isn't the version the seller named.
    r = run(models, "Specialized S-Works Tarmac SL5 2017", "", 2500)
    assert "SL5" in r["name_check"]["extra"]
    assert r["confidence"] is not None and str(r["confidence"]) in ("low", "laag")
    # The generation counts too, and an exact name has nothing to say.
    assert run(models, "Trek Domane SL6 gen 3", "", 1500)["name_check"]["conflicts"] == [("Gen 4", "Gen 3")]
    assert run(models, "Trek Domane SL 6 Gen 4 2023 maat 56", "", 2500)["name_check"] is None


def test_report_says_when_we_dispute_the_model(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    resp = client.post("/check", data={"title": "Trek Domane SL6 gen 3", "asking_price": "1500"})
    page = client.get(resp.headers["Location"] + "?lang=nl").data.decode()
    assert 'class="mb-chip bad"' in page and "De advertentie zegt Gen 3, dit is een Gen 4" in page


def test_value_uses_the_middle_estimated_year(models):
    # No year in the ad: the middle of the years its details allow within the generation's years (2023–2026).
    r = run(models, "Trek Domane SL 6 gen 4", "Shimano 105 Di2 2x12, schijfremmen", price=2000)
    assert r["value"]["model_year"] == 2024 and r["year"]["how"] == "estimate"
    assert any("details point to 2023–2026, so we go by 2024" in en(n) for n in r["value"]["notes"])
    # A stated year still wins.
    assert run(models, "Trek Domane SL 6 gen 4 2025", "Shimano 105 Di2 2x12", price=2000)["value"]["model_year"] == 2025
    # No clue in the ad: the middle of the years the generation was sold (launched as the 2021 model), not the
    # catalogue year.
    r = run(models, "Trek Emonda SL 6", price=1500)
    assert r["value"]["model_year"] == 2023 and r["year"]["how"] == "generation"


def test_condition_reads_negated_damage_and_the_ads_condition_field():
    assert checks.detect_condition("Hij heeft geen schade en is netjes behandeld") is None
    assert checks.detect_condition("Nooit gevallen, zonder scheurtjes. Zo goed als nieuw") == "like-new"
    assert checks.detect_condition("Kleine schade aan de lak") == "damaged"
    assert checks.detect_condition("Specificaties\nConditie: Gebruikt") == "used"
    assert checks.detect_condition("Conditie: Zo goed als nieuw") == "like-new"
    # The seller's picked condition wins over damage words in the text (check 55).
    assert checks.detect_condition("Nooit gevallen, kleine lakschade op de vork\n\nConditie: Zo goed als nieuw") == "like-new"
    assert checks.detect_condition("Krasje bij de crank\nConditie: Gebruikt") == "used"
    assert checks.detect_condition("Conditie: Defect") == "damaged"
    assert checks.detect_condition("Geen valschade, netjes onderhouden") is None
    assert checks.detect_condition("Nooit crashschade gehad") is None


def test_wheels_named_without_the_word_wheels():
    claims = checks.read_claims("Trek Madone SL 6", "Upgrades:\n- Bontrager Aeolus Pro 37\n- Aeolus RSL zadel")
    assert claims["wheels"] == {"label": "Bontrager Aeolus Pro 37", "tier": 4}
    assert checks.detect_part("Bontrager Aeolus Comp zadel, carbon frame", "wheels") is None
    # Check 55: the named wheelset further down wins over "carbon wielen" in the intro.
    text = "Mooi carbon frame met carbon wielen, tubeless.\nWielen: Bontrager Aeolus Pro 37 (Carbon 37mm)"
    assert checks.detect_part(text, "wheels") == {"label": "Bontrager Aeolus Pro 37 (Carbon 37mm)", "tier": 4}
    assert checks.detect_condition("het printplaatje van de vorige was kapot\n\nConditie: Zo goed als nieuw") == "like-new"



def test_wheels_of_the_same_family_without_a_version_match():
    # Check 63: the ad says "Bontrager Aeolus Carbon wielen", the original is the Aeolus Pro 37.
    original = "Bontrager Aeolus Pro 37, OCLV Carbon, Tubeless Ready, 37 mm velghoogte"
    assert checks.same_wheel_family("Bontrager Aeolus Carbon wielen", original)
    assert not checks.same_wheel_family("Bontrager Aeolus Elite 35 wielen", original)  # a version of its own
    assert not checks.same_wheel_family("Zipp carbon wielen", original)  # another family
    assert not checks.same_wheel_family("carbon wielen", original)


def test_wheels_rated_by_their_hubs_and_the_crankset_read():
    # Check 62: "met naaf 240" is split off the wheels clause, so the whole line rates them.
    claims = checks.read_claims("Racefiets", "DT swiss wielen met naaf 240\nNieuw crank stel ultegra 52/36\nLengte 172.5")
    assert claims["wheels"] == {"label": "DT swiss wielen met naaf 240", "tier": 4}
    assert claims["crankset"] == {"label": "Nieuw crank stel ultegra 52/36", "tier": 4}


def test_year_is_always_estimated(models):
    # No clue in the ad: the matched model's years, which can't rule out a stated year (it may be an older
    # generation we don't have).
    e = run(models, "Trek Domane SL 6 2019")["year_estimate"]
    assert e["first"] == 2023 and en(e["headline"]) == "Can't check 2019"
    assert run(models, "Trek Domane SL 6 2024")["year_estimate"]["status"] == checks.OK
    # The Émonda's launch year is entered by hand (reference.LINEAGES), so 2021 can be checked.
    e = run(models, "Trek Emonda SL 6 2021")["year_estimate"]
    assert e["status"] == checks.OK and en(e["headline"]) == "Fits 2021 or later"
    assert en(run(models, "Trek Emonda SL 6")["year_estimate"]["headline"]) == "Probably 2021 or later"


def test_value_replaces_a_stated_year_the_details_rule_out(models):
    r = run(models, "Trek Domane SL 6 gen 4 2019", "Shimano 105 Di2 2x12", price=2000)
    assert r["value"]["model_year"] == 2024
    assert any("stated 2019 doesn't fit the ad's details (2023–2026), so we go by 2024" in en(n)
               for n in r["value"]["notes"])
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
    assert tabs[2025]["moves"] == {}  # neither brake is in the tier tables
    # A brand whose archive wasn't searched says so instead of "no copy".
    assert checks.year_tabs(dict(model, year_specs={}), today=date(2026, 1, 1))[0]["state"] == "unchecked"


def test_year_tabs_put_our_scrape_under_its_model_year():
    """Giant lists its 2027 bikes from the autumn of 2026: the scrape is the 2027 tab, the 2026 sheet stays."""
    from datetime import date
    model = {"name": "Defy Advanced 0", "brand": "Giant", "seen_on": "2026-10-22", "model_year": 2027,
             "price_eur": 3799.0, "url": "u", "specs": {"Frame": "Advanced-Grade Composite"},
             "year_specs": {"years": {"2026": {"captured": "2026-03-01", "url": "a", "price": 3999.0,
                                               "specs": {"Frame": "Advanced-Grade Composite"}}}}}
    tabs = {t["year"]: t for t in checks.year_tabs(model, today=date(2026, 10, 31))}
    assert max(tabs) == 2027 and tabs[2027]["state"] == "scrape" and tabs[2027]["price"] == 3799.0
    assert tabs[2026]["state"] == "archive" and tabs[2026]["price"] == 3999.0
    assert checks.scrape_year(model) == 2027
    assert checks.scrape_year(dict(model, model_year=None)) == 2026  # no model year in the snapshot: the scrape date's
    assert checks.scrape_year(dict(model, seen_on=None)) is None  # an archived line has no scrape of its own


def test_seed_keeps_the_model_year(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    seed.load(conn)
    row = conn.execute("SELECT model_year, seen_on FROM models WHERE slug = 'giant-defy-advanced-0'").fetchone()
    assert row["model_year"] == 2027 and row["seen_on"].startswith("2026")


def test_seed_brings_loaded_models_up_to_a_newer_scrape(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    seed.load(conn)
    old_id = conn.execute("SELECT id FROM models WHERE slug = 'giant-contend-ar-1'").fetchone()["id"]
    # as on a database loaded from the 22 October Giant scrape, when Contend AR 1 was its 2025 page
    conn.execute("UPDATE models SET url = 'old', model_year = 2025, source_file = 'data/Giant/giant_bikes_20261022_151753.json'"
                 " WHERE slug = 'giant-contend-ar-1'")
    assert seed.refresh_catalogue(conn) >= 1
    row = conn.execute("SELECT id, url, model_year FROM models WHERE slug = 'giant-contend-ar-1'").fetchone()
    assert row["id"] == old_id  # saved checks keep their match
    assert row["url"] == "https://www.giant-bicycles.com/nl/contend-ar-1" and row["model_year"] == 2026
    assert seed.refresh_catalogue(conn) == 0  # nothing newer the second time


def test_seed_refresh_takes_the_last_bike_of_a_shared_page(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    seed.load(conn)
    full = dict(conn.execute("SELECT url, specs, model_year FROM models WHERE slug = 'giant-tcr-advanced-pro-0-di2'").fetchone())
    conn.execute("UPDATE models SET url = 'old', specs = '{}', source_file = 'data/Giant/giant_bikes_20261022_151753.json'"
                 " WHERE slug = 'giant-tcr-advanced-pro-0-di2'")
    seed.refresh_catalogue(conn)
    seed.refresh_images(conn)
    row = dict(conn.execute("SELECT url, specs, model_year FROM models WHERE slug = 'giant-tcr-advanced-pro-0-di2'").fetchone())
    assert row == full  # the same bike as a full load: the 2027 TCR Advanced Pro 0-Di2, not the 2026 Pro 0 Di2


def test_model_page_has_year_tabs(tmp_path):
    from webapp.app import create_app
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    page = create_app(path).test_client().get("/models/trek-domane-al-2-gen-4?lang=en").get_data(as_text=True)
    assert 'id="tab-2020"' in page and 'id="tab-2025" aria-controls="year-2025"' in page
    # data/years/Trek.json has the 2024 Wayback Machine copy, with its photo
    assert 'class="year-tab archive" id="tab-2024"' in page and "Trek/years/domaneal2gen4_2024.jpg" in page


def test_model_page_year_selector_runs_current_to_oldest(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/giant-defy-advanced-2?lang=nl").data.decode()
    years = re.findall(r'class="gallery-thumb[^"]*" aria-pressed="(\w+)" data-year="(\d+)"', page)
    assert len(years) > 2 and [int(y) for _p, y in years] == sorted((int(y) for _p, y in years), reverse=True)
    assert [p for p, _y in years] == ["true"] + ["false"] * (len(years) - 1)  # the current bike, on top, is shown first
    assert 'class="year-rail' in page  # the years pick the bike; the arrows on the photo go through its photos
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


def test_age_timeline_shows_every_catalogue_year(models):
    # No archived sheets: our own scrape and the brand's photo years still give a timeline, with an open start.
    m = dict(models[0], name="Endurace CF 6", brand="Canyon", missed_scrapes=0, last_seen="2026-10-01",
             seen_on="2025-08-03", specs={"Frame": "x"}, photo_years=[2024, 2026], year_specs={})
    age = checks.check_age(m, checks.read_claims("Canyon Endurace CF 6 2023", ""), TODAY)
    assert [t["year"] for t in age["timeline"] if t["sold"]] == [2024, 2025, 2026]
    assert age["status"] == checks.UNKNOWN and "2024" in en(age["detail"])
    assert checks.check_age(m, checks.read_claims("Canyon Endurace CF 6 2025", ""), TODAY)["status"] == checks.OK
    # A predecessor's sheets of an earlier generation show as such, before the generation table's first year.
    m = dict(models[0], name="Domane SL 7 Gen 4", brand="Trek", missed_scrapes=0, last_seen="2026-10-01",
             seen_on="2025-07-18", specs={"Frame": "x"}, photo_years=[], year_specs={"checked": list(range(2018, 2026)), "years": {
                 "2020": {"specs": {"Frame": "x"}, "sheet_name": "Domane SL 7"},
                 "2022": {"specs": {"Frame": "x"}, "sheet_name": "Domane SL 7 gen 3"},
                 "2023": {"specs": {"Frame": "x"}}}})
    age = checks.check_age(m, checks.read_claims("Trek Domane SL 7 2022", ""), TODAY)
    assert [(t["year"], t["sold"], t["earlier"]) for t in age["timeline"]] == [
        (2020, False, True), (2021, False, True), (2022, False, True), (2023, True, False), (2024, True, False),
        (2025, True, False), (2026, True, False)]
    assert age["status"] == checks.WARN and age["earlier"] and "Domane SL 7 gen 3" in en(age["detail"])
    assert "2020, 2022" in en(age["notes"][-1])
    # The age tab groups those years into blocks: gen 3 (2020–2022) under its newest sheet's name, then this model.
    assert [(g["kind"], g["name"], g["first"], g["last"]) for g in age["generations"]] == [
        ("earlier", "Domane SL 7 gen 3", 2020, 2022), ("own", "Domane SL 7 Gen 4", 2023, 2026)]


def test_spec_comparison_uses_a_year_the_estimate_allows(models):
    sheets = {"2021": {"specs": {"Shifter": "Shimano 105 R7000"}}, "2023": {"specs": {"Shifter": "Shimano 105 R7100"}},
              "2025": {"specs": {"Shifter": "Shimano 105 R7100"}}}
    m = dict(models[0], seen_on="2026-01-01", year_specs={"years": sheets})
    claims = checks.read_claims("Fiets 2022", "")
    assert checks.comparison_year(m, claims, {"status": checks.OK, "first": 2021, "last": 2022}) == 2021
    assert checks.comparison_year(m, claims, {"status": checks.BAD, "first": 2023, "last": None}) == 2023
    assert checks.comparison_year(m, checks.read_claims("Fiets 2023", ""), {"first": 2021, "last": 2025}) == 2023
    no_year = checks.read_claims("Fiets", "")
    assert checks.comparison_year(m, no_year, {"first": 2021, "last": 2023}) == 2021  # the earlier of the two middle sheets
    assert checks.comparison_year(m, no_year, {"first": 2021, "last": None}) is None  # our own scrape fits
    older = checks.year_model(m, 2021)
    assert older["specs"] == sheets["2021"]["specs"] and older["spec_year"] == 2021
    assert "2021" in en(checks.check_specs(older, claims)["detail"])


def test_colour_clue_reads_dutch_colour_words(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[{"name": "Cryo Silver/Chrome"}], specs={"Frame": "x"},
             year_specs={"years": {"2024": {"specs": {"Frame": "x"}, "colours": ["Charcoal/Milky Way"]},
                                   "2025": {"specs": {"Frame": "x"}, "colours": ["Frost Silver/Cordovan"]},
                                   "2026": {"specs": {"Frame": "x"}, "colours": ["Cyber Lime"]}}})
    clues = checks.sheet_clues(m, "Kleur frost zilver, modeljaar 2025")
    assert [(a, b) for a, b, _m in clues] == [(2025, 2025)]
    # Our own scrape in October shows next year's colours: it doesn't replace the 2026 sheet
    assert checks.year_sheets(m)[2026]["colours"] == ["Cyber Lime"]


def test_plain_colours_in_the_ad_rule_out_years_without_them(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[], specs={"Frame": "x"},
             year_specs={"years": {"2020": {"specs": {"Frame": "x"}, "colours": ["Gunmetal Black / Metallic Orange"]},
                                   "2021": {"specs": {"Frame": "x"}, "colours": ["Carbon/Charcoal"]},
                                   "2022": {"specs": {"Frame": "x"}, "colours": ["Deep Lake / Black"]},
                                   "2024": {"specs": {"Frame": "x"}, "colours": ["Tiger Red/Dried Chili"]},
                                   "2025": {"specs": {"Frame": "x"}, "colours": ["Carbon"]}}})
    clues = checks.sheet_clues(m, "Giant Defy Advanced 2 rood\nMooie fiets")
    assert [(a, b) for a, b, _m in clues] == [(2023, 2024)]  # 2023 has no sheet, so maybe
    assert "Tiger Red" in en(clues[0][2])
    # Black and orange: only 2020, the oldest sheet, so the start stays open
    clues = checks.sheet_clues(m, "Giant Defy\nKleur: zwart/oranje")
    assert [(a, b) for a, b, _m in clues] == [(None, 2020)]
    assert checks.sheet_clues(m, "Giant Defy zwart\n") == []  # black every year but 2024: no window left
    assert checks.sheet_clues(m, "Giant Defy paars\n") == []  # no year in that colour: says nothing
    assert checks.sheet_clues(m, "Giant Defy\nGeen kleur genoemd") == []


def test_colour_seen_in_the_photos_dates_the_frame_before_swappable_parts(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[], specs={"Cassette": "11-28"},
             year_specs={"years": {"2019": {"specs": {"Cassette": "11-28"}, "colours": ["Matte Trek Black", "Royal"]},
                                   "2021": {"specs": {"Cassette": "11-28"}, "colours": ["Trek Black/Radioactive Red", "Gloss Blue/Matte Trek Black"]},
                                   "2024": {"specs": {"Cassette": "11-34"}, "colours": ["Crimson"]}}})
    # A whole colourway, not the matte black half of a two-tone
    assert checks.seen_colour_years(checks.year_sheets(m), "Matte Trek Black") == ("Matte Trek Black", {2019})
    claims = checks.read_claims("Trek Emonda SL6 2021", "11-34 cassette")
    est = checks.estimate_year(m, [m], claims, "Trek Emonda SL6 2021\n11-34 cassette", "Trek Black/Radioactive Red")
    assert est["status"] == checks.OK and "swapped" in en(est["evidence"][-1])
    # Bought later than the frame's years: fine for a second-hand bike
    claims = checks.read_claims("Trek Emonda", "Tweedehands gekocht in 2025")
    est = checks.estimate_year(m, [m], claims, "Trek Emonda\nTweedehands gekocht in 2025", "Matte Trek Black")
    assert est["status"] == checks.OK and est["last"] == 2020


def test_slider_shows_the_photo_of_the_colour_in_the_ad(models):
    m = dict(models[0], seen_on="2026-10-22", colorways=[], specs={"Frame": "x"},
             year_specs={"years": {"2021": {"specs": {"Frame": "x"}, "image": "y/2021.jpg",
                                            "colours": ["Quicksilver/Brushed Chrome", "Carbon Blue Smoke/Metallic Blue"],
                                            "colour_images": {"Quicksilver/Brushed Chrome": "y/2021_q.jpg",
                                                              "Carbon Blue Smoke/Metallic Blue": "y/2021_b.jpg"}},
                                   "2024": {"specs": {"Frame": "x"}, "image": "y/2024.jpg", "colours": ["White Prismatic"]}}})
    claims = checks.read_claims("Trek Emonda SL5", "")
    assert checks.year_photo(m, claims, {"status": checks.UNKNOWN}, "Trek Emonda SL5\n", "Carbon Blue Smoke/Metallic Blue") == (
        2021, "y/2021_b.jpg", "Carbon Blue Smoke/Metallic Blue")


def test_photo_colours_file_only_applies_to_its_model(models, monkeypatch):
    m = dict(models[0], slug="trek-emonda-sl-6")
    monkeypatch.setitem(checks.photo_colour.__defaults__[0], "data", {
        "marktplaats:m2435934805": {"model": "trek-emonda-sl-6", "colour": "Crimson"}})
    ad = {"listing_url": "https://www.marktplaats.nl/v/fietsen-racefietsen/m2435934805-trek", "title": "Trek", "asking_price": 1}
    assert checks.photo_colour(m, ad) == "Crimson"
    assert checks.photo_colour(dict(m, slug="trek-emonda-sl-5"), ad) is None


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


def test_age_tab_says_what_its_section_says():
    age = {"status": checks.UNKNOWN, "headline": checks.Msg("Seller says {year}", year=2025), "detail": checks.Msg("x")}
    estimate = {"status": checks.OK, "headline": checks.Msg("Fits {years}", years="2025"), "detail": checks.Msg("y")}
    tab = checks.age_summary(age, estimate)
    assert tab["status"] == checks.OK and en(tab["headline"]) == "Year estimate: Fits 2025"
    ok = dict(age, status=checks.OK, headline=checks.Msg("Adds up"))
    assert en(checks.age_summary(ok, estimate)["headline"]) == "Adds up · Fits 2025"
    # The tab's pill says it adds up, so the headline gives the year, also when the estimate agrees.
    assert en(checks.age_summary(dict(ok, year=2025), estimate)["headline"]) == "Model year 2025"
    assert en(checks.age_summary(dict(ok, year=2025), None)["headline"]) == "Model year 2025"
    bad = dict(estimate, status=checks.BAD, headline=checks.Msg("Doesn't fit {years}", years="2023"))
    assert checks.age_summary(ok, bad)["status"] == checks.BAD


def test_report_tabs_put_the_price_first_like_the_home_page(models, tmp_path):
    app = create_app(str(tmp_path / "tabs.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane SL 6 Gen 4 2024 maat 56", 2450))
    conn.commit()
    page = app.test_client().get("/check/1?lang=en").get_data(as_text=True)
    tabs = re.findall(r'id="tab-(\w+)"', page)
    assert tabs == ["value", "age", "specs", "size"]  # the home page lists the checks in this order too
    assert re.search(r'id="tab-value"[^>]*aria-selected="true"', page)
    assert 'class="verdict-pill ok"' in page  # the verdict as a pill, the headline says what was found
    size_tab = re.search(r'id="tab-size"[^>]*class="report-tab (\w+)-bg', page, re.S)
    assert size_tab.group(1) == "unknown"  # no height given yet


def test_match_rate_shows_how_well_the_ads_words_fit(models):
    ad = "Giant Defy Advanced 1 Shimano 105 Di2 van €3599 voor € 2450"
    giant = [m for m in models if m["brand"] == "Giant"]
    by_name = {m["name"]: m for m in giant}
    if "Defy Advanced 1" not in by_name:
        pytest.skip("no Defy Advanced 1 in the seed catalogue")
    ours = checks.match_rate(by_name["Defy Advanced 1"], models, ad)
    assert ours["brand"]["pct"] == 100 and ours["family"] == {"name": "Defy Advanced", "pct": 100}
    assert ours["version"] == {"name": "1", "pct": 100}
    # Di2 says how it shifts, not which model: it agrees with this model's electronic 105, so nothing's off.
    assert ours["extra"] == [] and ours["shifting"] == {"ad": "electronic", "model": "electronic", "same": True}
    assert ours["pct"] == 100
    pro = checks.match_rate(by_name["Defy Advanced 1"], models, "Giant Defy Advanced Pro 1 Di2")
    assert pro["extra"] == ["Pro"] and pro["pct"] == 85  # a model word the model hasn't: 15 off
    if "Defy Advanced 2" in by_name:
        other = checks.match_rate(by_name["Defy Advanced 2"], models, ad)
        assert other["version"]["pct"] == 0 and other["pct"] < ours["pct"]  # the ad says 1, not 2


def test_shifting_the_ad_says_otherwise_lowers_the_match(models):
    mechanical = {"name": "X 1", "brand": "Giant", "specs": {"Shifter": "Shimano 105 R7000"}}
    assert checks.shifting(mechanical, "Giant X 1 Di2") == {"ad": "electronic", "model": "mechanical", "same": False}
    assert checks.shifting(mechanical, "Giant X 1", "mechanisch geschakeld")["same"] is True
    assert checks.shifting(mechanical, "Giant X 1") is None  # the ad doesn't say


def test_name_parts_split_family_from_version():
    assert checks.name_parts({"name": "Defy Advanced Pro 1"}) == ("Defy Advanced Pro", "1")
    assert checks.name_parts({"name": "Domane SL 6 Gen 4"}) == ("Domane SL", "6 Gen 4")
    assert checks.name_parts({"name": "Tarmac SL7 - Ultegra"}) == ("Tarmac", "SL7")


def test_the_model_panel_lists_candidates_best_first(models, tmp_path):
    app = create_app(str(tmp_path / "panel.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane SL 6 Gen 4 2024 maat 56", 2450))
    conn.commit()
    page = app.test_client().get("/check/1?lang=en").get_data(as_text=True)
    assert 'href="#pick-model"' in page and 'id="pick-model"' in page
    pcts = [int(p) for p in re.findall(r'class="mp-pct \w+">(\d+)%', page)]
    assert pcts and pcts == sorted(pcts, reverse=True)
    assert page.count('class="mp-cand ours"') == 1 and "OUR PICK" in page
    assert '<select id="model_id" name="model_id">' in page  # any model by hand, at the bottom


def test_frame_number_is_always_asked_with_the_stolen_check(models, tmp_path):
    app = create_app(str(tmp_path / "frame.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane SL 6 Gen 4 2024 maat 56", 2450))
    conn.commit()
    page = app.test_client().get("/check/1?lang=en").get_data(as_text=True)
    questions = page[page.index('id="questions"'):]
    assert "serial number under the bottom bracket" in questions.split("</ol>")[0]
    assert '<a href="https://www.stopheling.nl"' in questions
    assert "Serial number:" not in page  # no longer tucked away in the age section


def test_carbon_parts_are_no_frame_claim():
    assert checks.detect_material("Aluminium frame met carbon vork") == "Aluminium"
    assert checks.detect_material("Alu racefiets, carbon-zadelpen en carbon wielen") == "Aluminium"
    assert checks.detect_material("Vork: carbon. Frame aluminium") == "Aluminium"
    assert checks.detect_material("Carbon frame, carbon wielen") == "Carbon"
    assert checks.detect_material("carbon vork") is None
    assert checks.detect_material("Alu frame, carbon bars") == "Aluminium"
    assert checks.detect_material("Carbon rim brake racer") == "Carbon"
    assert checks.detect_material("Carbon rim-brakes") == "Carbon"
    assert checks.detect_material("carbon rims") is None


def test_a_year_sheet_without_a_material_is_no_evidence():
    model = {"name": "Domane AL 2", "brand": "Trek", "specs": {}, "seen_on": None,
             "year_specs": {"years": {"2020": {"specs": {"Zadel": "x"}}, "2021": {"specs": {"Frame": "Alpha Aluminium"}}}}}
    assert checks.model_materials(model) == {"Aluminium": [2021]}


def test_a_material_the_model_never_came_in_is_flagged(models):
    r = run(models, "Trek Domane AL 2 Gen 4 2021", "Carbon racefiets, maat 56", price=800)
    alert = r["material_alert"]
    assert alert and alert["claimed"] == "Carbon" and alert["made_in"] == ["Aluminium"]
    assert en(alert["headline"]) == "Impossible claim: the Domane AL 2 Gen 4 was never made in carbon"
    assert "every Trek spec sheet we have of it" in en(alert["detail"])
    token = i18n.current_language.set("nl")
    try:
        assert str(alert["headline"]) == "Onmogelijke claim: de Domane AL 2 Gen 4 is nooit in carbon gemaakt"
    finally:
        i18n.current_language.reset(token)
    frame = next(row for row in r["specs"]["rows"] if row["key"] == "frame")
    assert frame["status"] == checks.BAD and en(frame["result"]) == "Never made in carbon"
    assert any("was only ever made in aluminium" in en(q) for q in r["questions"])


def test_a_material_the_model_came_in_or_a_carbon_fork_is_no_alert(models):
    assert run(models, "Trek Domane AL 2 Gen 4 2021", "Aluminium frame, carbon vork")["material_alert"] is None
    assert run(models, "Trek Domane SL 6 Gen 4 2024", "carbon frame")["material_alert"] is None
    assert run(models, "Trek Domane SL 6 Gen 4 2024")["material_alert"] is None
    # A model that came in both in different years: either claim can be right.
    fx = next(m for m in models if m["name"] == "FX Sport 4")
    assert set(checks.model_materials(fx)) == {"Aluminium", "Carbon"}
    assert checks.impossible_material(fx, {"material": "Aluminium"}, "aluminium") is None


def test_the_report_shows_an_impossible_material_above_the_tabs(models, tmp_path):
    app = create_app(str(tmp_path / "material.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, description, asking_price) VALUES (?, ?, ?)",
                 ("Trek Domane AL 2 Gen 4 2021", "Carbon racefiets", 800))
    conn.commit()
    for lang, words in (("en", "Impossible claim"), ("nl", "Onmogelijke claim")):
        page = app.test_client().get(f"/check/1?lang={lang}").get_data(as_text=True)
        assert 'class="claim-alert" role="alert"' in page and words in page
        assert page.index("claim-alert") < page.index('class="report-tabs"')


def test_year_tabs_keep_one_row_order_and_mark_upgrades():
    from datetime import date
    model = {"name": "Defy Advanced 1", "brand": "Giant", "seen_on": "2026-07-18", "url": "u",
             "specs": {"Shifter": "Shimano 105 Di2", "Cassette": "Shimano 105, 12-speed"},
             "year_specs": {"years": {
                 "2024": {"captured": "2024-03-28", "url": "a",
                          "specs": {"Cassette": "Shimano Ultegra, 11-speed", "Shifter": "Shimano Tiagra"}},
                 "2025": {"captured": "2025-03-28", "url": "b",
                          "specs": {"Cassette": "Shimano Ultegra, 11-speed", "Shifter": "Shimano Ultegra"}}}}}
    tabs = {t["year"]: t for t in checks.year_tabs(model, today=date(2026, 10, 23))}
    orders = {y: [en for _g, rows in tabs[y]["specs"] for en, _nl, _v in rows] for y in (2024, 2025, 2026)}
    assert orders[2024] == orders[2025] == orders[2026]  # our own scrape's order, in every year
    assert tabs[2025]["moves"] == {"Shifters": "up"}
    assert tabs[2026]["moves"]["Shifters"] == "down"


def test_model_page_years_match_the_age_check(tmp_path):
    """The model page's model years come from the same catalogue years as the age check, earlier
    generations included and marked in the facts, the year tabs and the photo thumbs."""
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    model = next(m for m in db.all_models(db.connect(app.config["DB_PATH"])) if m["slug"] == "trek-domane-al-4-gen-4")
    earlier = sorted(y for y, (_n, old) in checks.catalogue_years(model).items() if old)
    assert earlier, "the 2021-2023 sheets are the gen 3 bike"
    page = app.test_client().get("/models/trek-domane-al-4-gen-4?lang=nl").get_data(as_text=True)
    first = checks.sold_years(model)[0]
    assert f'<div class="v">{first}–nu</div>' in page
    assert f"eerdere gen. {checks._years_list(earlier)}" in page
    assert f'class="year-tab archive earlier" id="tab-{earlier[0]}"' in page


def test_a_model_without_its_own_photo_opens_on_its_newest_year_photo(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    model = next(m for m in db.all_models(db.connect(app.config["DB_PATH"])) if m["slug"] == "trek-domane-al-2-rim")
    assert not model["image"]
    newest = [t for t in checks.year_tabs(model) if t.get("image") and t["state"] != "scrape"][-1]
    page = app.test_client().get("/models/trek-domane-al-2-rim?lang=nl").get_data(as_text=True)
    assert f'data-start="{newest["year"]}"' in page and newest["image"] in page
    gallery = page.split('id="model-gallery"')[1].split("</section>")[0]
    assert 'class="gallery-thumb"' in gallery and "[nog geen foto]" not in gallery


def test_a_model_without_year_photos_still_shows_its_photo(tmp_path):
    """The photo's size comes from .model-gallery .photo; without a carousel it needs the wrapper too."""
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/cannondale-caad14-2?lang=nl").get_data(as_text=True)
    assert '<div class="model-gallery"><div class="photo" id="model-photo"><img' in page


def test_age_timeline_rings_the_estimated_years(tmp_path):
    app = create_app(str(tmp_path / "t.sqlite3"))
    with app.app_context():
        seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL 6 gen 4", "asking_price": "2500",
                                "description": "Shimano 105 Di2 2x12, schijfremmen"})
    page = client.get("/check/1?lang=en").get_data(as_text=True)
    ringed = re.findall(r'<div class="gen-year(?: has-photo)? likely[^"]*"[^>]*>\s*<div class="gen-photo(?: gen-blank)?">(?:<img[^>]*>)?</div>\s*<span class="gen-dot"></span>\s*<span class="gen-y">(\d{4})</span>', page)
    assert ringed and min(int(y) for y in ringed) == 2023  # "Probably 2023 or later"
    assert "estimated" in page


def test_a_stated_year_we_cant_check_is_a_fallback_estimate(models):
    """No year clues and a stated year outside the catalogue's years: the estimate is only the catalogue's
    years (fallback), so the age timeline doesn't ring them."""
    model = dict(next(m for m in models if m["name"] == "Émonda ALR 5"), photo_years=[2023, 2024])
    claims = checks.read_claims("Trek Émonda ALR 5 2015", "mooie fiets")
    e = checks.estimate_year(model, models, claims, "Trek Émonda ALR 5 2015\nmooie fiets")
    assert e["status"] == checks.UNKNOWN and e["fallback"] is True


def test_a_tier_one_letter_off_is_another_model():
    assert checks.conflicts({"name": "Émonda SL 7"}, "Trek Émonda · SLR 7 Navy Carbon Smoke/Viper Red") == [("SL", "SLR")]
    assert checks.conflicts({"name": "Ultimate CFR"}, "Canyon Ultimate CF SLX") == [("CFR", "CF")]
    assert checks.conflicts({"name": "Émonda SL 7"}, "Trek Emonda SL7 2021") == []


def test_the_brands_colour_name_counts_for_its_model():
    model = {"colors": ["Navy Carbon Smoke/Viper Red", "Black"], "year_specs": {}}
    assert checks._colour_named(model, "Trek Émonda SLR 7 Heren Navy Carbon Smoke/Viper Red 56cm")
    assert not checks._colour_named(model, "Trek Émonda zwart black")  # one plain colour says little


def test_confidence_follows_the_fit_it_is_shown_with():
    assert checks.match_confidence(100, [60]) == "high"
    assert checks.match_confidence(95, [90]) == "medium"  # another model fits about as well
    assert checks.match_confidence(75, [35]) == "medium"
    assert checks.match_confidence(50, [20]) == "low"
    assert checks.match_confidence(100, [40], not_exact=True) == "low"


def test_a_version_we_dont_have_gets_the_closest_bike_with_low_confidence():
    base = {"brand": "Giant", "price_eur": 2000, "specs": {}, "colors": [], "year_specs": {}, "colorways": []}
    models = [dict(base, id=1, name="Defy Advanced 1"), dict(base, id=2, name="Defy Advanced Pro 1"),
              dict(base, id=3, name="Propel Advanced SL 1")]
    ranked = checks.match_models(models, "Giant Defy Advanced SL 1 Moonstone")
    assert ranked[0][1]["name"] == "Defy Advanced 1"
    check = checks.name_check(ranked[0][1], models, "Giant Defy Advanced SL 1 Moonstone")
    assert check["extra"] == ["SL"]


def test_an_ad_without_a_year_shows_the_middle_year_its_details_allow(models):
    # Émonda SLR 7 was sold 2020-2024; 12-speed rules out 2020 and 2021, leaving 2022-2024: the middle is 2023.
    r = checks.run_check(models, {"title": "Trek Emonda SLR 7", "description": "Ultegra Di2 2x12, maat 56"})
    assert r["model"]["name"] == "Émonda SLR 7"
    assert (r["year_estimate"]["first"], r["year_estimate"]["last"]) == (2022, None)
    assert r["spec_year"] == 2023 and r["photo_year"]["year"] == 2023
    # 11-speed leaves 2020-2021, but this generation launched as the 2021 model (reference.LINEAGES): 2020's sheet is
    # the previous one.
    r = checks.run_check(models, {"title": "Trek Emonda SLR 7", "description": "Ultegra Di2 2x11"})
    assert r["spec_year"] == 2021 and r["year"]["year"] == 2021
    assert checks.middle_year([2020, 2021, 2022, 2023, 2024]) == 2022 and checks.middle_year([2021, 2022]) == 2021


def test_a_two_tone_colour_shows_its_own_photo_not_another_with_the_same_first_part(models):
    for text in ("Trek Émonda SLR 7 Navy Carbon Smoke / Viper Red", "Trek Emonda SLR 7 blauw rood"):
        r = checks.run_check(models, {"title": text, "description": "12 speed"})
        assert r["photo_year"]["colour"] == "Navy Carbon Smoke/Viper Red", text
        assert "navycarbonsmokeviperred" in r["model"]["image"], text
        # The colour came in 2021-2024 and 12-speed rules out 2021: the middle of 2022-2024.
        assert r["photo_year"]["year"] == 2023 and r["spec_year"] == 2023, text


def test_a_stated_year_wins_over_a_groupset_that_could_be_an_upgrade(models):
    # The 12-speed 105 came on the Domane AL 4 from 2024, but parts get swapped: a 2022 bike with a newer groupset.
    r = run(models, "Racefiets Trek Domane AL4 - Shimano 105 12-speed - maat 54", "Bouwjaar 2022, nette staat", 975)
    assert r["year_estimate"]["status"] == checks.OK and en(r["year_estimate"]["headline"]) == "2022 fits"
    assert "probably upgraded" in " ".join(en(e) for e in r["year_estimate"]["evidence"])
    assert r["spec_year"] == 2022
    groupset = next(row for row in r["specs"]["rows"] if row["key"] == "groupset")
    assert groupset["step"] > 0  # an upgrade on the 2022 sheet


def _tarmac_sl8(models):
    # Like the S-Works Tarmac SL8 on the NAS: an archived line with only its 2026 sheet, so our oldest year is
    # two years after the real launch (the 2024 model, launched in 2023).
    return dict(models[0], brand="Specialized", name="S-Works Tarmac SL8 - SRAM RED AXS", seen_on=None, photo_years=[],
                source_file="years/archived/x.json", price_eur=None, specs={"Frame": "x"},
                year_specs={"checked": [2026], "years": {"2026": {"specs": {"Frame": "x"}, "price": 13000}}})


def test_a_generation_starts_at_its_launch_not_at_our_oldest_sheet(models):
    m = _tarmac_sl8(models)
    gen = checks.generation(m)
    assert (gen["first"], gen["name"]) == (2024, "Tarmac SL8") and gen["earlier"][-1] == (2021, 2023, "Tarmac SL7")
    age = checks.check_age(m, checks.read_claims("Specialized Tarmac SL8 2024", ""), TODAY)
    assert age["status"] == checks.OK
    # The year before launch is most likely when it was bought: priced as the 2024 model, not the 2023 one.
    claims = checks.read_claims("Specialized Tarmac SL8 2023", "")
    age = checks.check_age(m, claims, TODAY)
    assert age["status"] == checks.WARN and age["purchase"] and not age["earlier"]
    assert checks.resolve_year(m, claims, age, None, TODAY)["year"] == 2024
    # Two years before: the previous generation, by name.
    age = checks.check_age(m, checks.read_claims("Specialized Tarmac SL8 2021", ""), TODAY)
    assert age["earlier"] and "Tarmac SL7" in en(age["detail"])
    # Only a spec sheet of that year makes it this model's predecessor; a photo year doesn't.
    assert not age["earlier_sheet"]
    assert not checks.check_age(dict(m, photo_years=[2021]), checks.read_claims("Specialized Tarmac SL8 2021", ""),
                                TODAY)["earlier_sheet"]
    assert [g["name"] for g in age["generations"]] == ["Tarmac SL7", "S-Works Tarmac SL8 - SRAM RED AXS"]


def test_details_outside_the_generation_are_another_generation(models):
    # The details point to 2018-2020, before the SL8 launched (2024): priced at their middle, but not reliable.
    m = _tarmac_sl8(models)
    resolved = checks.resolve_year(m, checks.read_claims("Specialized Tarmac SL8", ""), {"status": checks.WARN},
                                   {"status": checks.UNKNOWN, "first": 2018, "last": 2020}, TODAY)
    assert (resolved["year"], resolved["reliable"]) == (2019, False)
    # A lineage's end doesn't retire a version the brand still lists.
    sl7 = dict(models[0], brand="Specialized", name="Tarmac SL7 Sport - Shimano 105", missed_scrapes=0,
               last_seen="2026-10-01", source_file="x.json")
    assert checks.catalogue_status(sl7, TODAY)[0] == "current"
    assert checks.catalogue_status(dict(sl7, missed_scrapes=2, latest_scrape="2026-10-01"), TODAY)[0] == "discontinued"
    assert checks.catalogue_status(dict(sl7, missed_scrapes=None), TODAY)[0] == "unknown"  # never checked


def test_one_year_for_the_price_and_the_specs(models):
    m = _tarmac_sl8(models)
    age = {"status": checks.WARN}
    no_year = checks.read_claims("Specialized Tarmac SL8", "")
    # No year and no clues: the middle of the generation's years (2024–2026), never as new.
    assert checks.resolve_year(m, no_year, age, None, TODAY)["year"] == 2025
    # Clues: the middle of what they allow within the generation.
    assert checks.resolve_year(m, no_year, age, {"status": checks.UNKNOWN, "first": 2025, "last": None}, TODAY)[
        "year"] == 2025
    # A purchase year after the years the details allow: the newest model year they allow (check 20).
    bought = checks.read_claims("Trek Emonda ALR 5", "gekocht in 2024")
    assert bought["year_is_purchase"]
    resolved = checks.resolve_year(m, bought, {"status": checks.OK, "year": 2024},
                                   {"status": checks.OK, "first": None, "last": 2025}, TODAY)
    assert (resolved["year"], resolved["how"]) == (2024, "ad")
    resolved = checks.resolve_year(m, dict(bought, year=2026), {"status": checks.OK, "year": 2026},
                                   {"status": checks.OK, "first": None, "last": 2025}, TODAY)
    assert (resolved["year"], resolved["how"]) == (2025, "purchase")
    tab = checks.age_summary({"status": checks.OK, "year": 2026, "headline": checks.Msg("Adds up"), "detail": checks.Msg("x")},
                             {"status": checks.OK, "headline": checks.Msg("y"), "detail": checks.Msg("z")}, resolved)
    assert en(tab["headline"]) == "Model year 2025, bought in 2026"
    # The value uses that year's own new price when we have it.
    value = checks.check_value(m, checks.read_claims("Specialized Tarmac SL8 2026", ""), 9000, {"rows": []},
                               {"status": checks.OK}, TODAY)
    assert value["original"] == 13000 and value["model_year"] == 2026


def test_an_ad_without_a_year_says_what_its_details_point_to():
    age = {"status": checks.WARN, "headline": checks.Msg("Year not stated"), "detail": checks.Msg("x")}
    estimate = {"status": checks.UNKNOWN, "first": 2022, "last": None, "headline": checks.Msg("y"),
                "detail": checks.Msg("The ad doesn't give a year, but its details point to {years}.", years="2022–2026")}
    tab = checks.age_summary(age, estimate, {"year": 2024, "how": "estimate", "first": 2022, "last": 2026})
    assert tab["status"] == checks.WARN and en(tab["headline"]) == "Probably 2024"
    assert "so we go by 2024, the middle" in en(tab["detail"])
    # A colour-dated year, and the generation's middle year without any clues, the same way.
    tab = checks.age_summary(age, estimate, {"year": 2023, "how": "photo", "first": 2023, "last": 2023})
    assert en(tab["headline"]) == "Probably 2023"
    tab = checks.age_summary(age, None, {"year": 2025, "how": "generation", "first": 2024, "last": 2026})
    assert en(tab["headline"]) == "Probably 2025" and "this generation was sold 2024–2026" in en(tab["detail"])


def test_an_earlier_generation_we_have_no_sheet_of_is_priced_with_a_warning(models):
    # Check 50: an Émonda SL 5 from 2017 is the first Émonda generation; we go by the ad's year but say its new
    # price was another one.
    r = run(models, "Trek Émonda SL 5", "Bouwjaar 2017", price=600)
    assert r["age"]["earlier"] and not r["year"]["reliable"]
    assert r["value"]["model_year"] == 2017
    assert any("probably an earlier generation" in en(n) for n in r["value"]["notes"])


def test_a_colour_the_ad_names_dates_the_years_whose_colourway_leads_with_it(models):
    # Giant Defy Advanced Pro 2: 2018 "Carbon Smoke/ Neon Red/ Charcoal", 2019 "Charcoal / Iris". A seller's
    # "kleur charcoal" is the charcoal bike of 2019, not the 2018 one with charcoal trim (check 53).
    r = run(models, "Giant Defy Advanced Pro 2 racefiets",
            "Ik verkoop mijn Giant Defy racefiets, kleur charcoal maat M. Shimano 105, schijfremmen, composiet frame.")
    assert r["year"]["year"] == 2019, r["year"]


def test_a_lead_colour_skips_a_plain_carbon_first_part(models):
    # Giant Defy Advanced 2: 2018 "Carbon Smoke/Neon Orange/Charcoal", 2021 "Carbon/Charcoal". Charcoal leads
    # the 2021 colourway once the plain "Carbon" is skipped.
    r = run(models, "Giant Defy Advanced 2 racefiets", "kleur charcoal maat M, Shimano 105, schijfremmen")
    assert r["model"]["name"].startswith("Defy Advanced 2"), r["model"]["name"]
    assert r["year"]["year"] == 2021, r["year"]


def test_an_earlier_year_shows_its_own_generation(tmp_path):
    """Picking a year of an earlier generation shows that bike: Trek's archive names the 2021-2023 sheets
    "Domane AL 2 gen 3", and the 2019-2020 rim-brake sheet before it had another frame, so it was gen 2."""
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    model = next(m for m in db.all_models(db.connect(path)) if m["slug"] == "trek-domane-al-2-gen-4")
    gens = checks.year_generations(model)
    assert (gens[2022]["title"], gens[2022]["first"], gens[2022]["last"], gens[2022]["number"]) == \
        ("Domane AL 2 Gen 3", 2021, 2023, 3)
    assert (gens[2020]["title"], gens[2020]["first"], gens[2020]["last"]) == ("Domane AL 2", 2019, 2020)
    assert (gens[2020]["number"], gens[2020]["counted"]) == (2, "before")
    assert 2024 not in gens  # our own generation
    from webapp.app import create_app
    page = create_app(path).test_client().get("/models/trek-domane-al-2-gen-4?lang=nl").get_data(as_text=True)
    assert 'data-fact="title">Domane AL 2 Gen 4</h1>' in page
    assert '<span data-fact="title">Domane AL 2 Gen 3</span>' in page
    assert '<div class="v">2021–2023</div>' in page and "eerdere gen. · gen 2" in page


def test_unnumbered_years_take_the_generation_of_the_launch_years():
    """Trek names only the 2022 Domane SL 5 sheet gen 3; the 2020-2021 one is the same generation."""
    sheet = {"specs": {"Frame": "500 Series OCLV Carbon, IsoSpeed"}}
    model = {"brand": "Trek", "name": "Domane SL 5 Gen 4", "seen_on": "2025-10-01", "specs": {"Frame": "x"},
             "year_specs": {"years": {"2020": dict(sheet, sheet_name="Domane SL 5", sheet_years="2020 - 2021"),
                                      "2021": dict(sheet, sheet_name="Domane SL 5", sheet_years="2020 - 2021"),
                                      "2022": dict(sheet, sheet_name="Domane SL 5 gen 3", sheet_years="2022")}}}
    gens = checks.year_generations(model)
    assert {(g["first"], g["last"], g["number"]) for g in gens.values()} == {(2020, 2022, 3)}
    assert gens[2020]["title"] == "Domane SL 5" and gens[2022]["title"] == "Domane SL 5 Gen 3"


def test_frame_decides_an_unnumbered_generation_only_when_clear():
    def model(old_frame):
        new = "100 Series Alpha Aluminium, tapered head tube, internal routing, fender mounts, disc, thru axle"
        return {"brand": "Trek", "name": "Domane AL 2 Gen 4", "seen_on": "2025-10-01", "specs": {"Frame": "x"},
                "year_specs": {"years": {
                    "2019": {"specs": {"Frame": old_frame}, "sheet_name": "Domane AL 2", "sheet_years": "2019 - 2020"},
                    "2020": {"specs": {"Frame": old_frame}, "sheet_name": "Domane AL 2", "sheet_years": "2019 - 2020"},
                    "2021": {"specs": {"Frame": new}, "sheet_name": "Domane AL 2 gen 3", "sheet_years": "2021 - 2023"}}}}
    clear = checks.year_generations(model("100 Series Alpha Aluminium, fender mounts, rim brake, 130 x 5 mm QR"))
    assert (clear[2020]["number"], clear[2020]["counted"], clear[2019]["first"]) == (2, "before", 2019)
    same = checks.year_generations(model(
        "100 Series Alpha Aluminium, tapered head tube, internal routing, fender mounts, disc, thru axle"))
    assert (same[2020]["number"], same[2020]["first"], same[2021]["first"]) == (3, 2019, 2019)
    unsure = checks.year_generations(model("100 Series Alpha Aluminium, tapered head tube, fender mounts, rim brake"))
    assert unsure[2020]["number"] is None and unsure[2020]["title"] == "Domane AL 2"


def test_model_titles_leave_shimano_out(tmp_path):
    assert checks.model_title("Tarmac SL9 Comp - Shimano 105 Di2") == "Tarmac SL9 Comp - 105 Di2"
    assert checks.model_title("Diverge 4 Pro LTD - Shimano XTR/GRX Di2") == "Diverge 4 Pro LTD - XTR/GRX Di2"
    assert checks.model_title("Defy Advanced 1 Shimano") == "Defy Advanced 1"
    assert checks.model_title("Aethos 2 Pro - SRAM Force AXS") == "Aethos 2 Pro - SRAM Force AXS"
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    client = create_app(path).test_client()
    tiles = client.get("/models?brand=Specialized&lang=nl").get_data(as_text=True)
    assert ">Tarmac SL9 Comp - 105 Di2</span>" in tiles and "Shimano 105 Di2</span>" not in tiles
    page = client.get("/models/" + seed.slugify("Specialized Tarmac SL9 Comp - Shimano 105 Di2")).get_data(as_text=True)
    assert ">Tarmac SL9 Comp - 105 Di2</h1>" in page


def test_models_page_tiles_leave_the_generation_out(tmp_path):
    assert checks.without_generation("Domane AL 2 Gen 4") == "Domane AL 2"
    assert checks.without_generation("Madone SLR 9 gen 8 frameset") == "Madone SLR 9 frameset"
    from webapp.app import create_app
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    client = create_app(path).test_client()
    tiles = client.get("/models?brand=Trek&lang=nl").get_data(as_text=True)
    assert ">Domane AL 2</span>" in tiles and ">Domane AL 2 Gen 4</span>" not in tiles
    # the model page itself keeps the generation
    assert "Domane AL 2 Gen 4" in client.get("/models/trek-domane-al-2-gen-4?lang=nl").get_data(as_text=True)


def test_only_the_estimated_years_next_to_the_ads_year_are_ringed():
    years = list(range(2011, 2027))
    # The ad says 2011, the details say 2012 or later: only 2012, not 2012-2026.
    assert checks.ringed_years(years, {"first": 2012, "last": None}, 2011) == {2012}
    # The estimate agrees with the ad's 2018: the year itself and one either side.
    assert checks.ringed_years(years, {"first": 2015, "last": 2022}, 2018) == {2017, 2018, 2019}
    # The estimate rules the ad's year out by far: where it points, the closest year and the one next to it.
    assert checks.ringed_years(years, {"first": 2020, "last": 2023}, 2011) == {2020, 2021}
    # No year in the ad: the whole estimate.
    assert checks.ringed_years(years, {"first": 2023, "last": None}) == {2023, 2024, 2025, 2026}
    assert checks.ringed_years(years, None, 2011) == set()


def test_report_value_section_without_and_with_an_asking_price(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    bare = client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56"})
    page = client.get(bare.headers["Location"] + "?lang=en").data.decode()
    assert 'class="price-slider"' in page and 'class="pin' not in page and "value-verdict" not in page
    priced = client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56", "asking_price": "9000"})
    page = client.get(priced.headers["Location"] + "?lang=en").data.decode()
    assert 'class="price-slider with-pin"' in page and 'class="value-verdict warn-bg"' in page
    assert "above the fair range" in page and "How we estimate this" in page
    assert "above fair" in page and "Middle €" in page and 'class="new"' in page
