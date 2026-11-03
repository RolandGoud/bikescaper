import json

from brand_scrapers import uk


def test_shop_words_leave_the_name():
    assert uk.clean_name("Return Bianchi Oltre XR3 Ultegra 61cm") == "Oltre XR3 Ultegra"
    assert uk.clean_name("Sigma Sports Exclusive SystemSix Ultegra Disc") == "SystemSix Ultegra Disc"
    assert uk.clean_name("Tarmac SL7 Pro Force eTap AXS 1x12-Speed Disc") == "Tarmac SL7 Pro Force eTap AXS Disc"
    assert uk.clean_name("Synapse Carbon 105 Disc Road Womens Bike") == "Synapse Carbon 105 Disc Women's"
    assert uk.clean_name("Tarmac SL7 S-Works eTap Disc") == "S-Works Tarmac SL7 eTap Disc"
    assert uk.clean_name("") == ""


def test_the_words_of_a_name_go_in_any_order():
    assert uk.key("Aria Disc Ultegra") == uk.key("Aria Ultegra Disc")
    assert uk.key("Aethos Pro Sram Force eTap AXS") == uk.key("Aethos Pro - SRAM Force eTAP AXS")
    assert uk.key("Aria Disc") != uk.key("Aria")


def test_specs_read_english_rows():
    specs = uk.specs_of([{"label": label, "value": value} for label, value in [
        ("Frame", "FACT 10r carbon"), ("Drivetrain", "Shimano Ultegra R8000, 11-speed"), ("Chainset", "Shimano Ultegra"),
        ("Chainrings", "52/36T"), ("Brakes", "Shimano RS505, hydraulic disc"), ("Pedals", "Not Included"),
        ("Post Clamp", "Alloy"), ("Shock", "None"), ("Manufacturers disclaimer", "Specs may change")]])
    assert specs == {"Frame": "FACT 10r carbon", "Crankstel": "Shimano Ultegra", "Kettingblad": "52/36T",
                     "Rem": "Shimano RS505, hydraulic disc", "Zadelpenklem": "Alloy",
                     "Achterderailleur": "Shimano Ultegra R8000, 11-speed"}  # Rutland's "Drivetrain"
    # a page with its own rear derailleur row keeps that one
    assert uk.specs_of([{"label": "Rear Derailleur", "value": "SRAM Rival"},
                        {"label": "Drivetrain", "value": "x"}])["Achterderailleur"] == "SRAM Rival"


ROWS = [{"label": label, "value": value} for label, value in [
    ("Rear Derailleur", "Shimano 105"), ("Front Derailleur", "Shimano 105"), ("Shift Levers", "Shimano 105"),
    ("Chainset", "Shimano 105"), ("Cassette", "11-30"), ("Fork", "Carbon"), ("Saddle", "Fizik")]]


def test_convert_keeps_pounds_out_of_the_new_price(tmp_path, monkeypatch):
    from brand_scrapers import mantel
    (tmp_path / "data" / "Bianchi").mkdir(parents=True)
    (tmp_path / "data" / "Bianchi" / "bianchi_bikes_20260101.json").write_text(json.dumps(
        [{"name": "Oltre XR4 CV Ultegra Di2", "category": "Race"}]))
    monkeypatch.setattr(mantel, "ROOT", str(tmp_path))
    entry = {"archived_url": "https://web.archive.org/web/20200301120000/https://www.sigmasports.com/item/x",
             "original_url": "https://www.sigmasports.com/item/x", "shop": "Sigma Sports", "price": 5999.0,
             "currency": "GBP", "specs": ROWS, "photo_live": False, "photo_url": "https://www.sigmasports.com/x.jpg"}
    raw = {"models": {"Bianchi": {
        "Oltre XR4 CV Ultegra Di2": {"2020": dict(entry, model_year=2020)},
        "Aria Ultegra Disc": {"2020": dict(entry, model_year=2020)},
        "Aria Disc Ultegra": {"2021": dict(entry, model_year=2021)},  # the same bike, worded the other way
        "": {"2020": dict(entry, model_year=2020)},  # a page without a name: left out
        "Intenso 105": {"2017": dict(entry, model_year=2017)}}}}  # before 2018: left out
    sheets, lines = uk.convert(raw)["Bianchi"]
    assert set(sheets) == {"Oltre XR4 CV Ultegra Di2", "Aria Ultegra Disc"}
    s = sheets["Oltre XR4 CV Ultegra Di2"]["2020"]
    assert s["captured"] == "2020-03-01" and s["source"] == "uk" and s["shop"] == "Sigma Sports"
    assert s["price"] is None and s["price_gbp"] == 5999.0
    assert s["image"] is None  # the shop no longer serves the photo
    [line] = lines
    assert line["name"] == "Aria Ultegra Disc" and line["years"] == [2020, 2021] and line["source"] == "uk"


def test_uk_lines_count_as_discontinued():
    from webapp import checks
    line = {"brand": "Bianchi", "name": "Aria Ultegra Disc", "source_file": "data/years/uk/lines/Bianchi.json",
            "year_specs": {"years": {"2021": {"specs": {"Frame": "x"}}}}}
    assert checks.catalogue_status(line)[0] == "discontinued"


def test_uk_fills_years_after_mantel(tmp_path, monkeypatch):
    from webapp import seed
    for folder in ("mantel", "uk"):
        (tmp_path / "data" / "years" / folder).mkdir(parents=True)
    (tmp_path / "data" / "years" / "mantel" / "Acme.json").write_text(json.dumps({"checked_on": "2026-11-01", "years": [2021], "models": {
        "Roadie": {"2021": {"source": "mantel", "specs": {"Frame": "mantel"}}}}}))
    (tmp_path / "data" / "years" / "uk" / "Acme.json").write_text(json.dumps({"checked_on": "2026-11-03", "years": [2020, 2021], "models": {
        "Roadie": {"2020": {"source": "uk", "specs": {"Frame": "uk"}}, "2021": {"source": "uk", "specs": {"Frame": "uk"}}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    found = seed.year_specs("Acme", "Roadie", {})
    assert {y: e["specs"]["Frame"] for y, e in found["years"].items()} == {"2020": "uk", "2021": "mantel"}
    assert found["checked"] == [] and found["checked_on"] == "2026-11-03"
