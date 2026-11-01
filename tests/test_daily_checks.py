from datetime import datetime, timedelta, timezone

import pytest

from webapp import daily_checks, db, seed

AD = "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2455946444-trek-domane-al-2"
# The ads name the generation: a bare "Domane AL 2" is ambiguous since Mantel's old pages added the Gen 3, so the
# match comes out with low confidence and the daily check passes the ad over.


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "app.sqlite3"))
    seed.load(c)
    return c


def ads(family, site=daily_checks.MARKTPLAATS):
    if family != "Trek Domane" or site != daily_checks.MARKTPLAATS:
        return []
    return [
        {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsonderdelen/m2400000001-trek-domane-frame",
         "title": "Trek Domane SL 6 frame", "price": 900, "photos": 3},  # a part, not a bike
        {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2400000002-trek-domane",
         "title": "Trek Domane SL 6", "price": 1, "photos": 3},  # "bieden"
        {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2400000003-trek-madone",
         "title": "Trek Madone SL 6", "price": 2500, "photos": 3},  # another family
        {"url": AD, "title": "Trek Domane AL 2 Gen 4", "price": 344, "photos": 3},
    ]


def fetch(url):
    return {"listing_url": url, "title": "Trek Domane AL 2 Gen 4", "description": "Maat 56, 2022",
            "asking_price": 344.0, "location": "Utrecht", "photos": ["https://images.marktplaats.com/1.jpg"]}


def test_checks_the_first_suitable_ad_once(conn):
    saved = daily_checks.run(conn, search=ads, fetch=fetch, pause=0)
    assert len(saved) == 1
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (saved[0],)).fetchone()
    assert row["listing_url"] == AD and row["source"] == "daily" and row["rider_height"] is None
    # The next day the same ad isn't checked again.
    assert daily_checks.run(conn, search=ads, fetch=fetch, pause=0) == []


def test_skips_ads_a_visitor_already_checked(conn):
    conn.execute("INSERT INTO checks (listing_url, title) VALUES (?, ?)",
                 ("https://www.marktplaats.nl/m2455946444", "Trek Domane AL 2 Gen 4"))
    assert daily_checks.run(conn, search=ads, fetch=fetch, pause=0) == []


def test_skips_ads_without_photos(conn):
    def bare(family, site):
        listed = ads(family, site)
        if listed:  # an ad without photos comes first
            listed.insert(0, {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/"
                                     "m2400000005-trek-domane", "title": "Trek Domane AL 2 Gen 4", "price": 1200, "photos": 0})
        return listed
    saved = daily_checks.run(conn, search=bare, fetch=fetch, pause=0)
    assert [conn.execute("SELECT listing_url FROM checks WHERE id = ?", (i,)).fetchone()[0] for i in saved] == [AD]


def test_tries_the_next_ad_when_the_ad_has_no_photos(conn):
    other = "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2400000006-trek-domane"

    def two(family, site):
        if family != "Trek Domane" or site != daily_checks.MARKTPLAATS:
            return []
        return [{"url": other, "title": "Trek Domane AL 2 Gen 4", "price": 1200, "photos": 2},
                {"url": AD, "title": "Trek Domane AL 2 Gen 4", "price": 344, "photos": 3}]

    fetched = []

    def fetch_bare_first(url):
        fetched.append(url)
        return dict(fetch(url), photos=[] if url == other else fetch(url)["photos"])

    saved = daily_checks.run(conn, search=two, fetch=fetch_bare_first, pause=0)
    assert fetched == [other, AD]
    assert [conn.execute("SELECT listing_url FROM checks WHERE id = ?", (i,)).fetchone()[0] for i in saved] == [AD]


def test_one_failing_model_does_not_stop_the_rest(conn):
    def flaky(family, site):
        if family == "Giant TCR":
            raise OSError("timeout")
        return ads(family, site)
    assert len(daily_checks.run(conn, search=flaky, fetch=fetch, pause=0)) == 1


def test_also_checks_three_models_on_2dehands(conn):
    searched = []

    def both(family, site):
        searched.append((site, family))
        if site != daily_checks.TWEEDEHANDS:
            return ads(family, site)
        title = {"Specialized Tarmac": "Specialized Tarmac SL7 Expert", "Trek Madone": "Trek Madone SL 6 Gen 7"}
        return [{"url": f"https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m246010000{len(searched)}",
                 "title": title.get(family, family + " SL 6"), "price": 1500, "photos": 1}]

    saved = daily_checks.run(conn, search=both, fetch=fetch, pause=0)
    assert [f for s, f in searched if s == daily_checks.TWEEDEHANDS] == ["Specialized Tarmac", "Trek Emonda", "Trek Madone"]
    urls = [conn.execute("SELECT listing_url FROM checks WHERE id = ?", (i,)).fetchone()[0] for i in saved]
    assert urls[0] == AD and len(urls) == 4 and all("2dehands.be" in u for u in urls[1:])


def test_the_same_ad_number_on_another_site_is_another_ad(conn):
    conn.execute("INSERT INTO checks (listing_url, title) VALUES (?, ?)",
                 ("https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2455946444-trek", "Trek"))
    assert len(daily_checks.run(conn, search=ads, fetch=fetch, pause=0)) == 1


def test_remove_deletes_only_daily_checks(conn, tmp_path):
    conn.execute("INSERT INTO checks (title) VALUES ('Visitor')")
    daily_checks.run(conn, search=ads, fetch=fetch, pause=0)
    assert daily_checks.remove(conn, str(tmp_path / "app.sqlite3")) == 1
    assert [r["title"] for r in conn.execute("SELECT title FROM checks")] == ["Visitor"]


def test_runs_at_most_once_a_day(tmp_path, monkeypatch):
    path = str(tmp_path / "app.sqlite3")
    passes = []
    monkeypatch.setattr(daily_checks, "run", lambda conn: passes.append(1) or [])
    now = datetime(2026, 10, 22, 18, tzinfo=timezone.utc)
    daily_checks.run_locked(path, now)
    daily_checks.run_locked(path, now + timedelta(hours=5))
    daily_checks.run_locked(path, now + timedelta(hours=21))
    assert len(passes) == 2


def test_s_works_counts_as_its_family(conn):
    models = db.all_models(conn)
    ad = {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/m2400000004-s-works",
          "title": "Specialized S-Works Tarmac SL9 Dura-Ace Di2", "price": 9000, "photos": 2}
    assert daily_checks.pick(models, "Specialized Tarmac", [ad], set()) == ad


def test_stores_photos_right_after_the_pass(tmp_path, monkeypatch):
    path = str(tmp_path / "app.sqlite3")
    stored = []
    monkeypatch.setattr(daily_checks, "run", lambda conn: [7, 8])
    monkeypatch.setattr(daily_checks.ad_photos, "store", lambda conn, db_path, check_id: stored.append(check_id))
    daily_checks.run_locked(path)
    assert stored == [7, 8]
