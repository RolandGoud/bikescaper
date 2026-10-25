import pytest

from brand_scrapers import factor, giant
from webapp import colour_match, db, seed
from webapp.app import create_app
from test_checks import models, run  # noqa: F401  (the fixture)


@pytest.mark.parametrize("title, description, colours", [
    ("Scott Addict 30 zwart maat 56", "", ["black"]),
    ("Specialized Tarmac SL7 donkerblauw", "", ["blue"]),
    ("Canyon Ultimate CF SL 8", "Mooie racefiets.\n\nKleur: wit/rood", ["white", "red"]),
    ("Giant TCR", "Een witte racefiets met zwarte banden", ["white"]),
    ("Trek Domane", "Het frame is grijs, nieuwe banden.", ["grey"]),
    # "carbon" in an ad is the frame, not its colour
    ("Trek Emonda SL5 carbon racefiets 60 cm", "", []),
])
def test_ad_colours(title, description, colours):
    assert colour_match.ad_colours(title, description) == colours


@pytest.mark.parametrize("name, families", [
    ("Carbon / Red", ["black", "red"]),
    ("surfblue 'n' black", ["blue", "black"]),
    ("Royal Plum (Matt) - Fantasy Purple C. View (Gloss)", ["purple"]),
    ("Chalk", ["white"]),
    ("Blaze Purple", ["purple"]),
    ("Satin Solidity Metallic", []),
])
def test_brand_colour_names(name, families):
    assert colour_match.families_in(name, brand_words=True) == families


def test_pick_by_the_colour_the_seller_names():
    model = {"colorways": [{"name": "Raptor Blue", "image": "a.jpg"}, {"name": "Quattro Grey", "image": "b.jpg"},
                           {"name": "Satin Solidity Metallic", "hex": "#3A92C3"}]}
    assert colour_match.pick(model, "Factor Aluto grijs")["name"] == "Quattro Grey"
    assert colour_match.pick(model, "Factor Aluto", "kleur: zilver")["name"] == "Quattro Grey"  # the nearest
    assert colour_match.pick(model, "Factor Aluto") is None
    assert colour_match.pick(model, "Factor Aluto rood") is None
    assert colour_match.pick(model, "Factor Aluto blauw") is None  # two blue ones
    tie = {"colorways": [{"name": "Black / Red"}, {"name": "Red / Black"}]}
    assert colour_match.pick(tie, "Fiets rood/zwart")["name"] == "Red / Black"  # leads with the first colour said
    assert colour_match.pick({"colorways": [{"name": "Black"}]}, "zwart") is None  # one colour: nothing to pick


def test_report_shows_the_catalogue_bike_in_the_ads_colour(models):  # noqa: F811
    r = run(models, "Scott Addict 30 zwart maat 56")
    assert r["model"]["name"] == "Addict 30"
    assert r["colourway"]["name"] == "carbon black"
    assert r["model"]["image"] == r["colourway"]["image"] and "carbon_black" in r["model"]["image"]
    green = run(models, "Scott Addict 30 groen maat 56")
    assert green["colourway"]["name"] == "sand green" and "sand_green" in green["model"]["image"]
    plain = run(models, "Scott Addict 30 maat 56")
    assert plain["colourway"] is None


def test_report_says_which_colour(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, description, asking_price) VALUES (?, ?, ?)",
                 ("Scott Addict 30 paars maat 54", "", 1500))
    conn.commit()
    page = app.test_client().get("/check/1?lang=en").data.decode()
    photo_line = page[page.index('class="mb-photo"'):].split("</div>")[0]
    assert "nebula purple" in photo_line.lower() and "the colour the ad names" in photo_line
    assert "Addict_30_colour_nebula_purple.jpg" in page


def test_swatch_is_the_frame_colour_in_the_photo():
    purple = seed.photo_colour("Scott/Addict_30_colour_nebula_purple.jpg")
    assert colour_match.hex_family(purple) == "purple"
    assert colour_match.hex_family(seed.photo_colour("Scott/Addict_30_colour_carbon_black.jpg")) in ("black", "grey")
    assert colour_match.hex_family(seed.photo_colour("Scott/Addict_20_colour_cumulus_white.jpg")) == "white"
    ways = seed.colorways({"brand": "Scott", "name": "Addict 30", "color_names": ["nebula purple", "sand green"],
                           "color_images": ["Scott/Addict_30_colour_nebula_purple.jpg", "Scott/Addict_30_colour_sand_green.jpg"],
                           "color_image_urls": ["u1", "u1"]}, None)
    assert ways[0]["swatch"] == purple
    assert ways[1]["image"] is None  # the same photo as the first colour's: not of this colour


def test_colourways_use_the_saved_colour_photos():
    bike = {"brand": "Scott", "name": "Addict 30", "color_names": ["carbon black", "nebula purple", "Kaze"],
            "color_images": ["Scott/Addict_30_colour_carbon_black.jpg", None, "Scott/missing.jpg"],
            "color_hexes": [None, "#6b4fa0"]}
    ways = seed.colorways(bike, "Scott/Addict_30.jpg")
    assert ways[0]["image"] == "Scott/Addict_30_colour_carbon_black.jpg"
    assert ways[1]["image"] is None and ways[1]["swatch"] == "#6b4fa0" and ways[1]["hex"] == "#6b4fa0"
    assert ways[2]["image"] is None  # a file that isn't there


def test_giant_colour_photo_is_the_side_view_of_that_colour():
    # The page also shows other models, and lists Mach Blue first though its photos are colour B.
    files = ["MY27PropelAdvanced2_ColorAWhite", "MY27PropelAdvanced2_ColorBMachBlue", "MY27PropelAdvanced2_ColorBMachBlue-D2",
             "MY27PropelAdvanced1_ColorACarbon", "MY27PropelAdvanced2_ColorAWhite_Rear", "MY25PropelAdvancedPro0-Di2_ColorBMercury"]
    page = " ".join(f"{letter * 20}/{f}.jpg" for letter, f in zip("abcdef", files))
    assert giant.colour_photo(page, "Propel Advanced 2", "Mach Blue").endswith("/" + "b" * 20 + "/MY27PropelAdvanced2_ColorBMachBlue.jpg")
    assert giant.colour_photo(page, "Propel Advanced 2", "White").endswith("/" + "a" * 20 + "/MY27PropelAdvanced2_ColorAWhite.jpg")
    assert giant.colour_photo(page, "Propel Advanced 2", "Carbon") is None  # Propel Advanced 1's
    assert giant.colour_photo(page, "Propel Advanced Pro 0 Di2", "Mercury").endswith("_ColorBMercury.jpg")


def test_factor_photo_per_colour():
    variant = ('{"title":"%s / 49","price":{"amount":"9199.0"},"selectedOptions":[{"name":"Colour","value":"%s"},'
               '{"name":"Size","value":"49"}],"category":"frameset","image":{"id":"gid://x","url":"%s"}}')
    page = ('<script>window.__remixContext = {"state":{"loaderData":{"routes/bike-builder":{"content":{},'
            '"defaultVariant":{}}}}};</script>' + ",".join(
                variant % (c, c, f"https://cdn.shopify.com/{c.replace(' ', '_')}.png") for c in ("Raptor Blue", "Quattro Grey"))
            + '{"name":"Colour","value":"Raptor Blue"}{"name":"Colour","value":"Quattro Grey"}')
    bike = factor.parse(page, "https://eu.factorbikes.com/bike-builder/aluto", {"model": "ALUTO"})
    assert bike["color_names"] == ["Raptor Blue", "Quattro Grey"]
    assert bike["color_image_urls"] == ["https://cdn.shopify.com/Raptor_Blue.png?width=1200&format=jpg",
                                        "https://cdn.shopify.com/Quattro_Grey.png?width=1200&format=jpg"]
