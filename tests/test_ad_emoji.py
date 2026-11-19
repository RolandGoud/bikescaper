"""An ad thick with emoji is shown without them; an ad with a few keeps them; the stored ad is never changed."""
import shutil

import pytest

from webapp import ad_emoji, db, seed
from webapp.app import create_app

HEAVY_TITLE = "🚴‍♂️🔥 Trek Domane SL 6 2022 maat 56 🔥"
HEAVY_TEXT = ("✅ Shimano 105 Di2 💪\n"
              "✅ Nieuwe banden 🛞\n"
              "🇳🇱 Ophalen in Utrecht 📍\n"
              "🔥🔥🔥\n"
              "Prijs is vast ❗️ ‼️")


def test_counts_emoji_as_a_reader_does():
    assert ad_emoji.count("🚴‍♂️") == 1  # one rider, joined from several code points
    assert ad_emoji.count("👍🏽") == 1  # with a skin tone
    assert ad_emoji.count("🇳🇱") == 1  # a flag
    assert ad_emoji.count("1️⃣ ❤️ ✅") == 3
    assert ad_emoji.count("Prijs € 1.450,- · maat 56 cm · 2x11 · 50°") == 0
    assert ad_emoji.count("zie link ↗ of ■") == 0  # bare symbols are text


def test_a_few_emoji_stay():
    ad = {"title": "Trek Domane SL 6 👍", "description": "Goed onderhouden ✅\nOphalen in Utrecht 🙂"}
    assert not ad_emoji.too_many(ad)
    assert ad_emoji.tame(ad["description"], ad) == ad["description"]
    assert ad_emoji.tame(ad["title"], ad) == ad["title"]


def test_a_lot_of_emoji_all_go_and_the_text_reads_plainly():
    ad = {"title": HEAVY_TITLE, "description": HEAVY_TEXT}
    assert ad_emoji.too_many(ad)
    assert ad_emoji.tame(ad["title"], ad) == "Trek Domane SL 6 2022 maat 56"
    assert ad_emoji.tame(ad["description"], ad) == ("Shimano 105 Di2\nNieuwe banden\nOphalen in Utrecht\n\n"
                                                     "Prijs is vast")


def test_the_whole_ad_counts_so_a_quiet_title_goes_with_a_loud_text():
    ad = {"title": "Giant TCR 🚀", "description": HEAVY_TEXT}
    assert ad_emoji.tame(ad["title"], ad) == "Giant TCR"


def test_works_on_a_database_row_and_on_nothing(tmp_path):
    conn = db.connect(str(tmp_path / "x.sqlite3"))
    conn.execute("CREATE TABLE t (title TEXT, description TEXT)")
    conn.execute("INSERT INTO t VALUES (?, ?)", (HEAVY_TITLE, HEAVY_TEXT))
    row = conn.execute("SELECT * FROM t").fetchone()
    assert ad_emoji.too_many(row)
    assert ad_emoji.tame(None, row) is None
    assert ad_emoji.tame("", row) == ""
    assert ad_emoji.strip("🔥🔥") == "🔥🔥"  # nothing but emoji: left as it is rather than shown empty


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


def test_the_report_shows_the_ad_without_its_emoji_and_keeps_the_original(app):
    client = app.test_client()
    resp = client.post("/check", data={"title": HEAVY_TITLE, "description": HEAVY_TEXT, "asking_price": "1450",
                                       "location": "Utrecht"})
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Shimano 105 Di2\nNieuwe banden" in page
    assert "🔥" not in page and "✅" not in page
    with app.app_context():
        conn = db.connect(app.config["DB_PATH"])
        stored = conn.execute("SELECT title, description FROM checks ORDER BY id DESC").fetchone()
    assert (stored["title"], stored["description"]) == (HEAVY_TITLE, HEAVY_TEXT)
    # The lists show it the same way.
    listings = client.get("/listings").get_data(as_text=True)
    assert "🔥" not in listings
