"""Bikes from before 2018: we have no data for them, so the catalogue leaves them out and we keep no checks of them."""
import os
import shutil

import pytest

from webapp import ad_photos, checks, daily_checks, db, seed
from webapp.app import create_app
from webapp.reference import FIRST_YEAR

from test_daily_checks import AD, ads, fetch


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("seeded") / "seeded.sqlite3"
    seed.load(db.connect(str(path)))
    return path


@pytest.fixture
def app(seeded, tmp_path):
    shutil.copy(seeded, tmp_path / "app.sqlite3")
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    return app


def check(client, title, description=""):
    resp = client.post("/check", data={"title": title, "description": description, "asking_price": "1450",
                                        "location": "Utrecht"})
    return resp.headers["Location"]


def run(models, title, description=""):
    return checks.run_check(models, {"title": title, "description": description, "asking_price": 1450})


def test_the_catalogue_has_nothing_from_before_2018(seeded):
    models = db.all_models(db.connect(str(seeded)))
    assert not [m["slug"] for m in models if (m["model_year"] or FIRST_YEAR) < FIRST_YEAR]
    assert any(m["source_file"].startswith("data/years/archived/") for m in models)  # later discontinued lines stay
    for m in models:
        found = m["year_specs"]
        assert all(int(y) >= FIRST_YEAR for y in found.get("years", {}))
        assert all(int(y) >= FIRST_YEAR for y in found.get("checked", []))
        assert all(int(y) >= FIRST_YEAR for y in found.get("list_prices", {}))


def test_the_year_the_report_goes_by_decides(seeded):
    models = db.all_models(db.connect(str(seeded)))
    assert checks.pre_2018_year(run(models, "Trek Domane SL 6", "bouwjaar 2016, maat 56")) == 2016
    assert checks.pre_2018_year(run(models, "Trek Domane SL 6 2022", "maat 56")) is None
    # A stated model year wins over a later purchase year (#273).
    assert checks.pre_2018_year(run(models, "Trek Domane SL 6", "gekocht in 2018, een 2017 model")) == 2017
    # Bought new in 2016: at most a 2017 model, though the report moves it up to the generation's first year (#291's miss,
    # check 74). Bought in 2017 it may be a 2018 model.
    assert checks.pre_2018_year(run(models, "Giant Contend racefiets, maat L", "Te koop: Giant Contend racefiets, gekocht in 2016.")) == 2016
    assert checks.pre_2018_year(run(models, "Giant Contend racefiets, maat L", "Te koop: Giant Contend racefiets, gekocht in 2017.")) is None
    # No model matched: the ad's own year.
    assert checks.pre_2018_year(run(models, "Batavus racefiets 2012")) == 2012
    assert checks.pre_2018_year(run(models, "Batavus racefiets")) is None


def test_a_check_of_an_old_bike_says_so_and_isnt_saved(app):
    client = app.test_client()
    resp = client.post("/check?lang=en", data={"title": "Trek Domane SL 6", "description": "Bouwjaar 2016, maat 56"})
    assert resp.status_code == 200 and b"We have no data for bikes from before 2018" in resp.data and b"2016" in resp.data
    assert b"Age check" not in resp.data
    resp = client.post("/check?lang=nl", data={"title": "Giant Contend racefiets", "description": "gekocht in 2016"})
    assert b"in 2016 gekocht, dus het is een model van v" in resp.data
    assert db.connect(app.config["DB_PATH"]).execute("SELECT count(*) FROM checks").fetchone()[0] == 0
    new = check(client, "Trek Domane SL 6 2022", "maat 56, Ultegra")
    assert b"Age check" in client.get(new + "?lang=en").data


def old_check(app, title="Specialized Tarmac SL4", description="modeljaar 2014, maat 54"):
    """A check saved before old bikes were turned away, with a stored report and photos."""
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (title, description, asking_price, location) VALUES (?, ?, ?, 'Utrecht')",
                 (title, description, 900))
    old_id = conn.execute("SELECT max(id) FROM checks").fetchone()[0]
    conn.execute("INSERT INTO check_results (check_id, inputs, result, computed_at) VALUES (?, 'x', x'00', 'now')",
                 (old_id,))
    conn.commit()
    folder = ad_photos.folder(app.config["DB_PATH"])
    os.makedirs(os.path.join(folder, str(old_id)))
    return conn, old_id, os.path.join(folder, str(old_id))


def test_checks_made_before_this_are_deleted(app):
    client = app.test_client()
    new = check(client, "Trek Domane SL 6 2022", "maat 56, Ultegra")
    new_id = new.rsplit("/", 1)[1]
    conn, old_id, photos = old_check(app)
    html = client.get("/listings").data.decode()
    assert f"/check/{old_id}\"" not in html and f"/check/{new_id}" in html
    assert not conn.execute("SELECT 1 FROM checks WHERE id = ?", (old_id,)).fetchone()
    assert not conn.execute("SELECT 1 FROM check_results WHERE check_id = ?", (old_id,)).fetchone()
    assert not os.path.exists(photos)
    assert conn.execute("SELECT 1 FROM checks WHERE id = ?", (new_id,)).fetchone()
    assert client.get(f"/check/{old_id}").status_code == 404


def test_an_old_checks_own_page_says_why_once(app):
    client = app.test_client()
    conn, old_id, _photos = old_check(app)
    page = client.get(f"/check/{old_id}?lang=en")
    assert page.status_code == 200 and b"We have no data for bikes from before 2018" in page.data
    assert not conn.execute("SELECT 1 FROM checks WHERE id = ?", (old_id,)).fetchone()
    assert client.get(f"/check/{old_id}").status_code == 404
    assert client.get(f"/check/{old_id}/report.pdf").status_code == 404


def test_removing_old_models_keeps_checks_working(app):
    conn = db.connect(app.config["DB_PATH"])
    client = app.test_client()
    url = check(client, "Trek Domane SL 6 2022", "maat 56")
    check_id = int(url.rsplit("/", 1)[1])
    client.get(url)
    # A catalogue loaded before old bikes were left out, with the check matched by hand to one of them.
    old = dict(next(m for m in db.all_models(conn) if m["brand"] == "BMC" and m["source_file"].endswith("BMC.json")
                    and "archived" in m["source_file"]))
    conn.execute("INSERT INTO models (brand, name, slug, model_year, source_file, specs, colors) VALUES (?,?,?,?,?,?,?)",
                 ("BMC", "Granfondo GF01 105", "bmc-granfondo-gf01-105-test", 2014, old["source_file"], "{}", "[]"))
    old_id = conn.execute("SELECT id FROM models WHERE slug = 'bmc-granfondo-gf01-105-test'").fetchone()[0]
    conn.execute("UPDATE checks SET model_id = ? WHERE id = ?", (old_id, check_id))
    conn.execute("INSERT INTO estimates (model_id, year) VALUES (?, 2014)", (old_id,))
    conn.commit()
    assert seed.remove_old_models(conn) == 1
    assert conn.execute("SELECT model_id FROM checks WHERE id = ?", (check_id,)).fetchone()[0] is None
    assert not conn.execute("SELECT 1 FROM estimates WHERE model_id = ?", (old_id,)).fetchone()
    page = client.get(url + "?lang=en")
    assert page.status_code == 200 and b"Age check" in page.data and b"Domane" in page.data
    assert f"/check/{check_id}" in client.get("/listings").data.decode()
    assert client.get("/value").status_code == 200
    assert seed.remove_old_models(conn) == 0


def test_the_daily_pass_takes_another_ad_for_an_old_bike(seeded, tmp_path):
    shutil.copy(seeded, tmp_path / "daily.sqlite3")
    conn = db.connect(str(tmp_path / "daily.sqlite3"))
    other = "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2400000007-trek-domane"

    def two(family, site):
        listed = ads(family, site)
        return [{"url": other, "title": "Trek Domane AL 2", "price": 400, "photos": 3}] + listed if listed else []

    def old_first(url):
        return dict(fetch(url), description="Maat 56, bouwjaar 2015") if url == other else fetch(url)

    saved = daily_checks.run(conn, search=two, fetch=old_first, pause=0)
    assert [conn.execute("SELECT listing_url FROM checks WHERE id = ?", (i,)).fetchone()[0] for i in saved] == [AD]
