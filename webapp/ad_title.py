"""The ad's title without the clutter, for the report's heading.

Sellers pad titles with prices ("van €3599 voor € 2450"), "te koop", emoji, shouting and the odd repeat.
The report shows the price on its own, so the heading keeps what the bike is: the model words first and
bold, the rest (groupset, size, year) after them.
"""
import re

from .checks import _tokens

_PRICE = re.compile(r"(?i)\b(?:(?:nieuw)?prijs|van|voor|nu|vraagprijs|nieuwprijs|was|ipv|i\.p\.v\.)?\s*:?\s*"
                    r"(?:€\s*\d[\d.,]*(?:\s*,-|-)?|\d[\d.,]*\s*(?:euro|eur)\b|\d[\d.,]*\s*,-)")
_FILLER = re.compile(r"(?i)\b(?:te koop|tk|t\.k\.|aangeboden|bieden|nette|mooie|zgan|z\.g\.a\.n\.?)\b")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def clean(title):
    """The title without prices, filler words, emoji, shouting or a word said twice in a row."""
    text = _EMOJI.sub(" ", title or "")
    text = _PRICE.sub(" ", text)
    text = _FILLER.sub(" ", text)
    text = re.sub(r"[!*#~_|]+", " ", text)
    words = []
    for w in text.split():
        if len(w) > 3 and w.isupper() and w.isalpha():
            w = w.capitalize()  # "TREK" → "Trek"; "SL", "105", "Di2" stay
        if words and w.lower() == words[-1].lower():
            continue
        words.append(w)
    while words and words[-1] in "-–—:,·/":
        words.pop()
    return " ".join(words).strip(" -–—:,·/") or (title or "").strip()


def parts(title, model=None):
    """(model words, the rest) of the cleaned title: "Giant Defy Advanced 1", "Shimano 105 Di2". The model
    words are the title's opening words that are the brand or in the model's name; without them, it's all
    the first part."""
    words = clean(title).split()
    if not model:
        return " ".join(words), ""
    known = set(_tokens(f"{model['brand']} {model['name']}"))
    at = 0
    while at < len(words) and _tokens(words[at]) and set(_tokens(words[at])) <= known:
        at += 1
    if at == 0:
        return " ".join(words), ""
    return " ".join(words[:at]), " ".join(words[at:])
