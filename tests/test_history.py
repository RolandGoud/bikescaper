from brand_scrapers import history


def test_trek_years_reads_the_range_trek_gives():
    assert history.trek_years("2021 - 2023") == [2021, 2022, 2023]
    assert history.trek_years("2019") == [2019]
    assert history.trek_years(None) == []


def test_generations_share_a_line():
    assert history.line_of("Domane AL 2 Gen 4") == history.line_of("Domane AL 2 gen 3") == history.line_of("Domane AL 2 Disc")
    assert history.line_of("Domane AL 2 Gen 4") != history.line_of("Domane AL 3 Gen 4")
    assert history.generation("Madone SL 6 Gen 7") == 7 and history.generation("Domane AL 2 Disc") == 0


def test_giant_year_comes_from_the_title():
    assert history.giant_year("<title>Defy Advanced 2 (2021) | Giant Bicycles Nederland") == 2021
    assert history.giant_year("<title>Giant Bicycles Nederland") is None


def test_site_sheets_win_over_wayback_copies(tmp_path, monkeypatch):
    import json
    from webapp import seed
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    (tmp_path / "data" / "years" / "Acme.json").write_text(json.dumps({"checked_on": "2026-01-01", "years": [2021, 2022], "models": {
        "Roadie": {"2021": {"captured": "2021-04-01", "specs": {"Frame": "old"}}, "2022": {"captured": "2022-04-01", "unreadable": True}}}}))
    (tmp_path / "data" / "years" / "site" / "Acme.json").write_text(json.dumps({"checked_on": "2026-02-01", "years": [2020, 2021, 2022], "models": {
        "Roadie": {"2020": {"source": "site", "specs": {"Frame": "older"}}, "2022": {"source": "site", "specs": {"Frame": "site"}}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    found = seed.year_specs("Acme", "Roadie", {})
    assert found["checked"] == [2020, 2021, 2022] and found["checked_on"] == "2026-02-01"
    assert {y: e["specs"]["Frame"] for y, e in found["years"].items()} == {"2020": "older", "2021": "old", "2022": "site"}


def test_site_sheets_keep_the_wayback_price(tmp_path, monkeypatch):
    import json
    from webapp import seed
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    (tmp_path / "data" / "years" / "Acme.json").write_text(json.dumps({"checked_on": "2026-01-01", "years": [2021], "models": {
        "Roadie": {"2021": {"captured": "2021-04-01", "url": "https://web.example/roadie", "price": 2499.0, "specs": {"Frame": "old"}}}}}))
    (tmp_path / "data" / "years" / "site" / "Acme.json").write_text(json.dumps({"checked_on": "2026-02-01", "years": [2021], "models": {
        "Roadie": {"2021": {"source": "site", "price": None, "specs": {"Frame": "site"}}}}}))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    entry = seed.year_specs("Acme", "Roadie", {})["years"]["2021"]
    assert entry["specs"]["Frame"] == "site" and entry["price"] == 2499.0
    assert entry["price_url"] == "https://web.example/roadie" and entry["price_captured"] == "2021-04-01"


def test_year_tabs_reach_back_to_the_earliest_sheet():
    from datetime import date
    from webapp import checks
    model = {"name": "Defy Advanced 2", "brand": "Giant", "seen_on": "2026-07-01", "url": "u", "specs": {"Frame": "x"},
             "year_specs": {"checked": [2017, 2018], "years": {"2017": {"source": "site", "specs": {"Frame": "y"}}}}}
    tabs = checks.year_tabs(model, today=date(2026, 10, 24))
    assert tabs[0]["year"] == 2017 and tabs[0]["state"] == "archive"
    assert checks.year_tabs(dict(model, year_specs={}), today=date(2026, 10, 24))[0]["year"] == checks.FIRST_SPEC_YEAR


def test_canyon_filter_chips_are_not_parts():
    from brand_scrapers.archive import read_specs
    specs, _ = read_specs("Generic", "", "https://example.test/")
    assert specs == {}
    from brand_scrapers import archive
    chips = {"Achterderailleur": "Ultegra105Dura AceBekijk meerBekijk minder", "Gewicht": "8.80 kg"}
    orig = archive._generic_pairs
    archive._generic_pairs = lambda page: list(chips.items())
    try:
        specs, _ = read_specs("Factor", "", "https://example.test/")
    finally:
        archive._generic_pairs = orig
    assert "Achterderailleur" not in specs and specs.get("Gewicht") == "8.80 kg"


def test_predecessor_recheck_uses_the_catalogue_groupset():
    from brand_scrapers.archive import _still_a_predecessor
    meta = {"name": "Aeroad CF SLX 8", "sheet_name": "aeroad-cf-slx-8-disc-etap"}
    assert _still_a_predecessor(meta, {})
    assert not _still_a_predecessor(meta, {"Shifter": "Shimano Ultegra Di2"})


def test_trek_gives_each_colour_its_own_side_view():
    import json
    from brand_scrapers import history
    full = {"name": "Checkpoint ALR 5", "modelYearIntroAndCurrent": "2021 - 2021",
            "variantAttributesDirectory": [{"options": [
                {"displayName": "Trek Black", "colorSwatchName": "black", "value": "bike_colorswatch_black"},
                {"displayName": "Teal", "colorSwatchName": "tealdark", "value": "bike_colorswatch_tealdark"}]}],
            "assetImageList": [{"imageOption": "A", "images": [{"assetId": "X_A_Alt1"}, {"assetId": "X_A_Primary"}]},
                               {"imageOption": "B", "images": [{"assetId": "X_B_Portrait"}, {"assetId": "X_B_Primary"}]}],
            "variants": [{"imageOption": "A", "variantAttributes": [{"key": "bike_colorSwatch", "value": "bike_colorswatch_black"}]},
                         {"imageOption": "B", "variantAttributes": [{"key": "bike_colorSwatch", "value": "bike_colorswatch_tealdark"}]}]}

    class Fake:
        def get(self, url, binary=False):
            return json.dumps(full if "/full" in url else {"specs": []})

    p = history.trek_product(Fake(), "32557")
    assert p["colour_image_urls"] == {"Trek Black": "https://media.trekbikes.com/image/upload/f_png,w_1200/X_A_Primary",
                                      "Teal": "https://media.trekbikes.com/image/upload/f_png,w_1200/X_B_Primary"}


def test_a_colour_name_gets_a_swatch():
    from webapp import colour_match
    assert colour_match.swatch_css("Trek Black") == colour_match.FAMILY_HEX["black"]
    assert colour_match.swatch_css("Trek Black / Carbon Smoke").startswith("linear-gradient(")
    assert colour_match.swatch_css("Starry Night Artline") is None or colour_match.swatch_css("Starry Night Artline")


def test_trek_lists_the_other_angles_of_each_colour():
    import json
    from brand_scrapers import history
    full = {"name": "Checkpoint ALR 5", "modelYearIntroAndCurrent": "2021 - 2021",
            "variantAttributesDirectory": [{"options": [
                {"displayName": "Trek Black", "colorSwatchName": "black", "value": "bike_colorswatch_black"}]}],
            "assetImageList": [{"imageOption": "A", "images": [{"assetId": "X_A_Alt2", "weight": 1}, {"assetId": "X_A_Primary"},
                                                               {"assetId": "X_A_Alt1", "weight": 2}]}],
            "variants": [{"imageOption": "A", "variantAttributes": [{"key": "bike_colorSwatch", "value": "bike_colorswatch_black"}]}]}

    class Fake:
        def get(self, url, binary=False):
            return json.dumps(full if "/full" in url else {"specs": []})

    angles = history.trek_product(Fake(), "32557")["colour_angle_urls"]["Trek Black"]
    assert [a.rsplit("/", 1)[1] for a in angles] == ["X_A_Alt2", "X_A_Alt1"]  # in Trek's order


def test_giant_angles_are_the_close_ups_of_that_colour():
    from brand_scrapers import giant
    page = " ".join("abcdefghij0123456789/MY25TCRAdvanced2_Color%s.jpg" % s for s in
                    ("AWhite", "AWhite-D1", "AWhite-Rear", "AWhite_Action", "BBlack-D1"))
    angles = giant.colour_angles(page, "TCR Advanced 2", "White")
    assert [a.rsplit("/", 1)[1] for a in angles] == ["MY25TCRAdvanced2_ColorAWhite-D1.jpg",
                                                      "MY25TCRAdvanced2_ColorAWhite-Rear.jpg"]


def test_specialized_old_pages_list_each_colours_views():
    from brand_scrapers import specialized
    page = ('<script>var p = {"attributes":[{"name":"Color","type":"swatch","options":[{"name":"Carbon/Silver Green",'
            '"skus":["94920-0444"],"imageSet":[{"id":"94920-04_SL7-CARB_HERO"},{"id":"94920-04_SL7-CARB_FDSQ"},'
            '{"id":"ROAD-3300__PDP_Carousel_Green_1"},{"id":"94920-04_SL7-CARB_D1-POV"}]}]}]};</script>')
    side, views = specialized.page_colours(page, "u")["Carbon/Silver Green"]
    assert side.split("/")[-1].startswith("94920-04_SL7-CARB_HERO?")
    assert [v.split("/")[-1].split("?")[0] for v in views] == ["94920-04_SL7-CARB_FDSQ", "94920-04_SL7-CARB_D1-POV"]  # no banners


def test_specialized_photos_keep_the_old_page_only_for_its_year(tmp_path, monkeypatch):
    import json
    from brand_scrapers import history, specialized
    (tmp_path / "data" / "years").mkdir(parents=True)
    entries = {"2020": {"url": "https://x/p/1", "ts": "20200401"}, "2024": {"url": "https://x/p/2", "ts": "20240401"}}
    (tmp_path / "data" / "years" / "Specialized.json").write_text(json.dumps({"models": {"Tarmac": entries}}))
    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    monkeypatch.setattr(history, "save_photo", lambda f, b, slug, year, url, colour=None, angle=None: f"{year}_{colour}_{angle}")
    years = {"https://x/p/1": 2021, "https://x/p/2": 2020}  # the second ID now shows a 2020 bike
    monkeypatch.setattr(history, "_specialized_year", lambda page: years[page])
    monkeypatch.setattr(specialized, "page_colours", lambda page, url: {"Red": ("side", ["front"])})

    class Fake:
        def get(self, url, binary=False):
            return url

    history.specialized_photos(fetcher=Fake())
    found = json.loads((tmp_path / "data" / "years" / "Specialized.json").read_text())["models"]["Tarmac"]
    assert found["2020"]["colour_images"] == {"Red": "2020_Red_None"} and found["2020"]["colour_angles"] == {"Red": ["2020_Red_1"]}
    assert found["2020"]["image"] == "2020_Red_None" and found["2020"]["colours"] == ["Red"]
    assert "colour_images" not in found["2024"]


def test_specialized_views_match_by_photo_not_spelling():
    from brand_scrapers import history
    live = {"Satin Carbon/Tarmac Black/Clean": ("https://r/image/171341-01_CRUX_HERO-SQUARE?q=80", ["front"])}
    views = history._views_by_photo(live)
    assert views[history._photo_stem("https://r/image/171341-01_CRUX_HERO?q=80")] == ["front"]
    assert views["SATIN CARBON/TARMAC BLACK/CLEAN".casefold()] == ["front"]


def test_giant_reads_current_pages_without_a_year():
    from brand_scrapers import giant

    class Sitemap:
        def get(self, url):
            return "".join(f"<loc>https://www.giant-bicycles.com/nl/{s}</loc>" for s in (
                "contend-ar-1-2025", "contend-ar-1", "contend-ar-1-2021", "bikes-road", "tcr-advanced-2-pc-2027"))

    assert giant.product_urls(Sitemap()) == [f"https://www.giant-bicycles.com/nl/{s}" for s in (
        "contend-ar-1-2025", "contend-ar-1", "tcr-advanced-2-pc-2027")]
    page = ("<title>Contend AR 1 (2026) | All-Rounder Fiets | Giant Bicycles Nederland</title>"
            "<h1>Contend AR 1</h1>")
    assert giant.parse(page, "https://www.giant-bicycles.com/nl/contend-ar-1")["model_year"] == 2026
    assert giant.parse(page, "https://www.giant-bicycles.com/nl/contend-ar-1-2025")["model_year"] == 2025


def test_a_renamed_giant_reads_its_earlier_names_years():
    class Pages:
        def get(self, url):
            year = {"tcr-advanced-2-pc-2027": 2027, "tcr-advanced-2-2025": 2025, "tcr-advanced-2": 2026,
                    "tcr-advanced-2-2026": 2026}.get(url.rsplit("/", 1)[1])
            # a year without a page of its own serves the newest one
            year = year or (2027 if "-pc" in url else 2026)
            return (f"<title>TCR Advanced 2 ({year}) | Race Fiets | Giant Bicycles Nederland</title><h1>TCR Advanced 2</h1>"
                    "<div class=label>Frame</div><div class=value>Advanced-grade composite</div>"
                    "<div class=label>Achterderailleur</div><div class=value>Shimano 105</div>"
                    "<div class=label>Vork</div><div class=value>Advanced-grade composite</div>"
                    + "".join(f"<div class=label>{k}</div><div class=value>Shimano 105</div>" for k in (
                        "Remmen", "Crankstel", "Cassette", "Ketting", "Voorderailleur", "Shifters", "Wielen")))

    found = history.collect("Giant", [("TCR Advanced 2-PC", "https://www.giant-bicycles.com/nl/tcr-advanced-2-pc-2027")],
                            Pages(), range(2025, 2027))
    years = found["TCR Advanced 2-PC"]
    assert sorted(years) == ["2025", "2026"]
    assert years["2025"]["sheet_name"] == "TCR Advanced 2"
    assert years["2025"]["url"].endswith("/tcr-advanced-2-2025")


def test_specialized_sitemap_lists_pages_the_shop_dropped():
    from brand_scrapers import specialized

    class Fake:
        pages = {
            specialized.SITEMAP: "<sitemapindex><sitemap><loc>https://media.specialized.com/sitemaps/NL-Category-nl-EUR.xml</loc>"
                                 "</sitemap><sitemap><loc>https://media.specialized.com/sitemaps/NL-Product-nl-EUR.xml</loc></sitemap>",
            "https://media.specialized.com/sitemaps/NL-Product-nl-EUR.xml":
                "<url><loc>https://www.specialized.com/nl/p/216955</loc></url>"
                "<url><loc>https://www.specialized.com/nl/tarmac-sl8-expert-sram-rival-axs/p/216955</loc></url>"
                "<url><loc>https://www.specialized.com/nl/s-works-venge/p/171336</loc></url>",
        }

        def get(self, url):
            return self.pages.get(url)

    assert specialized.sitemap_urls(Fake()) == [
        "https://www.specialized.com/nl/nl/tarmac-sl8-expert-sram-rival-axs/p/216955",
        "https://www.specialized.com/nl/nl/s-works-venge/p/171336"]


def test_specialized_archived_keeps_what_it_had_and_adds_other_years(tmp_path, monkeypatch):
    import json
    import sqlite3
    from brand_scrapers import specialized
    (tmp_path / "data" / "years" / "archived").mkdir(parents=True)
    (tmp_path / "data" / "years" / "site").mkdir()
    old = {"name": "S-Works Venge", "sku": "171336", "model_year": 2020, "years": [2020], "specifications": {}}
    (tmp_path / "data" / "years" / "archived" / "Specialized.json").write_text(json.dumps([old]))
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE models (brand, name, source_file)")
    conn.executemany("INSERT INTO models VALUES ('Specialized', ?, ?)", [
        ("S-Works Venge", "data/years/archived/Specialized.json"), ("Tarmac SL9 Comp", "data/Specialized/s.json"),
        # a row from before a merge renamed the bike: not a bike on sale
        ("S-Works Venge - SRAM", "data/years/archived/Specialized.json")])
    conn.commit()
    urls = ["https://www.specialized.com/nl/nl/s-works-venge/p/171336",          # already there
            "https://www.specialized.com/nl/nl/s-works-venge/p/154592",          # another year of it
            "https://www.specialized.com/nl/nl/tarmac-sl8-expert/p/216955",      # new
            "https://www.specialized.com/nl/nl/tarmac-sl9-comp/p/4293528",       # on sale
            "https://www.specialized.com/nl/nl/s-works-venge-frameset/p/171335"]  # a frameset
    bikes = {"154592": ("S-Works Venge", 2019), "216955": ("Tarmac SL8 Expert – SRAM Rival AXS", 2024)}
    fetched = []

    def parse(page, url):
        name, year = bikes[url.rsplit("/", 1)[-1]]
        return {"name": name, "model_year": year, "sku": url.rsplit("/", 1)[-1], "category": "Race", "price": 1,
                "specifications": {}, "image_url": None, "color_names": []}

    class Fake:
        def get(self, url):
            fetched.append(url)
            return "page"

    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    monkeypatch.setattr(specialized, "sitemap_urls", lambda _f: urls)
    monkeypatch.setattr(specialized, "parse", parse)
    monkeypatch.setattr(history, "recognised", lambda _s: 99)
    found = history.pages_archived("Specialized", None, str(db), fetcher=Fake())
    assert sorted(fetched) == sorted(urls[1:3])
    assert [(b["name"], b["years"]) for b in found] == [("S-Works Venge", [2019, 2020]),
                                                         ("Tarmac SL8 Expert - SRAM Rival AXS", [2024])]
    sheets = json.loads((tmp_path / "data" / "years" / "site" / "Specialized.json").read_text())["models"]
    assert sorted(sheets["S-Works Venge"]) == ["2019"] and sorted(sheets["Tarmac SL8 Expert - SRAM Rival AXS"]) == ["2024"]


def test_cannondale_archived_pages_are_not_keyed_by_product_number(tmp_path, monkeypatch):
    import sqlite3
    from brand_scrapers import cannondale
    import json
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    (tmp_path / "data" / "years" / "archived").mkdir()
    (tmp_path / "data" / "years" / "archived" / "Cannondale.json").write_text(json.dumps(
        [{"name": "Synapse 2", "sku": "C1", "model_year": 2022, "years": [2022], "specifications": {}}]))
    db = tmp_path / "t.db"
    sqlite3.connect(db).execute("CREATE TABLE models (brand, name, source_file)")
    cdx = tmp_path / "cdx"
    cdx.mkdir()
    (cdx / "Cannondale.txt").write_text(
        "20220401000000 https://www.cannondale.com/nl-nl/bikes/road/race/supersix-evo/supersix-evo-3\n"
        "20220401000000 https://www.cannondale.com/nl-nl/bikes/road/endurance/synapse/synapse-2\n")
    names = {"supersix-evo-3": "SuperSix EVO 3", "synapse-2": "Synapse 2"}

    def parse(page, url):
        return {"name": names[url.split("/")[-1]], "model_year": 2022, "sku": "C1", "category": "Race",
                "specifications": {}, "image_url": None, "color_names": []}

    class Fake:
        def get(self, url):
            return "page"

    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    monkeypatch.setattr(cannondale, "parse", parse)
    monkeypatch.setattr(history, "recognised", lambda _s: 99)
    found = history.pages_archived("Cannondale", str(cdx), str(db), fetcher=Fake())
    assert sorted(b["name"] for b in found) == ["SuperSix EVO 3", "Synapse 2"]
    assert not any("skus" in b for b in found)


def test_a_trek_product_without_a_model_year_takes_its_photos_year():
    import json
    from brand_scrapers import history
    full = {"name": "Domane AL 2 Gen 4", "modelYearIntroAndCurrent": None,
            "variantAttributesDirectory": [{"options": [
                {"displayName": "Crimson to Dark Carmine Fade", "colorSwatchName": "red_reddark",
                 "value": "bike_colorswatch_red_reddark"}]}],
            "assetImageList": [{"imageOption": "C", "images": [{"assetId": "DomaneAL2-24-41587-C-Primary"}]}],
            "variants": [{"imageOption": "C", "variantAttributes": [
                {"key": "bike_colorSwatch", "value": "bike_colorswatch_red_reddark"}]}]}

    class Fake:
        def get(self, url, binary=False):
            return json.dumps(full if "/full" in url else {"specs": []})

    p = history.trek_product(Fake(), "41587")
    assert p["years"] == [2024] and p["years_from_photos"]
    assert list(p["colour_image_urls"]) == ["Crimson to Dark Carmine Fade"]


def test_trek_product_numbers_in_old_and_new_page_urls():
    from brand_scrapers import history
    base = "https://www.trekbikes.com/nl/nl_NL/fietsen/racefietsen/prestatiegerichte-racefietsen/domane/domane-al"
    assert history.trek_code(base + "/domane-al-2/a/23522/") == "23522"
    assert history.trek_code(base + "/f/F221-5/domane-al-2-gen-4/41587/") == "41587"
    assert history.trek_code(base + "/f/F221-5/domane-al-2-gen-4/41587/5301359") == "41587"
    assert history.trek_code("https://www.trekbikes.com/nl/nl_NL/fietsen/") is None


def test_a_rerun_keeps_the_years_it_did_not_read_again(tmp_path, monkeypatch):
    """Trek no longer lists a product's older years: they were right, so a new run keeps them."""
    import json
    import sqlite3
    from brand_scrapers import history
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    sheet = tmp_path / "data" / "years" / "site" / "Trek.json"
    sheet.write_text(json.dumps({"years": [2022], "models": {"Domane AL 2 Gen 4": {
        "2022": {"colours": ["Viper Red/Trek Black"], "colour_angles": {"Viper Red/Trek Black": ["a.jpg"]}}}}}))
    db = tmp_path / "t.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE models (brand, name, url)")
    conn.execute("INSERT INTO models VALUES ('Trek', 'Domane AL 2 Gen 4', 'x')")
    conn.commit()
    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    monkeypatch.setattr(history, "trek_codes", lambda folder: [])
    monkeypatch.setattr(history, "trek_collect", lambda models, fetcher, years, codes: {
        "Domane AL 2 Gen 4": {"2025": {"colours": ["Crimson to Dark Carmine Fade"]}}})
    history.run(["Trek"], str(db), range(2020, 2027), names=["Domane AL 2 Gen 4"])
    years = json.loads(sheet.read_text())["models"]["Domane AL 2 Gen 4"]
    assert sorted(years) == ["2022", "2025"]
    assert years["2022"]["colour_angles"]  # as it was


def test_a_rerun_keeps_a_year_set_by_hand(tmp_path, monkeypatch):
    import json
    import sqlite3
    from brand_scrapers import history
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    sheet = tmp_path / "data" / "years" / "site" / "Trek.json"
    sheet.write_text(json.dumps({"years": [2023], "models": {"Émonda SL 6": {
        "2023": {"colours": ["Trek Black/Radioactive Red"], "manual": "by hand"}}}}))
    db = tmp_path / "t.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE models (brand, name, url)")
    conn.execute("INSERT INTO models VALUES ('Trek', 'Émonda SL 6', 'x')")
    conn.commit()
    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    monkeypatch.setattr(history, "trek_codes", lambda folder: [])
    monkeypatch.setattr(history, "trek_collect", lambda models, fetcher, years, codes: {
        "Émonda SL 6": {"2023": {"colours": ["Crimson"]}}})
    history.run(["Trek"], str(db), range(2020, 2027), names=["Émonda SL 6"])
    assert json.loads(sheet.read_text())["models"]["Émonda SL 6"]["2023"]["colours"] == ["Trek Black/Radioactive Red"]


def test_a_build_renamed_between_years_is_one_bike(tmp_path, monkeypatch):
    import json
    bikes = [{"name": "Tarmac SL8 Expert - SRAM Rival AXS", "sku": "216955", "model_year": 2024, "years": [2024]},
             {"name": "Tarmac SL8 Expert - SRAM Rival eTAP AXS", "sku": "4221538", "model_year": 2025, "years": [2025]},
             {"name": "Crux Expert - SRAM Rival XPLR eTAP AXS", "sku": "1", "model_year": 2025, "years": [2025]},
             {"name": "Tarmac SL8 Pro - SRAM Force AXS", "sku": "2", "model_year": 2026, "years": [2026]}]
    kept, renamed = history.merge_renamed(bikes, current=["Crux Expert - SRAM Rival XPLR AXS"])
    assert [(b["name"], b["years"], b.get("skus")) for b in kept] == [
        ("Tarmac SL8 Expert - SRAM Rival eTAP AXS", [2024, 2025], ["216955"]), ("Tarmac SL8 Pro - SRAM Force AXS", [2026], None)]
    assert renamed == {"Tarmac SL8 Expert - SRAM Rival AXS": "Tarmac SL8 Expert - SRAM Rival eTAP AXS",
                       "Crux Expert - SRAM Rival XPLR eTAP AXS": "Crux Expert - SRAM Rival XPLR AXS"}
    (tmp_path / "data" / "years" / "site").mkdir(parents=True)
    (tmp_path / "data" / "years" / "site" / "Specialized.json").write_text(json.dumps({"years": [2024], "models": {
        "Tarmac SL8 Expert - SRAM Rival AXS": {"2024": {"price": 6500}}}}))
    monkeypatch.setattr(history, "ROOT", str(tmp_path))
    history.rename_sheets("Specialized", renamed)
    models = json.loads((tmp_path / "data" / "years" / "site" / "Specialized.json").read_text())["models"]
    assert models == {"Tarmac SL8 Expert - SRAM Rival eTAP AXS": {"2024": {
        "price": 6500, "sheet_name": "Tarmac SL8 Expert - SRAM Rival AXS"}}}


def test_seed_folds_a_renamed_build_into_the_bike_it_is_now(tmp_path, monkeypatch):
    import json
    from webapp import db, seed
    (tmp_path / "data" / "years" / "archived").mkdir(parents=True)
    (tmp_path / "data" / "years" / "archived" / "Specialized.json").write_text(json.dumps(
        [{"name": "Tarmac SL8 Expert - SRAM Rival eTAP AXS"}]))
    monkeypatch.setattr(seed, "ROOT", str(tmp_path))
    conn = db.connect(str(tmp_path / "t.db"))
    rel = "data/years/archived/Specialized.json"
    for name in ("Tarmac SL8 Expert - SRAM Rival AXS", "Tarmac SL8 Expert - SRAM Rival eTAP AXS"):
        conn.execute("INSERT INTO models (brand, name, slug, source_file, specs, colors) VALUES ('Specialized', ?, ?, ?, '{}', '[]')",
                     (name, seed.slugify(name), rel))
    old, new = (conn.execute("SELECT id FROM models WHERE name = ?", (n,)).fetchone()[0]
                for n in ("Tarmac SL8 Expert - SRAM Rival AXS", "Tarmac SL8 Expert - SRAM Rival eTAP AXS"))
    conn.execute("INSERT INTO checks (listing_url, title, model_id) VALUES ('u', 't', ?)", (old,))
    conn.commit()
    assert seed.merge_renamed_models(conn) == 1
    assert [r[0] for r in conn.execute("SELECT name FROM models")] == ["Tarmac SL8 Expert - SRAM Rival eTAP AXS"]
    assert conn.execute("SELECT model_id FROM checks").fetchone()[0] == new
    assert seed.merge_renamed_models(conn) == 0


def test_trek_reads_a_carried_over_model_year_range():
    from brand_scrapers import trek
    assert trek.model_years("2027") == [2027] and trek.model_year("2027") == 2027
    assert trek.model_years("2026-2027") == [2026, 2027] and trek.model_year("2026-2027") == 2027
    assert trek.model_years(None) == [] and trek.model_year("") is None


def test_trek_files_a_product_under_every_year_trek_lists_it(tmp_path, monkeypatch):
    """The 2026 Domane AL 2 Gen 4 (41587, photos "-24-") is listed for 2026 next to its 2027 successor (80164), and
    the Checkpoint SL 6 AXS Gen 3 (55098, photos "-26-") is a 2026 bike Trek now lists as 2027: each year gets a sheet."""
    from brand_scrapers import history
    monkeypatch.setattr(history, "ROOT", str(tmp_path))  # no Wayback year file
    monkeypatch.setattr(history, "recognised", lambda specs: 99)
    monkeypatch.setattr(history, "save_photo", lambda *a, **k: "p.jpg")
    monkeypatch.setattr(history, "colour_photos", lambda *a, **k: {})
    shots = {"41587": ("Domane AL 2 Gen 4", 24), "80164": ("Domane AL 2 Gen 4", 27),
             "55098": ("Checkpoint SL 6 AXS Gen 3", 26)}
    monkeypatch.setattr(history, "trek_product", lambda fetcher, code: {
        "code": code, "name": shots[code][0], "years": [2000 + shots[code][1]], "years_from_photos": True,
        "url": f"https://www.trekbikes.com/nl/nl_NL/p/{code}/", "sheet_years": None, "specs": {"Frame": "x"},
        "colours": [], "colour_image_urls": {}, "image_url": None, "category": ""})
    listed = [{"code": "41587", "model_years": [2026]}, {"code": "80164", "model_years": [2027]},
              {"code": "55098", "model_years": [2027]}]
    models = [("Domane AL 2 Gen 4", "https://www.trekbikes.com/nl/nl_NL/p/80164/"),
              ("Checkpoint SL 6 AXS Gen 3", "https://www.trekbikes.com/nl/nl_NL/p/55098/")]
    found = history.trek_collect(models, None, range(2020, 2028), [], listed=listed)
    domane = found["Domane AL 2 Gen 4"]
    assert sorted(domane) == ["2024", "2026", "2027"]
    assert domane["2026"]["url"].endswith("/41587/") and domane["2027"]["url"].endswith("/80164/")
    assert sorted(found["Checkpoint SL 6 AXS Gen 3"]) == ["2026", "2027"]


def test_trek_catalogue_takes_the_newest_of_two_products_with_one_name(monkeypatch):
    from brand_scrapers import history, trek
    monkeypatch.setattr(trek, "listed", lambda fetcher: [
        {"code": "80164", "name": "Domane AL 2 Gen 4", "price": 999.0, "model_year": 2027},
        {"code": "41587", "name": "Domane AL 2 Gen 4", "price": 999.0, "model_year": 2026},
        {"code": "55098", "name": "Checkpoint SL 6 AXS Gen 3", "price": 4999.0, "model_year": 2027}])
    monkeypatch.setattr(history, "trek_product", lambda fetcher, code: {
        "specs": {"Frame": "x"}, "colours": [], "category": "", "image_url": None, "colour_image_urls": {}})
    assert [b["sku"] for b in trek.scrape(None)] == ["80164", "55098"]
