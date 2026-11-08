import re

from webapp import db, seed
from webapp.app import create_app


def test_brand_menu_most_bikes_first_ties_alphabetical(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    html = app.test_client().get("/models").get_data(as_text=True)
    menu = [(name, int(n)) for name, n in
            re.findall(r'<option value="([^"]+)" data-label="[^"]+" data-count="(\d+)"',
                       re.search(r'<select name="brand".*?</select>', html, re.S).group(0))]
    assert len(menu) > 1
    assert menu == sorted(menu, key=lambda b: (-b[1], b[0].lower()))


def test_type_menu_has_icons_and_no_counts(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models?lang=nl").get_data(as_text=True)
    menu = page.split('<select name="type"')[1].split("</select>")[0]
    options = menu.split("<option")[1:]
    assert len(options) > 2
    assert all('data-icon="/static/types/' in o and "data-count" not in o for o in options)
    assert re.search(r"\(\d+\)</option>", menu) is None
    assert 'types/all.svg' in options[0] and 'types/road.svg' in menu
