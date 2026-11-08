import re

from webapp import checks, db, seed
from webapp.app import create_app


def test_model_line():
    assert checks.model_line("Madone SL 6 Gen 8") == "Madone"
    assert checks.model_line("S-Works Tarmac SL8") == "Tarmac"
    assert checks.model_line("Men's S-Works Diverge STR") == "Diverge"
    assert checks.model_line("Speed Concept SLR 7") == "Speed Concept"
    assert checks.model_line("Domane+ SLR 9") == "Domane+"
    assert checks.model_line("UnReStricted One (URS)") == "URS"
    assert checks.model_line("Bugatti Factor ONE") == "ONE"
    assert checks.line_key("Émonda") == checks.line_key("Emonda") == "emonda"
    assert checks.line_key("CruX") == checks.line_key("Crux")


def _menu(html):
    menu = re.search(r'<select name="line".*?</select>', html, re.S).group(0)
    return re.findall(r'<option value="([^"]+)" data-label="([^"]+)" data-count="(\d+)"', menu)


def test_model_menu_filters_the_picked_brand(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    menu = _menu(client.get("/models?brand=Trek&current=0").get_data(as_text=True))
    keys = [k for k, _label, _n in menu]
    assert "madone" in keys and "domane" in keys and "domane+" in keys  # Domane+ is its own line
    assert dict((k, label) for k, label, _n in menu)["madone"] == "Madone"  # one brand: no brand in the label
    counts = [int(n) for _k, _l, n in menu]
    assert counts == sorted(counts, reverse=True)
    html = client.get("/models?brand=Trek&line=madone&current=0").get_data(as_text=True)
    names = re.findall(r'class="model-card[^"]*" href="/models/([^"]+)"', html)
    assert names and all("madone" in n for n in names)
    # a line of another brand is ignored once the brand changes
    html = client.get("/models?brand=Canyon&line=madone&current=0").get_data(as_text=True)
    assert "No models match." not in html
    # every brand on: each line says its brand
    labels = [label for _k, label, _n in _menu(client.get("/models").get_data(as_text=True))]
    assert any(label.startswith("Trek ") for label in labels)
