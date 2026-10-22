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
