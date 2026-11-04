from brand_scrapers import galleries


class Page:
    def __init__(self, page):
        self.page = page

    def get(self, url, binary=False):
        return self.page


def test_canyon_takes_the_top_and_detail_views_of_this_bike():
    base = "https://www.canyon.com/dw/image/v2/BCML_PRD/on/demandware.static/-/Sites-canyon-master/default/dw1/images/"
    page = " ".join('"%s%s"' % (base, p) for p in (
        "top/3705_TOP-1/2023/3705_TOP-1_endurace-7_P05_tt-rivet.jpg",
        "detail/detail_202/2023/detail_2024_3705_endurace-7_P05_P5.jpg",
        "full/full_2024_/2023/full_2024_3705_endurace-7_P05_P5.png",  # the side view the catalogue has
        "top/4000_TOP-1/2023/4000_TOP-1_other_P05_frame.jpg"))  # another bike on the page
    found = galleries.canyon(Page(page), {"url": "https://www.canyon.com/nl-nl/x/endurace-7/3705.html"})[""]
    assert [f.split("/images/")[1] for f in found] == [
        "top/3705_TOP-1/2023/3705_TOP-1_endurace-7_P05_tt-rivet.jpg?sw=1200",
        "detail/detail_202/2023/detail_2024_3705_endurace-7_P05_P5.jpg?sw=1200"]


def test_cannondale_leaves_out_the_profile_shot():
    page = ('<script type="application/ld+json">{"@type": "ProductGroup", "image": ["a_PD.jpg"], '
            '"hasVariant": [{"image": ["a_3Q.jpg", "a_PD.jpg"]}]}</script>')
    assert galleries.cannondale(Page(page), {"url": "u"}) == {"": ["a_3Q.jpg"]}


def test_cube_takes_the_details_not_the_side_view():
    page = " ".join('"https://file.cube.eu/x/media/y/synqup_123_%s.jpg"' % s for s in ("S_00", "D_00", "P_00"))
    found = galleries.cube(Page(page), {"url": "https://www.cube.eu/nl/bike/123"})[""]
    assert [f.rsplit("_", 2)[1] for f in found] == ["D", "P"]


class Pages:
    def __init__(self, pages):
        self.pages, self.delays = pages, {}

    def get(self, url, binary=False):
        return self.pages.get(url)


def test_bmc_takes_the_numbered_photos_after_the_side_view():
    import json
    stem = "https://cdn.shopify.com/s/files/1/x/files/bmc-2027-kaius-01-three-gravel-bike-black-%s.jpg?v=1"
    product = {"product": {"images": [{"src": stem % n} for n in (1, 5, 3, "2_ab12-cd34")]}}
    url = "https://nl.bmc-switzerland.com/products/kaius-01-three"
    found = galleries.bmc_page(Pages({url + ".json": json.dumps(product)}), {"url": url})[""]
    assert [f.split("black-")[1].split(".")[0] for f in found] == ["2_ab12-cd34", "3", "5"]
    assert galleries.bmc_page(Pages({}), {"url": "https://web.archive.org/web/2020/" + url}) == {}


def test_lapierre_splits_the_photos_by_colour_and_drops_the_geometry():
    import json
    img = lambda n, alt="", variants=(): {"position": n, "src": f"https://cdn.shopify.com/{n}.jpg", "alt": alt,
                                          "variant_ids": list(variants)}
    product = {"options": [{"name": "Frame Kind"}, {"name": "Color"}],
               "variants": [{"id": 1, "option2": "black - matt"}, {"id": 2, "option2": "paris stone beige - matt"}],
               "images": [img(1, variants=[1]), img(2), img(3), img(4, "Geometry_XeliusDRS"), img(5, variants=[2]), img(6)]}
    url = "https://lapierrebikes.com/en-be/products/xelius-drs-80-lxdtb"
    found = galleries.lapierre_page(Pages({url + ".json": json.dumps({"product": product})}), {"url": url})
    assert {c: [u.split("/")[-1].split("?")[0] for u in us] for c, us in found.items()} == {
        "Black - matt": ["2.jpg", "3.jpg"], "Paris stone beige - matt": ["6.jpg"]}


def test_lapierre_falls_back_to_the_store_listing_when_the_page_is_not_sold_here():
    import json
    galleries._LISTINGS.clear()
    product = {"handle": "pulsium-40", "options": [{"name": "Color"}], "variants": [{"id": 1, "option1": "grey"}],
               "images": [{"position": 1, "src": "s.jpg", "variant_ids": [1]}, {"position": 2, "src": "d.jpg"}]}
    listing = "https://lapierrebikes.com/en-be/products.json?limit=250&page=1"
    found = galleries.lapierre_page(Pages({listing: json.dumps({"products": [product]})}),
                                    {"url": "https://lapierrebikes.com/en-be/products/pulsium-40"})
    galleries._LISTINGS.clear()
    assert found == {"": ["d.jpg?width=1200"]}


def test_scott_leaves_out_each_colours_side_view(tmp_path, monkeypatch):
    import json
    (tmp_path / "data" / "Scott").mkdir(parents=True)
    src = "https://static.scott-sports.com/image/upload/v1/%s.png"
    (tmp_path / "data" / "Scott" / "scott_gallery.json").write_text(json.dumps({"Foil RC 10": {
        "url": "u", "images": [{"src": src % "2288160", "color": "black"}, {"src": src % "4275953020A", "color": "black"},
                               {"src": src % "2288161", "color": "red"}]}}))
    monkeypatch.setattr(galleries, "ROOT", str(tmp_path))
    found = galleries.scott_page(None, {"url": "u"})
    assert found == {"black": ["https://static.scott-sports.com/image/upload/w_1400/v1/4275953020A.png"]}


def test_orbea_takes_the_views_other_than_the_side_per_colour():
    import json
    product = {"type": "bike", "colors": [{"code": "A", "name": "Black"}, {"code": "B", "name": "Blue"}],
               "images": [{"src": "a-side.jpg", "color": "A", "view": "side"}, {"src": "a-34.jpg", "color": "A", "view": "34"},
                          {"src": "b-side.jpg", "color": "B", "view": "side"}, {"src": "b-top.jpg", "color": "B", "view": "top"}]}
    page = "<div x-init=\"product = JSON.parse('%s')\">" % json.dumps(product).replace('"', "&quot;")
    found = galleries.orbea_page(Page(page), {"url": "u"})
    assert found == {"Black": ["a-34.jpg"], "Blue": ["b-top.jpg"]}
