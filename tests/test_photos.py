from PIL import Image, ImageDraw

from brand_scrapers.common import trim


def test_a_close_up_loses_the_white_bars_around_it():
    img = Image.new("RGB", (1000, 562), "white")
    img.paste(Image.new("RGB", (682, 512), (20, 10, 10)), (159, 25))
    assert trim(img).size == (682, 512)


def test_a_bike_on_white_is_framed_like_the_main_photo():
    img = Image.new("RGB", (1000, 562), "white")
    ImageDraw.Draw(img).ellipse((300, 200, 500, 400), outline="black", width=8)
    out = trim(img)
    assert round(out.width / out.height, 2) == round(16 / 9, 2)
