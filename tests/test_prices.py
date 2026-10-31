from datetime import date, timedelta

import pytest

from webapp import db, prices, seed
from webapp.app import create_app

DOMANE = "trek-domane-sl-6-gen-4"


@pytest.fixture
def app(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    return app


def add_checks(app, rows):
    conn = db.connect(app.config["DB_PATH"])
    model_id = db.get_model(conn, slug=DOMANE)["id"]
    for days_ago, price in rows:
        when = (date.today() - timedelta(days=days_ago)).isoformat() + " 12:00:00"
        conn.execute("INSERT INTO checks (created_at, title, asking_price, model_id) VALUES (?,?,?,?)",
                     (when, "Racefiets", price, model_id))
    conn.commit()
    return conn, model_id


def test_median_counts_only_the_period_and_real_prices(app):
    conn, model_id = add_checks(app, [(1, 2000), (5, 2200), (10, 2400), (20, 2600), (25, 9000),
                                      (3, 1), (200, 1500)])
    ads = prices.known_ads(conn, db.all_models(conn))
    month = prices.asking_price(ads, model_id, 30)
    assert month["count"] == 5 and month["enough"]
    assert month["median"] == 2400 and month["low"] == 2000 and month["high"] == 9000
    year = prices.asking_price(ads, model_id, 365)
    assert year["count"] == 6 and year["median"] == 2300


def test_matches_ads_by_their_title_when_confident(app):
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane SL 6 Gen 4 maat 56", 2500))
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Mooie racefiets", 900))
    conn.commit()
    ads = prices.known_ads(conn, db.all_models(conn))
    assert [a["model_id"] for a in ads] == [db.get_model(conn, slug=DOMANE)["id"]]


def test_too_few_ads_shows_no_typical_price(app):
    conn, model_id = add_checks(app, [(1, 2000), (2, 2100)])
    result = prices.asking_price(prices.known_ads(conn, db.all_models(conn)), model_id, 90)
    assert result["count"] == 2 and not result["enough"]


def test_model_page_and_report_show_the_asking_price(app):
    add_checks(app, [(d, 2000 + 100 * d) for d in range(1, 7)])
    client = app.test_client()
    page = client.get(f"/models/{DOMANE}?lang=en&period=30").data.decode()
    assert "Second-hand asking price" in page and "Based on 6 ads from the last 30 days." in page
    assert "€2.350" in page  # median of 2100..2600
    page = client.get(f"/models/{DOMANE}?lang=nl").data.decode()
    assert "Vraagprijs tweedehands" in page and "90 dagen" in page
    # The report leaves its own ad out: five others are left, still enough.
    page = client.get("/check/1?lang=en&period=365").data.decode()
    assert "Based on 5 other ads from the last 365 days." in page and "less than the median" in page
    assert 'name="period" value="365"' in page  # the height form keeps the period


def test_empty_model_says_so(app):
    page = app.test_client().get(f"/models/{DOMANE}?lang=en").data.decode()
    assert "No ads for this model in the last 90 days yet." in page


def test_model_page_lists_matched_ads_also_removed_ones(app):
    conn = db.connect(app.config["DB_PATH"])
    url = "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2100000001-trek-domane"
    conn.execute("INSERT INTO checks (listing_url, title, asking_price) VALUES (?,?,?)",
                 (url, "Trek Domane SL 6 Gen 4 maat 56", 2500))
    conn.execute("INSERT INTO checks (listing_url, title, asking_price, source) VALUES (?,?,?,?)",
                 (url, "Trek Domane SL 6 Gen 4 maat 56", 2400, "daily"))  # the same ad again
    conn.execute("INSERT INTO checks (title, asking_price, removed_at) VALUES (?,?,?)",
                 ("Trek Domane SL 6 Gen 4 rood", 50, "2026-10-20 08:00:00"))
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Mooie racefiets", 900))
    conn.commit()
    client = app.test_client()
    page = client.get(f"/models/{DOMANE}?lang=en").data.decode()
    assert 'Matched ads <span class="muted count">2</span>' in page
    assert "Domane SL 6 Gen 4 rood" in page and "Trek Domane SL 6 Gen 4 rood" not in page and "Removed" in page
    assert "not in the asking price" in page  # the €50 one
    assert "Mooie racefiets" not in page
    models_page = client.get("/models?lang=en&q=domane sl 6 gen 4").data.decode()
    assert "Matched to 2 ads" in models_page


def test_report_alone_says_no_other_ads(app):
    add_checks(app, [(1, 2000)])
    client = app.test_client()
    page = client.get("/check/1?lang=nl").data.decode()
    assert "Nog geen andere advertenties voor dit model gevonden (in de laatste 90 dagen)." in page
    page = client.get(f"/models/{DOMANE}?lang=en").data.decode()
    assert "1 ad in the last 90 days" in page  # the model page does count it
    assert "Only" not in page and "only 1" not in page
    assert 'title="Not enough ads yet for a reliable median price."' in page
    page = client.get(f"/models/{DOMANE}?lang=nl").data.decode()
    assert "1 advertentie in de laatste 90 dagen" in page
    assert "Pas 1" not in page and "maar 1" not in page
    assert 'title="Nog niet genoeg advertenties voor een betrouwbare mediaanprijs."' in page
