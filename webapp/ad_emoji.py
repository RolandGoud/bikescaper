"""Ads that are thick with emoji, shown without them.

Some sellers put an emoji on every line ("\u2705 Shimano 105 \U0001F525 Nieuwe banden \U0001F6B4\u200D\u2642\uFE0F ..."). A couple is part of
how the seller writes, so an ad with a few keeps them; once there are a lot, every emoji goes and the text
reads plainly. Whether an ad has "a lot" is counted over its title and text together, so its title and its
text are treated alike. Only what is shown changes: the stored ad (and the matching, which reads it) keeps
the seller's own text.
"""
import re

# One emoji as a reader sees it: a pictograph or symbol with what joins onto it (skin tone, the emoji
# presentation selector, a zero-width joiner and the next pictograph, a keycap) or a pair of flag letters.
_PICTO = ("\U0001F000-\U0001F1E5\U0001F200-\U0001FAFF"  # pictographs, symbols, transport, faces, ...
          "\u2600-\u27BF"  # misc symbols and dingbats: sun, check marks, crosses, hearts, sparkles
          "\u2B00-\u2BFF"  # arrows and stars
          "\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2934\u2935\u3030\u303D\u3297\u3299"  # arrows, watch, play
          "\u203C\u2049")  # double exclamation, exclamation question
_ADD = "\U0001F3FB-\U0001F3FF\uFE0F\uFE0E\u20E3\U000E0020-\U000E007F"  # skin tones, selectors, keycap, tags
_ONE = ("(?:[0-9#*]\uFE0F?\u20E3"  # keycaps: 1 + selector + keycap
        "|[\U0001F1E6-\U0001F1FF]{2}"  # flags: a pair of regional letters
        f"|[{_PICTO}][{_ADD}]*(?:\u200D[{_PICTO}][{_ADD}]*)*)")  # with zero-width joiners: one rider
EMOJI = re.compile(_ONE)
# Arrows, squares and the like are emoji only in their coloured form (followed by U+FE0F); bare, they're text.
_TEXT_SYMBOLS = re.compile("[\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2B00-\u2BFF]")

# From this many emoji in an ad, they all go. Measured on the site's 221 ads in November 2026: 192 have none,
# 16 have one to three (a 👍, a 🔧, ✔ by a few lines), and the other 13 have eight to fifty, as a bullet on
# nearly every line and decoration around it (check 225: 🔥🔥, ⏩️⏩️, ✅️ on every spec, ‼️). Six sits in the
# empty gap between the two.
MANY = 6


def _emoji(text):
    """The emoji in the text, as a reader counts them."""
    found = []
    for m in EMOJI.finditer(text or ""):
        e = m.group(0)
        if len(e) == 1 and _TEXT_SYMBOLS.match(e):
            continue  # a bare ↗ or ■ is a symbol in the text, not an emoji
        found.append(m)
    return found


def count(*texts):
    """How many emoji the texts have between them."""
    return sum(len(_emoji(t)) for t in texts)


def _ad_texts(ad):
    if ad is None:
        return ()
    get = ad.get if hasattr(ad, "get") else (lambda k: ad[k] if k in ad.keys() else None)
    return tuple(get(k) or "" for k in ("title", "description"))


def too_many(ad):
    """Whether the ad (a row or dict with its title and description) has a lot of emoji."""
    return count(*_ad_texts(ad)) >= MANY


def strip(text):
    """The text without its emoji, tidied: no double spaces, no space at the start or end of a line, no line left
    with only punctuation, and no more than one empty line in a row."""
    if not text:
        return text
    out = text
    for m in reversed(_emoji(text)):
        out = out[:m.start()] + " " + out[m.end():]
    lines = []
    for line in out.split("\n"):
        line = re.sub(r"[ \t\u00A0]{2,}", " ", line).strip()
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)
        if line and not re.search(r"\w", line):
            line = ""  # a line that was only emoji (and a dash or a dot)
        lines.append(line)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out or text.strip()


def tame(text, ad=None):
    """The text as shown: without emoji when its ad has a lot of them, as it is otherwise. Without `ad`, the text
    is counted on its own."""
    if not text:
        return text
    many = too_many(ad) if ad is not None else count(text) >= MANY
    return strip(text) if many else text
