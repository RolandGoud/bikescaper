from webapp import checks, db, seed, stored_checks
from webapp.app import create_app


def app_with_a_check(tmp_path, title="Trek Domane SL6 2022 maat 56 Ultegra"):
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    resp = client.post("/check", data={"title": title, "asking_price": "2450", "rider_height": "180"})
    return app, client, resp.headers["Location"]


def test_a_report_is_worked_out_once(tmp_path, monkeypatch):
    app, client, url = app_with_a_check(tmp_path)
    runs = []
    real = checks.run_check
    monkeypatch.setattr(checks, "run_check", lambda *a, **k: runs.append(1) or real(*a, **k))
    first = client.get(url + "?lang=en").data
    second = client.get(url + "?lang=en").data
    assert len(runs) == 1 and b"Age check" in second and b"Run this check again" in second
    # the same report, with the catalogue model kept by slug and not copied in
    assert first.count(b"Domane") == second.count(b"Domane")
    client.get("/listings"), client.get("/checks"), client.get("/"), client.get("/admin")
    assert len(runs) == 1


def test_a_recheck_runs_it_again(tmp_path, monkeypatch):
    app, client, url = app_with_a_check(tmp_path)
    client.get(url)
    runs = []
    real = checks.run_check
    monkeypatch.setattr(checks, "run_check", lambda *a, **k: runs.append(1) or real(*a, **k))
    check_id = int(url.rsplit("/", 1)[1])
    assert client.post(f"/check/{check_id}/recheck").status_code == 302
    client.get(url), client.get(url)
    assert len(runs) == 1
    assert client.post("/admin/recheck").status_code == 302
    page = client.get("/admin?rechecked=1&lang=en").data
    assert len(runs) == 2 and b"1 reports kept" in page


def test_a_changed_input_runs_it_again_but_another_height_isnt_kept(tmp_path, monkeypatch):
    app, client, url = app_with_a_check(tmp_path)
    client.get(url)
    runs = []
    real = checks.run_check
    monkeypatch.setattr(checks, "run_check", lambda *a, **k: runs.append(1) or real(*a, **k))
    client.get(url + "?height=165"), client.get(url + "?height=165")
    assert len(runs) == 2  # a look at another height is worked out each time, and not stored over the check's own
    client.get(url)
    assert len(runs) == 2
    conn = db.connect(app.config["DB_PATH"])
    other = next(m for m in db.all_models(conn) if "Madone" in m["name"])
    check_id = int(url.rsplit("/", 1)[1])
    client.post(f"/check/{check_id}/match", data={"model_id": other["id"]})
    assert b"Madone" in client.get(url).data and len(runs) == 3


def test_a_stored_report_survives_a_catalogue_reload(tmp_path):
    app, client, url = app_with_a_check(tmp_path)
    client.get(url)
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)  # new ids for every model
    models = db.all_models(conn)
    row = conn.execute("SELECT result FROM check_results").fetchone()
    report = stored_checks.load(row["result"], models)
    assert any(report["model"]["slug"] == m["slug"] for m in models)
    assert all(c is next(m for m in models if m["slug"] == c["slug"]) for c in report["candidates"])


def test_a_recheck_keeps_the_checks_own_date(tmp_path, monkeypatch):
    app, client, url = app_with_a_check(tmp_path)
    check_id = int(url.rsplit("/", 1)[1])
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("UPDATE checks SET created_at = '2024-03-05 10:00:00' WHERE id = ?", (check_id,))
    conn.commit()
    days = []
    real = checks.run_check
    monkeypatch.setattr(checks, "run_check", lambda m, l, today=None: days.append(today) or real(m, l, today))
    client.post(f"/check/{check_id}/recheck")
    page = client.get(url + "?lang=en").data.decode()
    assert [str(d) for d in days] == ["2024-03-05"]
    assert "Checked on 2024-03-05." in page and "Run again on " in page
