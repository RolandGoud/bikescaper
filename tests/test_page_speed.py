"""Pages don't work out the same match again on every view (the NAS got slower with every ad and model)."""
import pytest

from webapp import checks, db, seed
from webapp.app import create_app


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    conn = db.connect(str(tmp_path_factory.mktemp("speed") / "app.sqlite3"))
    seed.load(conn)
    return db.all_models(conn)


def test_best_guess_is_match_models_top_and_confidence(models):
    title, text = "Trek Domane SL 6 Gen 4 maat 56", "Shimano 105 Di2"
    ranked = checks.match_models(models, title, text)
    assert checks.best_guess(models, title, text) == (ranked[0][1], checks.confidence(ranked))
    assert checks.best_guess(models, "Mooie racefiets") == (None, None)


def test_best_guess_is_worked_out_once_per_ad_and_catalogue(models, monkeypatch):
    calls = []
    real = checks.match_models
    monkeypatch.setattr(checks, "match_models", lambda *a, **k: calls.append(a[1]) or real(*a, **k))
    title = "Giant TCR Advanced 2 2021 kept once"
    first = checks.best_guess(models, title)
    assert checks.best_guess(models, title) == first and calls == [title]
    other = list(models)  # another catalogue (a reload) works it out again
    assert checks.best_guess(other, title) == first and calls == [title, title]


def test_the_app_reads_the_catalogue_again_only_when_it_changes(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    reads = []
    real = db.all_models
    monkeypatch.setattr(db, "all_models", lambda c: reads.append(1) or real(c))
    client = app.test_client()
    assert client.get("/models").status_code == 200 and client.get("/models").status_code == 200
    assert len(reads) == 1
    conn.execute("UPDATE models SET price_eur = coalesce(price_eur, 0) + 1 WHERE id = (SELECT min(id) FROM models)")
    conn.commit()
    assert client.get("/models").status_code == 200 and len(reads) == 2
