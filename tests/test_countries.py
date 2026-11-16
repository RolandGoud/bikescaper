import json
import os

from brand_scrapers import countries


def test_giant_names_lose_the_bike_type_and_brackets():
    assert countries.giant_name("Vélo Route TCR Advanced 3") == "TCR Advanced 3"
    assert countries.giant_name("Bici da corsa TCR Advanced 1-KOM") == "TCR Advanced 1-KOM"
    assert countries.giant_name("TCR Advanced 1 (KOM)") == "TCR Advanced 1 KOM"
    assert countries.giant_name("Propel Advanced SL 0 (Dura-Ace)") == "Propel Advanced SL 0 Dura-Ace"


def test_giant_writes_one_build_several_ways():
    key = countries.giant_key
    assert key("Propel Advanced SL 0 (Dura-Ace)") == key("Propel Advanced SL 0-DA") == key("propel-advanced-sl-0--dura-ace-")
    assert key("TCR Advanced 1 - Pro Compact") == key("tcr-advanced-1-pc")
    assert key("TCR Advanced 1 KOM") != key("TCR Advanced 1")


def test_trek_english_rows_fill_the_dutch_labels():
    specs = countries.trek_specs({"Frame": "500 Series OCLV", "Hub front": "Formula RX-512", "Brake rotor": "Tektro",
                                  "Stuur": "Bontrager Comp", "Handlebar": "Bontrager Comp", "Stem": "Elite",
                                  "Stuurpen": "Bontrager Elite", "Remschijf": "Shimano RT70"})
    assert specs == {"Frame": "500 Series OCLV", "Naaf voor": "Formula RX-512", "Stuur": "Bontrager Comp",
                     "Stuurpen": "Bontrager Elite", "Remschijf": "Shimano RT70"}


def test_known_names_leave_out_price_lists(tmp_path, monkeypatch):
    for rel, data in [("data/Giant/giant_bikes_20261031_164235.json", [{"name": "TCR Advanced 2", "model_year": 2026}]),
                      ("data/years/site/Giant.json", {"models": {"Defy Advanced 1": {"2024": {"sheet_name": "Defy 1"}}}}),
                      ("data/years/tourbike/Giant.json", {"models": {"ARX 16": {"2023": {"price": 399}}}}),
                      ("data/years/countries/Giant.json", [{"name": "TCR Advanced 3"}])]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    monkeypatch.setattr(countries, "ROOT", str(tmp_path))
    assert countries.known_names("Giant") == {"tcradvanced2", "defyadvanced1", "defy1"}
    assert countries.known_years("Giant") == {"TCR Advanced 2": {2026}, "Defy Advanced 1": {2024}}


def test_country_bikes_are_in_the_catalogue_without_a_price():
    """Every bike in data/years/countries/ comes without a price, with the country it was read from."""
    folder = os.path.join(countries.ROOT, "data", "years", "countries")
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), encoding="utf-8") as fh:
            for bike in json.load(fh):
                assert bike["price"] is None and bike["country"] and bike["source"] == "country", bike["name"]
                assert bike["specifications"], bike["name"]


def test_seed_adds_the_country_bikes(tmp_path):
    from webapp import db, seed
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    seed.add_archived(conn)
    row = conn.execute("SELECT price_eur, url, specs FROM models WHERE brand = 'Trek' AND name = 'Domane SL 4 Gen 5'").fetchone()
    assert row is not None and row[0] is None and "/us/" in row[1] and json.loads(row[2])["Frame"]
