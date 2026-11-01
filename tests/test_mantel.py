import json

from brand_scrapers import mantel


def test_shop_words_leave_the_name():
    assert mantel.clean_name("Checkpoint ALR 4 Gravel Bike") == "Checkpoint ALR 4"
    assert mantel.clean_name("Emonda SL 6 2018") == "Émonda SL 6"
    assert mantel.clean_name("Axial WS Dames Racefiets") == "Axial WS"
    assert mantel.clean_name("Madone SLR 6 Disc Dames") == "Madone SLR 6 Disc Women's"
    assert mantel.clean_name("Vélo de gravel Trek Checkpoint ALR 4 WSD") == "Checkpoint ALR 4 WSD"


def test_generation_comes_from_the_year():
    assert mantel.with_generation("Trek", "Madone SL 6 Disc", 2020) == "Madone SL 6 Disc Gen 6"
    assert mantel.with_generation("Trek", "Domane SL 6", 2021) == "Domane SL 6 Gen 3"
    assert mantel.with_generation("Trek", "Domane SL 6 Gen 4", 2021) == "Domane SL 6 Gen 4"
    assert mantel.with_generation("Giant", "TCR Advanced 2", 2019) == "TCR Advanced 2"


def test_specs_read_dutch_and_french_rows():
    specs = mantel.specs_of([
        {"label": "Remsysteem", "value": "Hydraulische schijfrem"}, {"label": "Type rem", "value": "Shimano 105 R7070"},
        {"label": "Schakelgroep", "value": "Shimano 105"}, {"label": "Kleur", "value": "Zwart"},
        {"label": "Fourche", "value": "Carbone"}, {"label": "Derailleur achter", "value": "Shimano 105 R7000"}])
    assert specs == {"Rem": "Hydraulische schijfrem, Shimano 105 R7070", "Shifter": "Shimano 105",
                     "Voorvork": "Carbon", "Achterderailleur": "Shimano 105 R7000"}
    # the brake model that already says what kind it is keeps just the model
    assert mantel.specs_of([{"label": "Système de freinage", "value": "Frein à disque mécanique"},
                            {"label": "Type de frein", "value": "C550 Spyre, mechanische schijfrem"}])["Rem"] == \
        "C550 Spyre, mechanische schijfrem"


ROWS = [{"label": label, "value": value} for label, value in [
    ("Derailleur achter", "Shimano 105"), ("Voorderailleur", "Shimano 105"), ("Shifters", "Shimano 105"),
    ("Crankstel", "Shimano 105"), ("Cassette", "11-30"), ("Voorvork", "Carbon"), ("Zadel", "Bontrager")]]


def test_convert_matches_ours_and_keeps_the_rest_as_lines(tmp_path, monkeypatch):
    (tmp_path / "data" / "Trek").mkdir(parents=True)
    (tmp_path / "data" / "Trek" / "trek_bikes_20260101.json").write_text(json.dumps(
        [{"name": "Émonda SL 6", "category": "Performance road bikes"}]))
    monkeypatch.setattr(mantel, "ROOT", str(tmp_path))
    entry = {"wayback_timestamp": "20190412093000", "original_url": "https://www.mantel.com/nl/trek-emonda-sl-6",
             "price_eur": 2599, "specs": ROWS, "photo_url_live": None}
    raw = {"models": {"Trek": {
        "Emonda SL 6 2019": {"2019": dict(entry, model_year=2019)},
        "Madone SL 6 Disc": {"2020": dict(entry, model_year=2020, wayback_timestamp="20200501000000")},
        "Domane AL 2": {"2017": dict(entry, model_year=2017)}}}}  # before 2018: left out
    sheets, lines = mantel.convert(raw)["Trek"]
    assert set(sheets) == {"Émonda SL 6", "Madone SL 6 Disc Gen 6"}
    assert sheets["Émonda SL 6"]["2019"]["captured"] == "2019-04-12"
    assert sheets["Émonda SL 6"]["2019"]["source"] == "mantel" and sheets["Émonda SL 6"]["2019"]["price"] == 2599.0
    [line] = lines
    assert line["name"] == "Madone SL 6 Disc Gen 6" and line["years"] == [2020]
    assert line["category"] == "Performance road bikes"  # no Madone of ours to copy it from: the road default
    assert line["url"].startswith("https://web.archive.org/web/20200501000000/")


def test_mantel_fills_only_the_years_the_brand_lacks(tmp_path, monkeypatch):
    from webapp import seed
    (tmp_path / "data" / "years" / "mantel").mkdir(parents=True)
    (tmp_path / "data" / "years" / "Acme.json").write_text(json.dumps({"checked_on": "2026-01-01", "years": [2021], "models": {
        "Roadie": {"2021": {"captured": "2021-04-01", "specs": {"Frame": "brand"}}}}}))
    (tmp_path / "data" / "years" / "mantel" / "Acme.json").write_text(json.dumps({"checked_on": "2026-11-01", "years": [2019, 2021], "models": {
        "Roadie": {"2019": {"source": "mantel", "specs": {"Frame": "mantel"}},
                   "2021": {"source": "mantel", "specs": {"Frame": "mantel"}}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    found = seed.year_specs("Acme", "Roadie", {})
    assert {y: e["specs"]["Frame"] for y, e in found["years"].items()} == {"2019": "mantel", "2021": "brand"}
    assert found["checked"] == [2021]  # Mantel not having a bike says nothing about the brand
    # a brand with only Mantel's sheets still gets them
    (tmp_path / "data" / "years" / "Acme.json").unlink()
    assert seed.year_specs("Acme", "Roadie", {})["years"]["2021"]["specs"]["Frame"] == "mantel"
