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
