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
    assert "Domane SL 6 gen 4" in page and "€2.500" in page and "Visible wear" in page
    client.post("/value", data={"brand": "Trek", "model": DOMANE})
    page = client.get("/value?lang=en").data.decode()
    assert page.count('<article class="check-row') == 2 and "#2 ·" in page


def test_a_model_link_estimates_without_saving(client):
    page = client.get(f"/value?model={DOMANE}&lang=en").data.decode()
    assert "Fair value" not in page and "Earlier estimates" not in page
    assert 'name="brand"' in page and '<option value="Trek" selected' in page


def test_an_unknown_model_saves_nothing(client):
    response = client.post("/value", data={"brand": "Trek", "model": "nope"})
    assert response.status_code == 302
    assert "Earlier estimates" not in client.get("/value?lang=en").data.decode()
