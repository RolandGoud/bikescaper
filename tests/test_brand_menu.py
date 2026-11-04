import re

from webapp import db, seed
from webapp.app import create_app


def test_brand_menu_most_bikes_first_ties_alphabetical(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    html = app.test_client().get("/models").get_data(as_text=True)
    menu = [(name, int(n)) for name, n in
            re.findall(r'<option value="([^"]+)" data-label="[^"]+" data-count="(\d+)"', html)]
    assert len(menu) > 1
    assert menu == sorted(menu, key=lambda b: (-b[1], b[0].lower()))
