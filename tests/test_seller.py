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
    # Gen 4 named: "Domane SL 6" with Ultegra alone reads as the Gen 3 (Ultegra 11-speed) from Mantel's old pages.
    draft = dict(DRAFT, title="Trek Domane SL 6 gen 4 racefiets", description="Shimano Ultegra Di2 groep, aluminium frame.")
    r = improve(models, draft)
    assert "Ultegra Di2" in r["title"]
    text = en(r["copy_text"])
    assert "Groupset: Shimano Ultegra Di2" in text and "Frame: Aluminium" in text
    titles = [en(f["title"]) for f in r["flags"]]
    assert any(t.startswith("Groupset: Upgrade") for t in titles)
    # A Domane SL was only made in carbon, so the frame is flagged as a claim that cannot be right.
    assert any(t.startswith("Frame: Never made in aluminium") for t in titles)


def test_a_year_before_the_generation_is_flagged(models):
    r = improve(models, year=2019)
    assert any(f["status"] == "bad" and en(f["title"]).startswith("Year:") for f in r["flags"])


def test_the_wizard_starts_with_the_photos_and_keeps_the_answers(client):
    c, app = client
    page = c.get("/sell?lang=en").data.decode()
    assert "Start with the photos" in page and page.count('class="shot"') == 11
    assert '<dialog class="camera" id="camera"' in page  # the camera in the page, with the outline over the view
    assert '<span><i>3</i>' in page  # nothing to fill in before there's a draft: the later steps aren't buttons yet
    assert 'value="ad">Next: your ad' in page
    # Each step is the same form sent again, so an answer given in one step is there in the next.
    page = c.post("/sell?lang=en", data={**DRAFT, "year": "2024", "size": "56", "go": "price"}).data.decode()
    assert 'aria-current="step"><i>4</i>' in page and "2024 · size 56" in page
    assert page.count('class="stack step-panel"') == 3 and page.count('class="stack step-panel" style="gap: 24px" hidden') == 2
    page = c.post("/sell?lang=en", data={**DRAFT, "year": "2024", "go": "photos"}).data.decode()
    assert "Start with the photos" in page and 'name="title" value="' + DRAFT["title"] in page
    assert '<option selected>2024</option>' in page  # the answer goes along, in the hidden step
    # An answer changed on screen sends the form without a button: it stays on the step it was sent from.
    page = c.post("/sell?lang=en", data={**DRAFT, "step": "copy"}).data.decode()
    assert 'aria-current="step"><i>5</i>' in page and "Your photos, in this order" in page
    # Going back to the draft or the photos never asks for a title.
    assert c.post("/sell?lang=en", data={"go": "ad"}).status_code == 200
    assert c.post("/sell?lang=en", data={"go": "price"}).status_code == 400


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


def year_fact(r):
    return next(f for f in r["facts"] if f["key"] == "year")


def test_the_drafts_parts_suggest_a_year(models):
    r = improve(models, {**DRAFT, "description": "Shimano 105 Di2 R7150, 12 speed. Ophalen in Utrecht."})
    guess = year_fact(r)["guess"]
    assert en(guess["years"]) == "2023 or later"
    assert guess["likely"] == [2026, 2025, 2024, 2023]
    assert any("105 Di2" in en(e) for e in guess["evidence"])


def test_an_older_groupset_adds_its_years_to_the_list(models):
    r = improve(models, {**DRAFT, "description": "Shimano Ultegra 6800, 11 speed."})
    fact = year_fact(r)
    assert fact["guess"]["likely"] == [2018, 2017, 2016, 2015]
    assert {2015, 2018} <= set(fact["options"])
    assert fact["options"] == sorted(fact["options"], reverse=True)


def test_no_year_clue_no_guess(models):
    assert year_fact(improve(models))["guess"] is None


def test_a_stated_year_gets_no_guess(models):
    r = improve(models, {**DRAFT, "title": "Trek Domane SL 6 2024", "description": "Shimano 105 Di2 R7150"})
    assert year_fact(r)["source"] == "draft" and year_fact(r)["guess"] is None


def test_the_year_buttons_fill_in_the_year(client):
    c, _ = client
    draft = {**DRAFT, "description": "Shimano 105 Di2 R7150, 12 speed."}
    page = c.post("/sell?lang=en", data=draft).data.decode()
    assert "Your text points to 2023 or later" in page and 'name="use_year" value="2024"' in page
    page = c.post("/sell?lang=en", data={**draft, "year": "", "use_year": "2024"}).data.decode()
    assert "<option selected>2024</option>" in page


def test_without_clues_the_page_says_where_to_find_the_year(client):
    c, _ = client
    page = c.post("/sell?lang=nl", data=DRAFT).data.decode()
    assert "framenummer" in page


def test_the_page_opens_on_the_link_and_shows_ads_we_improved(client):
    c, app = client
    page = c.get("/sell?lang=en").data.decode()
    assert 'id="sell-mode-link" checked' in page  # like the check form: the ad's link first
    assert "How we improved an ad" not in page  # nothing checked yet
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (listing_url, title, description, asking_price) VALUES (?, ?, ?, ?)",
                 ("https://www.marktplaats.nl/v/x", "trek domane racefiets", "Shimano 105, weinig gebruikt", 2400))
    conn.execute("INSERT INTO checks (title, description, asking_price) VALUES (?, ?, ?)",
                 ("Typed Domane SL 6", "not from a link", 2400))
    conn.commit()
    page = c.get("/sell?step=ad&lang=en").data.decode()  # the examples sit with the draft, step 2
    assert "How we improved an ad" in page and "trek domane racefiets" in page
    assert '<span class="site-mark"><img src="/static/logos/marktplaats.svg"' in page  # the site it was placed on
    assert "Typed Domane SL 6" not in page  # only ads read from a public link


def test_every_photo_shot_and_step_has_dutch():
    from webapp.app import PHOTO_SHOTS, SELL_STEPS
    texts = [t for _, _, title, tips in PHOTO_SHOTS for t in [title, *tips]] + [label for _, label in SELL_STEPS]
    assert [t for t in texts if t not in i18n.NL] == []
    import os
    assert all(os.path.exists(f"webapp/static/photo-guide/{key}.svg") for key, *_ in PHOTO_SHOTS)
