import shutil

import pytest

from webapp import alerts, daily_checks, db, mail, seed
from webapp.app import create_app

MP = "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsen-racefietsen/"


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("db") / "seeded.sqlite3")
    seed.load(db.connect(path))
    return path


@pytest.fixture
def conn(seeded, tmp_path):
    path = str(tmp_path / "app.sqlite3")
    shutil.copy(seeded, path)
    return db.connect(path)


@pytest.fixture
def client(seeded, tmp_path, monkeypatch):
    path = str(tmp_path / "app.sqlite3")
    shutil.copy(seeded, path)
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mail, "send", lambda to, subject, text, *a, **kw: sent.append((to, subject, text, kw)))
    monkeypatch.setattr(mail, "_sent", [])
    app = create_app(path)
    return app.test_client(), db.connect(path), sent


def model(conn, slug="trek-domane-sl-6-gen-3"):
    return db.get_model(conn, slug=slug)


def ads(family, site):
    if family != "Trek Domane" or site != daily_checks.MARKTPLAATS:
        return []
    return [
        # a good deal: fair is about €1620-1980 for a 2021 SL 6
        {"url": MP + "m2400000011-trek-domane", "title": "Trek Domane SL 6 Gen 3 racefiets", "price": 1500,
         "description": "Bouwjaar 2021, maat 56, Ultegra", "location": "Utrecht", "photos": 3},
        # same bike, too dear
        {"url": MP + "m2400000012-trek-domane", "title": "Trek Domane SL 6 Gen 3", "price": 2400,
         "description": "Bouwjaar 2021, maat 56", "location": "Delft", "photos": 3},
        # a good deal in another size
        {"url": MP + "m2400000013-trek-domane", "title": "Trek Domane SL 6 Gen 3", "price": 1450,
         "description": "Bouwjaar 2021, maat 52", "location": "Gouda", "photos": 3},
        # another Domane, cheap for what it is
        {"url": MP + "m2400000014-trek-domane", "title": "Trek Domane AL 2 Gen 4", "price": 450,
         "description": "maat 56, 2023", "location": "Ede", "photos": 3},
        # suspiciously cheap
        {"url": MP + "m2400000015-trek-domane", "title": "Trek Domane SL 6 Gen 3", "price": 600,
         "description": "Bouwjaar 2021, maat 56", "location": "Ede", "photos": 3},
        # a part
        {"url": "https://www.marktplaats.nl/v/fietsen-en-brommers/fietsonderdelen/m2400000016-frame",
         "title": "Trek Domane SL 6 frame", "price": 300, "description": "maat 56", "photos": 3},
    ]


def confirmed(conn, m, **kw):
    token = alerts.sign_up(conn, "rider@example.com", m, site="https://bikecheck.example/", **kw)
    alerts.confirm(conn, alerts.by_token(conn, token)["id"])
    return token


def test_mails_new_ads_under_the_fair_price_once(conn):
    token = confirmed(conn, model(conn), size="56")
    sent = []
    assert alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append((a, kw)), pause=0) == 1
    (to, subject, text), kw = sent[0]
    assert to == "rider@example.com"
    assert "m2400000011" in text  # the deal in size 56
    for other in ("m2400000012", "m2400000013", "m2400000014", "m2400000015", "m2400000016"):
        assert other not in text
    assert f"https://bikecheck.example/alerts/{token}/stop" in text
    assert kw["headers"]["List-Unsubscribe"] == f"<https://bikecheck.example/alerts/{token}/stop>"
    assert "Trek Domane SL 6, maat 56" in subject  # Dutch by default, the generation left out
    # The next day the same ads aren't mailed again.
    assert alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0) == 0


def test_any_size_and_the_whole_family(conn):
    confirmed(conn, model(conn), scope="family", lang="en")
    sent = []
    alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0)
    to, subject, text = sent[0]
    assert "any Trek Domane" in subject
    assert all(k in text for k in ("m2400000011", "m2400000013", "m2400000014"))
    assert "m2400000012" not in text and "m2400000015" not in text


def test_a_highest_price(conn):
    confirmed(conn, model(conn), max_price=1460)
    sent = []
    alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0)
    assert "m2400000013" in sent[0][2] and "m2400000011" not in sent[0][2]


def test_unconfirmed_alerts_get_nothing_and_are_forgotten(conn):
    alerts.sign_up(conn, "rider@example.com", model(conn))
    sent = []
    assert alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0) == 0
    conn.execute("UPDATE alerts SET created_at = datetime('now', '-8 days')")
    alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0)
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0


def test_sign_up_confirm_and_stop(client):
    c, conn, sent = client
    page = c.get("/models/trek-domane-sl-6-gen-3?lang=en").data.decode()
    assert 'action="/models/trek-domane-sl-6-gen-3/alert"' in page and "any Trek Domane" in page
    r = c.post("/models/trek-domane-sl-6-gen-3/alert?lang=en",
               data={"email": "rider@example.com", "scope": "model", "size": "56", "max_price": "1800"})
    assert r.status_code == 200 and "Check your inbox" in r.data.decode()
    to, subject, text, _ = sent[0]
    assert to == "rider@example.com" and "Trek Domane SL 6, size 56, up to €1.800" in text
    link = next(w for w in text.split() if "/confirm" in w).replace("http://localhost", "")
    assert conn.execute("SELECT confirmed_at FROM alerts").fetchone()[0] is None
    assert "Your alert is on" in c.get(link + "?lang=en").data.decode()
    assert conn.execute("SELECT confirmed_at FROM alerts").fetchone()[0] is not None
    stop = link.replace("/confirm", "/stop")
    # Opening the stop link only asks, so a mail scanner can't stop it; the button (or one-click POST) does.
    assert "Stop this alert?" in c.get(stop + "?lang=en").data.decode()
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    assert "Alert stopped" in c.post(stop + "?lang=en").data.decode()
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    assert c.get(link).status_code == 404


def test_bad_email_and_too_many(client):
    c, conn, sent = client
    assert c.post("/models/trek-domane-sl-6-gen-3/alert", data={"email": "nope"}).status_code == 400
    m = model(conn)
    for size in ("50", "52", "54", "56", "58"):
        alerts.sign_up(conn, "rider@example.com", m, size=size)
    r = c.post("/models/trek-domane-sl-6-gen-3/alert?lang=en", data={"email": "rider@example.com", "size": "60"})
    assert "Too many alerts" in r.data.decode() and not sent


def test_without_mail_there_is_no_alert_form(client, monkeypatch):
    c, _, _ = client
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert "/alert\"" not in c.get("/models/trek-domane-sl-6-gen-3").data.decode()


def test_asking_again_keeps_the_running_alert_until_confirmed(conn):
    m = model(conn)
    confirmed(conn, m, size="56")
    alerts.run(conn, search=ads, send=lambda *a, **kw: None, pause=0)
    token = alerts.sign_up(conn, "rider@example.com", m, size="56", max_price=1400)
    assert conn.execute("SELECT COUNT(*) FROM alerts WHERE confirmed_at IS NOT NULL").fetchone()[0] == 1
    alerts.confirm(conn, alerts.by_token(conn, token)["id"])
    rows = conn.execute("SELECT * FROM alerts").fetchall()
    assert len(rows) == 1 and rows[0]["max_price"] == 1400 and rows[0]["token"] == token
    # The ads the old alert mailed about stay seen.
    sent = []
    assert alerts.run(conn, search=ads, send=lambda *a, **kw: sent.append(a), pause=0) == 0


def test_another_generations_page_replaces_the_same_alert(conn):
    confirmed(conn, model(conn), size="56")
    confirmed(conn, model(conn, "trek-domane-sl-6-gen-4"), size="56")
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    # Another size is another alert.
    confirmed(conn, model(conn), size="58")
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 2


def test_alert_mails_leave_the_visitors_mail_limit_alone(conn, monkeypatch):
    monkeypatch.setattr(mail, "_sent", [])
    calls = []
    confirmed(conn, model(conn), size="56")
    alerts.run(conn, search=ads, send=lambda *a, **kw: calls.append(kw), pause=0)
    assert calls[0]["count"] is False


def test_asking_again_at_the_limit_still_replaces(conn):
    m = model(conn)
    for size in ("50", "52", "54", "56", "58"):
        confirmed(conn, m, size=size)
    # Changing one of the five (or retrying a lost confirmation mail, twice) still works...
    first = alerts.sign_up(conn, "rider@example.com", m, size="56", max_price=1400)
    again = alerts.sign_up(conn, "rider@example.com", m, size="56", max_price=1400)
    assert first and again and alerts.by_token(conn, first) is None  # the earlier request is replaced
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 6
    alerts.confirm(conn, alerts.by_token(conn, again)["id"])
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 5
    # ...but a sixth bike doesn't.
    assert alerts.sign_up(conn, "rider@example.com", m, size="60") is None


def test_a_pending_change_counts_as_the_alert_it_replaces(conn):
    m = model(conn)
    for size in ("50", "52", "54", "56"):
        confirmed(conn, m, size=size)
    alerts.sign_up(conn, "rider@example.com", m, size="56", max_price=1400)  # not confirmed yet
    assert alerts.sign_up(conn, "rider@example.com", m, size="58")  # the fifth bike


def test_family_names_as_the_brand_writes_them(conn):
    names = {m["name"]: alerts.family_label(m) for m in db.all_models(conn)}
    assert names["TCR Advanced 0"] == "Giant TCR"
    assert names["S5 Dura-Ace Di2"] == "Cervelo S5"
    assert names["S-Works Venge"] == "Specialized Venge"
