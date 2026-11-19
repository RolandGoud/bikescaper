import re

from webapp import db, seed
from webapp.app import create_app


def brand_menu(html):
    return [(name, int(n), int(ads)) for name, n, ads in
            re.findall(r'<option value="([^"]+)" data-label="[^"]+" data-count="(\d+)" data-ads="(\d+)"',
                       re.search(r'<select name="brand".*?</select>', html, re.S).group(0))]


def test_brand_menu_most_ads_checked_first_then_most_bikes(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    html = app.test_client().get("/models").get_data(as_text=True)
    menu = brand_menu(html)
    assert len(menu) > 1
    assert menu == sorted(menu, key=lambda b: (-b[2], -b[1], b[0].lower()))


def test_brand_with_more_ads_checked_goes_above_brand_with_more_models(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    menu = brand_menu(app.test_client().get("/models").get_data(as_text=True))
    last = menu[-1][0]  # the brand now at the bottom gets checked ads, the most of all
    model_id = conn.execute("SELECT id FROM models WHERE brand = ? LIMIT 1", (last,)).fetchone()[0]
    for n in range(max(b[2] for b in menu) + 1):
        conn.execute("INSERT INTO checks (listing_url, title, asking_price, model_id) VALUES (?, ?, ?, ?)",
                     (f"https://www.marktplaats.nl/v/fietsen/m{2000000000 + n}-test", "Racefiets", 1000, model_id))
    conn.commit()
    menu = brand_menu(app.test_client().get("/models").get_data(as_text=True))
    assert menu[0][0] == last


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
