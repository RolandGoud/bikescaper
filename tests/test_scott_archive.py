import json
import os

from brand_scrapers import scott_archive as sa


def test_names_lose_the_brand_the_shop_words_and_the_colour():
    assert sa.name_of("SCOTT Addict 10 Bike blue") == "Addict 10"
    assert sa.name_of("SCOTT Addict Gravel 10 disc Bike") == "Addict Gravel 10 Disc"
    assert sa.name_of("Vélo SCOTT FOIL 30") == "Foil 30"
    assert sa.name_of("Bicicleta SCOTT Addict RC 15 carbon onyx black") == "Addict RC 15"
    assert sa.name_of("SCOTT Foil RC 20 Fahrrad") == "Foil RC 20"
    assert sa.name_of("Rámová sada SCOTT Foil RC Pro HMX", "foil-rc-pro-hmx-frame-set") == "Foil RC Pro HMX Frameset"


def test_old_pages_specs_in_english_whatever_the_site():
    page = ('<h4 class="specs-list__title"> Rahmen</h4> <div class="specs-list__content"> Addict RC HMF<br/>Disc</div>'
            '<h4 class="specs-list__title"> Schaltwerk</h4> <div class="specs-list__content"> Shimano 105</div>'
            '<h4 class="specs-list__title"> Seat</h4> <div class="specs-list__content"> Syncros Belcarra</div>')
    assert sa.old_specs(page) == [{"label": "Frame", "value": "Addict RC HMF, Disc"},
                                  {"label": "Rear Derailleur", "value": "Shimano 105"},
                                  {"label": "Seat", "value": "Syncros Belcarra"}]


def test_windows_1252_pages_decode():
    assert sa.decode("Dérailleur arrière".encode("cp1252")) == "Dérailleur arrière"
    assert sa.decode("Přehazovačka".encode("utf-8")) == "Přehazovačka"


def test_a_page_is_dated_by_its_size_chart_else_its_article_series():
    assert sa.year_on('"title":"Bikes-SizeChart-2021-BIKE_SCOTT Sports"') == 2021
    assert sa.year_on('\\"code\\":\\"2024_SIZECHARTS') == 2024
    assert sa.year_on("no chart") is None
    page = ('<img src="https://pictures.ssg-service.com/286/286422_1795898_png_zoom_3.jpg">'
            '<a href="?article=280405000">suit</a><a href="?article=280405000">suit</a>')
    assert sa.articles(page) == ["286422"]  # the photo's number, not the linked product's
    assert sa.SERIES["286"] == 2022


def test_numbers_many_bikes_link_to_are_not_a_page_s_own():
    found = [{"name": n, "articles": ["280405", own]} for n, own in [("Addict RC 10", "280617"), ("Foil 30", "280604"),
                                                                       ("Plasma RC", "280596")]]
    shared = sa.shared_articles(found)
    assert shared == {"280405"}
    assert sa.article_of({"articles": ["280405", "280617"]}, shared) == "280617"


def test_only_road_bike_pages_are_read():
    assert sa.wanted("https://www.scott-sports.com/gb/en/product/scott-addict-rc-15-carbon-onyx-black-bike")
    assert not sa.wanted("https://www.scott-sports.com/fr/fr/product/combinaison-avec-chamois-scott-plasma-ld")
    assert not sa.wanted("https://www.scott-sports.com/us/en/product/scott-addict-eride-10-bike")
    assert not sa.wanted("https://www.scott-sports.com/gb/en/product/scott-speedster-jr-24-bike")
    assert sa.mantel_wanted("https://www.mantel.com/be/scott-addict-rc-20")
    assert not sa.mantel_wanted("https://www.mantel.com/be-fr/patte-de-derailleur-scott-addict---solace")
    assert not sa.mantel_wanted("https://www.mantel.com/de/scott-addict-rc-20")  # German labels: mantel.py has none


def test_mantel_page_reads_name_year_and_spec_table():
    page = ('<h1 itemprop="name"><span itemprop="brand">Scott</span> Contessa Speedster 15 WSD</h1>'
            '<table><tr><td>Modeljaar</td><td>2019</td></tr><tr><td>Achterderailleur</td><td>Shimano 105</td></tr>'
            '<tr><td>Gewicht</td><td>9,2 kg</td></tr></table>'
            '<meta property="og:image" content="https://cdn.mantel.com/images/product.php?image_id=123&w=760">')
    name, entry = sa.mantel_page(page, "20190501000000", "https://www.mantel.com/scott-contessa-speedster-15-wsd")
    assert name == "Contessa Speedster 15"
    assert entry["model_year"] == 2019 and entry["weight"] == "9,2 kg" and entry["photo_id"] == 123
    assert {"label": "Achterderailleur", "value": "Shimano 105"} in entry["specs"]
    assert sa.mantel_slug("https://www.mantel.com/scott-addict-20-2026&spec[]=25770") == ("", "scott-addict-20-2026")


def test_scott_year_sheets_are_in_the_catalogue_files():
    """The brand-site and Mantel sheets carry specs and, for the brand's own pages, no price."""
    root = sa.ROOT
    with open(os.path.join(root, "data", "years", "brandsites", "Scott.json"), encoding="utf-8") as fh:
        sheets = json.load(fh)["models"]
    assert len(sheets) > 30
    for name, years in sheets.items():
        for year, sheet in years.items():
            assert int(year) >= 2018 and sheet["specs"].get("Frame") and sheet["price"] is None, (name, year)
