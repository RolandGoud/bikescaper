"""A French ad text (2dehands, check 87) is shown in Dutch or English on the check page, the original a click away."""
import json
import os
import time
from types import SimpleNamespace

from webapp import ad_translate, db, seed

FRENCH = ("Vends mon vélo de course Canyon Endurace CF SL 7, taille M, en très bon état.\n"
          "Groupe Shimano 105 Di2, roues DT Swiss. Acheté en 2021, facture disponible.\n"
          "Entretien fait il y a un mois. Prix à discuter, pas d'échange.")
DUTCH = ("Mooie racefiets Canyon Endurace CF SL 7, maat M, in zeer goede staat.\n"
         "Shimano 105 Di2, wielen DT Swiss. Gekocht in 2021, factuur is er nog.")
ENGLISH = "Selling my Canyon Endurace CF SL 7, size M, in very good condition. Bought in 2021, invoice is still there."
ANSWER = {"nl": "Ik verkoop mijn racefiets Canyon Endurace CF SL 7, maat M, in zeer goede staat.",
          "en": "Selling my Canyon Endurace CF SL 7 road bike, size M, in very good condition."}


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, answers with a translation."""

    def __init__(self, answer, stop="end_turn"):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.answer, self.stop = answer, stop

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def wait_for(path):
    for _ in range(100):
        if os.path.exists(path):
            return
        time.sleep(0.05)


def test_language_tells_french_from_dutch_and_english():
    assert ad_translate.language(FRENCH) == "fr"
    assert ad_translate.language(DUTCH) == "nl"
    assert ad_translate.language(ENGLISH) == "en"
    # Too little to tell, or only bike words: shown as it is.
    assert ad_translate.language("Canyon Endurace CF SL 7, Shimano 105, 11 vitesses") is None
    assert ad_translate.language("") is None and ad_translate.language(None) is None


def test_translate_sends_the_text_and_parses_the_answer():
    client = FakeClient(ANSWER)
    assert ad_translate.translate(FRENCH, client) == ANSWER
    sent = client.calls[0]
    assert FRENCH in sent["messages"][0]["content"]
    assert sent["output_config"]["format"]["schema"] is ad_translate.SCHEMA


def test_a_refusal_or_empty_answer_is_no_translation():
    assert ad_translate.translate(FRENCH, FakeClient(ANSWER, stop="refusal")) is None
    assert ad_translate.translate(FRENCH, FakeClient({"nl": " ", "en": ""})) is None
    assert ad_translate.translate("", FakeClient(ANSWER)) is None


def test_translate_later_keeps_it_once_per_text(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = FakeClient(ANSWER)
    assert ad_translate.translate_later(str(tmp_path), 87, FRENCH, client)
    wait_for(tmp_path / "87" / "translation.json")
    assert ad_translate.stored(str(tmp_path), 87, FRENCH) == ANSWER
    assert not ad_translate.translate_later(str(tmp_path), 87, FRENCH, client)
    assert len(client.calls) == 1
    # The ad's text changed (fetched again): the old translation doesn't stand for it.
    assert ad_translate.stored(str(tmp_path), 87, FRENCH + " Urgent.") is None


def test_only_french_is_sent_and_nothing_without_a_key(tmp_path, monkeypatch):
    client = FakeClient(ANSWER)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    assert not ad_translate.translate_later(str(tmp_path), 1, DUTCH, client)
    assert not ad_translate.translate_later(str(tmp_path), 1, ENGLISH, client)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not ad_translate.translate_later(str(tmp_path), 1, FRENCH, client)
    assert client.calls == []


def test_report_page_shows_the_translation_with_the_original(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from webapp.app import create_app
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (listing_url, title, description, asking_price) VALUES (?,?,?,?)",
                 ("https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2300000087-canyon-endurace",
                  "Canyon Endurace CF SL 7", FRENCH, 1800))
    conn.commit()
    client = app.test_client()
    # Not translated yet (no key): the French text as before.
    page = client.get("/check/1?lang=nl").data.decode()
    assert "Vends mon vélo" in page and "Vertaald uit het Frans" not in page
    folder = os.path.join(os.path.dirname(app.config["DB_PATH"]), "ad-photos")
    os.makedirs(os.path.join(folder, "1"))
    with open(os.path.join(folder, "1", "translation.json"), "w", encoding="utf-8") as fh:
        json.dump({"text": ad_translate._digest(FRENCH), "translation": ANSWER}, fh)
    page = client.get("/check/1?lang=nl").data.decode()
    assert "Ik verkoop mijn racefiets" in page and "VERTAALD UIT HET FRANS" in page
    assert "Toon het origineel (Frans)" in page and "Vends mon vélo" in page
    page = client.get("/check/1?lang=en").data.decode()
    assert "Selling my Canyon Endurace CF SL 7 road bike" in page and "TRANSLATED FROM FRENCH" in page
