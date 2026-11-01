"""Lapierre, Bianchi and BMC: the bits of their stores the adapters read."""
import pytest

from brand_scrapers import bianchi, bmc, lapierre
from brand_scrapers.sizing import geometry_table


@pytest.mark.parametrize("src,year", [
    ("https://cdn.shopify.com/s/files/1/0747/files/LAPIERRE_MY26_PULSIUM-8.0-AXS_28Inch_90_LPTUA.png?v=1", 2026),
    # Lapierre's image pipeline base64-encodes the original name: ".../Xelius DRS 7.0 C1 - Lapierre MY25 - LXCTA - View (0).png"
    ("https://cdn.shopify.com/s/files/1/0747/files/czM6Ly9jczIwLWJ1Y2tldC1wcm9kL0FjY2VsbC9MYXBpZXJyZS9YZWxpdXMgRFJTIDcuMCBDMSAt"
     "IExhcGllcnJlIE1ZMjUgLSBMWENUQSAtIFZpZXcgKDApLnBuZw.png?v=1", 2025),
    ("https://cdn.shopify.com/s/files/1/0747/files/master_2.0.png?v=1", None),
])
def test_lapierre_model_year_from_photo_name(src, year):
    assert lapierre.model_year([{"src": src}]) == year


def test_lapierre_names_and_families():
    assert lapierre.tidy_name("xelius DRS 8.0") == "Xelius DRS 8.0"
    assert lapierre.tidy_name("Xélius DRS 5.0") == "Xelius DRS 5.0"
    assert lapierre.tidy_name("Aérostorm drs") == "Aerostorm DRS"
    assert lapierre.tidy_name("Xelius DRS Frameset -- cold rain grey - glossy") == "Xelius DRS Frameset"
    assert lapierre.family_of("Crosshill CF 7.0") == "crosshill"
    assert lapierre.family_of("Zesty CF 8.9") is None  # a mountain bike


def test_lapierre_spec_rows():
    page = ('<p><strong>Derailleur Rear</strong>: Shimano Ultegra Di2 R8150, 12s</p><p><strong>Motor</strong>: </p>'
            '<p><strong>Number of gears</strong>: 24</p><p><strong>Front Fork</strong>: Lapierre Carbon UD SLI</p>')
    assert lapierre.parse_page(page) == [("Achterderailleur", "Shimano Ultegra Di2 R8150, 12s"),
                                         ("Voorvork", "Lapierre Carbon UD SLI")]


def test_lapierre_geometry_rows_with_letters():
    page = ("<table><thead><tr><th>Component</th><th>S</th><th>M</th></tr></thead><tbody>"
            "<tr><td>H: Stack (mm)</td><td>516 mm</td><td>538 mm</td></tr>"
            "<tr><td>I: Reach (mm)</td><td>383 mm</td><td>393 mm</td></tr></tbody></table>")
    assert geometry_table(page) == {"S": {"stack": 516, "reach": 383}, "M": {"stack": 538, "reach": 393}}


@pytest.mark.parametrize("sku,year", [("YTB23", 2024), ("YUB21", 2025), ("YVB6K", 2026), ("YWB28", 2027),
                                      ("XTB12", 2024), ("", None)])
def test_bianchi_model_year_from_product_code(sku, year):
    assert bianchi.model_year(sku) == year


@pytest.mark.parametrize("short,sku,build", [
    ("<p>Ultegra Di2 12sp &#8211; 4iiii Power Meter &#8211; NEW</p><p>YWB28</p>", "YWB28", "Ultegra Di2"),
    ("<p>SHIMANO ULTEGRA DI2 12SP</p><p>YUB28</p>", "YUB28", "Ultegra Di2"),
    ("<p>Dura Ace-Di2 12sp &#8211; NEW</p>", "YWB21", "Dura-Ace Di2"),
    ("<p>Durace Di2 12sp 4iiii Power Meter</p>", "YUB42", "Dura-Ace Di2"),
    ("<p>Ultegra Di2 12sp- NEW YWB23</p>", "YWB23", "Ultegra Di2"),
    ("<p>FORCE ETAP AXS E1 PWM</p>", "YVB27", "Force eTap AXS E1"),
    ("<p>GRX 610 1x12sp &#8211; Velomann V24G</p>", "YUB87", "GRX 610"),
    ("<p>Frameset: frame, fork, headset, seatpost</p>", "XUB26", None),
    ("<p>LIMITED EDITION</p>", "YVBFS", None),
])
def test_bianchi_build_name(short, sku, build):
    assert bianchi.groupset(short, sku) == build


def test_bianchi_names_and_colours():
    assert bianchi.base_name("Oltre Comp &#8211; NEW") == "Oltre Comp"
    assert bianchi.base_name("Oltre COMP") == "Oltre Comp"
    assert bianchi.base_name("Infinito PRO &#8211; Frameset") == "Infinito Pro Frameset"
    assert bianchi.base_name("Oltre RC &#8211; Team Replica 2026") == "Oltre RC Team Replica"
    assert bianchi.colour_name("ZN - CK Metallic / Graphite") == "CK Metallic / Graphite"
    assert bianchi.colour_name("OK – Celeste: Celeste metallico / Logo CK16 [Full Glossy]") == "Celeste"
    assert bianchi.same_colour("zn-ck-metallic-graphite", "zn") and not bianchi.same_colour("znx", "zn")


def test_bianchi_geometry_reads_size_x_and_y():
    rows = [["SIZE", "A", "X", "Y"], ["470", "450", "385", "470"], ["500", "480", "392", "478"]]
    page = "<table>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"
    assert bianchi.geometry(page) == (["47", "50"], {"47": {"stack": 470, "reach": 385},
                                                     "50": {"stack": 478, "reach": 392}})
    gravel = page.replace("470</td><td>450", "SM</td><td>450").replace("500</td><td>480", "MD</td><td>480")
    assert bianchi.geometry(gravel)[0] == ["S", "M"]


def test_bianchi_skips_mountain_and_city_bikes():
    assert bianchi.category_of("https://www.bianchi.com/en/shop/bikes/road/aero/oltre/oltre-rc-2/") == "Aero Race"
    assert bianchi.category_of("https://www.bianchi.com/en/shop/bikes/gravel/racing/impulso/impulso-comp/") == "Gravel"
    assert bianchi.category_of("https://www.bianchi.com/en/shop/bikes/mtb/cross-country/nitron/") is None


@pytest.mark.parametrize("src,year,colour", [
    ("https://cdn.shopify.com/s/files/1/2361/3567/files/bmc-2027-teammachine-slr-three-road-bike-white-1.jpg?v=1",
     2027, "White"),
    ("https://cdn.shopify.com/s/files/1/files/bmc-2018-teammachine-slr01-disc-road-bike-team-red-1_052c.jpg?v=1",
     2018, "Team Red"),
    ("https://cdn.shopify.com/s/files/1/files/bmc-2027-teammachine-r-01-road-frameset-purple-1.jpg?v=1", 2027, "Purple"),
    ("https://cdn.shopify.com/s/files/1/files/bmc-2024-urs-two-gravel-bike-red-1_9a13.jpg?v=1", 2024, "Red"),
])
def test_bmc_year_and_colour_from_photo_name(src, year, colour):
    assert bmc.photo_facts(src) == (year, colour)


def test_bmc_names_and_disciplines():
    assert bmc.tidy_name("Teammachince SLR01 DISC ONE") == "Teammachine SLR 01 DISC ONE"
    assert bmc.handle_year("teammachine-slr-three-bikes-bmc-27a-000020") == 2027
    assert bmc.handle_year("urs-two-bikes-bmc-24-10619-005") == 2024
    road = {"title": "Teammachine SLR ONE", "product_type": "Bikes", "tags": ["Bikes | Road | Racing | Teammachine SLR"]}
    assert bmc.wanted(road) and bmc.category_of(road, road["title"]) == "Race"
    assert not bmc.wanted(dict(road, title="Roadmachine 01 AMP ONE"))  # an e-bike
    assert not bmc.wanted(dict(road, tags=["Bikes | Mountain | Cross-Country"]))
    archived = {"title": "Timemachine 01 ONE", "product_type": "Bike Archive", "tags": ["Road | Aero | Timemachine"]}
    assert bmc.wanted(archived) and bmc.category_of(archived, archived["title"]) == "Triathlon / TT"


def test_bmc_spec_rows():
    page = ("<p><b>Frame:</b><br> Teammachine SLR Gen 5</p><p><b>Rims: </b><br>PRD23 | 23mm</p>"
            "<p><b>General Product Safety Regulation (GPSR):</b><br><u>Safety Instructions</u></p>")
    assert bmc.spec_pairs(page) == [("Frame", " Teammachine SLR Gen 5"), ("Velg", "PRD23 | 23mm")]
