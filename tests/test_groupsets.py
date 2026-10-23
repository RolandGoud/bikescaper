import pytest

from webapp import db, groupsets, i18n, seed
from webapp.app import create_app
from webapp.groupsets import GENERATIONS, path, upgrades


def en(msg):
    token = i18n.current_language.set("en")
    try:
        return str(msg)
    finally:
        i18n.current_language.reset(token)


def effort(frm, to):
    return path(GENERATIONS[frm], GENERATIONS[to])["effort"]


def test_same_system_mixes():
    assert effort("r7000", "r8000") == 1  # 11-speed 105 to Ultegra
    assert effort("m6100", "m9100") == 1  # 12-speed Deore to XTR
    assert effort("rival-axs", "red-axs") == 1


def test_same_speeds_other_shifting_needs_shifters_and_derailleurs():
    p = path(GENERATIONS["r7000"], GENERATIONS["r8050"])
    assert p["effort"] == 2
    assert any("internal routing" in en(s) for s in p["steps"])  # wired Di2


def test_more_speeds_is_a_new_drivetrain():
    assert effort("r7000", "r7100") == 3
    assert effort("gx-eagle", "gx-eagle-axs") == 2  # same cassette and chain, other shifting


def test_freehub_and_frame_raise_the_effort():
    assert effort("m5100", "m8100") == 4  # HG to Micro Spline
    assert effort("nx-eagle", "gx-eagle") == 4  # HG to XD
    assert effort("5800", "r7100") == 5  # rim brake 11-speed to disc only
    p = path(GENERATIONS["gx-eagle-axs"], GENERATIONS["xx-t"])
    assert p["effort"] == 2 and any("UDH" in en(s) for s in p["steps"])  # AXS pods drive T-Type


def test_brand_switch_on_disc_road_brings_the_calipers():
    steps = [en(s) for s in path(GENERATIONS["r7000"], GENERATIONS["force-22"])["steps"]]
    assert any("Brand switch" in s for s in steps) and any("calipers" in s for s in steps)


def test_upgrades_go_up_and_stay_in_the_discipline():
    found = upgrades("r7000")
    keys = [g["key"] for g, _p in found]
    assert "r8000" in keys and "r9200" in keys and "r7100" in keys
    assert "4700" not in keys and "m8100" not in keys and "rival-axs" not in keys  # lower, MTB, same tier
    assert "9000" not in keys and "9000" in [g["key"] for g, _p in upgrades("5800")]  # older than yours
    assert found[0][0]["brand"] == "Shimano" and found[0][1]["effort"] == 1
    assert upgrades("xx-t") == []  # top tier, newest generation


def test_every_series_has_a_tier_and_every_text_a_translation():
    texts = {label for _key, label in groupsets.DISCIPLINES} | set(groupsets.SHIFT_LABELS.values()) \
        | set(groupsets.FREEHUBS.values()) | {t for pair in groupsets.EFFORT.values() for t in pair}
    for brand, by_discipline in groupsets.LADDERS.items():
        for ladders in by_discipline.values():
            for label, steps in ladders:
                texts.add(label)
                assert all(s["tier"] for s in steps), label
    for g in GENERATIONS.values():
        for other in GENERATIONS.values():
            texts |= {s.text for s in path(g, other)["steps"]}
    for text in texts:
        assert text in i18n.NL, text


def test_page_renders(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/groupsets?lang=nl").data.decode()
    assert "Groepset upgraden" in page and "Dura-Ace Di2 R9200" in page and "modellen met Shimano 105" in page
    page = client.get("/groupsets?have=r7000&lang=en").data.decode()
    assert "Upgrades from Shimano 105 R7000" in page and "Mix and match" in page and "Switching brand" in page
    assert "XTR M9100" in client.get("/groupsets?type=mtb").data.decode()
    assert client.get("/groupsets?have=nonsense").status_code == 200
    models = client.get("/models?groupset=105&lang=en").data.decode()
    assert "With Shimano 105" in models and 'name="groupset" value="105"' in models


def test_one_brand_at_a_time(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    client = app.test_client()
    page = client.get("/groupsets?lang=en").data.decode()
    assert "Dura-Ace Di2 R9200" in page and "Red AXS" not in page  # Shimano first
    page = client.get("/groupsets?brand=SRAM&lang=en").data.decode()
    assert "Red AXS" in page and "Dura-Ace" not in page
    page = client.get("/groupsets?brand=Campagnolo&type=mtb&lang=en").data.decode()
    assert "Super Record" in page and "Mountain bike" not in page  # no MTB groups: back to road
    page = client.get("/groupsets?have=gx-eagle&lang=en").data.decode()  # the groupset sets brand and type
    assert 'aria-current="true">SRAM<' in page and "XX1 Eagle AXS" in page
