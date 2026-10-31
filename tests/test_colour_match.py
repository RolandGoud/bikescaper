import pytest

from brand_scrapers import factor, giant
from webapp import checks, colour_match, db, scores, seed
from webapp.app import create_app
from test_checks import TODAY, models, run  # noqa: F401  (the fixture)


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
    caption = page[page.index('class="photo-cap"'):].split("</span>\n")[0]
    assert "nebula purple" in caption.lower() and "the colour the ad names" in caption
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


def ad_photo(tmp_path, image, name, background=(96, 120, 70)):
    """A catalogue photo pasted onto grass, a bit smaller, the way a seller's photo frames the bike."""
    from PIL import Image
    with Image.open(f"images/{image}") as bike:
        bike = bike.convert("RGB")
        bike.thumbnail((500, 500))
        photo = Image.new("RGB", (bike.width + 160, bike.height + 160), background)
        photo.paste(bike, (80, 80))
    path = tmp_path / name
    photo.save(path)
    return str(path)


EMONDA_2021 = [("Carbon Smoke/Factory Orange", "Trek/years/emondasl7_2021_carbonsmokefactoryorange_site.jpg"),
               ("Gloss Radioactive Red/Matte Carbon", "Trek/years/emondasl7_2021_glossradioactiveredmattecarbon_site.jpg")]


def test_colourway_from_the_ads_photos(tmp_path):
    for name, image in EMONDA_2021:
        assert colour_match.by_photos(EMONDA_2021, [ad_photo(tmp_path, image, f"{name[:5]}.jpg")]) == name
    orange = ad_photo(tmp_path, EMONDA_2021[0][1], "orange.jpg")
    assert colour_match.by_photos(EMONDA_2021[:1], [orange]) is None  # one colour: nothing to pick
    assert colour_match.by_photos(EMONDA_2021, []) is None
    assert colour_match.by_photos(EMONDA_2021, [str(tmp_path / "gone.jpg")]) is None
    grey = tmp_path / "grey.jpg"
    __import__("PIL.Image").Image.new("RGB", (400, 300), (128, 128, 128)).save(grey)
    assert colour_match.by_photos(EMONDA_2021, [str(grey)]) is None  # shows neither


def test_year_photo_in_the_colour_the_ads_photos_show(models, tmp_path):  # noqa: F811
    m = next(m for m in models if m["name"] == "Émonda SL 7")
    assert len(m["year_specs"]["years"]["2021"]["colour_images"]) == 2
    listing = {"title": "Trek Emonda SL7 2021 maat 56", "description": "", "asking_price": None, "rider_height": None,
               "photo_paths": [ad_photo(tmp_path, EMONDA_2021[0][1], "ad.jpg")]}
    r = checks.run_check(models, listing, today=TODAY)
    assert r["photo_year"] == {"year": 2021, "colour": "Carbon Smoke/Factory Orange"}
    assert r["model"]["image"] == EMONDA_2021[0][1] and r["colour_from_photos"]
    assert "colour" in scores.missing(r, listing)  # the seller still didn't say it
    plain = checks.run_check(models, dict(listing, photo_paths=[]), today=TODAY)
    assert plain["photo_year"]["colour"] is None and not plain["colour_from_photos"]


def _giant_page(files, own=None):
    page = " ".join(f"{chr(97 + n % 26) * 20}/{f}.jpg" for n, f in enumerate(files))
    if own:
        page = f"<meta property=og:image content=https://images2.giant-bicycles.com/x/{'a' * 20}/{own}.jpg>" + page
    return page


def test_giant_colours_come_from_the_photos_when_the_sheet_lists_none():
    # The 2027 TCR Advanced Pro 0-Di2 page has no Kleuren line: its colours were lost, and with them every photo.
    page = _giant_page(["MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite", "MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite-D4",
                        "MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite-Rear", "MY27TCRAdvancedPro0-Di2_ColorBUltraNavy",
                        "MY27TCRAdvancedPro-DA_ColorACryoSilver"])
    assert giant.photo_colours(page, "TCR Advanced Pro 0-Di2") == ["Icicle White", "Ultra Navy"]
    assert [a.rsplit("/", 1)[1] for a in giant.colour_angles(page, "TCR Advanced Pro 0-Di2", "Icicle White")] == [
        "MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite-D4.jpg", "MY27TCRAdvancedPro0-Di2_ColorAIcicleWhite-Rear.jpg"]


def test_giant_close_ups_named_in_other_ways_are_found():
    page = _giant_page(["MY23DefyAdvancedPro1ColorA_Airglow", "MY23DefyAdvancedPro1ColorA_Airglow_D1",
                        "MY21ContendAR1_ColorAMetallicNavy", "MY21ContendAR1_ColorAMetallicNavy_Road-5",
                        "MY21ContendAR1_ColorAMetallicNavy_back"])
    assert giant.colour_photo(page, "Defy Advanced Pro 1", "Airglow/Black").endswith("/MY23DefyAdvancedPro1ColorA_Airglow.jpg")
    assert len(giant.colour_angles(page, "Defy Advanced Pro 1", "Airglow/Black")) == 1
    assert len(giant.colour_angles(page, "Contend AR 1", "Metallic Navy")) == 2


def test_giant_photos_follow_the_page_photo_when_the_name_is_shortened():
    # "TCR Advanced Pro (Dura-Ace)" files its photos as TCRAdvancedPro-DA, and its close-ups drop the underscore.
    page = _giant_page(["MY26TCRAdvancedPro-DA_ColorACarbon_RossoCorsa", "MY26TCRAdvancedPro-DA_ColorACarbonRossoCorsa-D1",
                        "MY26TCRAdvancedPro-DA_ColorACarbonRossoCorsa-D3", "MY26TCRAdvancedPro0-Di2_ColorACarbon"],
                       own="MY26TCRAdvancedPro-DA_ColorACarbon_RossoCorsa")
    colours = ["Black/Rosso Corsa"]
    assert giant.colour_photo(page, "TCR Advanced Pro (Dura-Ace)", colours[0], colours).endswith("_ColorACarbon_RossoCorsa.jpg")
    assert len(giant.colour_angles(page, "TCR Advanced Pro (Dura-Ace)", colours[0], colours)) == 2
    # MY20DefyADV1_ColorB: an old page names neither the model nor the colour in full
    page = _giant_page(["MY20DefyADV1_ColorB"], own="MY20DefyADV1_ColorB")
    assert giant.colour_photo(page, "Defy Advanced 1", "Charcoal / Pure Red", ["Charcoal / Pure Red"]).endswith("/MY20DefyADV1_ColorB.jpg")


def test_giant_black_background_twins_are_left_out():
    page = _giant_page(["MY24RevoltAdvancedPro1_ColorABlueDragonfly", "MY24RevoltAdvancedPro1_ColorABlueDragonfly-D11",
                        "MY24RevoltAdvancedPro1_ColorABlueDragonfly-D11-1", "MY24Revolt2_ColorAMetallicBlack_B",
                        "MY21FastRoadAdvanced1_ColorACarbon", "MY21FastRoadAdvanced1_ColorACarbon-2"])
    assert [a.rsplit("_", 1)[1] for a in giant.colour_angles(page, "Revolt Advanced Pro 1", "Blue Dragonfly")] == ["ColorABlueDragonfly-D11.jpg"]
    assert len(giant.colour_angles(page, "FastRoad Advanced 1", "Carbon/Chrome")) == 1  # -2 is a close-up of the side view
