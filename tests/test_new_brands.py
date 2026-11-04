"""Lapierre, Bianchi, BMC, Cervélo, Ridley, Rose and Wilier: the bits of their stores the adapters read."""
import pytest

from urllib.parse import quote

from brand_scrapers import bianchi, bmc, cervelo, lapierre, ridley, rose, wilier
from brand_scrapers.nuxt import nuxt_data, nuxt_state
from brand_scrapers.sizing import cervelo_chart, geometry_table


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
    ("https://cdn.shopify.com/s/files/1/files/bmc-2027-speedmachine-01-two-aero-bike-blue-1_61d5.jpg?v=1", 2027, "Blue"),
    ("https://cdn.shopify.com/s/files/1/files/bmc-2027-speedmachine-01-aero-module-black-1_447f.jpg?v=1", 2027, "Black"),
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
    speed = {"title": "Speedmachine 01 TWO", "product_type": "Bikes", "tags": ["Bikes | Road | Aero | Speedmachine"]}
    assert bmc.category_of(speed, speed["title"]) == "Triathlon / TT"
    aero_road = {"title": "Timemachine TMR01 Ultegra", "product_type": "Bike Archive", "tags": ["Road | Aero"]}
    assert bmc.category_of(aero_road, aero_road["title"]) == "Aero Race"
    archived = {"title": "Timemachine 01 ONE", "product_type": "Bike Archive", "tags": ["Road | Aero | Timemachine"]}
    assert bmc.wanted(archived) and bmc.category_of(archived, archived["title"]) == "Triathlon / TT"


def test_bmc_spec_rows():
    page = ("<p><b>Frame:</b><br> Teammachine SLR Gen 5</p><p><b>Rims: </b><br>PRD23 | 23mm</p>"
            "<p><b>General Product Safety Regulation (GPSR):</b><br><u>Safety Instructions</u></p>")
    assert bmc.spec_pairs(page) == [("Frame", " Teammachine SLR Gen 5"), ("Velg", "PRD23 | 23mm")]


@pytest.mark.parametrize("title,name", [
    ("S5 ULTEGRA DI2", "S5 Ultegra Di2"),
    ("ÁSPERO-5 GRX RX827 DI2", "Aspero-5 GRX RX827 Di2"),
    ("CALEDONIA-5 DURA-ACE DI2", "Caledonia-5 Dura-Ace Di2"),
    ("P-SERIES 105", "P-Series 105"),
    ("ROUVIDA FORCE XPLR 1 E1", "Rouvida Force XPLR 1 E1"),
])
def test_cervelo_names(title, name):
    assert cervelo.tidy_name(title) == name


@pytest.mark.parametrize("handle,year,category", [
    ("s5-ultegra-di2-2027", 2027, "Race"),
    ("caledonia-5-rival-axs-2027", 2027, "Endurance"),
    ("aspero-apex-1-2027", 2027, "Gravel"),
    ("r5-cx-r5-cx-rival-axs-1-2027", 2027, "Gravel"),
    ("p-series-105-2027", 2027, "Triathlon / TT"),
])
def test_cervelo_year_and_category_from_handle(handle, year, category):
    assert cervelo.model_year(handle) == year
    assert cervelo.category_of(handle) == category


def test_cervelo_only_bikes_from_the_sitemap():
    assert cervelo.family_of("seatpost-clamp-assembly-0h0-r5") is None
    assert cervelo.model_year("aspero-fork-insert-dual-offset-threaded") is None


def test_cervelo_spec_sheet_of_this_build():
    other = quote('{"url":"/en-nl/products/s5-red-axs-2027","rear_derailleur":{"value":"SRAM Red AXS"}}')
    this = quote('{"url":"/en-nl/products/s5-ultegra-di2-2027","rear_derailleur":{"value":"Shimano Ultegra, R8150"},'
                 '"crankset":{"value":"Shimano Ultegra, R8100, 52/36T"},"brakes":{"value":""},"title":"S5"}')
    page = (f"products: [JSON.parse(decodeURIComponent('{other}'))] "
            f"products: [JSON.parse(decodeURIComponent('{this}'))]")
    assert cervelo.spec_sheet(page, "s5-ultegra-di2-2027") == [("Achterderailleur", "Shimano Ultegra, R8150"),
                                                              ("Crankstel", "Shimano Ultegra, R8100, 52/36T")]


def test_cervelo_rider_heights_per_size():
    def row(size, low, high, reach):
        return (f'<span class="type-text-medium-4 w-full" style="grid-column: 1;">\n  Size {size}\n</span>'
                f'<span x-cloak x-show="unit == \'cm\'">\n {low}cm</span><span x-show="unit == \'in\'">5\'3"</span>'
                f'<span x-cloak x-show="unit == \'cm\'">{high}cm</span>'
                f'<span class="type-text-regular-7">Reach: {reach}mm\n</span>')
    page = '<a>Size Guide</span>' + row(48, 149.9, 160, 367) + row(54, 167.6, 175, 384)
    assert cervelo_chart(page) == {"48": {"low": 150, "high": 160, "reach": 367},
                                   "54": {"low": 168, "high": 175, "reach": 384}}


def test_nuxt_state_reads_minified_state():
    page = ('<script>window.__NUXT__=(function(a,b,c,d){c.code="X1";c.sizes=Array(2);c.sizes[0]=b;'
            'return {data:[{bike:c,price:{msrp:"2699",old:void 0}}],state:{"on":true,n:1.5,list:[a,d,{}]}}}'
            '("Helium","M",{},null));</script>')
    assert nuxt_state(page) == {"data": [{"bike": {"code": "X1", "sizes": ["M", None]},
                                          "price": {"msrp": "2699", "old": None}}],
                                "state": {"on": True, "n": 1.5, "list": ["Helium", None, {}]}}
    assert nuxt_state("<html>no state</html>") is None


@pytest.mark.parametrize("text,tidy", [
    ("Sram Red AXS 2x12sp", "SRAM Red AXS 2x12"),
    ("Shimano 105 DI2 // 2x12s", "Shimano 105 Di2 2x12"),
    ("Shimano 105 - 2x12", "Shimano 105 2x12"),
    ("Shimano Dura Ace DI2 2x12", "Shimano Dura-Ace Di2 2x12"),
    ("Shimano GRX600 1x12sp", "Shimano GRX 600 1x12"),
    ("Shimano Cues 1x11, hydraulic disc brakes", "Shimano CUES 1x11"),
])
def test_ridley_groupset_names(text, tidy):
    assert ridley.tidy_groupset(text) == tidy


def test_ridley_year_colour_and_geometry():
    assert ridley.model_year({"collection_year": "Collectie Ridley 2027"}) == 2027
    assert ridley.model_year({"collections": "CY_RID2024"}) == 2024
    assert ridley.colour_name({"paint_des": "FR226L2As - Silver/Black/Candy Red Metallic"}) == "Silver/Black/Candy Red Metallic"
    assert ridley.colour_name({"paint_des": "KAD27D6S", "primary_basecolour": "Silver", "secondary_basecolour": "Red"}) == "Silver/Red"
    assert ridley.colour_name({"paint_des": "FEN01As (Arctic Grey Metallic - White)"}) == "Arctic Grey Metallic/White"
    assert ridley.colour_name({"paint_des": "KAD27D6S", "paint_bac": "Zilver // 0"}) == "Zilver"
    table = '[["","XS","S"],["A",760,785],["S",546,569],["R",379,387]]'  # sometimes a JSON string
    assert ridley.geometry({"attributes": {"excel_frame_geometry": table}}) == {
        "XS": {"stack": 546, "reach": 379}, "S": {"stack": 569, "reach": 387}}


def test_ridley_builds_leave_out_mtb_track_and_ebikes():
    def frame(model, electric="Nee"):
        return {"model": model, "electric": electric, "$$groupsets": [{"groupset": "Frameset", "designs": [{"externalid": "X"}]}]}
    state = {"state": {"bikes": {"items": [
        {"code": "AerotoWeight", "frameplatformdetails": [frame("Falcn RS 2.0"), frame("E-Falcn", electric="Ja")]},
        {"code": "Hardtail", "frameplatformdetails": [frame("Probe RS")]},
        {"code": "Track", "frameplatformdetails": [frame("Arena Fast")]},
    ]}}}
    assert [(p, f["model"]) for p, f, _ in ridley.builds(state)] == [("AerotoWeight", "Falcn RS 2.0")]


def test_nuxt_data_reads_devalue_state():
    table = '[{"data":1},{"product":2},["Reactive",3],{"name":4,"sizes":5,"self":-1},"Shave",[6,6],"M"]'
    page = f'<script type="application/json" id="__NUXT_DATA__" data-ssr="true">{table}</script>'
    assert nuxt_data(page) == {"data": {"product": {"name": "Shave", "sizes": ["M", "M"], "self": None}}}
    assert nuxt_data("<html></html>") is None


def test_rose_families_builds_and_categories():
    page = ('<a href="/fietsen/race/race/shave"></a><a href="/fietsen/race/elektrische-racefietsen/reveal-plus"></a>'
            '<a href="/fietsen/gravel/e-gravel/backroad-al-plus"></a><a href="/fietsen/gravel/everyday/hobo"></a>'
            '<a href="/p/rose-shave-105-di2-2726127"></a><a href="/p/rose-shave-105-di2-2726127"></a>')
    assert rose.families(page) == ["/fietsen/race/race/shave", "/fietsen/gravel/everyday/hobo"]
    assert rose.builds(page) == ["/p/rose-shave-105-di2-2726127"]
    assert rose.category_of("/fietsen/race/endurance/blend") == "Endurance"
    assert rose.category_of("/fietsen/gravel/race/backroad-ff") == "Gravel"


def test_rose_parts_list_and_rider_heights():
    def item(title, subtitle):
        return {"title": title, "subtitle": subtitle}
    variant = {"partsList": {"groups": [{"items": [
        item("Wielen", "<p>Newmen Advanced A.50</p> 28\""), item("Wielen", "<p>HR:&#160;Newmen Advanced A.50</p>"),
        item("Remmen", "<p>Shimano Ultegra ST-R8170, BR-R8170,</p>"), item("Pedalen", "<p>Pedalen zijn niet bij de levering inbegrepen</p>"),
        item("Kettinggeleiding", "K-Edge"), item("Powermeter", "4iiii"),
    ]}]}}
    assert rose.parts(variant) == [("Wiel voor", 'Newmen Advanced A.50 28"'), ("Wiel achter", "Newmen Advanced A.50"),
                                   ("Rem", "Shimano Ultegra ST-R8170, BR-R8170"), ("Vermogensmeter", "4iiii")]
    variants = [{"superAttributes": [{"type": "size", "value": s}], "bodyHeightMin": h}
                for s, h in (("S", 163), ("XS", 155), ("M/L", 177), ("M", 171), ("S", 163))]
    assert rose.size_chart(variants) == {"XS": {"low": 155, "high": 162}, "S": {"low": 163, "high": 170},
                                         "M": {"low": 171, "high": 176}, "ML": {"low": 177, "high": 184}}


@pytest.mark.parametrize("text,tidy", [
    ("SHIMANO DURA ACE Di2 2x12 R9270 ", "Shimano Dura-Ace Di2 2x12"),
    ("SRAM RIVAL XPLR AXS 1X13", "SRAM Rival XPLR AXS 1x13"),
    ("Shimano GRX 1x12s", "Shimano GRX 1x12"),
    ("-", ""),
    ("Solo telaio / Framekit only", ""),
    ("SHIMANO DURA-ACE Di2 R9270 2x12 + POWERMETER", "Shimano Dura-Ace Di2 2x12 + Powermeter"),
    ("CAMPAGNOLO SUPER RECORD WRL 2x13", "Campagnolo Super Record WRL 2x13"),
])
def test_wilier_groupset_names(text, tidy):
    assert wilier.tidy_groupset(text) == tidy


def test_wilier_build_from_family_page():
    product = {"name": "Filante SLR", "slug": "filante-slr", "year": {"name": "2027"},
               "category": {"slug": "road"}, "usages": [{"slug": "racing"}],
               "colors": [{"name": "F27 Carbon Iridium", "image": [{"original_url": "https://api.wilier.com/media/1/a.jpg"}]}],
               "geometries_table": {"label": ["XS", "XXL"], "stack": [505, 587], "reach": [380, 399]}}
    build = wilier.parse(product, {"code": "E603IDAS", "groupset": "SHIMANO DURA ACE Di2 2x12 R9270", "msrp": 699900,
                                   "shifters": "SHIMANO DURA-ACE Di2 ST-R9270", "stem": None, "tyres": "N/A"}, "u")
    assert (build["name"], build["price"], build["model_year"], build["category"]) == (
        "Filante SLR Shimano Dura-Ace Di2 2x12", 6999.0, 2027, "Race")
    assert build["specifications"]["Shifter"] == "SHIMANO DURA-ACE Di2 ST-R9270"
    assert "Buitenband" not in build["specifications"]
    assert build["sizes"] == ["XS", "2XL"] and build["color_names"] == ["F27 Carbon Iridium"]
    assert wilier.parse(product, {"code": "E603 (FRAMESET)", "groupset": "-", "msrp": 450000}, "u")["name"] == "Filante SLR Frameset"
    assert wilier.category_of({"category": {"slug": "road"}, "usages": [{"slug": "endurance"}]}) == "Endurance"
    assert wilier.geometry(product) == {"XS": {"stack": 505, "reach": 380}, "2XL": {"stack": 587, "reach": 399}}
