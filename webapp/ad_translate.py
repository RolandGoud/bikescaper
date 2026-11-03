"""Ad text in French, shown in Dutch (and English) on the check page.

2dehands is Belgian, and sellers in Wallonia and Brussels write their ads in French (check 87). The
check page shows such a text translated into the visitor's language, with the French original one
click away. Dutch and English ads are shown as they are.

- language() tells French from Dutch and English by their common short words: no library, no network.
- The translation comes from the Claude API when ANTHROPIC_API_KEY is set in the container, once per
  ad text, in the background on the first view of the check; kept in ad-photos/<check id>/translation.json
  next to the check's photos. Until it's there, and without a key, the page shows the French text as before.

The checks themselves keep reading the original text: their word lists already know French bike words.
"""
import hashlib
import json
import os
import re
import sys
import threading
from datetime import date

CACHE_NAME = "translation.json"
MODEL = os.environ.get("AD_TRANSLATE_MODEL", "claude-opus-5-5")
MAX_CHARS = 12000  # longer than any ad; a pasted page of junk isn't sent whole

# Short words that are common in one language and (nearly) never in the other two. "de" and "en" are left
# out: both are everyday words in French and in Dutch.
FRENCH = set("""le la les un une des du au aux et est sont avec pour sur dans pas très tres plus mais ou qui que
    vous nous il elle ce cette ces mon ma mes son sa ses votre vos été etat état bon bonne neuf neuve vends vend
    vendre prix cause taille roues pneus vitesses acheté achete facture peu jamais aucun aucune merci
    entretien révisé revise parfait parfaitement""".split())
DUTCH = set("""het een is zijn met voor op in niet zeer heel goede goed staat nieuw nieuwe te koop verkoop maat
    wielen banden versnellingen gekocht factuur weinig nooit geen mogelijk bedankt onderhoud perfecte prima ik
    u wij hij zij deze dit mijn zijn uw nog ook maar of die dat wordt werd""".split())
ENGLISH = set("""the a an and is are with for on in not very good condition new sale size wheels tyres tires
    bought invoice never no thanks serviced perfect i you we he she this my your still also but or
    that which""".split())

_WORD = re.compile(r"[a-zà-ÿ]+")


def language(text):
    """"fr", "nl" or "en" for the language most of the text is in, or None when there's too little to tell."""
    words = _WORD.findall((text or "").lower())
    counts = {"fr": sum(w in FRENCH for w in words), "nl": sum(w in DUTCH for w in words),
              "en": sum(w in ENGLISH for w in words)}
    best = max(counts, key=counts.get)
    # A few stray words ("Shimano 105, 11 vitesses") aren't enough, and a clear lead is needed over the runner-up.
    if counts[best] < 3 or counts[best] < 1.5 * max(v for k, v in counts.items() if k != best):
        return None
    return best


def is_french(text):
    return language(text) == "fr"


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- translating

PROMPT = """Below is the text of a second-hand bicycle ad from 2dehands.be, written in French. Translate it into
Dutch (as spoken in Belgium and the Netherlands, plain and natural) and into English.

- Keep the meaning, the order and the line breaks. Translate everything, also lists like "Taille: M".
- Leave brand names, model names, component names and codes as they are (Shimano 105, Ultegra Di2, SRAM Rival
  AXS, Canyon Endurace CF SL 7, R7000), and all numbers, sizes, prices and units.
- Write only the translation: no notes, no quotes around it.

The ad text:
"""

SCHEMA = {
    "type": "object",
    "properties": {"nl": {"type": "string"}, "en": {"type": "string"}},
    "required": ["nl", "en"],
    "additionalProperties": False,
}


def translate(text, client=None):
    """{"nl": ..., "en": ...} for a French ad text, or None when it couldn't be translated (an API error, a
    refusal). Errors are logged, never raised."""
    text = (text or "").strip()[:MAX_CHARS]
    if not text:
        return None
    import anthropic  # only needed when a key is set
    client = client or anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": PROMPT + text}],
        )
    except anthropic.APIStatusError as e:
        print(f"ad translation: API error {e.status_code}: {e.message}", file=sys.stderr, flush=True)
        return None
    except anthropic.APIConnectionError as e:
        print(f"ad translation: no connection ({e})", file=sys.stderr, flush=True)
        return None
    if response.stop_reason != "end_turn":
        print(f"ad translation: stopped ({response.stop_reason})", file=sys.stderr, flush=True)
        return None
    answer = next((b.text for b in response.content if b.type == "text"), "")
    try:
        result = json.loads(answer)
    except ValueError:
        print(f"ad translation: not JSON: {answer[:200]!r}", file=sys.stderr, flush=True)
        return None
    if not (result.get("nl") or "").strip():
        return None
    return {"nl": result["nl"].strip(), "en": (result.get("en") or "").strip()}


# ---------------------------------------------------------------- stored translations

def _cache_path(folder, check_id):
    return os.path.join(folder, str(check_id), CACHE_NAME)


def stored(folder, check_id, text):
    """The stored translation of this check's text ({"nl": ..., "en": ...}), or None when there's none (yet), or
    it's of another text (the ad was edited and fetched again)."""
    if check_id is None or not text:
        return None
    try:
        with open(_cache_path(folder, check_id), encoding="utf-8") as fh:
            saved = json.load(fh)
    except (OSError, ValueError):
        return None
    if saved.get("text") != _digest(text):
        return None
    return saved.get("translation") or None


_running = set()
_slots = threading.BoundedSemaphore(2)


def translate_later(folder, check_id, text, client=None):
    """Translate a French ad text in the background and keep it next to the check's photos. Does nothing for
    text that isn't French, without an API key, when it's translated already or being translated."""
    if check_id is None or not enabled() or not is_french(text) or check_id in _running:
        return False
    if stored(folder, check_id, text):
        return False
    _running.add(check_id)

    def work():
        try:
            with _slots:
                translation = translate(text, client)
            if translation is None:
                return  # an error: the next page view tries again
            os.makedirs(os.path.join(folder, str(check_id)), exist_ok=True)
            # Written next to it and then moved in place, so a page view never reads half a file.
            path = _cache_path(folder, check_id)
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump({"text": _digest(text), "from": "fr", "model": MODEL, "translated_on": date.today().isoformat(),
                           "translation": translation}, fh, ensure_ascii=False, indent=1)
            os.replace(path + ".part", path)
        except Exception as e:  # never take the page down
            print(f"translating the ad of check {check_id} failed: {e!r}", file=sys.stderr, flush=True)
        finally:
            _running.discard(check_id)

    threading.Thread(target=work, name=f"translate-{check_id}", daemon=True).start()
    return True


def for_page(folder, check_id, text, lang):
    """What the check page shows: {"text": the translation in `lang`, "original": the French text} for a
    translated French ad, else None (the page shows the text as it is). Starts the translation when needed."""
    if not is_french(text):
        return None
    translation = stored(folder, check_id, text)
    if not translation:
        translate_later(folder, check_id, text)
        return None
    shown = translation.get(lang) or translation.get("nl")
    return {"text": shown, "original": text} if shown else None
