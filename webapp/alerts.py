"""Price alerts: email a visitor when a new ad for a model asks less than the middle of its fair range.

A visitor leaves an email on a model page, for that model or any bike of its family ("any Trek Domane"),
optionally a frame size and a highest price. Nothing is mailed until they open the confirmation link.

Once a day, next to the daily checks (daily_checks.run_locked), one search per family that has a confirmed
alert, on Marktplaats and on 2dehands, reads the newest ads. Each ad is worked out like a check from its title
and the summary the search gives (no extra request per ad), and an ad an alert hasn't seen yet is a hit when:

  - it matches the alert's model (or family), with the size the alert asks for stated in the ad;
  - its asking price is at most the middle of the fair range, and at most the alert's highest price;
  - it isn't suspiciously cheap (under 60% of the fair range, as the report warns) or older than we have data for.

Each alert gets at most one mail a pass, with its hits and a link to stop the alert. Every ad an alert has seen
is remembered for that alert, so an ad is mailed once at most.

What's kept: the address, the model and the choices, the language, the site address the visitor used (for the links
in the mail), when it was confirmed and last mailed, and which ads the alert has seen. Stopping the alert deletes
all of it; an alert not confirmed within UNCONFIRMED_DAYS is deleted too.

    python -m webapp.alerts      # one pass by hand (also when the daily checks are off)
"""
import secrets
import unicodedata
import sys
import time

from . import checks, daily_checks, db, i18n, mail
from .i18n import gettext

UNCONFIRMED_DAYS = 7
PER_ADDRESS = 5        # alerts one address can have at a time
MAX_ADS_PER_MAIL = 5   # the cheapest hits, compared with their fair range, when there are more
MIN_PRICE = 100        # "bieden" and €1 ads aren't asking prices
SITES = (daily_checks.MARKTPLAATS, daily_checks.TWEEDEHANDS)


def family_label(model):
    """"Trek Domane" for any Domane build: how the form and the mail name the family, and what the alert searches."""
    return f"{model['brand']} {checks.model_line(model['name'])}"


def search_query(model):
    """What the alert searches for a line: "Trek Emonda", without accents, as the daily checks search it."""
    text = unicodedata.normalize("NFKD", family_label(model))
    return "".join(c for c in text if not unicodedata.combining(c))


def same_line(a, b):
    """Two models of one line, as the Models page's Model menu has them: any Tarmac, S-Works or not."""
    return a["brand"] == b["brand"] and checks.line_key(checks.model_line(a["name"])) == checks.line_key(
        checks.model_line(b["name"]))


def model_key(model):
    """One model whatever its build's groupset or generation: ("trek", "domane al 2") for "Domane AL 2 Gen 4"."""
    return (model["brand"].lower(), checks.without_generation(checks.split_build(model, frames=True)[0]).lower())


def model_label(model):
    return f"{model['brand']} {checks.model_title(checks.without_generation(checks.split_build(model, frames=True)[0]))}"


def norm_size(size):
    return (size or "").strip().upper().replace("XXS", "2XS").replace("XXL", "2XL").removesuffix(" CM") or None


# Signing up and stopping

def watches(alert, model):
    """What an alert watches, the same for every generation's or build's page: two alerts of one address with the
    same answer would mail the same ads."""
    what = checks.line_key(family_label(model)) if alert["scope"] == "family" else model_key(model)
    return (alert["scope"], what, alert["size"] or "")


def sign_up(conn, email, model, scope="model", size=None, max_price=None, lang="nl", site=""):
    """A new alert, unconfirmed: returns its token for the confirmation link, or None when the address has too
    many alerts already. A running alert is left alone until the new one is confirmed (confirm replaces it), so
    asking again by accident, or to change the highest price, never turns off one that works."""
    scope = "family" if scope == "family" else "model"
    size = norm_size(size)
    wanted = watches({"scope": scope, "size": size}, model)
    # The limit counts the bikes an address watches, so a running alert and its pending replacement are one.
    watched, earlier = set(), []
    for other in conn.execute("SELECT * FROM alerts WHERE lower(email) = lower(?)", (email,)).fetchall():
        other_model = db.get_model(conn, model_id=other["model_id"])
        key = watches(other, other_model) if other_model else ("gone", other["id"])
        if key == wanted:
            if not other["confirmed_at"]:
                earlier.append(other["id"])
        else:
            watched.add(key)
    if len(watched) >= PER_ADDRESS:
        return None
    for alert_id in earlier:  # an earlier request for the same, whose mail may never have come
        stop(conn, alert_id)
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO alerts (email, model_id, scope, size, max_price, lang, site, token) "
                 "VALUES (?,?,?,?,?,?,?,?)", (email, model["id"], scope, size, max_price, lang, site, token))
    conn.commit()
    return token


def by_token(conn, token):
    return conn.execute("SELECT * FROM alerts WHERE token = ?", (token,)).fetchone()


def confirm(conn, alert_id):
    """Start the alert. Another alert of the same address that watches the same bikes (from another generation's
    page, or asked for again) is replaced by it, keeping the ads that one already mailed about."""
    alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if alert is None or alert["confirmed_at"]:
        return
    model = db.get_model(conn, model_id=alert["model_id"])
    for other in conn.execute("SELECT * FROM alerts WHERE lower(email) = lower(?) AND id != ?",
                              (alert["email"], alert_id)).fetchall():
        other_model = db.get_model(conn, model_id=other["model_id"])
        if model and other_model and watches(other, other_model) == watches(alert, model):
            conn.execute("INSERT OR IGNORE INTO alert_ads (alert_id, ad_key) "
                         "SELECT ?, ad_key FROM alert_ads WHERE alert_id = ?", (alert_id, other["id"]))
            stop(conn, other["id"])
    conn.execute("UPDATE alerts SET confirmed_at = datetime('now') WHERE id = ?", (alert_id,))
    conn.commit()


def stop(conn, alert_id):
    """Delete the alert and the ads it saw: nothing of it is kept."""
    conn.execute("DELETE FROM alert_ads WHERE alert_id = ?", (alert_id,))
    conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()


def forget_unconfirmed(conn):
    old = [r["id"] for r in conn.execute(
        "SELECT id FROM alerts WHERE confirmed_at IS NULL AND created_at < datetime('now', ?)",
        (f"-{UNCONFIRMED_DAYS} days",))]
    for alert_id in old:
        stop(conn, alert_id)
    return len(old)


def describe(alert, model):
    """What the alert watches, in the current language: "Trek Domane AL 2, size 56, up to €900"."""
    parts = [gettext("any {family}", family=family_label(model)) if alert["scope"] == "family" else model_label(model)]
    if alert["size"]:
        parts.append(gettext("size {size}", size=alert["size"]))
    if alert["max_price"]:
        parts.append(gettext("up to {price}", price=checks.eur(alert["max_price"])))
    return ", ".join(parts)


# The daily pass

def judge(models, ad):
    """What an ad is, read like a check from its title and the search's summary of it:
    {"model", "size", "year", "low", "high", "suspect"}, or None when we can't price it."""
    report = checks.run_check(models, {"title": ad["title"], "description": ad.get("description") or "",
                                       "asking_price": ad["price"]})
    value = report.get("value") or {}
    if not report.get("model") or not value.get("low") or not value.get("high"):
        return None
    if checks.pre_2018_year(report):
        return None
    return {"model": report["model"], "size": norm_size(report["claims"].get("size")),
            "year": (report.get("year") or {}).get("year"), "low": value["low"], "high": value["high"],
            "suspect": ad["price"] < value["low"] * 0.6,
            "sure": report["confidence"].text if report.get("confidence") else None}


def fits(alert, model, ad, found):
    """Whether an ad the alert hasn't seen is one to mail about."""
    if found is None or found["suspect"]:
        return False
    if alert["scope"] == "family":
        if not same_line(found["model"], model):
            return False
    elif model_key(found["model"]) != model_key(model) or found["sure"] not in ("high", "medium"):
        return False
    if alert["size"] and found["size"] != alert["size"]:
        return False
    if alert["max_price"] and ad["price"] > alert["max_price"]:
        return False
    return ad["price"] <= (found["low"] + found["high"]) / 2


def mail_text(alert, model, hits):
    """Subject and body of one alert's mail, in the current language."""
    site = (alert["site"] or "").rstrip("/")
    what = describe(alert, model)
    subject = (gettext("A {what} under the fair price", what=what) if len(hits) == 1
               else gettext("{n} ads under the fair price: {what}", n=len(hits), what=what))
    lines = [gettext("New ads for your alert ({what}), asking at most the middle of their fair range:", what=what), ""]
    for ad, found in hits:
        lines.append(ad["title"])
        facts = [gettext("Asking {price}", price=checks.eur(ad["price"])),
                 gettext("fair {low}–{high}", low=checks.eur(found["low"]), high=checks.eur(found["high"]))]
        if found["size"]:
            facts.append(gettext("size {size}", size=found["size"]))
        if ad.get("location"):
            facts.append(ad["location"])
        lines.append(" · ".join(facts))
        lines.append(ad["url"])
        lines.append("")
    lines.append(gettext("The fair range is a rough one, from the ad's title and summary. Paste the link on "
                         "Bikecheck for the full check: {link}", link=f"{site}/check"))
    lines.append("")
    lines.append(gettext("Stop this alert: {link}", link=f"{site}/alerts/{alert['token']}/stop"))
    return subject, "\n".join(lines)


def run(conn, search=daily_checks.search, send=mail.send, pause=daily_checks.PAUSE, today=None):
    """One pass over the confirmed alerts. Returns how many mails it sent."""
    forget_unconfirmed(conn)
    alerts = conn.execute("SELECT * FROM alerts WHERE confirmed_at IS NOT NULL ORDER BY id").fetchall()
    if not alerts:
        return 0
    models = db.all_models(conn)
    by_id = {m["id"]: m for m in models}
    families = {}
    for alert in alerts:
        model = by_id.get(alert["model_id"])
        if model is not None:
            # one search per line, however the catalogue spells it ("CruX", "Crux")
            line = (model["brand"].lower(), checks.line_key(checks.model_line(model["name"])))
            families.setdefault(line, (search_query(model), []))[1].append((alert, model))
    sent = 0
    first = True
    for family, watching in families.values():
        ads = []
        for site in SITES:
            if not first and pause:
                time.sleep(pause)
            first = False
            try:
                ads += search(family, site)
            except Exception as e:  # one search failing doesn't stop the others
                print(f"alert search for {family} on {site} failed: {e}", file=sys.stderr, flush=True)
        judged = {}
        hits = {alert["id"]: [] for alert, _ in watching}
        for ad in ads:
            if not daily_checks.is_bike(ad["url"]) or not ad["price"] or ad["price"] < MIN_PRICE:
                continue
            key = daily_checks.key(ad["url"])
            for alert, model in watching:
                if conn.execute("SELECT 1 FROM alert_ads WHERE alert_id = ? AND ad_key = ?",
                                (alert["id"], key)).fetchone():
                    continue
                conn.execute("INSERT INTO alert_ads (alert_id, ad_key) VALUES (?, ?)", (alert["id"], key))
                if key not in judged:
                    try:
                        judged[key] = judge(models, ad)
                    except Exception as e:
                        print(f"alert check of {ad['url']} failed: {e}", file=sys.stderr, flush=True)
                        judged[key] = None
                if fits(alert, model, ad, judged[key]):
                    hits[alert["id"]].append((ad, judged[key]))
        conn.commit()
        for alert, model in watching:
            found = sorted(hits[alert["id"]], key=lambda h: h[0]["price"] / ((h[1]["low"] + h[1]["high"]) / 2))
            if not found:
                continue
            language = i18n.current_language.set(alert["lang"] if alert["lang"] in i18n.LANGUAGES else "nl")
            try:
                subject, text = mail_text(alert, model, found[:MAX_ADS_PER_MAIL])
            finally:
                i18n.current_language.reset(language)
            site = (alert["site"] or "").rstrip("/")
            try:
                send(alert["email"], subject, text, count=False, headers={
                    "List-Unsubscribe": f"<{site}/alerts/{alert['token']}/stop>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
            except Exception as e:  # the ads stay seen: better one missed mail than the same ads twice
                print(f"alert mail {alert['id']} failed: {e}", file=sys.stderr, flush=True)
                continue
            conn.execute("UPDATE alerts SET last_mail_at = datetime('now') WHERE id = ?", (alert["id"],))
            conn.commit()
            sent += 1
    return sent


if __name__ == "__main__":
    if not mail.configured():
        sys.exit("SMTP_HOST isn't set, so no alert can be mailed.")
    print(f"alert mails sent: {run(db.connect(db.DB_PATH))}")
