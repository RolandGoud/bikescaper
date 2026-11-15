"""The listings page puts each ad under the day of its newest check: Today, Yesterday, else the date, never the time."""
import shutil
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from webapp import db, seed
from webapp.app import create_app, day_heading, local_day
from webapp.i18n import current_language


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("seeded") / "seeded.sqlite3"
    seed.load(db.connect(str(path)))
    return path


@pytest.fixture
def site(seeded, tmp_path):
    shutil.copy(seeded, tmp_path / "app.sqlite3")
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    return app.test_client(), tmp_path / "app.sqlite3"


def check(site, title, when):
    client, path = site
    client.post("/check", data={"title": title, "asking_price": "1450", "location": "Utrecht"})
    con = sqlite3.connect(path)
    con.execute("UPDATE checks SET created_at = ?, too_old = 0 WHERE id = (SELECT MAX(id) FROM checks)", (when,))
    con.commit()


def stamp(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


def headings(html):
    return [part.split("</span>")[0] for part in html.split('<div class="day-rail"><span>')[1:]]


def test_day_heading():
    today = date(2026, 11, 15)
    assert day_heading(today, today, "nl") == "Vandaag"
    assert day_heading(date(2026, 11, 12), today, "nl") == "12 nov"
    assert day_heading(date(2026, 3, 2), today, "nl") == "2 mrt"
    token = current_language.set("en")
    try:
        assert day_heading(date(2026, 11, 14), today, "en") == "Yesterday"
        assert day_heading(date(2025, 7, 20), today, "en") == "20 Jul 2025"
    finally:
        current_language.reset(token)


def test_the_day_is_the_dutch_one():
    assert local_day("2026-11-15 23:30:00") == date(2026, 11, 16)  # 00:30 in Amsterdam
    assert local_day("2026-07-01 21:59:59") == date(2026, 7, 1)    # 23:59 summer time


def test_one_heading_per_day_and_days_share_rows(site):
    client, _ = site
    check(site, "Trek Domane SL6 2022 maat 56", "2025-07-20 09:05:00")
    check(site, "Canyon Endurace CF 7 2021 maat M", stamp(1))
    check(site, "Giant TCR Advanced 2 2020 maat M", stamp(0))
    check(site, "Scott Addict 30 2019 maat 54", stamp(0))
    html = client.get("/listings?lang=nl").data.decode()
    # Named once each, over the day's first card, newest first; every card stays in the one grid.
    assert headings(html) == ["Vandaag", "Gisteren", "20 jul 2025"]
    assert html.count('<div class="day-rail" aria-hidden="true">') >= 1  # the second card of today: a line, no name
    assert html.count('listing-grid"') == 1 and "09:05" not in html
    assert "day-rail.js" in html
    assert headings(client.get("/listings?lang=en").data.decode()) == ["Today", "Yesterday", "20 Jul 2025"]


def test_an_ad_checked_again_goes_under_its_newest_check(site):
    client, _ = site
    check(site, "Trek Domane SL6 2022 maat 56", "2025-03-02 10:00:00")
    check(site, "Trek Domane SL6 2022 maat 56", "2025-10-05 10:00:00")
    assert headings(client.get("/listings?lang=nl").data.decode()) == ["5 okt 2025"]
