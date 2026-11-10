import re

import pytest

from webapp import checks, db, seed
from webapp.app import create_app


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    conn = db.connect(str(tmp_path_factory.mktemp("db") / "app.sqlite3"))
    seed.load(conn)
    return db.all_models(conn)


def _by_name(models, name):
    return next(m for m in models if m["brand"] == "Ridley" and m["name"] == name)


def test_split_build():
    assert checks.split_build({"brand": "Ridley", "name": "Noah Fast 3.0 Shimano Ultegra Di2 2x12"}) == \
        ("Noah Fast 3.0", "Shimano Ultegra Di2 2x12")
    assert checks.split_build({"brand": "Ridley", "name": "Kanzo A Frameset"}) == ("Kanzo A Frameset", None)  # its own model
    assert checks.split_build({"brand": "Ridley", "name": "Fenix Disc Classified Rival AXS 1x12"})[0] == "Fenix Disc"
    assert checks.split_build({"brand": "Trek", "name": "Madone SL 6 Gen 8"}) == ("Madone SL 6 Gen 8", None)
    assert checks.build_label({"brand": "Ridley", "name": "Noah Fast 3.0 Shimano Ultegra Di2 2x12"}) == "Fast 3.0 Ultegra Di2 2x12"
    assert checks.model_group("Noah Fast 3.0 SRAM Red AXS 2x12", "Ridley") == "Noah"


def _top(models, title):
    return checks.match_models(models, title)[0][1]["name"]


def test_matching_finds_the_model_before_the_build(models):
    assert _top(models, "Ridley Noah Fast Ultegra Di2 maat M") == "Noah Fast 3.0 Shimano Ultegra Di2 2x12"
    # a year is no version, and 105 is a groupset, not a Noah 105
    assert _top(models, "Ridley Noah Fast 2020 Dura-Ace").startswith("Noah Fast 3.0")
    assert _top(models, "Ridley Noah 105 di2") == "Noah 3.0 Shimano 105 Di2 2x12"
    # a groupset the model isn't sold with today doesn't pull the ad to another model
    assert _top(models, "Ridley Kanzo Fast GRX").startswith("Kanzo Fast 2.0")
    # the frameset only when the ad sells the frame
    assert "Frameset" not in _top(models, "Ridley Noah Fast 3.0 maat M zgan")
    assert _top(models, "Ridley Noah Fast 3.0 frameset maat M") == "Noah Fast 3.0 Frameset"


def test_build_choice(models):
    named = checks.run_check(models, {"title": "Ridley Noah Fast Ultegra Di2", "description": "", "asking_price": 6000})
    assert named["builds"]["state"] == "named" and named["model"]["name"].endswith("Ultegra Di2 2x12")
    unknown = checks.run_check(models, {"title": "Ridley Noah Fast 3.0 maat M", "description": "", "asking_price": 6000})
    complete = [b for b in unknown["builds"]["all"] if not checks.is_frameset(b)]
    assert unknown["builds"]["state"] == "unknown"
    assert unknown["model"]["id"] == complete[(len(complete) - 1) // 2]["id"]  # the middle one by price
    other = checks.run_check(models, {"title": "Ridley Kanzo Fast GRX", "description": "", "asking_price": 2000})
    assert other["builds"]["state"] == "other"
    picked = _by_name(models, "Noah Fast 3.0 SRAM Red AXS 2x12")
    by_hand = checks.run_check(models, {"title": "Ridley Noah Fast 3.0", "description": "", "asking_price": 6000,
                                        "model_id": picked["id"]})
    assert by_hand["builds"]["state"] == "named" and by_hand["model"]["id"] == picked["id"]
    assert checks.run_check(models, {"title": "Trek Madone SL 6", "description": "", "asking_price": 3000})["builds"] is None


def test_pages_show_one_model_with_its_builds(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    html = client.get("/models?brand=Ridley&lang=en").get_data(as_text=True)
    titles = re.findall(r'<span style="font-weight: 700">([^<]+)</span>', html)
    # the model is the family: the Noah 3.0 and Noah Fast 3.0 are levels of the Noah
    assert titles.count("Noah") == 1 and not any("Ultegra" in t or "Fast" in t for t in titles)
    assert not any("rameset" in t for t in titles)  # a frameset is the last level of its family, no tile
    assert "12 builds" in html and "New from €" not in html and "New €" not in html
    page = client.get("/models/ridley-noah-fast-3-0-shimano-ultegra-di2-2x12?lang=en").get_data(as_text=True)
    pills = re.findall(r'class="build-pill t\d( on)?" href="/models/([^"]+)"', page)
    assert len(pills) == 12 and [s for on, s in pills if on] == ["ridley-noah-fast-3-0-shimano-ultegra-di2-2x12"]


def test_a_model_with_one_build_has_no_build_section(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/ridley-x-ride-disc-shimano-grx-600-2x12?lang=en").get_data(as_text=True)
    assert "X-Ride Disc" in page and 'class="builds build-card"' not in page and "build-pill" not in page



def test_the_frameset_is_one_candidate_with_the_builds(models):
    # the frameset is a model of its own on the site, but for the matching its word is the build's, so it neither
    # wins a complete-bike ad nor counts as another model close behind
    assert _top(models, "Ridley Noah Fast 3.0 Ultegra Di2 maat M") == "Noah Fast 3.0 Shimano Ultegra Di2 2x12"
    frame = _by_name(models, "Noah Fast 3.0 Frameset")
    built = _by_name(models, "Noah Fast 3.0 Shimano Ultegra Di2 2x12")
    assert checks.same_model(frame, built) and not checks.builds_of(frame, models, split=checks.split_build)
    report = checks.run_check(models, {"title": "Ridley Noah Fast 3.0 Ultegra Di2", "description": "", "asking_price": 6000})
    others = [r["pct"] for r in report["matches"] if not checks.same_model(r["model"], report["model"])]
    assert str(report["confidence"]) != "medium" or not others or max(others) >= report["match"]["pct"] - 15


def test_a_frameset_check_doesnt_count_the_builds_as_rivals(models):
    report = checks.run_check(models, {"title": "Ridley Noah Fast 3.0 frameset maat M", "description": "", "asking_price": 2500})
    assert report["model"]["name"] == "Noah Fast 3.0 Frameset" and report["builds"] is None
    rivals = [r["pct"] for r in report["matches"] if r is not report["match"]
              and not checks.same_model(r["model"], report["model"])]
    assert report["confidence"].text == checks.match_confidence(report["match"]["pct"], rivals, report.get("not_exact"))


def test_the_model_page_starts_at_the_first_year_it_knows(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    model = next(m for m in db.all_models(db.connect(app.config["DB_PATH"])) if m["slug"] == "trek-madone-sl-6-gen-8")
    tabs = checks.year_tabs(model)
    first = next(t["year"] for t in tabs if t.get("image") or t.get("specs"))
    page = app.test_client().get("/models/trek-madone-sl-6-gen-8?lang=nl").get_data(as_text=True)
    assert f'id="tab-{first}"' in page and f'id="tab-{first - 1}"' not in page
    assert f'id="tab-{tabs[-1]["year"]}"' in page  # the last year always shows


def test_trek_names_split_into_model_build_generation_and_edition():
    assert checks.trek_parts("Madone SLR 9 AXS Gen 8 - No. 76 ICON") == ("Madone SLR", "9 AXS", 8, "No. 76 ICON")
    # a Disc version is the same bike as the one without: one build, one frameset
    assert checks.trek_parts("Madone SL Disc Gen 6 frameset") == ("Madone SL frameset", None, 6, None)
    assert checks.trek_parts("Madone SL 6 Disc Gen 6") == ("Madone SL", "6", 6, None)
    assert checks.trek_parts("Émonda SL 7 Disc eTap")[:2] == ("Émonda SL", "7 eTap")
    assert checks.trek_parts("Checkpoint AL 3 Gen 1")[:2] == ("Checkpoint ALR", "3")  # Trek's old name for the line
    assert checks.trek_parts("Domane SLR 9 AXS No. 76 Gen 5")[:2] == ("Domane SLR", "9 AXS")
    assert checks.model_group("Madone SL 7 Gen 8 - The First 50 Replica", "Trek") == "Madone"
    # the site shows the family as the model, its frame as the level
    assert checks.trek_levels("Madone SL 6 AXS Gen 8") == ("Madone", "SL", "6 AXS")
    assert checks.trek_levels("Madone SLR Gen 7 frameset") == ("Madone frameset", "SLR", None)
    assert checks.trek_levels("Speed Concept SLR 7")[:2] == ("Speed Concept", "SLR")


def test_trek_model_page_lists_each_build_once(models):
    gen6 = next(m for m in models if m["slug"] == "trek-madone-sl-6-gen-6")
    builds = checks.builds_of(gen6, models)
    labels = [checks.build_label(b) for b in builds]
    # the Madone holds the SL and SLR levels; each build once
    assert len(labels) == len(set(labels)) and "SL 7" in labels and "SL 6" in labels and "SLR 9" in labels
    assert not any("Disc" in label for label in labels)
    assert not any("First 50" in b["name"] for b in builds if checks.build_level(b) == "SL")  # a colour
    assert all("frameset" in b["name"] for b in builds if checks.build_level(b) == "Frameset")
    assert builds[-1]["name"].endswith("frameset") or "frameset" in builds[-1]["name"]  # the framesets last
    # by number, then tier low to high
    sl = [l for l in labels if l.startswith("SL ")]
    numbers = [int(l.split()[1]) for l in sl]
    assert numbers == sorted(numbers)
    sevens = [checks.model_tier(b) or 0 for b in builds if checks.build_label(b).startswith("SL 7")]
    assert sevens == sorted(sevens)
    # the 6 of every generation is one build: the newest one
    assert next(b for b in builds if checks.build_label(b) == "SL 6")["name"] == "Madone SL 6 Gen 8"


def test_bianchi_names_split_into_model_and_build():
    assert checks.bianchi_parts("Oltre Pro Team Replica Ultegra Di2") == ("Oltre Pro", "Ultegra Di2", "Team Replica")
    # CV is a frame of its own; Disc is the same build, as for Trek
    assert checks.bianchi_parts("Oltre XR4 CV Disc Ultegra Di2") == ("Oltre XR4 CV", "Ultegra Di2", None)
    assert checks.bianchi_parts("Oltre XR4 Ultegra Di2 Disc")[:2] == ("Oltre XR4", "Ultegra Di2")
    # the women's version is a build of its own, under its model
    assert checks.bianchi_parts("Dama Bianca Intenso 105") == ("Intenso", "105 Dama Bianca", None)
    assert checks.bianchi_parts("Oltre RC Frameset") == ("Oltre RC frameset", None, None)
    # the same groupset spelled another way is one build
    assert checks.bianchi_parts("Specialissima D/A Di2 40T")[1] == checks.bianchi_parts("Specialissima Dura-Ace Di2")[1]
    assert checks.bianchi_parts("Impulso All Road GRX 400")[:2] == checks.bianchi_parts("Impulso Allroad GRX 400")[:2]
    assert checks.bianchi_parts("Nirone 7")[0] == "Via Nirone 7"


def test_bianchi_model_page_lists_its_builds(models):
    oltre = next(m for m in models if m["name"] == "Oltre RC Dura-Ace Di2")
    labels = [checks.build_label(b) for b in checks.builds_of(oltre, models)]
    # the Oltre is the model, its RC, XR4, CV… the levels; the frameset its last level
    assert "RC Dura-Ace Di2" in labels and "RC Founder Edition" in labels and len(labels) == len(set(labels))
    assert labels[-1].startswith("Frameset")
    assert checks.model_group("Oltre RC Team Replica Dura-Ace Di2", "Bianchi") == "Oltre"
    assert checks.bianchi_levels("Oltre XR4 CV Ultegra Di2")[:2] == ("Oltre", "XR4 CV")


def test_a_build_without_a_groupset_shows_its_model_name_once(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    slug = conn.execute("SELECT slug FROM models WHERE name = 'Impulso Allroad'").fetchone()[0]
    page = app.test_client().get(f"/models/{slug}?lang=nl").get_data(as_text=True)
    pills = [re.sub(r"<[^>]+>", "", p) for p in re.findall(r'<a class="build-pill.*?</a>', page, re.S)]
    allroad = page[page.index('data-level="Allroad">'):]
    allroad = [re.sub(r"<[^>]+>", "", p) for p in re.findall(r'<a class="build-pill.*?</a>', allroad[:allroad.index("</div>")], re.S)]
    assert any(p.startswith("GRX 400") for p in allroad)
    assert any(re.match(r"Allroad\W", p) for p in allroad)  # the entry without a groupset: its level's name, once
    assert not any("Impulso Allroad" in p for p in pills)


def test_specialized_names_split_into_model_and_build():
    assert checks.specialized_parts("Tarmac SL8 Expert - Shimano Ultegra Di2") == ("Tarmac", "Expert SL8 Ultegra Di2", None)
    # an older name without the dash, with Disc: the same build
    assert checks.specialized_parts("Tarmac SL7 Expert Ultegra Di2 Disc")[:2] == ("Tarmac", "Expert SL7 Ultegra Di2")
    # S-Works is the top level of the model, its build the groupset; an edition is a colour of its build, also
    # when "LTD" sits in the name and the edition after the dash
    assert checks.specialized_parts("S-Works Tarmac SL7 - Shimano Dura-Ace Di2")[:2] == ("Tarmac", "S-Works SL7 Dura-Ace Di2")
    assert checks.specialized_parts("S-Works Tarmac SL8 LTD - Red Bull 2025 TdF") == ("Tarmac", "S-Works SL8", "Red Bull 2025 TdF")
    assert checks.specialized_parts("S-Works Crux 5 LTD - Built for Legends")[:2] == ("Crux", "S-Works 5")
    assert checks.specialized_parts("Tarmac SL7 Expert - Shimano Ultegra Di2 Team Replica")[1:] == ("Expert SL7 Ultegra Di2", "Team Replica")
    # Aethos 2 is the Aethos; a frameset is one model over its generations, the S-Works frame its build
    assert checks.specialized_parts("Aethos 2 Pro - SRAM Force AXS")[:2] == ("Aethos", "Pro Force eTap AXS")
    assert checks.specialized_parts("S-Works Tarmac SL9 Team Replica Frameset - Soudal Quick-Step")[:2] == ("Tarmac frameset", "S-Works SL9")
    assert checks.specialized_parts("S-Works Tarmac SL8 Frameset LTD - Demi Dreaming")[0] == "Tarmac frameset"
    # Women's is a build of its own; Men's is left out; the alloy Diverge is a model of its own
    assert checks.specialized_parts("Women's Tarmac Disc Expert")[1] == "Expert Women's"
    assert checks.specialized_parts("Men's Diverge Comp")[:2] == ("Diverge", "Comp")
    assert checks.specialized_parts("Diverge Comp E5 - SRAM Apex")[:2] == ("Diverge", "Comp Alloy Apex")
    # the model is the family: Allez Sprint is the Allez, the Sprint frame a part of its build
    assert checks.specialized_parts("Allez Sprint Comp - Shimano 105")[:2] == ("Allez", "Comp Sprint 105")


def test_specialized_model_page_shows_the_levels_first(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    slug = conn.execute("SELECT slug FROM models WHERE name = 'Aethos 2 Expert - Shimano Ultegra Di2'").fetchone()[0]
    page = app.test_client().get(f"/models/{slug}?lang=nl").get_data(as_text=True)
    assert re.findall(r'class="level-tab[^"]*" data-level="([\w-]+)"', page) == ["Sport", "Comp", "Expert", "Pro", "S-Works", "Frameset"]
    assert 'class="level-tab on" data-level="Expert"' in page  # the bike's own level is open
    # the other levels' groupsets are there, hidden; a pill names the groupset only
    assert '<div class="build-row" data-level="Comp" hidden>' in page and '<div class="build-row" data-level="Expert">' in page
    expert = page[page.index('data-level="Expert">'):]
    assert "<span>Ultegra Di2</span>" in expert[:expert.index("</div>")]
    # a model without levels keeps one row of pills
    assert "level-tab" not in app.test_client().get("/models/ridley-x-ride-disc-shimano-grx-600-2x12?lang=nl").get_data(as_text=True)


def test_ridley_models_are_families_with_levels():
    rs = {"brand": "Ridley", "name": "Falcn RS 2.0 Shimano Ultegra Di2 2x12"}
    assert checks.site_split(rs) == ("Falcn", "RS 2.0 Shimano Ultegra Di2 2x12")
    assert checks.build_level(rs) == "RS 2.0"
    plain = {"brand": "Ridley", "name": "Falcn Shimano 105 Di2 2x12"}
    assert checks.site_split(plain) == ("Falcn", "Shimano 105 Di2 2x12") and checks.build_level(plain) is None
    # a frameset stays a model of its own, and the matching still sees the RS on its own words
    assert checks.site_split({"brand": "Ridley", "name": "Astr RS Frameset"}) == ("Astr", "Frameset RS")
    assert checks.split_build(rs) == ("Falcn RS 2.0", "Shimano Ultegra Di2 2x12")
    assert checks.site_split({"brand": "Ridley", "name": "Grifn RS Road Shimano Ultegra Di2 2x12"}) == ("Grifn", "RS Shimano Ultegra Di2 2x12")
    assert checks.site_split({"brand": "Ridley", "name": "Fenix Disc Shimano 105 2x12"}) == ("Fenix", "Shimano 105 2x12")


def test_bmc_cannondale_and_scott_models_are_families_with_levels():
    assert checks.level_parts("BMC", "Teammachine SLR 01 DISC TWO") == ("Teammachine", "SLR 01", "TWO")
    assert checks.level_parts("BMC", "Roadmachine FIVE") == ("Roadmachine", None, "FIVE")
    assert checks.level_parts("BMC", "Teammachine R 01 Frameset") == ("Teammachine frameset", "R 01", None)
    assert checks.level_parts("Cannondale", "CAAD13 Disc Ultegra") == ("CAAD", "CAAD13", "Ultegra")
    assert checks.level_parts("Cannondale", "Synapse HiMOD Force eTap AXS Disc") == ("Synapse", "Hi-MOD", "Force eTap AXS")
    assert checks.level_parts("Cannondale", "SuperSix Evo Carbon Ultegra Di2") == ("SuperSix EVO", None, "Ultegra Di2")
    assert checks.level_parts("Cannondale", "Topstone Carbon 105 Women's Disc")[1:] == ("Carbon", "105 Women's")
    assert checks.level_parts("Scott", "Addict RC Pro") == ("Addict", "RC", "Pro")
    assert checks.level_parts("Scott", "Foil RC Pro HMX Frameset") == ("Foil frameset", "RC", "Pro HMX")
    assert checks.build_level({"brand": "Scott", "name": "Speedster Gravel 20"}) == "Gravel"


def test_the_other_brands_split_into_family_level_and_build():
    assert checks.level_parts("Canyon", "Aeroad CF SL 8 WMN Disc") == ("Aeroad", "CF SL", "8 Women's")
    assert checks.level_parts("Giant", "TCR Advanced Pro 1 Disc") == ("TCR", "Advanced Pro", "1")
    assert checks.level_parts("Cervelo", "Caledonia-5 Ultegra Di2") == ("Caledonia", "5", "Ultegra Di2")
    assert checks.level_parts("Cube", "Litening AIR C:68X SLX") == ("Litening", "AIR C:68X", "SLX")
    assert checks.level_parts("Factor", "OSTRO VAM - Shimano Ultegra") == ("OSTRO", "VAM", "Shimano Ultegra")
    assert checks.level_parts("Wilier", "Filante SLR Frameset")[:2] == ("Filante frameset", "SLR")


def test_a_build_pill_shows_the_price_its_page_shows(tmp_path):
    # the Émonda ALR 4 has no list price of its own; its page shows the newest year's (German) price, so does its pill
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/trek-emonda-alr-4?lang=nl").get_data(as_text=True)
    row = page[page.index('data-level="ALR">'):]
    pills = [re.sub(r"<[^>]+>", " ", p).split() for p in re.findall(r'<a class="build-pill.*?</a>', row[:row.index("</div>")], re.S)]
    four = next(p for p in pills if "4" in p[:2])
    assert four[-1] == "€1.949*" and "–" not in four
    # and the price tag says the same before any year is picked
    assert '<b data-fact="sticker">€1.949*</b>' in page
    note = re.search(r'class="small muted price-note" data-fact="price-note">(.*?)</p>', page, re.S).group(1)
    assert note.startswith("*")
