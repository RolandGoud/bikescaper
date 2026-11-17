from datetime import date, timedelta

import pytest

from webapp import close_ads, db, seed
from webapp.app import create_app, matched_ads

OWN = "cannondale-synapse-carbon-2"


@pytest.fixture
def app(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    return app


def add_ads(app, ads):
    """ads: [(slug, price, days ago, gone)]"""
    conn = db.connect(app.config["DB_PATH"])
    for slug, price, days_ago, gone in ads:
        model = db.get_model(conn, slug=slug)
        when = (date.today() - timedelta(days=days_ago)).isoformat() + " 12:00:00"
        conn.execute("INSERT INTO checks (created_at, title, asking_price, model_id, removed_at, gone_reason)"
                     " VALUES (?,?,?,?,?,?)", (when, f"{model['brand']} {model['name']}", price, model["id"],
                                               when if gone else None, "expired" if gone else None))
    conn.commit()
    return conn


def ranked(conn):
    models = db.all_models(conn)
    rows = conn.execute("SELECT * FROM checks").fetchall()
    own = db.get_model(conn, slug=OWN)
    return [(other["slug"], step) for _r, _n, other, step in close_ads.close_ads(own, models, matched_ads(rows, models))]


def test_closest_first_and_live_ads_before_gone_ones(app):
    conn = add_ads(app, [("giant-defy-advanced-pro-1", 3500, 3, False),
                         ("cannondale-supersix-evo-4", 3300, 2, False),
                         ("cannondale-synapse-carbon-2-rle", 3400, 30, True),
                         ("cannondale-synapse-carbon-1", 4600, 10, False),
                         ("cannondale-synapse-carbon-3-smartsense", 3100, 5, False)])
    assert ranked(conn) == [("cannondale-synapse-carbon-1", "build"),  # new price nearest the Carbon 2's
                            ("cannondale-synapse-carbon-3-smartsense", "build"),
                            ("cannondale-synapse-carbon-2-rle", "build"),  # gone from the site: last of its step
                            ("cannondale-supersix-evo-4", "brand"),
                            ("giant-defy-advanced-pro-1", "similar")]


def test_leaves_out_bikes_too_far_off(app):
    conn = add_ads(app, [("cannondale-synapse-lab71-smartsense", 9000, 3, False),  # same line: still in
                         ("cannondale-supersix-evo-lab71", 8000, 3, False),  # same brand, twice the price
                         ("giant-defy-advanced-4", 900, 3, False)])  # other brand, far cheaper
    assert ranked(conn) == [("cannondale-synapse-lab71-smartsense", "build")]


def test_at_most_eight(app):
    conn = add_ads(app, [("cannondale-synapse-carbon-1", 4000 + d, d, False) for d in range(12)])
    assert len(ranked(conn)) == close_ads.LIMIT


def test_model_page_shows_alternates_only_without_own_ads(app):
    conn = add_ads(app, [("cannondale-synapse-carbon-1", 4600, 3, False)])
    page = app.test_client().get(f"/models/{OWN}?lang=en").data.decode()
    assert "Alternatives" in page and "Synapse Carbon 1" in page and "No ads matched to this model yet." not in page
    assert "<dt>Ads</dt><dd>0</dd>" in page  # the alternates don't count as this model's ads
    add_ads(app, [(OWN, 3000, 2, False)])
    page = app.test_client().get(f"/models/{OWN}?lang=en").data.decode()
    assert "Alternatives" not in page
