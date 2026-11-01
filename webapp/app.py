"""Flask app for the Bike Compare prototype.

Run from the repo root:
    python -m webapp.seed
    flask --app webapp.app run --debug
"""
import json
from collections import Counter
import os
import random
import re
import secrets
import sys
import threading
from datetime import date

from flask import Flask, Response, abort, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from . import ad_photos, ad_title, bike_fit, checks, colour_match, daily_checks, db, fetch_ad, groupset_shops, groupsets, mail, photo_counts, photo_groupset, places, prices, recheck, report_pdf, scores, seed, seller, sponsored, stored_checks
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language, gettext
from .reference import (BRANDS, DISCIPLINES, GROUPSET_AGE_MAX_DROP, GROUPSET_AGE_STEP, GROUPSETS, SIZE_CHARTS, TIER_EXAMPLES,
                        TIERS)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OTHER = [("other", "Other")]  # models no discipline rule recognises yet
STATUS_LABELS = {"current": "Still sold", "discontinued": "Discontinued",
                 "unknown": "Status unknown"}
# Our own links are relative (url_for), so any link to http(s):// leaves the site.
TOWNS_PER_PAGE = 12  # towns per page of the list beside the listings map
EXTERNAL_LINK = re.compile(r'<a\s[^>]*href="https?://[^>]*>')
# Home hero backgrounds: openly licensed photos from Wikimedia Commons, one picked at random per visit.
# credits.json holds each photo's author, licence and source, shown as a credit line in the hero.
HERO_DIR = os.path.join(os.path.dirname(__file__), "static", "hero")
HERO_BACKGROUNDS = sorted(f for f in os.listdir(HERO_DIR) if f.endswith(".jpg"))


def load_galleries():
    """{model page URL: {colour or "": [photo]}}: the other angles of each current model, from
    data/galleries/<Brand>.json (brand_scrapers/galleries.py)."""
    found, folder = {}, os.path.join(ROOT, "data", "galleries")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                found.update({url: g for url, g in json.load(fh).items() if g})
    return found


GALLERIES = load_galleries()
with open(os.path.join(HERO_DIR, "credits.json"), encoding="utf-8") as f:
    HERO_CREDITS = json.load(f)
# Photo tips on the Selling page: (icon paths for a 40x40 SVG, heading, text).
PHOTO_TIPS = [
    ('<circle cx="10" cy="26" r="7"/><circle cx="30" cy="26" r="7"/><path d="M10 26l6-11h8l6 11M16 15l5 11"/>',
     "Whole bike, drive side", "Chainring towards the camera, bike facing right, like the catalogue photo."),
    ('<rect x="5" y="9" width="30" height="22" rx="3"/><path d="M5 25l9-8 7 6 5-4 9 7"/>',
     "Plain background, daylight", "An empty wall or outside in the shade. No flash."),
    ('<circle cx="20" cy="20" r="7"/><circle cx="20" cy="20" r="2"/><path d="M20 6v4M20 30v4M6 20h4M30 20h4"/>',
     "Groupset and wheels up close", "Shifters, derailleur and cassette, so buyers can see the parts."),
    ('<rect x="6" y="14" width="28" height="12" rx="2"/><path d="M11 20h2M16 20h2M21 20h2M26 20h3"/>',
     "Serial number", "Under the bottom bracket. Buyers ask for it, and it builds trust."),
    ('<path d="M8 30l9-9 5 5 10-12"/><path d="M27 14h5v5"/>',
     "Scratches, honestly", "Better now than at the viewing. Don't edit them out."),
    ('<rect x="10" y="6" width="20" height="28" rx="2"/><path d="M14 12h12M14 17h12M14 22h6"/><path d="M14 28h12" stroke-width="4"/>',
     "Invoice", "With your name and address covered."),
]


def parse_number(value):
    """A number as people type it in the Netherlands: "1.049,-", "€ 344,00", "2450". The comma is the
    decimal mark and a dot groups thousands, but a dot with one or two digits after it is a decimal
    point too ("344.0" from a form we filled in ourselves), and so is the last mark when both appear."""
    text = re.sub(r"[,.]-+$", "", re.sub(r"[^\d,.-]", "", str(value if value is not None else "")).strip("-"))
    if not re.search(r"\d", text):
        return None
    marks = [c for c in text if c in ",."]
    if "," in marks and "." in marks:
        decimal = marks[-1]
    elif "," in marks:
        decimal = ","
    elif "." in marks:
        decimal = "." if len(marks) == 1 and not re.search(r"\.\d{3}$", text) else None
    else:
        decimal = None
    if decimal:
        whole, _, frac = text.rpartition(decimal)
        text = re.sub(r"\D", "", whole) + "." + re.sub(r"\D", "", frac)
    else:
        text = re.sub(r"\D", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def open_in_new_tab(tag):
    """Give an external <a> tag target="_blank" and a rel with noopener, keeping what it already has."""
    if " target=" not in tag:
        tag = tag[:-1] + ' target="_blank">'
    rel = re.search(r' rel="([^"]*)"', tag)
    if not rel:
        tag = tag[:-1] + ' rel="noopener">'
    elif "noopener" not in rel.group(1).split():
        tag = tag.replace(rel.group(0), f' rel="noopener {rel.group(1)}"')
    return tag


def group_checks(rows):
    """One entry per ad, newest check first: (newest row as a dict, times checked).
    The ad counts as removed once any of its checks found it gone."""
    groups = {}
    for row in rows:  # newest first
        key = fetch_ad.ad_key(row)
        if key not in groups:
            groups[key] = [dict(row), 0]
        newest, _ = groups[key]
        groups[key][1] += 1
        newest["removed_at"] = newest.get("removed_at") or row["removed_at"]
    return [(newest, count) for newest, count in groups.values()]


def matched_ads(rows, models):
    """Every ad the site knows, per catalogue model it's matched to: {model_id: [(newest row, times checked)]}.
    The match is the one the ad's report shows: the visitor's pick, otherwise our best guess. Daily checks
    count too (they are real ads), and an ad checked again counts once."""
    by_id = {m["id"]: m for m in models}
    ads = {}
    for newest, count in group_checks(rows):
        model = by_id.get(newest["model_id"])
        if model is None:
            ranked = checks.match_models(models, newest["title"], newest["description"] or "")
            model = ranked[0][1] if ranked else None
        if model:
            ads.setdefault(model["id"], []).append((newest, count))
    return ads


def create_app(db_path=None):
    app = Flask(__name__)
    if os.environ.get("BEHIND_PROXY"):  # only then is X-Forwarded-For set by us, not by the visitor
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["DB_PATH"] = db_path or db.DB_PATH
    app.config["SPONSORED_PATH"] = sponsored.PATH
    app.config["GROUPSET_SHOPS_PATH"] = groupset_shops.PATH
    # The groupsets page is hidden for now: off the menu and a 404, unless SHOW_GROUPSETS is set.
    app.config["SHOW_GROUPSETS"] = bool(os.environ.get("SHOW_GROUPSETS"))

    @app.url_defaults
    def static_version(endpoint, values):
        """Stylesheet and script URLs carry the file's modification time (?v=...), so a browser
        fetches the new one after an update instead of using its cached copy."""
        if endpoint == "static" and values.get("filename", "").endswith((".css", ".js")) and "v" not in values:
            try:
                values["v"] = int(os.stat(os.path.join(app.static_folder, values["filename"])).st_mtime)
            except OSError:
                pass
    app.jinja_env.globals["_"] = gettext  # also reaches imported macros, which get no request context
    app.jinja_env.globals["tier_names"] = TIERS
    app.jinja_env.globals["age_step"] = GROUPSET_AGE_STEP
    app.jinja_env.globals["age_max_drop"] = GROUPSET_AGE_MAX_DROP
    app.jinja_env.globals["size_systems"] = checks.size_systems
    app.jinja_env.globals["split_title"] = checks.split_title
    app.jinja_env.globals["key_parts"] = checks.key_parts
    app.jinja_env.globals["ringed_years"] = checks.ringed_years

    def ad_photo_fit(ad_photo, model):
        """Where to draw a stored ad photo so its bike sits on the catalogue bike (bike_fit), or None."""
        prefix = url_for("ad_photo", name="")
        if not (model and model.get("image") and ad_photo.startswith(prefix)):
            return None
        stored = os.path.join(ad_photos.folder(app.config["DB_PATH"]), ad_photo[len(prefix):])
        # .photo img.trek in style.css: Trek's own product shots (…-Primary_01.jpg) come with a wide white margin
        zoom = (1.12, 0.03) if model.get("brand") == "Trek" and not model.get("year_photo") and "Primary" in model["image"] else None
        return bike_fit.style(stored, os.path.join(ROOT, "images", model["image"]), zoom)

    app.jinja_env.globals["ad_photo_fit"] = ad_photo_fit

    def duo_pick(photos, model=None, look=6):
        """The ad photo for the merged slider: the first one, unless its bike faces left and a later one
        (of the first few) shows the whole bike facing right like the catalogue bike, so it needn't be
        mirrored. A close-up facing right (a derailleur, a rim) doesn't count: then the first is mirrored."""
        prefix = url_for("ad_photo", name="")
        folder = ad_photos.folder(app.config["DB_PATH"])
        def path(p):
            found = os.path.join(folder, p[len(prefix):])
            return found if p.startswith(prefix) and os.path.exists(found) else None
        def left(p):
            return bike_fit.faces_left(path(p)) if path(p) else None
        if not photos or not left(photos[0]):
            return photos[0] if photos else None
        catalogue = os.path.join(ROOT, "images", model["image"]) if model and model.get("image") else None
        if not catalogue or not os.path.exists(catalogue):
            return photos[0]
        return next((p for p in photos[1:look] if left(p) is False and bike_fit.whole_bike(path(p), catalogue)),
                    photos[0])

    app.jinja_env.globals["duo_pick"] = duo_pick
    app.jinja_env.filters["swatch"] = colour_match.swatch
    app.jinja_env.filters["swatch_css"] = colour_match.swatch_css
    app.jinja_env.filters["photo_colour"] = seed.photo_colour  # the frame's colour in a photo, for a name we can't read
    app.jinja_env.filters["years_list"] = checks._years_list
    app.jinja_env.filters["without_generation"] = checks.without_generation
    app.jinja_env.filters["model_title"] = checks.model_title  # the model's name as shown: without "Shimano"
    app.jinja_env.globals["ad_title"] = ad_title.parts
    app.jinja_env.filters["no_brand"] = ad_title.without_brand

    def conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DB_PATH"])
        return g.conn

    @app.teardown_appcontext
    def close(_exc):
        c = g.pop("conn", None)
        if c is not None:
            c.close()

    def models():
        if "models" not in g:
            g.models = db.all_models(conn())
        return g.models

    def number(value, cast=float):
        value = parse_number(value)
        return cast(value) if value is not None else None

    storing = set()  # checks whose photos are being downloaded in this process

    def store_photos_later(check_id):
        """Copy the ad's photos to our own disk in the background; the page shows the links meanwhile."""
        if check_id in storing:
            return
        storing.add(check_id)
        path = app.config["DB_PATH"]

        def work():
            c = db.connect(path)
            try:
                ad_photos.store(c, path, check_id)
            except Exception as e:  # the next page view tries again
                print(f"storing photos of check {check_id} failed: {e}", file=sys.stderr, flush=True)
            finally:
                c.close()
                storing.discard(check_id)

        threading.Thread(target=work, name=f"photos-{check_id}", daemon=True).start()

    def stored_check(listing, store=True):
        """The listing's check report, worked out once and kept (webapp/stored_checks.py)."""
        return stored_checks.report(conn(), models(), listing, store=store)

    def listing_dict(row, height=None, count=1):
        listing = dict(row)
        listing["times_checked"] = count
        photos = json.loads(listing["photos"]) if listing.get("photos") else []
        if any(not ad_photos.is_stored(p) for p in photos) and app.config.get("STORE_AD_PHOTOS", True):
            store_photos_later(listing["id"])  # also picks up checks made before photos were stored
        # The stored photos on disk, for reading the bike's colour from them.
        listing["photo_paths"] = [os.path.join(ad_photos.folder(app.config["DB_PATH"]), p)
                                  for p in photos if ad_photos.is_stored(p)][:3]
        # The groupset, crankset and any purchase receipt read from the photos (webapp/photo_groupset.py):
        # once the photos it reads are all on our disk. Every ad is read, since any can show a receipt.
        # While photos are still being copied it waits for them; once copying is done, a photo that failed (it
        # stays a link) doesn't hold up the read of the others.
        first = photos[:photo_groupset.MAX_PHOTOS]
        names = [p for p in first if ad_photos.is_stored(p)]
        if len(names) < len(first) and listing.get("id") in storing:
            names = []
        photo_folder = ad_photos.folder(app.config["DB_PATH"])
        # The last read, also of other photos than now (more were copied since): the next read replaces it.
        listing["photo_groupset"] = photo_groupset.stored(photo_folder, listing, names)
        by_eye = (listing["photo_groupset"] or {}).get("source") == "eye"
        if names and listing.get("id") is not None and not (by_eye and not photo_groupset.outdated(listing["photo_groupset"])):
            photo_groupset.read_later(photo_folder, listing["id"], names)  # only when these photos weren't read yet
        listing["photos"] = [p if not ad_photos.is_stored(p) else url_for("ad_photo", name=p) for p in photos]
        if height:
            listing["rider_height"] = height
        return listing

    @app.before_request
    def pick_language():
        # ?lang= switches and is remembered in a cookie; otherwise follow the browser, defaulting to Dutch.
        lang = request.args.get("lang")
        if lang not in LANGUAGES:
            lang = request.cookies.get("lang")
        if lang not in LANGUAGES:
            lang = request.accept_languages.best_match(list(LANGUAGES)) or DEFAULT_LANGUAGE
        g.lang = lang
        current_language.set(lang)

    @app.after_request
    def external_links_in_new_tab(response):
        """Every link off the site opens in a new tab, whichever template or feature made it."""
        if response.mimetype == "text/html" and not response.direct_passthrough:
            html = response.get_data(as_text=True)
            response.set_data(EXTERNAL_LINK.sub(lambda m: open_in_new_tab(m.group(0)), html))
        return response

    @app.after_request
    def remember_language(response):
        if request.args.get("lang") in LANGUAGES:
            response.set_cookie("lang", request.args["lang"], max_age=365 * 24 * 3600, samesite="Lax")
        return response

    def lang_url(code):
        args = {k: v for k, v in request.args.lists() if k != "lang"}  # lists keep every picked brand
        if request.endpoint and request.method == "GET":
            return url_for(request.endpoint, **(request.view_args or {}), **args, lang=code)
        return url_for("home", lang=code)

    def this_page(**changes):
        """This page's address with some query arguments changed, e.g. a different period."""
        args = {**request.args.to_dict(), **changes}
        return url_for(request.endpoint, **(request.view_args or {}), **args)

    def on_map(place, listing_url=None):
        """The listings map opened at this ad's town, or None when the map doesn't know the place."""
        spot = places.locate(place, listing_url)
        return url_for("listings_map", place=place, cc=spot[2]) if spot else None

    @app.context_processor
    def globals_():
        return {"brands": BRANDS, "logos": {b["name"]: b["logo"] for b in BRANDS if b.get("logo")},
                "status_labels": STATUS_LABELS, "charted": SIZE_CHARTS,
                "lang": g.get("lang", DEFAULT_LANGUAGE),
                "languages": LANGUAGES, "lang_url": lang_url, "this_page": this_page, "on_map": on_map,
                "periods": prices.PERIODS,
                "covered": [b["name"] for b in BRANDS if b["scraper"]]}

    def offers(slots=sponsored.SLOTS, tiles=False):
        """The sponsored offers for this page's slots (webapp/sponsored.py); with tiles, also the
        offers the grid's every-5th ad tiles cycle through, under "tiles"."""
        lang, every = g.get("lang", DEFAULT_LANGUAGE), sponsored.load(app.config["SPONSORED_PATH"])
        picked = sponsored.pick(every, lang, slots=slots)
        if tiles:
            picked["tiles"] = sponsored.rotation(every, lang)
        return picked

    @app.template_filter("eur")
    def eur(value):
        return "€{:,.0f}".format(value).replace(",", ".") if value is not None else "–"

    @app.route("/")
    def home():
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        ads = group_checks(rows)
        cards = [(listing_dict(r, count=n), stored_check(listing_dict(r))) for r, n in ads[:12]]
        hero_bg = random.choice(HERO_BACKGROUNDS) if HERO_BACKGROUNDS else None
        return render_template("home.html", cards=cards, total=len(ads), nav="check", hero_bg=hero_bg,
                               hero_credit=HERO_CREDITS.get(hero_bg), sponsored=offers())

    @app.route("/check", methods=["GET", "POST"])
    def new_check():
        if request.method == "GET":
            return render_template("check_form.html", nav="check", form={}, error=None)
        form = request.form.to_dict()
        height = number(form.get("rider_height"), int)

        def again(error):
            return render_template("check_form.html", nav="check", form=form, error=error), 400

        if form.get("mode") == "link":
            url = (form.get("ad_link") or "").strip()
            if not url:
                return again(gettext("Paste the link to the ad."))
            try:
                ad = fetch_ad.fetch_listing(url)
            except fetch_ad.FetchError as e:
                # Fall back to typing it in, with the link kept so it's saved with the check.
                form.update(mode="manual", listing_url=fetch_ad.with_scheme(url))
                return again(gettext("{reason} Fill in the details yourself instead.", reason=gettext(str(e))))
            return save_check(ad["listing_url"], ad["title"], ad["description"], ad["asking_price"],
                              ad["location"], height, ad["photos"])
        title = (form.get("title") or "").strip()
        if not title:
            return again(gettext("Paste at least the ad's title."))
        return save_check(form.get("listing_url") or None, title, form.get("description") or "",
                          number(form.get("asking_price")), form.get("location") or None, height)

    def save_check(url, title, description, price, location, height, photos=None):
        cur = conn().execute(
            "INSERT INTO checks (listing_url, title, description, asking_price, location, rider_height, photos)"
            " VALUES (?,?,?,?,?,?,?)",
            (url, title, description, price, location, height, json.dumps(photos) if photos else None),
        )
        conn().commit()
        if photos and app.config.get("STORE_AD_PHOTOS", True):
            store_photos_later(cur.lastrowid)
        return redirect(url_for("report", check_id=cur.lastrowid))

    @app.route("/check/<int:check_id>")
    def report(check_id):
        row = conn().execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
        if row is None:
            abort(404)
        height = request.args.get("height", type=int)
        # Another rider height than the check's own changes the size check: shown, but not kept.
        result = stored_check(listing_dict(row, height), store=height in (None, row["rider_height"]))
        value = result.get("value") or {}
        if value.get("low") and value.get("original"):  # also for reports stored with an older slider
            value["slider"] = checks.price_slider(value["low"], value["high"], value["original"], value.get("asking"))
        asking = None
        if result["model"]:
            asking = prices.asking_price(prices.known_ads(conn(), models()), result["model"]["id"],
                                         prices.period_of(request.args.get("period", type=int)), leave_out=check_id)
        key = fetch_ad.ad_key(row)
        times = sum(fetch_ad.ad_key(r) == key for r in conn().execute(
            "SELECT listing_url, title, asking_price FROM checks").fetchall())
        other_ads = []
        if result["model"]:  # the other ads matched to the same model, as on its model page
            known = prices.known_ads(conn(), models())
            priced = {i for a in known if a["model_id"] == result["model"]["id"] for i in a["check_ids"]}
            rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
            other_ads = [(dict(listing_dict(r, count=n), in_price=r["id"] in priced), {"model": result["model"]})
                         for r, n in sorted(matched_ads(rows, models()).get(result["model"]["id"], []),
                                            key=lambda a: a[0]["created_at"], reverse=True)
                         if fetch_ad.ad_key(r) != key]
        return render_template("report.html", listing=listing_dict(row, count=times), r=result, height=height or row["rider_height"],
                               checked_at=stored_checks.computed_at(conn(), check_id),
                               all_models=models(), asking=asking, nav="check", other_ads=other_ads,
                               can_mail=mail.configured(), mailed=request.args.get("mailed"))

    def pdf_of(check_id, height):
        row = conn().execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
        if row is None:
            abort(404)
        listing = listing_dict(row, height)
        result = stored_check(listing, store=height in (None, row["rider_height"]))
        url = url_for("report", check_id=check_id, height=height, _external=True)
        return listing, report_pdf.build(listing, result, height or row["rider_height"], url)

    def pdf_name(listing):
        slug = re.sub(r"[^a-z0-9]+", "-", listing["title"].lower()).strip("-")[:50] or "check"
        return f"bike-compare-{listing['id']}-{slug}.pdf"

    @app.route("/check/<int:check_id>/report.pdf")
    def report_pdf_download(check_id):
        listing, pdf = pdf_of(check_id, request.args.get("height", type=int))
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{pdf_name(listing)}"'})

    @app.route("/check/<int:check_id>/email", methods=["POST"])
    def email_report(check_id):
        height = request.form.get("height", type=int)
        to = (request.form.get("email") or "").strip()
        back = lambda status: redirect(url_for("report", check_id=check_id, height=height, mailed=status) + "#size")
        if not mail.configured():
            abort(404)
        if not mail.valid(to):
            return back("invalid")
        ip = request.remote_addr or ""
        if not mail.allowed(ip):
            return back("limit")
        listing, pdf = pdf_of(check_id, height)
        try:
            mail.send(to, gettext("Your Bike Compare check: {title}", title=listing["title"]),
                      gettext("Here is your check report for “{title}”, checked on {date}. The PDF is attached; "
                              "the report online: {url}", title=listing["title"], date=listing["created_at"][:10],
                              url=url_for("report", check_id=check_id, height=height, _external=True)),
                      pdf, pdf_name(listing), ip=ip)
        except Exception as e:  # SMTP down or wrong settings: say so, don't crash the page
            print(f"emailing check {check_id} failed: {e}", file=sys.stderr, flush=True)
            return back("failed")
        return back("sent")

    @app.route("/check/<int:check_id>/match", methods=["POST"])
    def change_match(check_id):
        model_id = request.form.get("model_id", type=int)
        conn().execute("UPDATE checks SET model_id = ? WHERE id = ?", (model_id, check_id))
        conn().commit()
        return redirect(url_for("report", check_id=check_id))

    @app.route("/check/<int:check_id>/recheck", methods=["POST"])
    def recheck_report(check_id):
        """Run this check again with today's matching and catalogue, e.g. after the matching changed."""
        stored_checks.forget(conn(), check_id)
        return redirect(url_for("report", check_id=check_id))

    @app.route("/admin/recheck", methods=["POST"])
    def recheck_all():
        """Forget every stored report: each check runs again, once, the next time it's shown."""
        stored_checks.forget(conn())
        return redirect(url_for("admin", rechecked=1))

    @app.route("/listings")
    def listings():
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        cards = [(listing_dict(r, count=n), stored_check(listing_dict(r)))
                 for r, n in group_checks(rows)]
        return render_template("listings.html", cards=cards, nav="listings", sponsored=offers(("side",), tiles=True))

    @app.route("/checks")
    def all_checks():
        """Every check one by one, newest first: what was put in and what came out."""
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        times = {}
        for r in rows:
            times[fetch_ad.ad_key(r)] = times.get(fetch_ad.ad_key(r), 0) + 1
        known = prices.known_ads(conn(), models())
        items = []
        for r in rows:
            listing = listing_dict(r, count=times[fetch_ad.ad_key(r)])
            result = stored_check(listing)
            asking = (prices.asking_price(known, result["model"]["id"], prices.DEFAULT_PERIOD, leave_out=r["id"])
                      if result["model"] else None)
            items.append((listing, result, asking))
        return render_template("checks.html", items=items, nav="listings")

    @app.route("/listings/map")
    def listings_map():
        """Every ad on a map of the Netherlands and Belgium, one pin per place; a pin opens its ads' reports.
        ?place= (a town's name, as the cards and reports link it) opens the map at that town's pin."""
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        pins = {}
        for row, count in group_checks(rows):
            spot = places.locate(row["location"], row["listing_url"])
            if not spot:  # a place we can't find stays off the map
                continue
            listing = listing_dict(row, count=count)
            result = stored_check(listing)
            model = result["model"]
            pin = pins.setdefault(spot[:2], {"lat": spot[0], "lng": spot[1], "country": spot[2],
                                             "place": row["location"], "ads": []})
            pin["ads"].append({
                "url": url_for("report", check_id=row["id"]),
                "name": f"{model['brand']} {checks.model_title(model['name'])}" if model else row["title"],
                "title": ad_title.without_brand(row["title"], model["brand"]) if model else None,
                "price": eur(row["asking_price"]) if row["asking_price"] else None,
                "status": result["value"]["status"] if model else "unknown",
                "verdict": str(result["value"]["headline"]) if model else gettext("No matching model yet"),
                # The seller's first photo, else the catalogue photo of the matched model.
                "photo": listing["photos"][0] if listing["photos"] else
                         url_for("images", path=model["image"]) if model and model["image"] else None,
                "catalogue": not listing["photos"],
                "removed": bool(row["removed_at"]),
            })
        focus = places.locate(request.args.get("place"), in_country=request.args.get("cc"))
        pins = sorted(pins.values(), key=lambda p: (-len(p["ads"]), p["place"]))  # busiest towns first in the list
        for pin in pins:  # each town's own address: the page with that town selected
            pin["link"] = url_for("listings_map", place=pin["place"], cc=pin["country"])
        selected = next((i for i, p in enumerate(pins) if focus and [p["lat"], p["lng"]] == list(focus[:2])), None)
        # The town list comes in pages (?page=, busiest towns on page 1); a picked town opens on its own page,
        # so "All places" goes back to where it is in the list.
        pages = max(1, -(-len(pins) // TOWNS_PER_PAGE))
        page = selected // TOWNS_PER_PAGE + 1 if selected is not None else min(max(number(request.args.get("page"), int) or 1, 1), pages)
        page_urls = [url_for("listings_map", **({"page": n} if n > 1 else {})) for n in range(1, pages + 1)]
        return render_template("listings_map.html", pins=pins, nav="map", selected=selected,
                               page=page, page_urls=page_urls, per_page=TOWNS_PER_PAGE)

    @app.route("/models")
    def catalog():
        picked = [b for b in request.args.getlist("brand") if b]  # several brands can be on at once
        q = (request.args.get("q") or "").strip().lower()
        kind = request.args.get("type")
        # "Only bikes still sold" is on unless the address says current=0; the form's hidden 0 after the checkbox sends that.
        current = request.args.get("current") != "0"
        tier = request.args.get("tier", type=int)
        groupset = request.args.get("groupset") or None  # from a series on the groupsets page
        groupset_name = next((name for key, name, _p, _t in GROUPSETS if key == groupset), None)
        items = [dict(m, discipline=checks.discipline_of(m), status=checks.catalogue_status(m)[0],
                      tier=checks.model_tier(m))
                 for m in models() if (not q or q in m["name"].lower())
                 and (not groupset or groupset_key(m) == groupset)]
        items = [m for m in items if not current or m["status"] == "current"]
        # each brand's count in the brand menu: what picking it would show with the other filters kept
        brand_counts = Counter(m["brand"] for m in items
                               if (not tier or m["tier"] == tier) and (not kind or m["discipline"] == kind))
        items = [m for m in items if not picked or m["brand"] in picked]
        tier_counts = {t: sum(1 for m in items if m["tier"] == t and (not kind or m["discipline"] == kind))
                       for t in TIERS}
        items = [m for m in items if not tier or m["tier"] == tier]
        counts = {key: sum(1 for m in items if m["discipline"] == key) for key, _label in DISCIPLINES + OTHER}
        items = [m for m in items if not kind or m["discipline"] == kind]
        matched = matched_ads(conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall(), models())
        for m in items:
            m["matched"] = len(matched.get(m["id"], []))
        groups = [(key, label, sorted((m for m in items if m["discipline"] == key),
                                      key=lambda m: (not m["price_eur"], m["price_eur"] or 0, m["brand"], m["name"])))
                  for key, label in DISCIPLINES + OTHER]
        return render_template("models.html", groups=[g for g in groups if g[2]], disciplines=DISCIPLINES,
                               counts=counts, brand_counts=brand_counts, kind=kind, picked=picked, q=q, current=current, count=len(items),
                               tier=tier, tier_counts=tier_counts, groupset=groupset, groupset_name=groupset_name,
                               nav="models", sponsored=offers(("side",), tiles=True))

    def groupset_key(model):
        found = checks.detect_groupset(checks.groupset_text(model))
        return found and found["key"]

    def logo_if_there(path):
        return path if path and os.path.exists(os.path.join(app.static_folder, path)) else None

    @app.route("/groupsets")
    def groupset_paths():
        """Each brand's groupsets from basic to top, and what it takes to upgrade from the one you have."""
        app.config["SHOW_GROUPSETS"] or abort(404)
        current = groupsets.GENERATIONS.get(request.args.get("have"))
        # One brand at a time, Shimano first; the groupset you pick sets the brand and type.
        brand = current["brand"] if current else request.args.get("brand")
        brand = brand if brand in groupsets.LADDERS else next(iter(groupsets.LADDERS))
        kinds = [(key, label) for key, label in groupsets.DISCIPLINES if key in groupsets.LADDERS[brand]]
        kind = current["kind"] if current else request.args.get("type")
        kind = kind if kind in dict(kinds) else kinds[0][0]
        paths = groupsets.upgrades(current["key"]) if current else []
        down = groupsets.downgrades(current["key"]) if current else []
        return render_template("groupsets.html", kind=kind, current=current, paths=paths,
                               down=down, by_key={g["key"]: p for g, p in paths + down}, ladders=groupsets.ladders(kind, brand),
                               brand=brand, brands=[{"name": b, "logo": logo_if_there(groupsets.BRAND_LOGOS.get(b))}
                                                     for b in groupsets.LADDERS], disciplines=kinds,
                               effort=groupsets.EFFORT, cost=groupsets.COST, not_worth_it=groupsets.NOT_WORTH_IT, advise_against=groupsets.ADVISE_AGAINST, fit=groupsets.FIT, shift_labels=groupsets.SHIFT_LABELS,
                               freehubs=groupsets.FREEHUBS, other_brands=groupsets.OTHER_BRANDS,
                               columns=groupsets.columns,
                               series_logo=lambda s: logo_if_there(groupsets.logo_path(s)),
                               cross_upgrades=groupsets.cross_upgrades, split_wireless=groupsets.split_wireless,
                               wireless=groupsets.WIRELESS, nav="groupsets")

    @app.route("/groupsets/<key>/shop")
    def groupset_shop(key):
        """Where to buy one groupset: affiliate links to web shops (webapp/groupset_shops.py)."""
        app.config["SHOW_GROUPSETS"] or abort(404)
        gen = groupsets.GENERATIONS.get(key) or abort(404)
        return render_template("groupset_shop.html", g=gen, shift_label=groupsets.SHIFT_LABELS[gen["shift"]],
                               shops=groupset_shops.links(groupset_shops.load(app.config["GROUPSET_SHOPS_PATH"]), gen),
                               nav="groupsets")

    @app.route("/models/<slug>")
    def model_page(slug):
        model = db.get_model(conn(), slug=slug)
        if model is None:
            abort(404)
        siblings = sorted((dict(m, status=checks.catalogue_status(m)[0], tier=checks.model_tier(m)) for m in models()
                           if checks.family_of(m["name"]) == checks.family_of(model["name"])
                           and m["brand"] == model["brand"] and m["id"] != model["id"]),
                          key=lambda m: (m["price_eur"] or 0, m["name"]))  # shown as tiles, cheapest first
        size_chart = checks.model_size_chart(model)
        known = prices.known_ads(conn(), models())
        priced = {i for a in known if a["model_id"] == model["id"] for i in a["check_ids"]}
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        ads = [(dict(listing_dict(r, count=n), in_price=r["id"] in priced), stored_check(listing_dict(r)))
               for r, n in sorted(matched_ads(rows, models()).get(model["id"], []), key=lambda a: a[0]["created_at"],
                                  reverse=True)]
        year_tabs = checks.year_tabs(model)
        # A discontinued line's own photo and colours are of all its years at once: it opens on its newest year instead.
        if "/archived/" in (model.get("source_file") or "") and any(t.get("image") for t in year_tabs):
            model = dict(model, image=None, colorways=None)
        return render_template("model.html", ads=ads, m=model, years=checks.sold_years(model), siblings=siblings,
                               year_tabs=year_tabs, angles_now=GALLERIES.get(model.get("url")) or {},
                               specs=checks.spec_groups(model), tiers=checks.spec_tiers(model),
                               status=checks.catalogue_status(model),
                               discipline=dict(DISCIPLINES + OTHER)[checks.discipline_of(model)],
                               size_chart=size_chart, size_note=checks.size_note(size_chart, model["brand"]),
                               asking=prices.asking_price(known, model["id"],
                                                          prices.period_of(request.args.get("period", type=int))),
                               nav="models")

    @app.route("/size")
    def size_finder():
        slug = request.args.get("model")
        picked = db.get_model(conn(), slug=slug) if slug else None
        brand = request.args.get("brand") or (picked and picked["brand"]) or None
        height = request.args.get("height", type=int) or 178
        if brand is None:  # nothing to show until a brand is picked; the Model list stays greyed out
            return render_template("size.html", brand=None, height=height, picker=[], line=None, nav="size")
        lines = checks.size_lines(models(), brand)
        line = next((l for l in lines if picked and any(m["slug"] == slug for m in l["models"])), None)
        chart = line["chart"] if line else {"sizes": checks.size_options(brand), "geometry": {}, "source": "generic"}
        rows = [{"size": k, "low": lo, "high": hi, "fit": lo <= height <= hi, "near": lo - 4 <= height <= hi + 4,
                 "geometry": chart["geometry"].get(k)} for k, (lo, hi) in chart["sizes"].items()]
        by_size = {r["size"]: r for r in rows}
        rows = [(heading, [by_size[k] for k in keys]) for heading, keys in checks.size_systems(by_size)]
        own = {source: sum(len(l["models"]) for l in lines if l["chart"]["source"] == source)
               for source in ("brand", "geometry")}
        return render_template("size.html", brand=brand, height=height, rows=rows, lines=lines, line=line,
                               picker=checks.size_picker(lines), kinds=dict(DISCIPLINES + OTHER),
                               chart=chart, note=checks.size_note(chart, brand), own=own,
                               total=sum(len(l["models"]) for l in lines), nav="size")

    def estimate(model, year, condition, asking, today=None):
        claims = {"year": year, "condition": condition, "groupset": None}
        return checks.check_value(model, claims, asking, {"rows": []}, {"status": checks.OK}, today=today)

    @app.route("/value", methods=["GET", "POST"])
    def value():
        if request.method == "POST":
            # Every estimate is saved, so the page can list them below the form; the redirect keeps a
            # reload from saving it twice.
            model = db.get_model(conn(), slug=request.form.get("model"))
            if model is None:
                return redirect(url_for("value", brand=request.form.get("brand")))
            condition = request.form.get("condition") or None
            cur = conn().execute("INSERT INTO estimates (model_id, year, condition, asking_price) VALUES (?,?,?,?)",
                                 (model["id"], number(request.form.get("year"), int),
                                  condition if condition in checks.CONDITION_LABEL else None,
                                  number(request.form.get("asking"))))
            conn().commit()
            return redirect(url_for("value", estimate=cur.lastrowid))
        by_id = {m["id"]: m for m in models()}
        rows = conn().execute("SELECT * FROM estimates ORDER BY id DESC").fetchall()
        shown = next((r for r in rows if r["id"] == request.args.get("estimate", type=int)), None)
        if shown:
            model, year, condition, asking = by_id.get(shown["model_id"]), shown["year"], shown["condition"], shown["asking_price"]
        else:
            slug = request.args.get("model")
            model = db.get_model(conn(), slug=slug) if slug else None
            year = request.args.get("year", type=int)
            condition = request.args.get("condition") or None
            asking = number(request.args.get("asking"))
        result = estimate(model, year, condition, asking) if model else None
        brand = model["brand"] if model else request.args.get("brand")
        known = prices.known_ads(conn(), models())
        history = []
        for r in rows:
            m = by_id.get(r["model_id"])
            if m is None:  # its model left the catalogue
                continue
            made = date.fromisoformat(r["created_at"][:10])
            past = estimate(m, r["year"], r["condition"], r["asking_price"], made)
            if past.get("low") and not past.get("bar"):  # no asking price: the bar shows just the fair range
                past["bar"] = checks.value_bar(past["low"], past["high"], past["original"])
            history.append({"row": r, "model": m, "result": past,
                            "asking": prices.asking_price(known, m["id"], prices.DEFAULT_PERIOD)})
        return render_template("value.html", models=models(), model=model, brand=brand, year=year, condition=condition,
                               asking=asking, result=result, shown=shown, history=history,
                               this_year=date.today().year, nav="value")

    def improved_examples(limit=5):
        """Recently checked ads next to the ad we would write for them, for the Selling page. Only ads
        read from a public link: drafts typed on the Selling page are never saved."""
        rows = conn().execute("SELECT * FROM checks WHERE listing_url IS NOT NULL AND removed_at IS NULL "
                              "ORDER BY id DESC LIMIT 60").fetchall()
        found, ads = [], None
        for row, _n in group_checks(rows):
            listing = listing_dict(row)
            ads = ads if ads is not None else prices.known_ads(conn(), models())
            r = seller.improve(models(), {"title": listing["title"], "description": listing["description"] or "",
                                          "asking_price": listing["asking_price"], "model_id": listing["model_id"]}, ads=ads)
            if not r.get("model") or str(r["title"]) == listing["title"]:
                continue
            found.append({"listing": listing, "r": r, "photo": duo_pick(listing["photos"], r["model"]),
                          "added": [f["label"] for f in r["facts"] if f["source"] == "cat"],
                          "missing": [f["label"] for f in r["facts"] if f["source"] == "open"]})
            if len(found) == limit:
                break
        return found

    @app.route("/sell", methods=["GET", "POST"])
    def sell():
        """Help a seller improve a draft ad. Everything comes from the form; nothing is saved."""
        hero_bg = random.choice(HERO_BACKGROUNDS) if HERO_BACKGROUNDS else None  # the home page's photos
        hero = {"hero_bg": hero_bg, "hero_credit": HERO_CREDITS.get(hero_bg)}
        if request.method == "GET":
            return render_template("sell.html", nav="sell", form={}, r=None, error=None, examples=improved_examples(), **hero)
        form = request.form.to_dict()
        error = None
        link = (form.get("ad_link") or "").strip()
        if link and not (form.get("title") or "").strip():
            try:
                ad = fetch_ad.fetch_listing(link)
                form.update(title=ad["title"], description=ad["description"],
                            asking_price=form.get("asking_price") or (f"{ad['asking_price']:g}" if ad["asking_price"] else ""))
            except fetch_ad.FetchError as e:
                error = gettext("{reason} Paste your title and text instead.", reason=gettext(str(e)))
        if not (form.get("title") or "").strip():
            error = error or gettext("Paste at least your ad's title.")
            return render_template("sell.html", nav="sell", form=form, r=None, error=error, **hero), 400
        draft = {"title": form["title"].strip()[:200], "description": (form.get("description") or "")[:5000],
                 "asking_price": number(form.get("asking_price")), "model_id": number(form.get("model_id"), int)}
        answers = {"year": number(form.get("use_year") or form.get("year"), int), "size": form.get("size"), "condition": form.get("condition"),
                   "invoice": form.get("invoice"), "service": form.get("service"), "wheels": form.get("wheels")}
        r = seller.improve(models(), draft, answers, ads=prices.known_ads(conn(), models()))
        return render_template("sell.html", nav="sell", form=form, r=r, error=error, all_models=models(), **hero,
                               photo_tips=PHOTO_TIPS, condition_labels=checks.CONDITION_LABEL, can_mail=mail.configured())

    # The paid photo review isn't built: the offer on the Selling page counts who would want it.
    @app.route("/sell/photo-review", methods=["POST"])
    def photo_review():
        conn().execute("INSERT INTO photo_review_interest (kind, model_id, lang) VALUES ('click', ?, ?)",
                       (number(request.form.get("model_id"), int), g.lang))
        conn().commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return ("", 204)
        return render_template("sell_soon.html", nav="sell", done=False, can_mail=mail.configured())

    @app.route("/sell/photo-review/notify", methods=["POST"])
    def photo_review_notify():
        """Mail a confirmation link to the address; it only counts (and only reaches NOTIFY_EMAIL) once opened.
        Without mail set up the address is kept unconfirmed, so nothing is ever sent unasked."""
        email = (request.form.get("email") or "").strip()[:200]
        ip = request.remote_addr
        known = conn().execute("SELECT confirmed_at, created_at > datetime('now', '-1 day') AS recent "
                               "FROM photo_review_interest WHERE kind = 'email' AND lower(email) = lower(?) "
                               "ORDER BY id DESC", (email,)).fetchall()
        # Each address gets at most one link a day, and none once it's confirmed.
        if mail.valid(email) and not any(r["confirmed_at"] or r["recent"] for r in known):
            token = secrets.token_urlsafe(24)
            conn().execute("INSERT INTO photo_review_interest (kind, email, token, lang) VALUES ('email', ?, ?, ?)",
                           (email, token, g.lang))
            conn().commit()
            if mail.configured() and mail.allowed(ip):
                link = url_for("photo_review_confirm", token=token, _external=True)
                try:
                    mail.send(email, gettext("Confirm your email for Bike Compare"),
                              gettext("Someone, hopefully you, asked to hear when the Bike Compare photo review "
                                      "launches. Open this link to confirm:\n\n{link}\n\nDidn't ask for this? "
                                      "Ignore this email and you won't hear from us.", link=link), ip=ip)
                except Exception as e:  # the visitor still sees the same answer; the address stays unconfirmed
                    print(f"confirmation mail failed: {e}", file=sys.stderr, flush=True)
        if request.headers.get("X-Requested-With") == "fetch":
            return ("", 204)
        return render_template("sell_soon.html", nav="sell", done="sent")

    @app.route("/sell/photo-review/confirm/<token>")
    def photo_review_confirm(token):
        row = conn().execute("SELECT * FROM photo_review_interest WHERE kind = 'email' AND token = ?",
                             (token,)).fetchone()
        if row is None:
            return render_template("sell_soon.html", nav="sell", done="unknown"), 404
        if not row["confirmed_at"]:
            conn().execute("UPDATE photo_review_interest SET confirmed_at = datetime('now') WHERE id = ?", (row["id"],))
            conn().commit()
            notify = os.environ.get("NOTIFY_EMAIL")
            if notify and mail.configured():
                total = conn().execute("SELECT COUNT(*) FROM photo_review_interest WHERE kind = 'email' "
                                       "AND confirmed_at IS NOT NULL").fetchone()[0]
                try:
                    mail.send(notify, f"Photo review: {row['email']} confirmed",
                              f"{row['email']} confirmed they want the photo review. Confirmed addresses so far: {total}.")
                except Exception as e:
                    print(f"signup note failed: {e}", file=sys.stderr, flush=True)
        return render_template("sell_soon.html", nav="sell", done="confirmed")

    @app.route("/sell/photo-review/interest")
    def photo_review_interest():
        """How many sellers clicked the offer and left an email; counts only, never the addresses."""
        rows = conn().execute("SELECT date(created_at) AS day, SUM(kind = 'click') AS clicks, "
                              "SUM(kind = 'email' AND confirmed_at IS NOT NULL) AS emails, "
                              "SUM(kind = 'email' AND confirmed_at IS NULL) AS pending FROM photo_review_interest "
                              "GROUP BY day ORDER BY day DESC").fetchall()
        return render_template("sell_interest.html", nav="sell", rows=rows,
                               clicks=sum(r["clicks"] for r in rows), emails=sum(r["emails"] for r in rows),
                               pending=sum(r["pending"] for r in rows))

    @app.route("/how-it-works")
    def how():
        seen = {}
        for m in models():
            seen.setdefault(m["brand"], set()).add(m["seen_on"])
        return render_template("how.html", nav=None, count=len(models()),
                               seen={b: max(d for d in dates if d) for b, dates in seen.items() if any(dates)},
                               tier_examples=TIER_EXAMPLES)

    @app.route("/admin")
    def admin():
        """Statistics for us: what ads leave out, where matching goes wrong, and photo and ad scores."""
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        first = {}
        for r in rows:  # newest first, so the last one seen is the ad's first check
            first[fetch_ad.ad_key(r)] = r["created_at"][:10]
        folder = ad_photos.folder(app.config["DB_PATH"])
        items = []
        for r, n in group_checks(rows):
            photos = json.loads(r["photos"]) if r.get("photos") else []
            listing = listing_dict(r, count=n)
            report = stored_check(listing)
            ad, ad_lost = scores.ad_score(listing, report)
            photo, photo_lost = scores.photo_score(
                len(photos), [os.path.join(folder, p) for p in photos if ad_photos.is_stored(p)][:12])
            level = getattr(report.get("confidence"), "text", None)
            items.append({"day": first[fetch_ad.ad_key(r)], "listing": listing, "model": report.get("model"),
                          "brand": report["model"]["brand"] if report.get("model") else report["claims"].get("brand"),
                          "matched": bool(report.get("model")), "confidence": level,
                          "missing": scores.missing(report, listing), "problems": scores.match_problems(report),
                          "ad": ad, "ad_lost": ad_lost, "photo": photo, "photo_lost": photo_lost})
        stats = scores.summarise(items)
        worst = sorted(items, key=lambda it: (it["ad"] + (it["photo"] if it["photo"] is not None else it["ad"])))[:15]
        return render_template("admin.html", stats=stats, worst=worst, nav=None,
                               photos=photo_counts.overview(models(), GALLERIES),
                               stored=stored_checks.summary(conn()), rechecked=request.args.get("rechecked"),
                               missing_keys=scores.MISSING, problem_keys=scores.PROBLEMS)

    @app.route("/ad-photos/<path:name>")
    def ad_photo(name):
        response = send_from_directory(ad_photos.folder(app.config["DB_PATH"]), name)
        response.cache_control.max_age = 30 * 24 * 3600  # a stored photo never changes
        return response

    @app.route("/images/<path:path>")
    def images(path):
        return send_from_directory(os.path.join(ROOT, "images"), path)

    return app


app = create_app()
if "gunicorn" in os.path.basename(sys.argv[0]):
    # On the server, re-check pasted ad links in the background and mark removed ads.
    recheck.start_background(app.config["DB_PATH"])
    # And check a few current ads of popular models once a day.
    daily_checks.start_background(app.config["DB_PATH"])
