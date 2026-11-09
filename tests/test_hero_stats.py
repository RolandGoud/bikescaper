"""The band of headline numbers at the bottom of the home page's hero."""
from webapp import db, seed
from webapp.app import HERO_MIN_PRICED, create_app, too_high_share


def priced(asking, high=1000):
    return {"value": {"asking": asking, "high": high, "low": high - 200}}


def test_too_high_share_counts_ads_over_the_fair_range():
    results = [priced(1200)] * 3 + [priced(900)] * 7 + [{"value": {"status": "unknown"}}, {"value": None}]
    assert too_high_share(results) == 30  # the two without a price comparison don't count


def test_too_high_share_waits_for_enough_priced_ads():
    assert too_high_share([priced(1200)] * (HERO_MIN_PRICED - 1)) is None


def test_home_shows_the_catalogue_numbers_in_the_hero(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    models, brands = conn.execute("SELECT count(*), count(DISTINCT brand) FROM models").fetchone()
    page = app.test_client().get("/?lang=nl").data.decode()
    band = page[page.index('class="hero-stats"'):page.index("</dl>")]
    assert "advertenties gecheckt</dt><dd>0<" in band
    assert f"modellen in onze catalogus</dt><dd>{models:,}<".replace(",", ".") in band
    assert f"merken</dt><dd>{brands}<" in band
    assert "eerlijke prijs" not in band  # no checked ads yet, so no share to show
