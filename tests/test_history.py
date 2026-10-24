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
