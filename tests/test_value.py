import json
from webapp import db, seed
from webapp.app import create_app

import pytest

DOMANE = "trek-domane-sl-6-gen-4"


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    return app.test_client()


def test_an_estimate_is_saved_and_listed(client):
    response = client.post("/value?lang=en", data={"brand": "Trek", "model": DOMANE, "year": "2023",
                                                   "condition": "used", "asking": "2.500"})
    assert response.status_code == 302 and "estimate=1" in response.headers["Location"]
    page = client.get(response.headers["Location"]).data.decode()
    assert "Earlier estimates" in page and "Shown above" in page
    assert "Domane SL 6 (Gen 4)" in page and "€2.500" in page and "Visible wear" in page
    assert page.count('class="value-bar"') == 1  # the fair price with its bar, as there's an asking price
    client.post("/value", data={"brand": "Trek", "model": DOMANE})
    page = client.get("/value?lang=en").data.decode()
    assert page.count('<article class="check-row') == 2 and "#2 ·" in page
    # every estimate gets the bar; only the one with an asking price has its marker
    assert page.count('class="value-bar"') == 2 and page.count('class="ask"') == 1
    assert 'class="verdict' not in page  # no estimate open, so no result card above the list
    page = client.get("/value?estimate=1&lang=en").data.decode()
    assert "Visible wear" in page and page.count('class="verdict') == 1  # the open one, not the newest


def test_a_model_link_estimates_without_saving(client):
    page = client.get(f"/value?model={DOMANE}&lang=en").data.decode()
    assert "Fair value" not in page and "Earlier estimates" not in page
    assert 'name="brand"' in page and '<option value="Trek" selected' in page


def test_an_unknown_model_saves_nothing(client):
    response = client.post("/value", data={"brand": "Trek", "model": "nope"})
    assert response.status_code == 302
    assert "Earlier estimates" not in client.get("/value?lang=en").data.decode()


def estimates(client):
    from webapp import db
    conn = db.connect(client.application.config["DB_PATH"])
    return conn, conn.execute("SELECT * FROM estimates ORDER BY id").fetchall()


def test_a_quick_follow_up_updates_the_last_estimate(client):
    first = {"brand": "Trek", "model": DOMANE, "year": "2023", "condition": ""}
    client.post("/value", data=first)
    response = client.post("/value", data=first | {"asking": "1.950"})
    assert "estimate=1" in response.headers["Location"]  # no second entry
    _conn, rows = estimates(client)
    assert len(rows) == 1 and rows[0]["asking_price"] == 1950 and rows[0]["updated_at"]
    page = client.get("/value?lang=nl").data.decode()
    assert page.count('<article class="check-row') == 1
    assert "Bijgewerkt" in page and "Vraagprijs – → €1.950" in page and "Dit was geen update" in page
    page = client.get("/value?lang=en").data.decode()
    assert "Asking price – → €1.950" in page and "This was not an update" in page
    client.post("/value", data=first | {"asking": "1.950"})  # the same again changes nothing
    assert len(estimates(client)[1]) == 1


def test_not_an_update_splits_it_off(client):
    first = {"brand": "Trek", "model": DOMANE, "year": "2023"}
    client.post("/value", data=first)
    client.post("/value", data=first | {"condition": "used", "asking": "2000"})
    response = client.post("/value/1/split")
    assert "estimate=2" in response.headers["Location"]
    _conn, rows = estimates(client)
    assert [(r["condition"], r["asking_price"], r["updated_at"], r["revisions"]) for r in rows] == \
        [(None, None, None, None), ("used", 2000, None, None)]
    page = client.get("/value?lang=en").data.decode()
    assert page.count('<article class="check-row') == 2 and "This was not an update" not in page
    # a further tweak now revises the split-off one
    client.post("/value", data=first | {"condition": "used", "asking": "1800"})
    _conn, rows = estimates(client)
    assert len(rows) == 2 and rows[1]["asking_price"] == 1800 and rows[0]["asking_price"] is None


def test_a_different_bike_or_a_later_one_gets_its_own_entry(client):
    first = {"brand": "Trek", "model": DOMANE, "year": "2023", "condition": "used", "asking": "2000"}
    client.post("/value", data=first)
    client.post("/value", data=first | {"year": "2019", "condition": "damaged", "asking": "900"})  # all three changed
    conn, rows = estimates(client)
    assert len(rows) == 2
    conn.execute("UPDATE estimates SET created_at = datetime('now', '-11 minutes')")
    conn.commit()
    client.post("/value", data=first | {"year": "2019", "condition": "damaged", "asking": "950"})  # too late
    assert len(estimates(client)[1]) == 3
    other = client.application.test_client()  # another visitor never revises yours
    other.post("/value", data=first | {"year": "2019", "condition": "damaged", "asking": "950"})
    assert len(estimates(client)[1]) == 4


def test_only_its_own_browser_can_split_an_estimate(client):
    first = {"brand": "Trek", "model": DOMANE, "year": "2023"}
    client.post("/value", data=first)
    client.post("/value", data=first | {"asking": "2000"})
    other = client.application.test_client()
    assert "This was not an update" not in other.get("/value?lang=en").data.decode()
    other.post("/value/1/split")
    assert len(estimates(client)[1]) == 1


def test_estimates_from_before_folding_are_folded_once(tmp_path):
    from webapp import db
    path = str(tmp_path / "old.sqlite3")
    conn = db.connect(path)
    seed.load(conn)
    trek = db.get_model(conn, slug=DOMANE)["id"]
    other = conn.execute("SELECT id FROM models WHERE id != ? LIMIT 1", (trek,)).fetchone()[0]
    rows = [("2026-11-15 20:55:10", trek, 2025, None, None),
            ("2026-11-15 20:56:20", trek, 2025, None, 1950),        # #2: revises #1
            ("2026-11-15 20:58:00", trek, 2025, "used", 1900),      # #3: revises it again
            ("2026-11-15 21:30:00", trek, 2025, "used", 1900),      # #4: too late
            ("2026-11-15 21:31:00", other, 2025, "used", 1900),     # #5: another model
            ("2026-11-15 21:32:00", other, 2019, "damaged", 500)]   # #6: all three changed
    conn.executemany("INSERT INTO estimates (created_at, model_id, year, condition, asking_price) VALUES (?,?,?,?,?)", rows)
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn = db.connect(path)
    left = conn.execute("SELECT * FROM estimates ORDER BY id").fetchall()
    assert [r["id"] for r in left] == [1, 4, 5, 6]
    first = left[0]
    assert (first["condition"], first["asking_price"], first["updated_at"]) == ("used", 1900, "2026-11-15 20:58:00")
    assert [(r["condition"], r["asking_price"]) for r in json.loads(first["revisions"])] == [(None, None), (None, 1950)]
    conn.execute("INSERT INTO estimates (model_id, year) VALUES (?, 2025)", (other,))
    conn.commit()
    assert len(db.connect(path).execute("SELECT id FROM estimates").fetchall()) == 5  # only once
    app = create_app(path)
    client = app.test_client()
    with client.session_transaction() as s:
        s["admin"] = True
    app.config["ADMIN_PASSWORD"] = "x"
    assert "This was not an update" in client.get("/value?lang=en").data.decode()
    client.post("/value/1/split")  # the last fold comes back as its own estimate
    conn = db.connect(path)
    assert conn.execute("SELECT asking_price FROM estimates WHERE id = 1").fetchone()[0] == 1950
    assert conn.execute("SELECT created_at FROM estimates ORDER BY id DESC").fetchone()[0] == "2026-11-15 20:58:00"
