"""An admin corrects a check by hand (the report's edit mode): the model, year, groupset, size and main photo stay
set when the check runs again, and only a logged-in admin can set them."""
import json

from webapp import checks, db, seed
from webapp.app import create_app

TITLE = "Trek Domane SL6 2022 maat 56 Ultegra"


def setup(tmp_path, monkeypatch, password="geheim"):
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    url = client.post("/check", data={"title": TITLE, "asking_price": "2450", "rider_height": "180"}).headers["Location"]
    return app, client, url, int(url.rsplit("/", 1)[1])


def login(client, password="geheim"):
    return client.post("/admin/login", data={"password": password, "next": "/admin"})


def test_only_a_logged_in_admin_can_correct_a_check(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    assert client.post(f"/check/{check_id}/override", data={"field": "year", "value": "2020"}).status_code == 403
    assert b"edit-year" not in client.get(url + "?edit=1").data
    assert login(client, "wrong").status_code == 400
    assert login(client).status_code == 302
    page = client.get(url + "?edit=1&lang=en").data
    assert b"Edit mode" in page and b"edit-year" in page and b"edit-model" in page and b"edit-groupset" in page
    client.post("/admin/logout")
    assert client.post(f"/check/{check_id}/override", data={"field": "year", "value": "2020"}).status_code == 403


def test_no_password_set_means_no_login(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch, password="")
    assert login(client, "").status_code == 400
    assert b"ADMIN_PASSWORD" in client.get("/admin/login?lang=en").data


def test_values_set_by_hand_win_and_survive_a_recheck(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    madone = next(m for m in db.all_models(conn) if "Madone" in m["name"])
    for data in ({"field": "year", "value": "2020"}, {"field": "size", "value": "54"},
                 {"field": "groupset", "value": "105:3", "electronic": "1"}, {"field": "model", "value": madone["slug"]}):
        assert client.post(f"/check/{check_id}/override", data=data).status_code == 302
    # A visitor's pick of another model doesn't undo the admin's.
    other = next(m for m in db.all_models(conn) if "Domane" in m["name"])
    client.post(f"/check/{check_id}/match", data={"model_id": other["id"]})
    client.post(f"/check/{check_id}/recheck"), client.post("/admin/recheck")
    page = client.get(url + "?lang=en").data.decode()
    assert "Madone" in page
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    overrides = json.loads(row["overrides"])
    assert overrides == {"year": 2020, "size": "54", "groupset": {"key": "105", "tier": 3, "electronic": True},
                         "model": madone["slug"]}
    report = checks.run_check(db.all_models(conn), dict(row, overrides=overrides))
    assert report["model"]["slug"] == madone["slug"]
    assert report["claims"]["year"] == 2020 and report["year"]["year"] == 2020 and report["year"]["how"] == "ad"
    assert report["claims"]["size"] == "54" and report["size"]["rows"]
    assert report["claims"]["groupset"]["key"] == "105" and report["claims"]["groupset"]["electronic"]
    assert report["locked"] == ["groupset", "model", "size", "year"]
    # Back to automatic: one field, then all.
    client.post(f"/check/{check_id}/override", data={"field": "year", "clear": "1"})
    assert "year" not in json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0])
    client.post(f"/check/{check_id}/override", data={"field": "all"})
    assert conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0] is None
    assert checks.run_check(db.all_models(conn), dict(row, overrides={}))["claims"]["year"] == 2022


def test_the_main_photo_goes_first(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    conn = db.connect(app.config["DB_PATH"])
    photos = [f"https://example.com/{i}.jpg" for i in range(4)]
    conn.execute("UPDATE checks SET photos = ? WHERE id = ?", (json.dumps(photos), check_id))
    conn.commit()
    login(client)
    assert client.post(f"/check/{check_id}/override", data={"field": "main_photo", "value": "9"}).status_code == 400
    assert client.post(f"/check/{check_id}/override", data={"field": "main_photo", "value": "2"}).status_code == 302
    page = client.get(url).data.decode()
    big = page.index('class="ag-main"')
    assert page.index("example.com/2.jpg", big) < page.index("example.com/0.jpg", big)
    # The stored order is the ad's own: only what's shown changes.
    assert json.loads(conn.execute("SELECT photos FROM checks WHERE id = ?", (check_id,)).fetchone()[0]) == photos


def test_bad_values_are_refused(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    for data in ({"field": "year", "value": "1890"}, {"field": "model", "value": "no-such-bike"},
                 {"field": "groupset", "value": "nope:9"}, {"field": "colour", "value": "red"}):
        assert client.post(f"/check/{check_id}/override", data=data).status_code == 400


def test_the_admin_page_needs_a_login(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    response = client.get("/admin")
    assert response.status_code == 302 and "/admin/login" in response.headers["Location"]
    assert client.post("/admin/recheck").status_code == 403
    login(client)
    assert client.get("/admin").status_code == 200


def test_the_header_has_a_login_icon_and_once_logged_in_an_account_menu(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    page = client.get("/?lang=en").get_data(as_text=True)
    assert 'class="account-login"' in page and "/admin/login" in page and 'id="account-menu"' not in page
    login(client)
    page = client.get("/?lang=en").get_data(as_text=True)
    assert 'id="account-menu"' in page and "Admin</button>" in page
    assert 'href="/admin"' in page and "Log out" in page and 'class="account-login"' not in page


def test_logging_in_from_the_header_goes_to_the_admin_page(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    assert 'href="/admin/login"' in client.get(url).get_data(as_text=True)
    response = client.post("/admin/login", data={"password": "geheim"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/admin")
    # Sent to the login from a page that needs it: back to that page.
    client.post("/admin/logout")
    response = client.post("/admin/login", data={"password": "geheim", "next": "/admin?rechecked=1"})
    assert response.headers["Location"].endswith("/admin?rechecked=1")


def test_a_colour_set_by_hand_wins_and_dates_the_bike(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    row = dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone(), title="Trek Domane AL 2 Gen 4", description="")
    models = db.all_models(conn)
    model = checks.run_check(models, dict(row, overrides={}))["model"]
    sheets = checks.year_sheets(model)
    # A colourway only some years came in.
    colour, years = next((c, {y for y, s in sheets.items() if c in s["colours"]}) for c in checks.colour_choices(model)
                         if 0 < len({y for y, s in sheets.items() if c in s["colours"]}) < len(sheets))
    report = checks.run_check(models, dict(row, overrides={"colour": colour}))
    assert report["colour_set"] == colour and "colour" in report["locked"]
    assert report["year"]["year"] in years
    # The year set by hand still wins over the colour's years.
    other = next(y for y in sheets if y not in years)
    report = checks.run_check(models, dict(row, overrides={"colour": colour, "year": other}))
    assert report["year"]["year"] == other and report["spec_year"] == other and report["colour_set"] == colour
    # A colour another model has counts as not set.
    assert checks.run_check(models, dict(row, overrides={"colour": "No Such Colour"}))["colour_set"] is None


def test_the_colour_editor_takes_only_the_models_colourways(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("UPDATE checks SET title = 'Trek Domane AL 2 Gen 4' WHERE id = ?", (check_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    model = checks.run_check(db.all_models(conn), dict(row, overrides={}))["model"]
    colour = checks.colour_choices(model)[-1]
    assert b"edit-colour" in client.get(url + "?edit=1&lang=en").data
    assert client.post(f"/check/{check_id}/override", data={"field": "colour", "value": colour}).status_code == 302
    assert json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0]) == {"colour": colour}
    page = client.get(url + "?lang=en").get_data(as_text=True)
    assert colour in page
