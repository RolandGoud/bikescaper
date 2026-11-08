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
    assert checks.build_label({"brand": "Ridley", "name": "Noah Fast 3.0 Shimano Ultegra Di2 2x12"}) == "Ultegra Di2 2x12"
    assert checks.model_group("Noah Fast 3.0 SRAM Red AXS 2x12", "Ridley") == "Noah Fast 3.0"


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
    assert titles.count("Noah Fast 3.0") == 1 and not any("Ultegra" in t for t in titles)
    assert "Noah Fast 3.0 Frameset" in titles  # a frameset is a tile of its own, never a build
    assert "4 builds" in html and "New from €" not in html and "New €" not in html
    page = client.get("/models/ridley-noah-fast-3-0-shimano-ultegra-di2-2x12?lang=en").get_data(as_text=True)
    pills = re.findall(r'class="build-pill t\d( on)?" href="/models/([^"]+)"', page)
    assert len(pills) == 4 and [s for on, s in pills if on] == ["ridley-noah-fast-3-0-shimano-ultegra-di2-2x12"]


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
    assert checks.same_model(frame, built) and not checks.builds_of(frame, models)
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
    assert checks.model_group("Madone SL 7 Gen 8 - The First 50 Replica", "Trek") == "Madone SL"


def test_trek_model_page_lists_each_build_once(models):
    gen6 = next(m for m in models if m["slug"] == "trek-madone-sl-6-gen-6")
    builds = checks.builds_of(gen6, models)
    labels = [checks.build_label(b) for b in builds]
    assert len(labels) == len(set(labels)) and "7" in labels and "6" in labels
    assert not any("Disc" in label for label in labels)
    assert not any("First 50" in b["name"] or "frameset" in b["name"] for b in builds)  # a colour; a model of its own
    # by number, then tier low to high
    numbers = [int(l.split()[0]) for l in labels]
    assert numbers == sorted(numbers)
    sevens = [checks.model_tier(b) or 0 for b in builds if checks.build_label(b).startswith("7")]
    assert sevens == sorted(sevens)
    # the 6 of every generation is one build: the newest one
    assert next(b for b in builds if checks.build_label(b) == "6")["name"] == "Madone SL 6 Gen 8"
