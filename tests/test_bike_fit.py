import json
import os
import time

from PIL import Image, ImageFilter, ImageOps

from webapp import bike_direction, bike_fit, db, seed
from webapp.app import create_app

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOGUE = os.path.join(ROOT, "images", "Trek", "DomaneAL4-24-41607-A-Primary_01.jpg")
OTHER = os.path.join(ROOT, "images", "Cannondale", "CAAD14_1.jpg")


def fake_ad(catalogue, path, mirror):
    """A seller's photo: the bike small and off to one side, in front of a blurry wall, maybe facing left."""
    wall = Image.new("RGB", (1200, 900), (150, 135, 120)).filter(ImageFilter.GaussianBlur(4))
    bike = Image.open(catalogue).convert("RGB")
    bike = bike.resize((640, round(640 * bike.height / bike.width)))
    wall.paste(bike, (480, 360))
    (ImageOps.mirror(wall) if mirror else wall).save(path, quality=90)


def test_finds_the_bike_and_which_way_it_faces(tmp_path):
    for mirror in (False, True):
        for catalogue in (CATALOGUE, OTHER):  # also when the catalogue shows another bike
            ad = tmp_path / f"ad-{mirror}.jpg"
            fake_ad(CATALOGUE, ad, mirror)
            fit = bike_fit.find(Image.open(ad), Image.open(catalogue))
            assert fit and fit["flip"] == mirror, (catalogue, mirror)
            if catalogue == CATALOGUE:
                assert 0.4 < fit["w"] < 0.65
                assert abs((1 - fit["x"] - fit["w"] if mirror else fit["x"]) - 0.4) < 0.08


def test_unsure_without_a_whole_bike(tmp_path):
    # Real ads often show only part of the bike: then the photo is drawn as it is, not zoomed in on a guess.
    ad = tmp_path / "ad.jpg"
    fake_ad(CATALOGUE, ad, False)
    photo = Image.open(ad)
    close_ups = [photo.crop((800, 360, 1120, 600)), photo.crop((480, 560, 800, 900)), photo.crop((0, 0, 1200, 300))]
    for close_up in close_ups:
        assert bike_fit.find(close_up.resize((1024, 768)), Image.open(CATALOGUE)) is None


def test_placement_puts_the_bike_on_the_catalogue_bike_without_gaps(tmp_path):
    ad = tmp_path / "ad.jpg"
    fake_ad(CATALOGUE, ad, True)
    place = bike_fit.work_out(str(ad), CATALOGUE)
    assert place["flip"] and place["width"] > 120  # the small bike is drawn bigger
    assert place["left"] <= 0 and place["top"] <= 0
    assert place["left"] + place["width"] >= 100 and place["top"] + place["height"] >= 100


def test_worked_out_once_in_the_background_then_kept(tmp_path):
    ad = tmp_path / "ad.jpg"
    fake_ad(CATALOGUE, ad, True)
    # not lined up yet, but already the right way round
    assert bike_fit.style(str(ad), CATALOGUE) == {"flip": True}
    key = bike_fit._key(CATALOGUE, None)
    for _ in range(100):
        if key in bike_fit._read(str(ad)):
            break
        time.sleep(0.1)
    kept = bike_fit.style(str(ad), CATALOGUE)
    assert kept and kept["flip"] and "width" in kept
    assert json.load(open(str(ad) + ".fit.json")) == {key: kept, bike_fit.DIRECTION: True}


def test_stays_mirrored_while_another_catalogue_photo_is_lined_up(tmp_path):
    # The report shows the catalogue bike in the ad's colour: another photo, so another placement to
    # work out. Meanwhile the ad photo must not turn back to facing left.
    ad = tmp_path / "ad.jpg"
    fake_ad(CATALOGUE, ad, True)
    with open(str(ad) + ".fit.json", "w") as f:
        json.dump({bike_fit._key(CATALOGUE, None): bike_fit.work_out(str(ad), CATALOGUE)}, f)
    assert bike_fit.style(str(ad), OTHER) == {"flip": True}
    right = tmp_path / "right.jpg"
    fake_ad(CATALOGUE, right, False)
    assert bike_fit.style(str(right), OTHER) is None


def test_merged_tile_draws_the_ad_photo_lined_up(tmp_path):
    # No year in the ad, so the report keeps the current catalogue photo (a stated year shows that year's photo).
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    os.makedirs(tmp_path / "ad-photos" / "1")
    fake_ad(CATALOGUE, tmp_path / "ad-photos" / "1" / "01.jpg", True)
    conn.execute("INSERT INTO checks (title, asking_price, photos) VALUES (?, ?, ?)",
                 ("Trek Domane AL 4 Gen 4 maat 54", 1050, '["1/01.jpg"]'))
    conn.commit()
    model = next(m for m in db.all_models(conn) if m["image"] and m["image"].endswith("DomaneAL4-24-41607-A-Primary_01.jpg"))
    stored = str(tmp_path / "ad-photos" / "1" / "01.jpg")
    place = bike_fit.work_out(stored, CATALOGUE, (1.12, 0.03))
    with open(stored + ".fit.json", "w") as f:
        json.dump({bike_fit._key(os.path.join(ROOT, "images", model["image"]), (1.12, 0.03)): place}, f)
    page = app.test_client().get("/check/1?lang=en").get_data(as_text=True)
    assert f'class="flip" style="left: {place["left"]}%; top: {place["top"]}%;' in page


def test_tells_which_way_the_bike_faces():
    for path in (CATALOGUE, OTHER):
        photo = Image.open(path)
        assert bike_direction.faces_left(photo) is False
        assert bike_direction.faces_left(ImageOps.mirror(photo)) is True
        assert bike_direction.score(ImageOps.mirror(photo)) == -bike_direction.score(photo)


def test_mirrored_even_when_it_cant_be_lined_up(tmp_path):
    # A close-up of a left-facing bike: too little of it to line up, but it still gets turned round.
    ad = tmp_path / "ad.jpg"
    bike = Image.open(OTHER).convert("RGB")
    ImageOps.mirror(bike).crop((0, 0, bike.width * 3 // 4, bike.height)).save(ad)
    place = bike_fit.work_out(str(ad), CATALOGUE)
    assert place == {"flip": True}
