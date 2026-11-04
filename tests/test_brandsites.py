import json

from brand_scrapers import brandsites, mantel


def test_site_words_leave_the_name():
    assert brandsites.clean_name("Oltre XR4 Disc - Dura Ace 11sp 52/36") == "Oltre XR4 Disc Dura-Ace"
    assert brandsites.clean_name("Infinito CV - Infinito CV Disc - Force eTap AXS 12sp") == "Infinito CV Disc Force eTap AXS"
    assert brandsites.clean_name("Aeroad CFR Disc AXS New") == "Aeroad CFR Disc AXS"
    assert brandsites.clean_name("Endurace CF SL Disc 8.0 Di2") == "Endurace CF SL Disc 8 Di2"
    assert brandsites.clean_name("O2 &#8211; Miami Blue") == "O2"
    assert brandsites.clean_name("Road Super Light") == "O2 VAM"  # Factor's name for the O2 VAM's page
    assert brandsites.clean_name("O2 VAM Custom Bike Build") == ""
    assert brandsites.clean_name("Men's Tarmac SL5 Comp") == "Tarmac SL5 Comp"
    assert brandsites.clean_name("TARMAC ELITE") == "Tarmac Elite"


def test_canyons_two_spellings_are_one_name():
    assert brandsites.key("Aeroad CF SL Disc 8.0") == brandsites.key("Aeroad CF SL 8 Disc")
    assert brandsites.key("Men's Tarmac Comp") == brandsites.key("Tarmac Comp")


def test_specs_read_the_sites_labels():
    specs = brandsites.specs_of([{"label": label, "value": value} for label, value in [
        ("Shift-/ Brake Lever", "Shimano 105 R7020"), ("Brake Rotor", "Shimano RT800"), ("Material", "Carbon"),
        ("BB", "Pressfit 41"), ("Sprocket", "11-30"), ("Manuals and Accessories", "Manual"), ("53", "507")]])
    assert specs == {"Shifter": "Shimano 105 R7020", "Remschijf": "Shimano RT800", "Material": "Carbon",
                     "Bottom bracket": "Pressfit 41", "Cassette": "11-30"}


ROWS = [{"label": label, "value": value} for label, value in [
    ("Rear Derailleur", "Shimano 105"), ("Front Derailleur", "Shimano 105"), ("Shift-/ Brake Lever", "Shimano 105"),
    ("Crank", "Shimano 105"), ("Cassette", "11-30"), ("Fork", "Carbon"), ("Saddle", "Fizik")]]


def entry(**kw):
    out = {"wayback_timestamp": "20200301120000", "original_url": "https://www.canyon.com/en-nl/x.html", "price": 2199,
           "currency": "EUR", "specs": ROWS, "photo_live": True, "photo_url": "https://x/main.png",
           "model_year_source": "page_image_path"}
    return dict(out, **kw)


def test_convert_keeps_euros_and_drops_undated_specialized_pages(tmp_path, monkeypatch):
    (tmp_path / "data" / "Canyon").mkdir(parents=True)
    (tmp_path / "data" / "Canyon" / "canyon_bikes_20260101.json").write_text(json.dumps(
        [{"name": "Endurace CF 7", "category": "Endurance"}]))
    monkeypatch.setattr(mantel, "ROOT", str(tmp_path))
    raw = {"models": {
        "Canyon": {"Endurace CF 7.0": {"2020": entry(model_year=2020)},
                   "Aeroad CF SL 8.0": {"2019": entry(model_year=2019, currency="GBP", price=2399)}},
        "Specialized": {"S-Works Tarmac SL4": {"2019": entry(model_year=2019, model_year_source="capture_date_guess")},
                        "Aethos Expert": {"2021": entry(model_year=2021, model_year_source="page_article_number")}}}}
    out = brandsites.convert(raw)
    sheets, lines = out["Canyon"]
    assert set(sheets) == {"Endurace CF 7", "Aeroad CF SL 8"}
    assert sheets["Endurace CF 7"]["2020"]["price"] == 2199.0 and sheets["Endurace CF 7"]["2020"]["source"] == "brandsite"
    gbp = sheets["Aeroad CF SL 8"]["2019"]
    assert gbp["price"] is None and (gbp["price_foreign"], gbp["currency"]) == (2399.0, "GBP")
    assert [line["name"] for line in lines] == ["Aeroad CF SL 8"]
    # Specialized's page of a 2014 bike, still online in 2019, gives that bike no 2019
    assert set(out["Specialized"][0]) == {"Aethos Expert"}


def test_the_pages_other_photos_become_that_years_angles(tmp_path, monkeypatch):
    monkeypatch.setattr(mantel, "ROOT", str(tmp_path))
    raw = {"models": {"Factor": {"O2 VAM": {"2020": entry(
        model_year=2020, model_year_source="capture_date_guess",
        gallery=["https://x/main.png", "https://x/side.jpg", "https://x/gone.jpg", "https://x/bb.jpg"],
        gallery_live=[True, True, False, True])}}}}
    saved = lambda brand, slug, year, url, n=None: f"{brand}/years/{slug}_{year}_brandsite{f'_{n}' if n else ''}.jpg"
    [sheet] = brandsites.convert(raw, saved)["Factor"][0]["O2 VAM"].values()
    assert sheet["image"] == "Factor/years/o2vam_2020_brandsite.jpg"
    assert sheet["colour_angles"] == {"": ["Factor/years/o2vam_2020_brandsite_1.jpg",
                                           "Factor/years/o2vam_2020_brandsite_2.jpg"]}
    assert sheet["year_guessed"] is True


def test_brand_sites_come_before_the_shops(tmp_path, monkeypatch):
    from webapp import seed
    for folder in ("brandsites", "uk"):
        (tmp_path / "data" / "years" / folder).mkdir(parents=True)
    (tmp_path / "data" / "years" / "uk" / "Acme.json").write_text(json.dumps({"checked_on": "2026-11-03", "years": [2020, 2021], "models": {
        "Roadie": {"2020": {"source": "uk", "specs": {"Frame": "uk"}}, "2021": {"source": "uk", "specs": {"Frame": "uk"}}}}}))
    (tmp_path / "data" / "years" / "brandsites" / "Acme.json").write_text(json.dumps({"checked_on": "2026-11-04", "years": [2021], "models": {
        "Roadie": {"2021": {"source": "brandsite", "specs": {"Frame": "brand"}}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    found = seed.year_specs("Acme", "Roadie", {})
    assert {y: e["specs"]["Frame"] for y, e in found["years"].items()} == {"2020": "uk", "2021": "brand"}
    assert found["checked"] == []


def test_brand_site_lines_count_as_discontinued():
    from webapp import checks
    line = {"brand": "Canyon", "name": "Aeroad CF SL 8", "source_file": "data/years/brandsites/lines/Canyon.json",
            "year_specs": {"years": {"2019": {"specs": {"Frame": "x"}}}}}
    assert checks.catalogue_status(line)[0] == "discontinued"
