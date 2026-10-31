import json

from brand_scrapers import tourbike
from brand_scrapers.archive import read_specs
from webapp import checks, seed


def test_model_page_gives_year_and_price():
    data = {"props": {"pageProps": {"content": {"model": {
        "model": {"name": "Émonda SL 7 Disc AXS ", "year": 2022, "_search": {"priceMin": 6699}},
        "variants": [{"prices": [{"price": 6699}]}, {"prices": [{"price": 6699}]}]}}}}}
    page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    assert tourbike.parse(page) == {"name": "Émonda SL 7 Disc AXS", "year": 2022, "prices": [6699]}
    assert tourbike.parse("<html></html>") is None


def test_names_match_across_the_generation_suffix():
    models = {"Checkpoint ALR 3": {"2025": {"price": 1299}}, "Domane SL 7 Gen 4": {"2024": {"price": 6499}},
              "Domane+ AL 5": {"2024": {"price": 3299}}, "Émonda SL 7 Disc": {"2022": {"price": 5999}}}
    assert seed.tour_bike_prices(models, "Checkpoint ALR 3 Gen 2")["2025"]["price"] == 1299
    assert seed.tour_bike_prices(models, "Domane SL 7 gen 3") == {}  # another generation
    assert seed.tour_bike_prices(models, "Domane AL 5 Gen 4") == {}  # Domane+ is the e-bike
    assert seed.tour_bike_prices(models, "Émonda SL 7")["2022"]["price"] == 5999
    # Both our generations were sold in 2025: the name without one can't say which it is.
    ours = {"Checkpoint ALR 3 Gen 2": {"2024": {}, "2025": {}}, "Checkpoint ALR 3 Gen 3": {"2025": {}}}
    assert seed.tour_bike_prices(models, "Checkpoint ALR 3 Gen 2", ours) == {}


def test_rival_years_come_from_both_the_archive_and_the_site(tmp_path, monkeypatch):
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    (tmp_path / "data" / "years" / "tourbike").mkdir(parents=True)
    (tmp_path / "data" / "years" / "Acme.json").write_text(json.dumps({"checked_on": "2026-01-01", "years": [2025], "models": {
        "Roadie Gen 2": {"2024": {"specs": {}}}, "Roadie Gen 3": {"2025": {"specs": {}}}}}))
    (tmp_path / "data" / "years" / "site" / "Acme.json").write_text(json.dumps({"checked_on": "2026-01-01", "years": [2025], "models": {
        "Roadie Gen 3": {"2026": {"specs": {}}}}}))
    (tmp_path / "data" / "years" / "tourbike" / "Acme.json").write_text(json.dumps({"models": {
        "Roadie": {"2025": {"price": 1999, "url": "u"}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    assert "list_prices" not in seed.year_specs("Acme", "Roadie Gen 2", {})  # 2025 is Gen 3's, on the archive side


def test_german_price_only_fills_a_missing_dutch_one():
    model = {"year_specs": {"years": {"2023": {"price": 3299, "specs": {}}, "2022": {"specs": {}}},
                            "list_prices": {"2022": {"price": 3199, "url": "u"}, "2023": {"price": 3099, "url": "u"}}}}
    assert checks.year_prices(model) == {2022: (3199, True), 2023: (3299, False)}
    assert checks.new_price(model, 2022) == 3199 and checks.new_price(model, 2023) == 3299
    assert checks.new_price(model, 2021) is None


def test_trek_price_is_this_bikes_not_the_one_beside_it():
    page = ('"impressions": [{"id": "41395", "name": "Domane AL 5 Gen 4", "price": "1999.0"},'
            ' {"id": "41587", "name": "Domane AL 2 Gen 4", "price": "999.0"}]')
    assert read_specs("Trek", page, "https://www.trekbikes.com/nl/nl_NL/x/p/41587/")[1] == 999.0
    assert read_specs("Trek", page, "https://www.trekbikes.com/nl/nl_NL/x/p/33037/")[1] is None


def test_model_page_marks_a_german_price_with_an_asterisk(tmp_path):
    from webapp import db as webdb
    from webapp.app import create_app
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(webdb.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/models/trek-emonda-slr-7?lang=nl").get_data(as_text=True)
    assert "(Duitse adviesprijs)" not in page
    assert "Nieuw € 8.499*" in page or "Nieuw €8.499*" in page
    assert "De betrouwbaarheid kunnen we daarom niet voor 100% garanderen." in page
