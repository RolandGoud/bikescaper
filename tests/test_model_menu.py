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
    assert labels["madone"] == "All Madone" and labels["madone-sl-7"] == "Madone SL 7"
    assert "domane-plus" in labels and not any("gen" in k for k in labels)
    # one Madone SL 7 holds every generation
    sl7 = _cards(client.get("/models?brand=Trek&model=madone-sl-7&current=0").get_data(as_text=True))
    assert any("gen-7" in s for s in sl7) and any("gen-8" in s for s in sl7)
    assert all("madone-sl-7" in s for s in sl7)
    # the whole line
    madone = _cards(client.get("/models?brand=Trek&model=madone&current=0").get_data(as_text=True))
    assert len(madone) > len(sl7) and all("madone" in s for s in madone)
    # the address the menu used to send still works
    assert _cards(client.get("/models?brand=Trek&line=madone&current=0").get_data(as_text=True)) == madone
    # the keys #348 sent for lines with "+" or a space
    assert _cards(client.get("/models?brand=Trek&line=domane%2B&current=0").get_data(as_text=True)) == \
        _cards(client.get("/models?brand=Trek&model=domane-plus&current=0").get_data(as_text=True))
    speed = _cards(client.get("/models?brand=Trek&line=speed+concept&current=0").get_data(as_text=True))
    assert speed and all("speed-concept" in s for s in speed)
    # a model of another brand is ignored once the brand changes
    assert "No models match." not in client.get("/models?brand=Canyon&model=madone-sl-7&current=0").get_data(as_text=True)
    # no brand picked: the menu is greyed out and a model in the address is ignored
    html = client.get("/models?model=madone-sl-7&current=0").get_data(as_text=True)
    assert re.search(r'<select name="model" disabled>', html)
    assert len(_cards(html)) > len(sl7)
