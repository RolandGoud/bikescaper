import re

from webapp import checks, db, seed
from webapp.app import create_app


def test_model_line_and_group():
    assert checks.model_line("Madone SL 6 Gen 8") == "Madone"
    assert checks.model_line("S-Works Tarmac SL8") == "Tarmac"
    assert checks.model_line("Men's S-Works Diverge STR") == "Diverge"
    assert checks.model_line("Speed Concept SLR 7") == "Speed Concept"
    assert checks.model_line("Domane+ SLR 9") == "Domane+"
    assert checks.model_line("UnReStricted One (URS)") == "URS"
    assert checks.model_line("Bugatti Factor ONE") == "ONE"
    assert checks.line_key("Émonda") == checks.line_key("Emonda") == "emonda"
    assert checks.line_key("CruX") == checks.line_key("Crux")
    assert checks.line_key("Domane+ SLR 6") == "domane-plus-slr-6"
    # every generation and edition of a model is one model
    assert checks.model_group("Madone SL 7 Gen 7") == checks.model_group("Madone SL 7 Gen 8") == "Madone SL 7"
    assert checks.model_group("Madone SL 7 Gen 8 - The First 50 Replica") == "Madone SL 7"
    assert checks.model_group("S-Works Tarmac SL8 \u2013 Shimano Dura-Ace Di2") == checks.model_group("S-Works Tarmac SL8")
    assert checks.line_key(checks.model_group("Domane SLR 7 gen 4")) == checks.line_key(checks.model_group("Domane SLR 7 Gen 5"))


def _menu(html):
    menu = re.search(r'<select name="model".*?</select>', html, re.S).group(0)
    return re.findall(r'<option value="([^"]+)" data-label="([^"]+)" data-count="(\d+)"', menu)


def _cards(html):
    return re.findall(r'class="model-card[^"]*" href="/models/([^"]+)"', html)


def test_model_menu_lists_models_without_generations(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    menu = _menu(client.get("/models?brand=Trek&current=0&lang=en").get_data(as_text=True))
    labels = dict((k, label) for k, label, _n in menu)
    # the model is the family (SL and SLR are its levels), the frameset a model of its own
    assert labels["madone"] == "All Madone" and labels["madone-model"] == "Madone" and "madone-sl" not in labels
    assert "madone-frameset" not in labels  # the frameset is the Madone's last level
    assert "domane-plus" in labels and not any("gen" in k for k in labels)
    # one Madone holds every level, build and generation: one tile
    sl = _cards(client.get("/models?brand=Trek&model=madone-model&current=0").get_data(as_text=True))
    assert len(sl) == 1 and "madone-" in sl[0] and "frameset" not in sl[0]
    # the addresses of a model and a build from before still find it
    assert _cards(client.get("/models?brand=Trek&model=madone-sl&current=0").get_data(as_text=True)) == sl
    assert _cards(client.get("/models?brand=Trek&model=madone-sl-7&current=0").get_data(as_text=True)) == sl
    sl7 = sl
    # the whole line
    madone = _cards(client.get("/models?brand=Trek&model=madone&current=0").get_data(as_text=True))
    assert madone == sl7  # the line holds the one Madone model now (its frameset is a level of it)
    # the address the menu used to send still works
    assert _cards(client.get("/models?brand=Trek&line=madone&current=0").get_data(as_text=True)) == madone
    # the keys #348 sent for lines with "+" or a space
    assert _cards(client.get("/models?brand=Trek&line=domane%2B&current=0").get_data(as_text=True)) == \
        _cards(client.get("/models?brand=Trek&model=domane-plus&current=0").get_data(as_text=True))
    speed = _cards(client.get("/models?brand=Trek&line=speed+concept&current=0").get_data(as_text=True))
    assert speed and all("speed-concept" in s for s in speed)
    # a model of another brand is ignored once the brand changes
    assert "No models match." not in client.get("/models?brand=Canyon&model=madone-sl&current=0").get_data(as_text=True)
    # no brand picked: the menu is greyed out and a model in the address is ignored
    html = client.get("/models?model=madone-sl&current=0").get_data(as_text=True)
    assert re.search(r'<select name="model" disabled>', html)
    assert len(_cards(html)) > len(sl7)


def test_model_named_like_its_line_keeps_its_own_option(tmp_path):
    # Trek's "Boone 5" is the model "Boone" in the line "Boone": "All Boone" holds the frameset, "Boone" does not
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    labels = dict((k, label) for k, label, _n in _menu(client.get("/models?brand=Trek&current=0&lang=en").get_data(as_text=True)))
    assert labels["boone"] == "All Boone" and labels["boone-model"] == "Boone"
    line = _cards(client.get("/models?brand=Trek&model=boone&current=0").get_data(as_text=True))
    model = _cards(client.get("/models?brand=Trek&model=boone-model&current=0").get_data(as_text=True))
    # the frameset is a build of the Boone now: one tile for the line and the model
    assert len(model) == 1 and "frameset" not in model[0] and line == model
    # the address of a build from before finds the model, not the whole line
    assert _cards(client.get("/models?brand=Trek&model=boone-5&current=0").get_data(as_text=True)) == model


def test_model_tile_is_a_build_on_sale(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    trek = [m for m in db.all_models(conn) if m["brand"] == "Trek"]
    html = app.test_client().get("/models?brand=Trek&current=0").get_data(as_text=True)
    by_slug = {m["slug"]: m for m in trek}
    for slug in _cards(html):
        tile = by_slug[slug]
        siblings = [m for m in trek if checks.site_split(m)[0] == checks.site_split(tile)[0]]
        if any(checks.catalogue_status(m)[0] == "current" for m in siblings):
            assert checks.catalogue_status(tile)[0] == "current", slug


def test_all_tiers_counts_each_model_once(tmp_path):
    # a Trek model with builds of several tiers is under each of those tiers, but "All tiers" counts it once
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    html = app.test_client().get("/models?brand=Trek&current=0&lang=en").get_data(as_text=True)
    menu = re.search(r'<select name="tier".*?</select>', html, re.S).group(0)
    total = int(re.search(r'data-label="All tiers" data-count="(\d+)"', menu).group(1))
    per_tier = [int(n) for n in re.findall(r'data-tier="\d" data-label="[^"]+" data-count="(\d+)"', menu)]
    # (a model without a known tier is in none of them)
    assert max(per_tier) <= total <= len(_cards(html)) and total < sum(per_tier)


def test_the_catalogue_is_one_grid_with_the_type_on_each_tile(tmp_path):
    from webapp import db, seed
    from webapp.app import create_app
    path = str(tmp_path / "t.sqlite3")
    seed.load(db.connect(path))
    page = create_app(path).test_client().get("/models?brand=Cannondale&lang=nl").get_data(as_text=True)
    assert page.count('<div class="model-grid">') == 1  # no heading per type: the type is a filter
    # the second line names the type, after its line drawing
    assert re.search(r'class="small muted kind-line"><span class="type-icon"[^>]*gravel.svg[^>]*></span>Gravel', page)
