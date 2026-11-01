import json
import os

import pytest

from webapp import db, groupsets, i18n, seed
from webapp.app import create_app
from webapp.groupsets import GENERATIONS, path, upgrades


@pytest.fixture(autouse=True)
def show_groupsets(monkeypatch):
    """The page is hidden on the site for now; these tests switch it on."""
    monkeypatch.setenv("SHOW_GROUPSETS", "1")


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
    assert p["effort"] == 2 and p["fit"] == "check"
    assert any("internal routing" in en(s) for s in p["frame"])  # wired Di2


def test_more_speeds_is_a_new_drivetrain():
    assert effort("r7000", "r7100") == 3
    assert effort("gx-eagle", "gx-eagle-axs") == 2  # same cassette and chain, other shifting


def test_any_move_to_wireless_gets_the_same_remark():
    wireless = "Wireless shifting: no cables or wires"
    for frm, to in (("r7000", "r8100"), ("6870", "r9200"), ("rival-22", "rival-axs"), ("m8000", "m8250")):
        assert any(wireless in en(s) for s in path(GENERATIONS[frm], GENERATIONS[to])["steps"]), (frm, to)
    assert not any(wireless in en(s) for s in path(GENERATIONS["rival-axs"], GENERATIONS["red-axs"])["steps"])


def test_freehub_and_frame_raise_the_effort():
    assert effort("m5100", "m8100") == 4  # HG to Micro Spline
    assert effort("nx-eagle", "gx-eagle") == 4  # HG to XD
    p = path(GENERATIONS["gx-eagle-axs"], GENERATIONS["xx-t"])
    assert p["effort"] == 2 and p["fit"] == "check" and any("UDH" in en(s) for s in p["frame"])  # pods drive T-Type


def test_other_brake_mounts_dont_fit():
    p = path(GENERATIONS["5800"], GENERATIONS["r7100"])  # rim brake 11-speed to disc only
    assert p["fit"] == "no" and any("no mounts" in en(s) for s in p["frame"])
    assert path(GENERATIONS["r7000"], GENERATIONS["r7100"])["fit"] == "ok"  # R7000 came in disc too
    assert path(GENERATIONS["apex-12"], GENERATIONS["rival-axs"])["fit"] == "check"  # 1x to 2x: front mount
    found = upgrades("5800")
    fits = [p["fit"] == "no" for g, p in found if g["brand"] == "Shimano"]
    assert fits == sorted(fits)  # the ones that don't fit come last


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
        | set(groupsets.FREEHUBS.values()) | {t for pair in groupsets.EFFORT.values() for t in pair} \
        | {t for pair in groupsets.FIT.values() for t in pair} | set(groupsets.COST.values()) | {groupsets.NOT_WORTH_IT}
    for brand, by_discipline in groupsets.LADDERS.items():
        for ladders in by_discipline.values():
            for label, steps in ladders:
                texts.add(label)
                assert all(s["tier"] for s in steps), label
    for g in GENERATIONS.values():
        for other in GENERATIONS.values():
            p = path(g, other)
            texts |= {s.text for s in p["steps"] + p["frame"]}
    for text in texts:
        assert text in i18n.NL, text


def test_page_renders(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    page = client.get("/groupsets?lang=nl").data.decode()
    assert "Groepset upgraden" in page and "Dura-Ace Di2 R9200" in page and "modellen met" not in page  # no bike links
    assert "GRX RX820" not in page and "GRX RX820" in client.get("/groupsets?type=gravel").data.decode()  # own type
    page = client.get("/groupsets?have=r7000&lang=en").data.decode()
    assert "Upgrades from Shimano 105 R7000" in page and "Mix and match" in page and "Switching brand" in page
    page = client.get("/groupsets?have=r9100&lang=en").data.decode()
    assert "Check your frame" in page and "For example a UDH dropout" in page
    assert "<h3>Doesn&#39;t fit your frame</h3>" in client.get("/groupsets?have=5800&lang=en").data.decode()
    page = client.get("/groupsets?have=r9100&lang=en").data.decode()  # every group shows, empty or not
    assert all(f"<h3>{h}</h3>" in page for h in ("Mix and match", "New freehub body", "Doesn&#39;t fit your frame"))
    assert "None from here." in page and "How to read this" not in page
    assert "Is it worth it?" in page and "Easiest route" not in page  # no view switch
    page = client.get("/groupsets?have=4700&lang=nl").data.decode()  # level 4 from Tiagra, and ! cards at 4
    assert "Vaak niet kostenefficiënt" in page and "Deze upgrade raden we af" in page and "zeker als je huidige fiets goed verkoopbaar is" in page
    assert page.index('class="stack brand-ladders"') < page.index('id="paths"')  # the ladders come first
    assert "XTR M9100" in client.get("/groupsets?type=mtb").data.decode()
    assert client.get("/groupsets?have=nonsense").status_code == 200
    page = client.get("/groupsets?have=5800&lang=nl").data.decode()
    assert "Upgrades vanaf hier" not in page and 'href="/groupsets/r8000/shop">Waar te koop</a>' in page
    shop = client.get("/groupsets/r8000/shop?lang=nl").data.decode()
    assert "Shimano Ultegra R8000 kopen" in shop and "Bekijk bij Bike24" in shop and 'rel="sponsored noopener"' in shop
    assert client.get("/groupsets/nonsense/shop").status_code == 404
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
    assert 'aria-current="true"><span class="pill-logo" role="img" aria-label="SRAM"' in page and "XX1 Eagle AXS" in page


def test_gravel_has_its_own_type_but_upgrades_cross():
    assert GENERATIONS["rx810"]["kind"] == "gravel" and GENERATIONS["rx810"]["discipline"] == "road"
    assert "rx820" in [g["key"] for g, _p in upgrades("r7000")]  # 105 to GRX still counts


def test_ladder_arrows_and_tier_labels():
    road = groupsets.LADDERS["Shimano"]["road"][0][1]
    cols = groupsets.columns(road)
    assert [[s["name"] for s in series] for _t, series, _up in cols][0] == ["Claris", "Sora"]  # both basic
    assert [up for _t, _s, up in cols] == [False, True, True, True, True]
    campa = groupsets.columns(groupsets.LADDERS["Campagnolo"]["road"][0][1])
    assert [s["name"] for s in campa[-1][1]] == ["Record", "Super Record"]
    page = create_app(":memory:").test_client().get("/groupsets?lang=en").data.decode()
    assert page.count('class="tier-span"') == 5 and "Same level" not in page


def test_downgrades_stay_with_the_brand_and_go_down():
    keys = [g["key"] for g, _p in groupsets.downgrades("r8000")]
    assert "r7000" in keys and "6800" in keys and "r9100" not in keys and "rival-22" not in keys
    assert groupsets.downgrades("r2000") == []
    page = create_app(":memory:").test_client().get("/groupsets?have=r8000&lang=en").data.decode()
    assert "Downgrades: " in page


def test_series_show_their_logo_once_the_file_is_there(tmp_path):
    assert groupsets.logo_path({"name": "SX / NX Eagle"}) == "logos/groupsets/sx-nx-eagle.svg"
    app = create_app(str(tmp_path / "app.sqlite3"))
    logo = os.path.join(app.static_folder, groupsets.logo_path({"name": "Claris"}))
    assert not os.path.exists(logo)  # the test adds and removes it
    page = app.test_client().get("/groupsets?lang=en").data.decode()
    assert '<span class="step-name">Claris</span>' in page
    assert 'aria-label="Dura-Ace"' in page  # a shipped logo
    with open(logo, "w") as f:
        f.write("<svg xmlns='http://www.w3.org/2000/svg'/>")
    try:
        page = app.test_client().get("/groupsets?lang=en").data.decode()
        assert 'aria-label="Claris"' in page and "logos/groupsets/claris.svg" in page
    finally:
        os.remove(logo)


def test_wireless_generations_come_last():
    for brand in groupsets.LADDERS.values():
        for ladders in brand.values():
            for _label, steps in ladders:
                for s in steps:
                    wireless = [g["shift"] in groupsets.WIRELESS for g in s["gens"]]
                    assert wireless == sorted(wireless), s["name"]
    ultegra = groupsets.LADDERS["Shimano"]["road"][0][1][4]
    assert ultegra["gens"][-1]["key"] == "r8100" and ultegra["gens"][0]["key"] == "6800"


def test_cross_system_upgrades():
    assert groupsets.cross_upgrades("r7100") == ["r7150", "r8100", "r9200"]
    assert "r8000" not in groupsets.cross_upgrades("r7100")  # on its own system, and too old


def test_route_view_is_gone(tmp_path):
    client = create_app(str(tmp_path / "app.sqlite3")).test_client()
    page = client.get("/groupsets?have=4700&show=route&lang=en").data.decode()  # old links show the full page
    assert "data-route" not in page and "off-route" not in page and "<h3>Mix and match</h3>" in page


def test_shop_page_links_each_shop(tmp_path):
    from webapp import groupset_shops
    path = tmp_path / "shops.json"
    path.write_text(json.dumps([{"name": "A", "url": "https://aff.example/?q={q}"},
                                {"name": "B", "url": "", "groupsets": {"r8000": "https://b.example/r8000"}},
                                {"name": "C", "url": "http://plain.example/{q}"}]))
    gen = groupsets.GENERATIONS["r8000"]
    assert groupset_shops.links(groupset_shops.load(path), gen) == [
        ("A", "https://aff.example/?q=Shimano+Ultegra+R8000"), ("B", "https://b.example/r8000"), ("C", "#")]
    assert groupset_shops.load(tmp_path / "missing.json") == []


def test_wireless_row(tmp_path):
    shimano = groupsets.LADDERS["Shimano"]["road"][0][1]
    assert groupsets.split_wireless(shimano)
    t_type = [steps for label, steps in groupsets.LADDERS["SRAM"]["mtb"] if "Transmission" in steps[0]["name"]][0]
    assert not groupsets.split_wireless(t_type)  # wireless only: one row
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/groupsets?have=r7100&lang=nl").data.decode()
    wired, wireless = page.index('class="row-label wired"'), page.index('class="row-label wireless"')
    assert wired < page.index('data-key="r7100"') < wireless < page.index('data-key="r7150"')
    assert wireless < page.index('data-key="r8100"') and page.index('data-key="r8050"') < wireless
    page = app.test_client().get("/groupsets?brand=SRAM&type=mtb").data.decode()
    assert 'data-key="xx-t"' in page  # a wireless-only ladder keeps its tiles, in one row


def test_freehub_upgrades_are_advised_against(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    page = app.test_client().get("/groupsets?have=4700&lang=nl").data.decode()  # Tiagra 10s: level 4 upgrades
    assert "Deze upgrade raden we af" in page and "Afgeraden" in page
    page = app.test_client().get("/groupsets?have=r9100&lang=nl").data.decode()  # no level 4: still said
    assert "Deze upgrade raden we af" in page


def test_hidden_unless_switched_on(tmp_path, monkeypatch):
    monkeypatch.delenv("SHOW_GROUPSETS")
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    assert client.get("/groupsets").status_code == 404
    assert client.get("/groupsets/r8000/shop").status_code == 404
    for page in ("/?lang=en", "/models?groupset=105&lang=en"):
        assert 'href="/groupsets' not in client.get(page).data.decode()


def test_a_negated_electronic_mention_reads_as_mechanical():
    """Check 71: "Shimano Ultegra (niet elektronisch)" was reported as the ad saying electronic."""
    from webapp import checks
    for text in ("De fiets is afgemonteerd met Shimano Ultegra (niet elektronisch).", "Shimano Ultegra, geen Di2",
                 "Ultegra non-Di2", "Ultegra, Di2: nee", "Ultegra zonder elektronische schakeling", "Ultegra mechanisch"):
        assert checks.says_electronic(text) is False, text
        assert checks.detect_groupset(text)["electronic"] is False, text
    for text in ("Ultegra Di2", "Ultegra Di2 R8050, niet mechanisch", "geen schijfremmen maar Ultegra Di2"):
        assert checks.says_electronic(text) is True, text
        assert checks.detect_groupset(text)["electronic"] is True, text
    assert checks.says_electronic("Shimano Ultegra") is None


def test_shifting_chip_follows_the_negation():
    from webapp import checks
    model = {"name": "Émonda SL 6", "specs": {"Shifter": "Shimano Ultegra R8000, 11-speed"}}
    if checks.detect_groupset(checks.groupset_text(model)) is None:
        return
    got = checks.shifting(model, "Trek Emonda SL6 Pro", "Shimano Ultegra (niet elektronisch)")
    assert got["ad"] == "mechanical" and got["same"]


def test_a_negation_on_another_line_doesnt_count():
    """Bugbot on #281: "Di2" at a line's end and "No scratches" on the next isn't "Di2: no"."""
    from webapp import checks
    assert checks.says_electronic("Shimano Ultegra Di2\nNo scratches") is True
    assert checks.says_electronic("Geen krassen\nUltegra Di2") is True
    assert checks.says_electronic("Ultegra Di2 nee") is True  # no colon: not the "Di2: nee" spec style
