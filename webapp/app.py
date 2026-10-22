"""Flask app for the Bike Compare prototype.

Run from the repo root:
    python -m webapp.seed
    flask --app webapp.app run --debug
"""
import os
import re
from datetime import date

from flask import Flask, abort, g, redirect, render_template, request, send_from_directory, url_for

from . import checks, db
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language, gettext
from .reference import BRANDS, DISCIPLINES, SIZE_CHARTS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OTHER = [("other", "Other")]  # models no discipline rule recognises yet


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or db.DB_PATH
    app.jinja_env.globals["_"] = gettext  # also reaches imported macros, which get no request context

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

    @app.context_processor
    def globals_():
        return {"brands": BRANDS, "charted": SIZE_CHARTS, "lang": g.get("lang", DEFAULT_LANGUAGE),
                "languages": LANGUAGES, "lang_url": lang_url,
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
        form = request.form
        title = (form.get("title") or "").strip()
        if not title:
            return render_template("check_form.html", nav="check", form=form,
                                   error=gettext("Paste at least the ad's title.")), 400
        cur = conn().execute(
            "INSERT INTO checks (listing_url, title, description, asking_price, location, rider_height)"
            " VALUES (?,?,?,?,?,?)",
            (form.get("listing_url") or None, title, form.get("description") or "",
             number(form.get("asking_price")), form.get("location") or None,
             number(form.get("rider_height"), int)),
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
        return render_template("report.html", listing=dict(row), r=result, height=height or row["rider_height"],
                               all_models=models(), nav="check")

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
        items = [dict(m, discipline=checks.discipline_of(m)) for m in models()
                 if (not brand or m["brand"] == brand) and (not q or q in m["name"].lower())]
        counts = {key: sum(1 for m in items if m["discipline"] == key) for key, _label in DISCIPLINES + OTHER}
        items = [m for m in items if not kind or m["discipline"] == kind]
        groups = [(key, label, sorted((m for m in items if m["discipline"] == key),
                                      key=lambda m: (m["price_eur"] or 0, m["brand"], m["name"])))
                  for key, label in DISCIPLINES + OTHER]
        return render_template("models.html", groups=[g for g in groups if g[2]], disciplines=DISCIPLINES,
                               counts=counts, kind=kind, brand=brand, q=q, count=len(items), nav="models")

    @app.route("/models/<slug>")
    def model_page(slug):
        model = db.get_model(conn(), slug=slug)
        if model is None:
            abort(404)
        gen = checks.generation_of(model["name"])
        years = checks.GENERATIONS.get((model["brand"], checks.family_of(model["name"]), gen))
        siblings = [m for m in models() if checks.family_of(m["name"]) == checks.family_of(model["name"])
                    and m["brand"] == model["brand"] and m["id"] != model["id"]]
        return render_template("model.html", m=model, years=years, siblings=siblings,
                               sizes=checks.size_options(model["brand"]), nav="models")

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
        return render_template("how.html", nav=None, count=len(models()))

    @app.route("/images/<path:path>")
    def images(path):
        return send_from_directory(os.path.join(ROOT, "images"), path)

    return app


app = create_app()
