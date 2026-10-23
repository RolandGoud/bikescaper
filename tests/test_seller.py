from datetime import date

import pytest

from webapp import db, i18n, seed, seller
from webapp.app import create_app

TODAY = date(2026, 10, 23)
DRAFT = {"title": "Trek Domane SL 6 racefiets",
         "description": "Mooie racefiets, weinig gebruikt. Shimano 105 groep. Ophalen in Utrecht.", "asking_price": 2600}


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    conn = db.connect(str(tmp_path_factory.mktemp("db") / "test.sqlite3"))
    seed.load(conn)
    return db.all_models(conn)


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    return app.test_client(), app


def en(msg):
    token = i18n.current_language.set("en")
    try:
        return str(msg)
    finally:
        i18n.current_language.reset(token)


def improve(models, draft=DRAFT, **answers):
    token = i18n.current_language.set("en")
    try:
        return seller.improve(models, draft, answers, today=TODAY)
    finally:
        i18n.current_language.reset(token)


def sources(r):
    return {f["key"]: f["source"] for f in r["facts"]}


def test_fills_the_gaps_from_the_catalogue(models):
    r = improve(models)
    assert r["model"]["name"] == "Domane SL 6 gen 4"
    assert sources(r) == {"model": "draft", "groupset": "cat", "frame": "cat", "brakes": "cat", "wheels": "cat",
                          "year": "open", "size": "open", "condition": "open", "invoice": "open", "service": "open"}
    # The draft says 105; this model has 105 Di2, so the new ad names it and says why.
    assert "105 Di2" in r["title"]
    assert any(en(f["title"]) == "We added “Di2”" for f in r["flags"])
    assert r["before"]["size"]["status"] == "warn"


def test_answers_go_into_the_new_ad_and_the_buyers_check(models):
    r = improve(models, year=2024, size="56", condition="like-new", wheels="original", invoice="yes")
    assert en(r["title"]) == "Trek Domane SL 6 Gen 4 · 2024 · size 56 · 105 Di2 · carbon"
    text = en(r["copy_text"])
    assert "from 2024, size 56 (fits about 174–180 cm)" in text
    assert "Like new" in text and "Invoice: yes" in text
    assert "Mooie racefiets, weinig gebruikt." in text  # the seller's own words stay
    # Service is still open: shown as a gap, but not copied into the ad.
    assert "Service" not in text
    assert any(kind == "todo" for line in r["description"] for _, kind in line)
    after = r["after"]
    assert [after[k]["status"] for k in ("age", "specs", "size", "value")] == ["ok", "ok", "ok", "ok"]
    assert r["suggested"] == round((r["value"]["low"] + r["value"]["high"]) / 2 / 50) * 50


def test_the_sellers_own_parts_win_and_are_flagged(models):
    draft = dict(DRAFT, description="Shimano Ultegra Di2 groep, aluminium frame.")
    r = improve(models, draft)
    assert "Ultegra Di2" in r["title"]
    text = en(r["copy_text"])
    assert "Groupset: Shimano Ultegra Di2" in text and "Frame: Aluminium" in text
    titles = [en(f["title"]) for f in r["flags"]]
    assert any(t.startswith("Groupset: Upgrade") for t in titles)
    assert any(t.startswith("Frame: Differs") for t in titles)


def test_a_year_before_the_generation_is_flagged(models):
    r = improve(models, year=2019)
    assert any(f["status"] == "bad" and en(f["title"]).startswith("Year:") for f in r["flags"])


def test_no_model_found(models):
    r = improve(models, {"title": "Mooie fiets", "description": "", "asking_price": 300})
    assert r["model"] is None and "facts" not in r


def test_the_page_works_and_saves_nothing(client):
    c, app = client
    assert "Improve my ad" in c.get("/sell?lang=en").data.decode()
    page = c.post("/sell?lang=en", data={**DRAFT, "year": "2024", "size": "56"}).data.decode()
    assert "Your new ad" in page and "2024 · size 56" in page
    assert c.post("/sell", data={"title": ""}).status_code == 400
    conn = db.connect(app.config["DB_PATH"])
    assert conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0] == 0


def test_the_photo_review_offer_counts_interest(client):
    c, app = client
    assert c.post("/sell/photo-review?lang=en", data={"model_id": "1"}).status_code == 200
    assert c.post("/sell/photo-review", data={}, headers={"X-Requested-With": "fetch"}).status_code == 204
    c.post("/sell/photo-review/notify", data={"email": "rider@example.com"}, headers={"X-Requested-With": "fetch"})
    c.post("/sell/photo-review/notify", data={"email": "not an email"})
    conn = db.connect(app.config["DB_PATH"])
    rows = conn.execute("SELECT kind, email FROM photo_review_interest ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("click", None), ("click", None), ("email", "rider@example.com")]
    page = c.get("/sell/photo-review/interest?lang=en").data.decode()
    assert "rider@example.com" not in page and "<td>2</td>" in page


def test_an_email_counts_only_once_confirmed(client, monkeypatch):
    c, app = client
    from webapp import mail
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NOTIFY_EMAIL", "owner@example.com")
    monkeypatch.setattr(mail, "send", lambda to, subject, text, *a, **kw: sent.append((to, text)))
    monkeypatch.setattr(mail, "_sent", [])
    assert 'name="email"' in c.post("/sell/photo-review?lang=en", data={}).data.decode()
    c.post("/sell/photo-review/notify?lang=en", data={"email": "rider@example.com"})
    # Asking again the same day sends no second link.
    c.post("/sell/photo-review/notify?lang=en", data={"email": "Rider@example.com"})
    assert [to for to, _ in sent] == ["rider@example.com"]
    link = next(w for w in sent[0][1].split() if "/confirm/" in w)
    page = c.get("/sell/photo-review/interest?lang=en").data.decode()
    assert "Confirmed emails</div><div class=\"v\">0" in page and "Waiting for confirmation</div><div class=\"v\">1" in page
    # Opening the link confirms it and tells the owner, once.
    assert "Email confirmed" in c.get(link.replace("http://localhost", "") + "?lang=en").data.decode()
    c.get(link.replace("http://localhost", ""))
    assert [to for to, _ in sent] == ["rider@example.com", "owner@example.com"]
    page = c.get("/sell/photo-review/interest?lang=en").data.decode()
    assert "Confirmed emails</div><div class=\"v\">1" in page
    # A confirmed address gets no new links, and a made-up link confirms nothing.
    c.post("/sell/photo-review/notify", data={"email": "rider@example.com"})
    assert len(sent) == 2
    assert c.get("/sell/photo-review/confirm/nope").status_code == 404


def test_without_mail_there_is_no_email_form(client, monkeypatch):
    c, _ = client
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert 'name="email"' not in c.post("/sell/photo-review?lang=en", data={}).data.decode()


@pytest.mark.parametrize("text,value", [
    ("344", 344), ("344,00", 344), ("344.0", 344), ("344.00", 344), ("€ 1.049,-", 1049), ("1.049", 1049),
    ("1.049,50", 1049.5), ("€2.450", 2450), ("€ 344,-", 344), ("", None), ("bieden", None),
])
def test_prices_are_read_the_european_way(text, value):
    from webapp.app import parse_number
    assert parse_number(text) == value


def test_a_price_from_an_ad_link_stays_the_same(client, monkeypatch):
    c, _ = client
    from webapp import fetch_ad
    monkeypatch.setattr(fetch_ad, "fetch_listing", lambda url: {
        "title": "Trek Domane SL 6 racefiets", "description": "Shimano 105", "asking_price": 344.0})
    page = c.post("/sell?lang=en", data={"ad_link": "https://www.marktplaats.nl/v/x"}).data.decode()
    assert 'value="344"' in page and "€3.440" not in page
    # Sending the filled-in form again (as answering a question does) keeps it at 344.
    page = c.post("/sell?lang=en", data={"title": "Trek Domane SL 6 racefiets", "asking_price": "344"}).data.decode()
    assert "€344" in page and "€3.440" not in page
