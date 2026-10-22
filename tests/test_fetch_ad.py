import pytest

from webapp import db, fetch_ad, seed
from webapp.app import create_app

# Trimmed from a real Marktplaats ad page: the listing JSON, the description and the "Kenmerken" list.
AD_HTML = """<html><head>
<meta property="og:title" content="Trek Domane SL6 (a1) — Fietsen | Racefietsen — Marktplaats"/>
<script>window.__CONFIG__ = {"listing":{"itemId":"a1","title":"Trek Domane SL6 2022 maat 56",
"priceInfo":{"priceCents":245000,"priceType":"FIXED"},
"seller":{"name":"Jan","location":{"cityName":"Utrecht"}},
"gallery":{"imageUrls":["//images.marktplaats.com/api/v1/x/images/aa/1?rule=eps_#.JPG"]}}};</script>
</head><body>
<div class="Attributes-module-root"><div class="Attributes-module-list">
<div class="Attributes-module-item"><div class="Attributes-module-label">Conditie</div><div class="Attributes-module-value">Zo goed als nieuw</div></div>
<div class="Attributes-module-item"><div class="Attributes-module-label">Handelsnaam fabrikant</div><div class="Attributes-module-value">Trek</div></div>
<div class="Attributes-module-item"><div class="Attributes-module-label">Materiaal</div><div class="Attributes-module-value"><a href="/l/x">Carbon</a></div></div>
</div></div>
<div class="Description-module-description"><div data-collapsable="description"><p>Mooie fiets, Ultegra.</p><ul><li>Maat: 56</li><li>Bouwjaar: 2022</li></ul><br>Weinig gereden</div></div>
<div class="Other">not this</div>
</body></html>"""


def test_parses_marktplaats_ad():
    ad = fetch_ad.parse_listing(AD_HTML)
    assert ad["title"] == "Trek Domane SL6 2022 maat 56"
    assert ad["asking_price"] == 2450
    assert ad["location"] == "Utrecht"
    assert ad["photos"] == ["https://images.marktplaats.com/api/v1/x/images/aa/1?rule=eps_85.JPG"]
    assert ad["description"] == ("Mooie fiets, Ultegra.\n\n- Maat: 56\n- Bouwjaar: 2022\n\nWeinig gereden\n\n"
                                 "Conditie: Zo goed als nieuw\nMateriaal: Carbon")


def test_only_known_sites_are_fetched():
    assert fetch_ad.supported("https://www.marktplaats.nl/v/a/b/a1-x")
    assert fetch_ad.supported("https://www.2dehands.be/v/a/b/a1-x")
    assert not fetch_ad.supported("https://marktplaats.nl.evil.example/v/a")
    assert not fetch_ad.supported("http://192.168.1.10/admin")
    with pytest.raises(fetch_ad.FetchError):
        fetch_ad.fetch_listing("http://192.168.1.10/admin")


def test_redirects_off_the_sites_are_not_followed():
    handler = fetch_ad._SameSitesRedirects()
    req = fetch_ad.urllib.request.Request("https://www.marktplaats.nl/v/a/b/a1-x")
    with pytest.raises(fetch_ad.FetchError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://192.168.1.10/admin")
    assert handler.redirect_request(req, None, 301, "Moved", {}, "https://www.marktplaats.nl/v/a/b/a1-y")


def test_clean_url_drops_tracking():
    assert (fetch_ad.clean_url("http://WWW.Marktplaats.nl/v/a/b/a1-x?c=abc&correlationId=1#top")
            == "https://www.marktplaats.nl/v/a/b/a1-x")


def test_check_from_link(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False  # no downloads in tests; test_stores_ad_photos covers them
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()

    def fake_fetch(url):
        ad = fetch_ad.parse_listing(AD_HTML)
        ad["listing_url"] = fetch_ad.clean_url(url)
        return ad

    monkeypatch.setattr(fetch_ad, "fetch_listing", fake_fetch)
    resp = client.post("/check", data={"mode": "link", "ad_link": "https://www.marktplaats.nl/v/a/b/a1-x?c=1",
                                       "rider_height": "180"})
    assert resp.status_code == 302
    page = client.get(resp.headers["Location"] + "?lang=en").data.decode()
    assert "Trek Domane SL6 2022 maat 56" in page and "€2.450" in page and "Utrecht" in page
    assert "eps_85.JPG" in page and "https://www.marktplaats.nl/v/a/b/a1-x" in page
    assert '<dialog class="lightbox"' in page and 'data-photo="0"' in page and "lightbox.js" in page


def test_failed_fetch_falls_back_to_manual(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "app.sqlite3"))
    client = app.test_client()

    def failing(url):
        raise fetch_ad.FetchError("The site didn't answer in time.")

    monkeypatch.setattr(fetch_ad, "fetch_listing", failing)
    resp = client.post("/check?lang=en", data={"mode": "link", "ad_link": "https://www.marktplaats.nl/v/a/b/a1-x"})
    page = resp.data.decode()
    assert resp.status_code == 400
    assert "The site didn&#39;t answer in time. Fill in the details yourself instead." in page
    assert 'id="mode-manual" checked' in page
    assert 'name="listing_url" type="url" value="https://www.marktplaats.nl/v/a/b/a1-x"' in page
    assert client.post("/check", data={"mode": "link", "ad_link": " "}).status_code == 400
    # a link pasted without https:// comes back as a valid URL, or the browser would refuse the manual form
    page = client.post("/check", data={"mode": "link", "ad_link": "www.marktplaats.nl/v/a/b/a1-x"}).data.decode()
    assert 'name="listing_url" type="url" value="https://www.marktplaats.nl/v/a/b/a1-x"' in page


def test_ad_id_from_any_link():
    assert fetch_ad.ad_id("https://www.marktplaats.nl/v/fietsen-en-brommers/racefietsen/a1512951815-bianchi") == "a1512951815"
    assert fetch_ad.ad_id("www.2dehands.be/v/x/y/a167600933-trek?c=1") == "a167600933"
    assert fetch_ad.ad_id("https://www.marktplaats.nl/a/x/y/m1900000000-oud.html") == "m1900000000"
    assert fetch_ad.ad_id("https://www.marktplaats.nl/a1512951815") == "a1512951815"
    assert fetch_ad.ad_id("https://www.marktplaats.nl/l/fietsen-en-brommers/") is None


def test_recheck_marks_removed_ads(tmp_path):
    from datetime import datetime, timedelta

    from webapp import recheck

    conn = db.connect(str(tmp_path / "app.sqlite3"))
    now = datetime(2026, 10, 22, 12, 0)
    old = recheck._stamp(now - timedelta(days=200))
    rows = [("https://www.marktplaats.nl/v/a/b/a100000-gone", None),     # 1: removed
            ("https://www.marktplaats.nl/v/a/b/a200000-live", None),     # 2: still up
            ("https://www.2dehands.be/v/a/b/a300000-unsure", None),      # 3: site didn't answer
            (None, None),                                           # 4: typed in, no link
            ("https://example.com/a400000-other", None),                 # 5: another site
            ("https://www.marktplaats.nl/v/a/b/a500000-old", old)]       # 6: past the watch window
    for url, created in rows:
        conn.execute("INSERT INTO checks (listing_url, title, created_at) VALUES (?, 't', COALESCE(?, datetime('now')))",
                     (url, created))
    asked = []

    def status(url):
        asked.append(url)
        return {"a100000": "removed", "a200000": "live"}.get(fetch_ad.ad_id(url))

    assert recheck.run(conn, now=now, status=status, pause=0) == 1
    assert [fetch_ad.ad_id(u) for u in asked] == ["a100000", "a200000", "a300000"]
    got = {r["id"]: (r["last_checked_at"], r["removed_at"]) for r in conn.execute("SELECT * FROM checks")}
    assert got[1] == ("2026-10-22 12:00:00", "2026-10-22 12:00:00")
    assert got[2] == ("2026-10-22 12:00:00", None)
    assert got[3] == (None, None)
    # Checked ones wait a day; removed ones are never asked again; the unsure one is retried.
    asked.clear()
    recheck.run(conn, now=now + timedelta(hours=2), status=status, pause=0)
    assert [fetch_ad.ad_id(u) for u in asked] == ["a300000"]
    asked.clear()
    recheck.run(conn, now=now + timedelta(hours=21), status=status, pause=0)
    assert [fetch_ad.ad_id(u) for u in asked] == ["a200000", "a300000"]


def test_removed_badge(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (listing_url, title, removed_at) VALUES"
                 " ('https://www.marktplaats.nl/v/a/b/a1-x', 'Trek Domane SL6 2022', '2026-10-21 08:00:00')")
    conn.commit()
    client = app.test_client()
    assert "Verwijderd van de site op 2026-10-21" in client.get("/check/1?lang=nl").data.decode()
    for url in ["/?lang=en", "/listings?lang=en"]:
        assert 'class="removed-tag">Removed</span>' in client.get(url).data.decode(), url


def test_only_one_process_rechecks_at_a_time(tmp_path, monkeypatch):
    import fcntl

    from webapp import recheck

    path = str(tmp_path / "app.sqlite3")
    db.connect(path).close()
    passes = []
    monkeypatch.setattr(recheck, "run", lambda conn: passes.append(1) or 0)
    with open(path + ".recheck.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recheck.run_locked(path)  # another worker holds the lock: skip
    assert passes == []
    recheck.run_locked(path)
    assert passes == [1]


def test_same_ad_checked_twice_is_one_card(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    conn = db.connect(app.config["DB_PATH"])
    rows = [  # oldest first
        ("https://www.marktplaats.nl/v/fietsen/racefietsen/a1512951815-trek?c=1", "Trek Domane SL6 2022", 2500, 170),
        ("http://marktplaats.nl/a1512951815", "Trek Domane SL6 2022 (prijs verlaagd)", 2300, 190),  # same ad
        (None, "Giant TCR Advanced 2 2021 maat M", 1500, None),
        (None, "giant  TCR advanced 2 2021 maat m", 1500, None),   # same typed ad
        (None, "Giant TCR Advanced 2 2021 maat M", 1400, None),    # other price: another ad
    ]
    for url, title, price, height in rows:
        conn.execute("INSERT INTO checks (listing_url, title, asking_price, rider_height) VALUES (?,?,?,?)",
                     (url, title, price, height))
    conn.commit()
    client = app.test_client()

    page = client.get("/listings?lang=nl").data.decode()
    assert page.count('class="listing-card"') == 3
    assert page.count("2× gecheckt · laatst op ") == 2 and page.count("Gecheckt op ") == 1
    assert "€2.300" in page and "€2.500" not in page  # the card shows the newest check
    assert 'href="/check/2"' in page and 'href="/check/1"' not in page

    # each person's own report still exists, with their own height
    assert "Deze advertentie is 2 keer gecheckt." in client.get("/check/1?lang=nl").data.decode()
    assert "Deze advertentie is 2 keer gecheckt." in client.get("/check/2?lang=nl").data.decode()
    assert "keer gecheckt" not in client.get("/check/5?lang=nl").data.decode()

    home = client.get("/?lang=nl").data.decode()
    assert home.count('class="listing-card"') == 3


def test_asking_price_counts_an_ad_once():
    from webapp import prices

    class Rows:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, sql, args):
            return sorted(self.rows, key=lambda r: -r["id"])

    def row(i, url, price):
        return {"id": i, "listing_url": url, "title": "Trek Domane", "asking_price": price,
                "model_id": 7, "created_at": "2026-10-20 10:00:00", "description": ""}

    ads = prices.known_ads(Rows([row(1, "https://www.marktplaats.nl/a1512951815", 2500),
                                 row(2, "https://www.marktplaats.nl/v/x/y/a1512951815-z", 2300),
                                 row(3, "https://www.marktplaats.nl/a1600000000", 2000)]),
                           [{"id": 7}])
    assert sorted(a["price"] for a in ads) == [2000, 2300]
    # viewing the older check of the same ad still leaves that ad out
    from datetime import date
    got = prices.asking_price(ads, 7, 90, today=date(2026, 10, 22), leave_out=1)
    assert got["count"] == 1 and got["median"] == 2000


def test_ad_key_takes_the_site_from_the_host():
    def key(url):
        return fetch_ad.ad_key({"listing_url": url, "title": "", "asking_price": 0})
    assert key("https://www.marktplaats.nl/v/fietsen/racefietsen/m200000-van-2dehands") == "marktplaats:m200000"
    assert key("WWW.2DEHANDS.BE/a/fietsen/m200000-x") == "2dehands:m200000"
    assert key("https://www.2ememain.be/a/velos/m200000-x") == "2dehands:m200000"


def test_stores_ad_photos(tmp_path):
    import json

    from webapp import ad_photos

    path = str(tmp_path / "app.sqlite3")
    conn = db.connect(path)
    links = ["https://admarkt-cdn.marktplaats.com/images/aa/1?rule=eps_85.JPG",
             "https://images.marktplaats.com/images/bb/2?rule=eps_85.JPG",
             "https://evil.example/3.jpg"]                      # not an ad image server
    conn.execute("INSERT INTO checks (title, photos) VALUES ('t', ?)", (json.dumps(links),))
    conn.commit()
    assert ad_photos.missing(conn) == [1]

    calls = []

    def fake(url):
        calls.append(url)
        return None if "/2?" in url else (b"jpeg bytes", ".jpg")   # the second one fails this time

    assert ad_photos.store(conn, path, 1, download=lambda u: fake(u) if ad_photos._allowed(u) else None) == 1
    stored = json.loads(conn.execute("SELECT photos FROM checks").fetchone()[0])
    assert stored == ["1/01.jpg", links[1], links[2]]
    assert open(tmp_path / "ad-photos" / "1" / "01.jpg", "rb").read() == b"jpeg bytes"
    assert calls == links[:2]

    # the next try only fetches what's still a link, and keeps the numbering
    ad_photos.store(conn, path, 1, download=lambda u: (b"png", ".png") if ad_photos._allowed(u) else None)
    stored = json.loads(conn.execute("SELECT photos FROM checks").fetchone()[0])
    assert stored == ["1/01.jpg", "1/02.png", links[2]]

    # the site serves them, and pages use our copy
    app = create_app(path)
    app.config["STORE_AD_PHOTOS"] = False
    client = app.test_client()
    assert client.get("/ad-photos/1/01.jpg").data == b"jpeg bytes"
    assert client.get("/ad-photos/../app.sqlite3").status_code == 404
    page = client.get("/check/1").data.decode()
    assert 'src="/ad-photos/1/01.jpg"' in page and 'src="/ad-photos/1/02.png"' in page
