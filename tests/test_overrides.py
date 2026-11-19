"""An admin corrects a check by hand (the report's edit mode): the model, year, groupset, size and main photo stay
set when the check runs again, and only a logged-in admin can set them."""
import json

from webapp import checks, db, seed
from webapp.app import create_app

TITLE = "Trek Domane SL6 2022 maat 56 Ultegra"


def setup(tmp_path, monkeypatch, password="geheim"):
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    url = client.post("/check", data={"title": TITLE, "asking_price": "2450", "rider_height": "180"}).headers["Location"]
    return app, client, url, int(url.rsplit("/", 1)[1])


def login(client, password="geheim"):
    return client.post("/admin/login", data={"password": password, "next": "/admin"})


def test_only_a_logged_in_admin_can_correct_a_check(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    assert client.post(f"/check/{check_id}/override", data={"field": "year", "value": "2020"}).status_code == 403
    assert b"edit-year" not in client.get(url + "?edit=1").data
    assert login(client, "wrong").status_code == 400
    assert login(client).status_code == 302
    page = client.get(url + "?edit=1&lang=en").data
    assert b"Edit mode" in page and b"edit-year" in page and b"edit-match" in page and b"edit-groupset" in page
    # The ad card has one pencil for all its values, by its heading, like Our match: none on the tiles.
    assert page.count(b'class="ed-pen"') == 2 and b'id="edit-ad"' in page
    client.post("/admin/logout")
    assert client.post(f"/check/{check_id}/override", data={"field": "year", "value": "2020"}).status_code == 403


def test_no_password_set_means_no_login(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch, password="")
    assert login(client, "").status_code == 400
    assert b"ADMIN_PASSWORD" in client.get("/admin/login?lang=en").data


def test_values_set_by_hand_win_and_survive_a_recheck(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    madone = next(m for m in db.all_models(conn) if "Madone" in m["name"])
    for data in ({"field": "year", "value": "2020"}, {"field": "size", "value": "54"},
                 {"field": "groupset", "value": "105:3", "electronic": "1"}, {"field": "model", "value": madone["slug"]}):
        assert client.post(f"/check/{check_id}/override", data=data).status_code == 302
    # A visitor's pick of another model doesn't undo the admin's.
    other = next(m for m in db.all_models(conn) if "Domane" in m["name"])
    client.post(f"/check/{check_id}/match", data={"model_id": other["id"]})
    client.post(f"/check/{check_id}/recheck"), client.post("/admin/recheck")
    page = client.get(url + "?lang=en").data.decode()
    assert "Madone" in page
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    overrides = json.loads(row["overrides"])
    assert overrides == {"year": 2020, "size": "54", "groupset": {"key": "105", "tier": 3, "electronic": True},
                         "model": madone["slug"]}
    report = checks.run_check(db.all_models(conn), dict(row, overrides=overrides))
    assert report["model"]["slug"] == madone["slug"]
    assert report["claims"]["year"] == 2020 and report["year"]["year"] == 2020 and report["year"]["how"] == "ad"
    assert report["claims"]["size"] == "54" and report["size"]["rows"]
    assert report["claims"]["groupset"]["key"] == "105" and report["claims"]["groupset"]["electronic"]
    assert report["locked"] == ["groupset", "model", "size", "year"]
    # Back to automatic: one field, then all.
    client.post(f"/check/{check_id}/override", data={"field": "year", "clear": "1"})
    assert "year" not in json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0])
    client.post(f"/check/{check_id}/override", data={"field": "all"})
    assert conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0] is None
    assert checks.run_check(db.all_models(conn), dict(row, overrides={}))["claims"]["year"] == 2022


def test_the_main_photo_goes_first(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    conn = db.connect(app.config["DB_PATH"])
    photos = [f"https://example.com/{i}.jpg" for i in range(4)]
    conn.execute("UPDATE checks SET photos = ? WHERE id = ?", (json.dumps(photos), check_id))
    conn.commit()
    login(client)
    assert client.post(f"/check/{check_id}/override", data={"field": "main_photo", "value": "9"}).status_code == 400
    assert client.post(f"/check/{check_id}/override", data={"field": "main_photo", "value": "2"}).status_code == 302
    page = client.get(url).data.decode()
    big = page.index('class="ag-main"')
    assert page.index("example.com/2.jpg", big) < page.index("example.com/0.jpg", big)
    # The stored order is the ad's own: only what's shown changes.
    assert json.loads(conn.execute("SELECT photos FROM checks WHERE id = ?", (check_id,)).fetchone()[0]) == photos


def test_bad_values_are_refused(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    for data in ({"field": "year", "value": "1890"}, {"field": "model", "value": "no-such-bike"},
                 {"field": "groupset", "value": "nope:9"}, {"field": "colour", "value": "  "}):
        assert client.post(f"/check/{check_id}/override", data=data).status_code == 400


def test_the_admin_page_needs_a_login(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    response = client.get("/admin")
    assert response.status_code == 302 and "/admin/login" in response.headers["Location"]
    assert client.post("/admin/recheck").status_code == 403
    login(client)
    assert client.get("/admin").status_code == 200


def test_the_header_has_a_login_icon_and_once_logged_in_an_account_menu(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    page = client.get("/?lang=en").get_data(as_text=True)
    assert 'class="account-login"' in page and "/admin/login" in page and 'id="account-menu"' not in page
    login(client)
    page = client.get("/?lang=en").get_data(as_text=True)
    assert 'id="account-menu"' in page and "</svg><span class=\"account-label\">Admin</span><span class=\"live-spin\"" in page
    assert 'aria-label="Admin" title="Admin"' in page  # the wide header shows only the icon
    assert 'href="/admin"' in page and "Log out" in page and 'class="account-login"' not in page


def test_logging_in_from_the_header_goes_to_the_admin_page(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    assert 'href="/admin/login"' in client.get(url).get_data(as_text=True)
    response = client.post("/admin/login", data={"password": "geheim"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/admin")
    # Sent to the login from a page that needs it: back to that page.
    client.post("/admin/logout")
    response = client.post("/admin/login", data={"password": "geheim", "next": "/admin?rechecked=1"})
    assert response.headers["Location"].endswith("/admin?rechecked=1")


def test_a_colour_set_by_hand_wins_and_dates_the_bike(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    row = dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone(), title="Trek Domane AL 2 Gen 4", description="")
    models = db.all_models(conn)
    model = checks.run_check(models, dict(row, overrides={}))["model"]
    sheets = checks.year_sheets(model)
    # A colourway only some years came in.
    colour, years = next((c, {y for y, s in sheets.items() if c in s["colours"]}) for c in checks.colour_choices(model)
                         if 0 < len({y for y, s in sheets.items() if c in s["colours"]}) < len(sheets))
    report = checks.run_check(models, dict(row, overrides={"colour": colour}))
    assert report["colour_set"] == colour and "colour" in report["locked"]
    assert report["year"]["year"] in years
    # The year set by hand still wins over the colour's years.
    other = next(y for y in sheets if y not in years)
    report = checks.run_check(models, dict(row, overrides={"colour": colour, "year": other}))
    assert report["year"]["year"] == other and report["spec_year"] == other and report["colour_set"] == colour
    # A colour the model doesn't have is shown as typed, but doesn't date the bike.
    report = checks.run_check(models, dict(row, overrides={"colour": "No Such Colour"}))
    assert report["colour_set"] is None and report["colour_typed"] == "No Such Colour"


def test_the_match_card_always_has_a_colour_tile_and_the_ad_card_only_a_named_one(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    conn = db.connect(app.config["DB_PATH"])
    # An ad that names no colour: no Kleur tile in the ad card, a "Not known" one in the match card.
    conn.execute("UPDATE checks SET title = 'Trek Domane SL 6 Gen 4 maat 56', description = '' WHERE id = ?", (check_id,))
    conn.commit()
    page = client.get(url + "?lang=en").get_data(as_text=True)
    ad_card, match_card = page.split('class="match-strip')
    assert "COLOUR" not in ad_card and 'class="ms-facts"' in match_card and 'class="ms-photo"' in match_card
    assert "MODEL YEAR" in match_card and "COLOUR" in match_card and "GROUPSET" in match_card
    # The match form sets the model year and the colour at once; "automatic" clears a value.
    login(client)
    assert 'id="edit-match"' in client.get(url + "?edit=1&lang=en").get_data(as_text=True)
    assert client.post(f"/check/{check_id}/override", data={"field": "match", "model": "", "year": "2023", "colour": "Mat petrol"}).status_code == 302
    assert json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0]) == {"year": 2023, "colour": "Mat petrol"}
    page = client.get(url + "?lang=en").get_data(as_text=True).split('class="match-strip')[1]
    assert "Mat petrol" in page
    # The ad names no year: the model year tile shows the year picked for the match, and says the ad gives none.
    year_tile = page.split("MODEL YEAR")[1].split("</small>")[0]
    assert "2023</b>" in year_tile and "No year in the ad" in year_tile and "We go by 2023 for the price" in year_tile
    assert "🔒" not in year_tile
    assert client.post(f"/check/{check_id}/override", data={"field": "match", "model": "", "year": "", "colour": ""}).status_code == 302
    assert conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0] is None
    assert client.post(f"/check/{check_id}/override", data={"field": "match", "model": "no-such-bike"}).status_code == 400


def test_the_colour_editor_offers_the_models_colourways(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("UPDATE checks SET title = 'Trek Domane AL 2 Gen 4' WHERE id = ?", (check_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    model = checks.run_check(db.all_models(conn), dict(row, overrides={}))["model"]
    colour = checks.colour_choices(model)[-1]
    assert colour.encode() in client.get(url + "?edit=1&lang=en").data  # offered in the match form
    assert client.post(f"/check/{check_id}/override", data={"field": "colour", "value": colour}).status_code == 302
    assert json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0]) == {"colour": colour}
    page = client.get(url + "?lang=en").get_data(as_text=True)
    assert colour in page


def test_the_admin_ranking_shows_both_scores_and_orders_from_the_header(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    page = client.get("/admin?lang=en").get_data(as_text=True)
    for rank in ("photo-low", "photo-high", "ad-low", "ad-high", "confidence-low", "confidence-high"):
        assert f'data-rank="{rank}"' in page
    ad_low = page.split('data-rank="ad-low"')[1].split("</table>")[0]
    assert f"/check/{check_id}" in ad_low and ad_low.rindex('class="sc') > ad_low.rindex('class="why"')
    # Both scores in either tab, the order switched from the score column's header.
    row = ad_low.split("<td>", 1)[1]
    assert row.count('<span class="sc') == 2
    assert 'data-sort="photo"' in ad_low and 'data-sort="ad"' in ad_low and 'data-sort="confidence"' in ad_low and 'aria-sort="ascending"' in ad_low
    assert "data-rank-order" not in page and "data-rank-kind" not in page


def test_an_admin_can_delete_a_whole_check(tmp_path, monkeypatch):
    import os
    from webapp import ad_photos
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    folder = os.path.join(ad_photos.folder(app.config["DB_PATH"]), str(check_id))
    os.makedirs(folder)
    client.get(url)  # stores the report
    # Not logged in: no button, and a post is refused.
    assert b"delete-check" not in client.get(url + "?edit=1").data
    assert client.post(f"/check/{check_id}/delete", data={"confirm": check_id}).status_code == 403
    login(client)
    assert b"delete-check" not in client.get(url).data  # only in the edit mode
    page = client.get(url + "?edit=1&lang=nl").data.decode()
    assert "Deze check verwijderen" in page and "Definitief verwijderen" in page
    # Without the ticked box (or with another check's number) nothing goes.
    assert client.post(f"/check/{check_id}/delete").status_code == 400
    assert client.post(f"/check/{check_id}/delete", data={"confirm": check_id + 1}).status_code == 400
    assert client.get(url).status_code == 200
    response = client.post(f"/check/{check_id}/delete", data={"confirm": check_id})
    assert response.status_code == 302 and f"/admin?deleted={check_id}" in response.headers["Location"]
    conn = db.connect(app.config["DB_PATH"])
    assert conn.execute("SELECT COUNT(*) FROM checks WHERE id = ?", (check_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM check_results WHERE check_id = ?", (check_id,)).fetchone()[0] == 0
    assert not os.path.exists(folder)
    assert client.get(url).status_code == 404
    assert "Klaar: check" in client.get(response.headers["Location"] + "&lang=nl").data.decode()
    assert client.post(f"/check/{check_id}/delete", data={"confirm": check_id}).status_code == 404


def test_the_ad_card_sets_all_its_values_in_one_go(tmp_path, monkeypatch):
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    conn = db.connect(app.config["DB_PATH"])
    stored = lambda: json.loads(conn.execute("SELECT overrides FROM checks WHERE id = ?", (check_id,)).fetchone()[0] or "{}")
    data = {"field": "ad", "year": "2020", "size": "54", "groupset": "105:3", "electronic": "1"}
    response = client.post(f"/check/{check_id}/override", data=data)
    assert response.status_code == 302 and response.headers["Location"].endswith("#edit-ad")
    assert stored() == {"year": 2020, "size": "54", "groupset": {"key": "105", "tier": 3, "electronic": True}}
    # Left on automatic (empty), a value goes back to the matching; the others stay locked.
    client.post(f"/check/{check_id}/override", data=dict(data, year=""))
    assert stored() == {"size": "54", "groupset": {"key": "105", "tier": 3, "electronic": True}}
    # The form shows what's locked as picked, and the automatic value for the rest.
    page = client.get(url + "?edit=1&lang=en").get_data(as_text=True)
    form = page.split('id="edit-ad"')[1].split("</details>")[0]
    assert "<option selected>54</option>" in form and "Automatic: 2022" in form
    # A bad value refuses the whole form.
    assert client.post(f"/check/{check_id}/override", data=dict(data, year="1890")).status_code == 400
    assert stored() == {"size": "54", "groupset": {"key": "105", "tier": 3, "electronic": True}}


def test_the_match_picker_shows_the_catalogue_per_model_year(tmp_path, monkeypatch):
    """The "Our match" pencil opens the match picker: the candidate models, each with its catalogue model years,
    their colours, main parts and new price, and what's automatic; it posts the same "match" form."""
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    login(client)
    page = client.get(url + "?edit=1&lang=nl").get_data(as_text=True)
    assert 'id="match-picker"' in page and "match-picker.js" in page and "Onze match kiezen" in page
    data = json.loads(page.split('id="match-picker-data">')[1].split("</script>")[0])
    conn = db.connect(app.config["DB_PATH"])
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    auto = checks.run_check(db.all_models(conn), dict(row, overrides={}))
    assert data["auto"]["model"] == auto["model"]["slug"] and data["set"] == {"model": "", "year": "", "colour": ""}
    first = next(m for m in data["models"] if m["slug"] == auto["model"]["slug"])
    assert first["pct"] and first["years"] and first["years"] == sorted(first["years"], key=lambda y: -y["year"])
    year = next(y for y in first["years"] if y["parts"])
    assert {p["key"] for p in year["parts"]} >= {"Frame", "Groupset"}
    assert all(y["image"] for y in first["years"])  # each model year with its own photo
    # The texts in the visitor's language; every model year to pick, also one the catalogue hasn't.
    assert data["t"]["automatic"] == "Automatisch" and data["years"][0] >= data["years"][-1]
    # Another model from the search comes from its own address, for an admin only.
    other = next(m for m in db.all_models(conn) if "Madone" in m["name"])
    more = client.get(data["more"].replace("SLUG", other["slug"])).get_json()
    assert more["slug"] == other["slug"] and more["years"]
    assert client.get(data["more"].replace("SLUG", "no-such-bike")).status_code == 404
    client.post("/admin/logout")
    assert client.get(data["more"].replace("SLUG", other["slug"])).status_code == 302
    assert 'id="match-picker"' not in client.get(url + "?edit=1").get_data(as_text=True)


def test_a_year_set_by_hand_is_not_shown_as_the_ads_year(tmp_path, monkeypatch):
    """Check 218: the ad gives no year and the match was set to 2022. The price and specs go by 2022, but the year
    tiles, the heading and the comparisons don't say the ad gives one."""
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("UPDATE checks SET title = 'Trek Domane SL 6 maat 56', description = '' WHERE id = ? ", (check_id,))
    conn.commit()
    login(client)
    client.post(f"/check/{check_id}/override", data={"field": "match", "model": "", "year": "2022", "colour": ""})
    row = dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone())
    report = checks.run_check(db.all_models(conn), dict(row, overrides={"year": 2022}))
    assert report["ad_year"] is None and report["year"]["year"] == 2022
    assert all(str(label) != "Year" for label, _value in report["facts"])
    assert checks.ad_facts(report, 2000)["year_stated"] is False
    page = client.get(url + "?lang=en").get_data(as_text=True)
    ad_card, match_card = page.split('class="match-strip')
    assert ">Year<" not in ad_card
    # The match card's tile shows the matched year (Roland, 19 Nov), saying the ad gives none.
    year_tile = match_card.split("MODEL YEAR")[1].split("</small>")[0]
    assert "2022</b>" in year_tile and "No year in the ad" in year_tile and "Not known" not in year_tile
    # The ad's own year stays, also next to a different one set by hand.
    report = checks.run_check(db.all_models(conn), dict(row, title=TITLE, overrides={"year": 2021}))
    assert report["ad_year"] == 2022 and report["year"]["year"] == 2021
    assert any(str(label) == "Year" and value == "2022" for label, value in report["facts"])


def test_the_model_year_tile_shows_one_matched_year_not_a_range(tmp_path, monkeypatch):
    """Roland, 19 Nov: the tile shows the year we matched, also when only the generation's years are known."""
    app, client, url, check_id = setup(tmp_path, monkeypatch)
    url = client.post("/check", data={"title": "Specialized Tarmac SL6 Tiagra", "asking_price": "1200",
                                      "rider_height": "180"}).headers["Location"]
    tile = client.get(url + "?lang=en").get_data(as_text=True).split('class="match-strip')[1]
    tile = tile.split("MODEL YEAR")[1].split("</small>")[0]
    assert "2019</b>" in tile and "–" not in tile.split("</b>")[0]
