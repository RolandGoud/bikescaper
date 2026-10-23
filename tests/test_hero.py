import json
import os

HERO_DIR = os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "hero")


def test_every_hero_photo_has_a_credit():
    with open(os.path.join(HERO_DIR, "credits.json"), encoding="utf-8") as f:
        credits = json.load(f)
    photos = {f for f in os.listdir(HERO_DIR) if f.endswith(".jpg")}
    assert photos and photos == set(credits)
    for credit in credits.values():
        assert credit["author"] and credit["license"]
        assert credit["source"].startswith("https://") and credit["license_url"].startswith("https://")
