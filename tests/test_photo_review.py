import io
import json
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from webapp import db, photo_review, seed
from webapp.app import PHOTO_SHOTS, create_app

REVIEW = {
    "photos": [
        {"photo": 1, "shows_en": "The whole bike from the drive side", "shows_nl": "De hele fiets van de aandrijfzijde",
         "matches_shot": True, "light": "good", "background": "ok", "sharpness": "sharp", "angle": "good",
         "details": "n/a", "stock_photo": False, "privacy_en": "", "privacy_nl": "", "verdict": "keep",
         "tip_en": "", "tip_nl": "", "notes_en": "Good light, whole bike in view.", "notes_nl": "Goed licht, hele fiets in beeld."},
        {"photo": 2, "shows_en": "A blurry derailleur", "shows_nl": "Een onscherpe derailleur", "matches_shot": True,
         "light": "poor", "background": "busy", "sharpness": "blurry", "angle": "ok", "details": "no",
         "stock_photo": False, "privacy_en": "A number plate", "privacy_nl": "Een kenteken", "verdict": "retake",
         "tip_en": "Get closer and tap to focus.", "tip_nl": "Ga dichterbij en tik om scherp te stellen.",
         "notes_en": "The model name can't be read.", "notes_nl": "De modelnaam is niet te lezen."},
    ],
    "summary_en": "Retake the derailleur.", "summary_nl": "Maak de derailleur opnieuw.",
}


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, answers with a review."""

    def __init__(self, answer=REVIEW, stop="end_turn"):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.answer, self.stop = answer, stop

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def jpeg(size=(2400, 1800)):
    out = io.BytesIO()
    Image.new("RGB", size, (40, 120, 200)).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    photo_review._asked.clear()
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    c = app.test_client()
    c.post("/admin/login", data={"password": "pw", "next": "/admin"})
    return c, app


def wait_done(path, token, lang="en"):
    for _ in range(100):
        found = photo_review.result(path, token, lang)
        if found["status"] != "running":
            return found
        time.sleep(0.05)
    return found


def test_prepare_shrinks_photos_and_refuses_what_isnt_one():
    import base64
    data = photo_review.prepare(jpeg())
    with Image.open(io.BytesIO(base64.b64decode(data))) as im:
        assert max(im.size) == photo_review.MAX_SIDE
    assert photo_review.prepare(b"not a photo") is None
    assert photo_review.prepare(b"") is None


def test_review_sends_each_photo_with_its_shot_and_parses_the_answer():
    client = FakeClient()
    data = photo_review.prepare(jpeg())
    review = photo_review.review_photos([("drive-side", data), ("derailleur", data)], PHOTO_SHOTS, client)
    assert review == REVIEW
    sent = client.calls[0]
    content = sent["messages"][0]["content"]
    assert sum(b["type"] == "image" for b in content) == 2
    assert 'Photo 2, taken for the shot "Rear derailleur"' in content[2]["text"]
    assert sent["output_config"]["format"]["schema"] is photo_review.SCHEMA
    assert photo_review.review_photos([("drive-side", data)], PHOTO_SHOTS, FakeClient(stop="refusal")) is None
    assert photo_review.review_photos([], PHOTO_SHOTS, client) is None


def test_a_review_runs_in_the_background_and_reads_in_the_page_language(tmp_path):
    path = str(tmp_path / "x.sqlite3")
    data = photo_review.prepare(jpeg())
    token = photo_review.start(path, [("drive-side", data), ("derailleur", data)], PHOTO_SHOTS, "nl", client=FakeClient())
    found = wait_done(path, token, "nl")
    assert found["status"] == "done" and found["summary"] == "Maak de derailleur opnieuw."
    assert [p["shot"] for p in found["photos"]] == ["drive-side", "derailleur"]
    assert found["photos"][1]["tip"] == "Ga dichterbij en tik om scherp te stellen."
    assert found["photos"][1]["privacy"] == "Een kenteken"
    assert found["photos"][0]["tip"] == ""
    assert photo_review.result(path, token, "en")["photos"][1]["notes"] == "The model name can't be read."
    assert photo_review.result(path, "nope", "en") == {"status": "unknown"}
    # A failed call is said so, not left running.
    token = photo_review.start(path, [("drive-side", data)], PHOTO_SHOTS, "en", client=FakeClient(stop="max_tokens"))
    assert wait_done(path, token)["status"] == "failed"


def test_the_site_and_each_visitor_have_a_limit(tmp_path, monkeypatch):
    path = str(tmp_path / "x.sqlite3")
    photo_review._asked.clear()
    assert photo_review.allowed(path, "1.2.3.4")
    for _ in range(photo_review.PER_HOUR):
        photo_review._asked.append((time.time(), "1.2.3.4"))
    assert not photo_review.allowed(path, "1.2.3.4")
    assert photo_review.allowed(path, "5.6.7.8")
    monkeypatch.setattr(photo_review, "PER_DAY", 0)
    assert not photo_review.allowed(path, "5.6.7.8")
    photo_review._asked.clear()


def test_without_a_key_the_offer_stays_coming_soon(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(str(tmp_path / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))
    c = app.test_client()
    page = c.get("/sell?step=photos&lang=en").data.decode()
    assert "data-fake-door" in page and "data-photo-review" not in page and "photo-review.js" not in page
    assert c.post("/sell/photo-review/start").status_code == 404
    assert c.get("/sell/photo-review/result/x").status_code == 404


def test_with_a_key_only_the_admin_gets_the_prototype(client):
    c, app = client
    page = c.get("/sell?step=photos&lang=nl").data.decode()
    assert "data-photo-review" in page and "data-fake-door" not in page and "photo-review.js" in page
    assert "PROTOTYPE · FOTOCHECK" in page and "ALLEEN VOOR JOU (ADMIN)" in page
    assert "Anthropic" in page  # told where the photos go
    # A visitor still sees the paid offer that only counts interest, and can't start a review.
    visitor = app.test_client()
    page = visitor.get("/sell?step=photos&lang=en").data.decode()
    assert "data-fake-door" in page and "data-photo-review" not in page and "€5" in page
    assert visitor.post("/sell/photo-review/start").status_code == 404
    assert visitor.get("/sell/photo-review/result/x").status_code == 404


def test_the_page_sends_the_slots_and_gets_the_review(client, monkeypatch):
    c, app = client
    seen = {}

    def fake_review(photos, shots, client=None):
        seen["keys"] = [k for k, _ in photos]
        return REVIEW

    monkeypatch.setattr(photo_review, "review_photos", fake_review)
    r = c.post("/sell/photo-review/start?lang=en", data={
        "shot-drive-side": (io.BytesIO(jpeg()), "a.jpg"), "shot-derailleur": (io.BytesIO(jpeg()), "b.jpg"),
        "shot-made-up": (io.BytesIO(jpeg()), "c.jpg"), "model_id": ""}, content_type="multipart/form-data")
    assert r.status_code == 202
    token = r.get_json()["token"]
    for _ in range(100):
        found = c.get(f"/sell/photo-review/result/{token}?lang=en").get_json()
        if found["status"] != "running":
            break
        time.sleep(0.05)
    assert found["status"] == "done" and found["photos"][1]["verdict"] == "retake"
    assert seen["keys"] == ["drive-side", "derailleur"]  # only real shots, in page order
    conn = db.connect(app.config["DB_PATH"])
    assert conn.execute("SELECT COUNT(*) FROM photo_review_interest WHERE kind = 'review'").fetchone()[0] == 1
    assert c.get("/sell/photo-review/result/nope").status_code == 404
    # Nothing usable sent: a reason, no review.
    r = c.post("/sell/photo-review/start?lang=en", data={"shot-drive-side": (io.BytesIO(b"x"), "a.jpg")},
               content_type="multipart/form-data")
    assert r.status_code == 400 and r.get_json()["error"] == "Add at least one photo first."
