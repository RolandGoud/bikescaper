"""Flask app for the Bike Compare prototype.

Run from the repo root:
    python -m webapp.seed
    flask --app webapp.app run --debug
"""
import json
import os
import re
import sys
from datetime import date

from flask import Flask, abort, g, redirect, render_template, request, send_from_directory, url_for

from . import checks, db, fetch_ad, prices, recheck
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language, gettext
from .reference import BRANDS, DISCIPLINES, SIZE_CHARTS, TIER_EXAMPLES, TIERS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OTHER = [("other", "Other")]  # models no discipline rule recognises yet
STATUS_LABELS = {"current": "Still sold", "discontinued": "Discontinued",
                 "unknown": "Status unknown"}


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or db.DB_PATH
    app.jinja_env.globals["_"] = gettext  # also reaches imported macros, which get no request context
    app.jinja_env.globals["tier_names"] = TIERS

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
        try:
            digits = re.sub(r"[^\d,]", "", str(value)).replace(",", ".").rstrip(".")
            return cast(float(digits)) if digits else None
        except ValueError:
            return None

    def listing_dict(row, height=None):
        listing = dict(row)
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
    def remember_language(response):
        if request.args.get("lang") in LANGUAGES:
            response.set_cookie("lang", request.args["lang"], max_age=365 * 24 * 3600, samesite="Lax")
        return response

    def lang_url(code):
        args = {k: v for k, v in request.args.items() if k != "lang"}
        if request.endpoint and request.method == "GET":
            return url_for(request.endpoint, **(request.view_args or {}), **args, lang=code)
        return url_for("home", lang=code)

    def this_page(**changes):
        """This page's address with some query arguments changed, e.g. a different period."""
        args = {**request.args.to_dict(), **changes}
        return url_for(request.endpoint, **(request.view_args or {}), **args)

    @app.context_processor
    def globals_():
        return {"brands": BRANDS, "logos": {b["name"]: b["logo"] for b in BRANDS if b.get("logo")},
                "status_labels": STATUS_LABELS, "charted": SIZE_CHARTS,
                "lang": g.get("lang", DEFAULT_LANGUAGE),
                "languages": LANGUAGES, "lang_url": lang_url, "this_page": this_page,
                "periods": prices.PERIODS,
                "covered": [b["name"] for b in BRANDS if b["scraper"]]}

    @app.template_filter("eur")
    def eur(value):
        return "€{:,.0f}".format(value).replace(",", ".") if value is not None else "–"

    @app.route("/")
    def home():
        recent = conn().execute("SELECT * FROM checks ORDER BY id DESC LIMIT 3").fetchall()
        cards = [(r, checks.run_check(models(), listing_dict(r))) for r in recent]
        return render_template("home.html", cards=cards, nav="check")

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
        return redirect(url_for("report", check_id=cur.lastrowid))

    @app.route("/check/<int:check_id>")
    def report(check_id):
        row = conn().execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
        if row is None:
            abort(404)
        height = request.args.get("height", type=int)
        result = checks.run_check(models(), listing_dict(row, height))
        listing = dict(row)
        listing["photos"] = json.loads(listing["photos"]) if listing.get("photos") else []
        asking = None
        if result["model"]:
            asking = prices.asking_price(prices.known_ads(conn(), models()), result["model"]["id"],
                                         prices.period_of(request.args.get("period", type=int)), leave_out=check_id)
        return render_template("report.html", listing=listing, r=result, height=height or row["rider_height"],
                               all_models=models(), asking=asking, nav="check")

    @app.route("/check/<int:check_id>/match", methods=["POST"])
    def change_match(check_id):
        model_id = request.form.get("model_id", type=int)
        conn().execute("UPDATE checks SET model_id = ? WHERE id = ?", (model_id, check_id))
        conn().commit()
        return redirect(url_for("report", check_id=check_id))

    @app.route("/listings")
    def listings():
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        cards = [(r, checks.run_check(models(), listing_dict(r))) for r in rows]
        status = request.args.get("result")
        if status:
            cards = [c for c in cards if c[1].get("model") and status in
                     {c[1]["age"]["status"], c[1]["specs"]["status"], c[1]["value"]["status"]}]
        return render_template("listings.html", cards=cards, status=status, nav="listings")

    @app.route("/models")
    def catalog():
        brand = request.args.get("brand")
        q = (request.args.get("q") or "").strip().lower()
        kind = request.args.get("type")
        current = request.args.get("current")
        tier = request.args.get("tier", type=int)
        items = [dict(m, discipline=checks.discipline_of(m), status=checks.catalogue_status(m)[0],
                      tier=checks.model_tier(m))
                 for m in models() if (not brand or m["brand"] == brand) and (not q or q in m["name"].lower())]
        items = [m for m in items if not current or m["status"] == "current"]
        tier_counts = {t: sum(1 for m in items if m["tier"] == t and (not kind or m["discipline"] == kind))
                       for t in TIERS}
        items = [m for m in items if not tier or m["tier"] == tier]
        counts = {key: sum(1 for m in items if m["discipline"] == key) for key, _label in DISCIPLINES + OTHER}
        items = [m for m in items if not kind or m["discipline"] == kind]
        groups = [(key, label, sorted((m for m in items if m["discipline"] == key),
                                      key=lambda m: (m["price_eur"] or 0, m["brand"], m["name"])))
                  for key, label in DISCIPLINES + OTHER]
        return render_template("models.html", groups=[g for g in groups if g[2]], disciplines=DISCIPLINES,
                               counts=counts, kind=kind, brand=brand, q=q, current=current, count=len(items),
                               tier=tier, tier_counts=tier_counts, nav="models")

    @app.route("/models/<slug>")
    def model_page(slug):
        model = db.get_model(conn(), slug=slug)
        if model is None:
            abort(404)
        siblings = [m for m in models() if checks.family_of(m["name"]) == checks.family_of(model["name"])
                    and m["brand"] == model["brand"] and m["id"] != model["id"]]
        return render_template("model.html", m=model, years=checks.model_years(model), siblings=siblings,
                               specs=checks.spec_groups(model), tiers=checks.spec_tiers(model),
                               status=checks.catalogue_status(model),
                               discipline=dict(DISCIPLINES + OTHER)[checks.discipline_of(model)],
                               sizes=checks.size_options(model["brand"]),
                               asking=prices.asking_price(prices.known_ads(conn(), models()), model["id"],
                                                          prices.period_of(request.args.get("period", type=int))),
                               nav="models")

    @app.route("/size")
    def size_finder():
        brand = request.args.get("brand") or "Trek"
        height = request.args.get("height", type=int) or 178
        chart = checks.size_options(brand)
        rows = [{"size": k, "low": lo, "high": hi, "fit": lo <= height <= hi,
                 "near": lo - 4 <= height <= hi + 4} for k, (lo, hi) in chart.items()]
        return render_template("size.html", brand=brand, height=height, rows=rows,
                               nav="size")

    @app.route("/value")
    def value():
        slug = request.args.get("model")
        model = db.get_model(conn(), slug=slug) if slug else None
        year = request.args.get("year", type=int)
        condition = request.args.get("condition") or None
        asking = number(request.args.get("asking"))
        result = None
        if model:
            claims = {"year": year, "condition": condition, "groupset": None}
            age = {"status": checks.OK}
            result = checks.check_value(model, claims, asking, {"rows": []}, age)
        return render_template("value.html", models=models(), model=model, year=year, condition=condition,
                               asking=asking, result=result, this_year=date.today().year, nav="value")

    @app.route("/how-it-works")
    def how():
        seen = {}
        for m in models():
            seen.setdefault(m["brand"], set()).add(m["seen_on"])
        return render_template("how.html", nav=None, count=len(models()),
                               seen={b: max(d for d in dates if d) for b, dates in seen.items() if any(dates)},
                               tier_examples=TIER_EXAMPLES)

    @app.route("/images/<path:path>")
    def images(path):
        return send_from_directory(os.path.join(ROOT, "images"), path)

    return app


app = create_app()
if "gunicorn" in os.path.basename(sys.argv[0]):
    # On the server, re-check pasted ad links in the background and mark removed ads.
    recheck.start_background(app.config["DB_PATH"])
