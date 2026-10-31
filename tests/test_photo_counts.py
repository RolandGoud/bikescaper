from webapp import db, photo_counts, seed
from webapp.app import create_app


def test_photos_count_once_per_model_year():
    model = {"brand": "Giant", "name": "Defy 1", "slug": "giant-defy-1", "seen_on": "2026-03-01", "url": "u",
             "image": "a.jpg", "colorways": [{"image": "a.jpg"}, {"image": "b.jpg"}, {"image": None}],
             "year_specs": {"years": {"2024": {"image": "y.jpg", "colour_images": {"Red": "y.jpg", "Blue": "gone.jpg"},
                                               "colour_angles": {"Red": ["y2.jpg"]}}}}}
    galleries = {"u": {"Red": ["a.jpg", "c.jpg"]}}
    found = photo_counts.model_photos(model, galleries, exists=lambda p: p != "gone.jpg")
    assert found == {2026: {"a.jpg", "b.jpg", "c.jpg"}, 2024: {"y.jpg", "y2.jpg"}}
    archived = dict(model, seen_on=None, slug="giant-defy-2", name="Defy 2", year_specs={}, colorways=[])
    out = photo_counts.overview([model, archived], galleries, exists=lambda p: True)
    giant = out["brands"][0]
    assert out["years"] == [2024, 2026, None]
    assert giant["total"] == 8 and giant["years"] == {2024: 3, 2026: 3, None: 2}  # gone.jpg counts here
    assert giant["none"] == 0 and giant["one"] == 0


def test_admin_page_shows_the_photo_counts(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    page = app.test_client().get("/admin?lang=en").get_data(as_text=True)
    assert "Catalogue photos" in page and 'id="photos-giant"' in page and "/models/giant-" in page
    assert "Catalogusfoto" in app.test_client().get("/admin?lang=nl").get_data(as_text=True)
