"""Flask app for the Bike Compare prototype.

Run from the repo root:
    python -m webapp.seed
    flask --app webapp.app run --debug
"""
import json
import os
import re
import sys
import threading
from datetime import date

from flask import Flask, Response, abort, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from . import ad_photos, checks, daily_checks, db, fetch_ad, mail, prices, recheck, report_pdf
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language, gettext
from .reference import BRANDS, DISCIPLINES, SIZE_CHARTS, TIER_EXAMPLES, TIERS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OTHER = [("other", "Other")]  # models no discipline rule recognises yet
STATUS_LABELS = {"current": "Still sold", "discontinued": "Discontinued",
                 "unknown": "Status unknown"}
# Our own links are relative (url_for), so any link to http(s):// leaves the site.
EXTERNAL_LINK = re.compile(r'<a\s[^>]*href="https?://[^>]*>')


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
    app.jinja_env.globals["_"] = gettext  # also reaches imported macros, which get no request context
    app.jinja_env.globals["tier_names"] = TIERS
    app.jinja_env.globals["size_systems"] = checks.size_systems
    app.jinja_env.globals["split_title"] = checks.split_title

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

    def listing_dict(row, height=None, count=1):
        listing = dict(row)
        listing["times_checked"] = count
        photos = json.loads(listing["photos"]) if listing.get("photos") else []
        if any(not ad_photos.is_stored(p) for p in photos) and app.config.get("STORE_AD_PHOTOS", True):
            store_photos_later(listing["id"])  # also picks up checks made before photos were stored
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
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        ads = group_checks(rows)
        cards = [(listing_dict(r, count=n), checks.run_check(models(), listing_dict(r))) for r, n in ads[:12]]
        return render_template("home.html", cards=cards, total=len(ads), nav="check")

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
        result = checks.run_check(models(), listing_dict(row, height))
        asking = None
        if result["model"]:
            asking = prices.asking_price(prices.known_ads(conn(), models()), result["model"]["id"],
                                         prices.period_of(request.args.get("period", type=int)), leave_out=check_id)
        key = fetch_ad.ad_key(row)
        times = sum(fetch_ad.ad_key(r) == key for r in conn().execute(
            "SELECT listing_url, title, asking_price FROM checks").fetchall())
        return render_template("report.html", listing=listing_dict(row, count=times), r=result, height=height or row["rider_height"],
                               all_models=models(), asking=asking, nav="check",
                               can_mail=mail.configured(), mailed=request.args.get("mailed"))

    def pdf_of(check_id, height):
        row = conn().execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
        if row is None:
            abort(404)
        listing = listing_dict(row, height)
        result = checks.run_check(models(), listing)
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

    @app.route("/listings")
    def listings():
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        cards = [(listing_dict(r, count=n), checks.run_check(models(), listing_dict(r)))
                 for r, n in group_checks(rows)]
        status = request.args.get("result")
        if status:
            cards = [c for c in cards if c[1].get("model") and status in
                     {c[1]["age"]["status"], c[1]["specs"]["status"], c[1]["value"]["status"]}]
        return render_template("listings.html", cards=cards, status=status, nav="listings")

    @app.route("/checks")
    def all_checks():
        """Every check one by one, newest first: what was put in and what came out."""
        rows = conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
        source = request.args.get("source")
        counts = {"visitors": sum(1 for r in rows if not r["source"]),
                  "daily": sum(1 for r in rows if r["source"] == daily_checks.SOURCE)}
        times = {}
        for r in rows:
            times[fetch_ad.ad_key(r)] = times.get(fetch_ad.ad_key(r), 0) + 1
        if source == "visitors":
            rows = [r for r in rows if not r["source"]]
        elif source == "daily":
            rows = [r for r in rows if r["source"] == daily_checks.SOURCE]
        known = prices.known_ads(conn(), models())
        items = []
        for r in rows:
            listing = listing_dict(r, count=times[fetch_ad.ad_key(r)])
            result = checks.run_check(models(), listing)
            asking = (prices.asking_price(known, result["model"]["id"], prices.DEFAULT_PERIOD, leave_out=r["id"])
                      if result["model"] else None)
            items.append((listing, result, asking))
        return render_template("checks.html", items=items, source=source, counts=counts, total=sum(counts.values()),
                               nav="listings")

    @app.route("/models")
    def catalog():
        picked = [b for b in request.args.getlist("brand") if b]  # several brands can be on at once
        q = (request.args.get("q") or "").strip().lower()
        kind = request.args.get("type")
        current = request.args.get("current")
        tier = request.args.get("tier", type=int)
        items = [dict(m, discipline=checks.discipline_of(m), status=checks.catalogue_status(m)[0],
                      tier=checks.model_tier(m))
                 for m in models() if (not picked or m["brand"] in picked) and (not q or q in m["name"].lower())]
        items = [m for m in items if not current or m["status"] == "current"]
        tier_counts = {t: sum(1 for m in items if m["tier"] == t and (not kind or m["discipline"] == kind))
                       for t in TIERS}
        items = [m for m in items if not tier or m["tier"] == tier]
        counts = {key: sum(1 for m in items if m["discipline"] == key) for key, _label in DISCIPLINES + OTHER}
        items = [m for m in items if not kind or m["discipline"] == kind]
        matched = matched_ads(conn().execute("SELECT * FROM checks ORDER BY id DESC").fetchall(), models())
        for m in items:
            m["matched"] = len(matched.get(m["id"], []))
        groups = [(key, label, sorted((m for m in items if m["discipline"] == key),
                                      key=lambda m: (m["price_eur"] or 0, m["brand"], m["name"])))
                  for key, label in DISCIPLINES + OTHER]
        return render_template("models.html", groups=[g for g in groups if g[2]], disciplines=DISCIPLINES,
                               counts=counts, kind=kind, picked=picked, q=q, current=current, count=len(items),
                               tier=tier, tier_counts=tier_counts, nav="models")

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
        ads = [(dict(listing_dict(r, count=n), in_price=r["id"] in priced), checks.run_check(models(), listing_dict(r)))
               for r, n in sorted(matched_ads(rows, models()).get(model["id"], []), key=lambda a: a[0]["created_at"],
                                  reverse=True)]
        return render_template("model.html", ads=ads, m=model, years=checks.model_years(model), siblings=siblings,
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
        brand = request.args.get("brand") or (picked and picked["brand"]) or "Trek"
        height = request.args.get("height", type=int) or 178
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
            history.append({"row": r, "model": m, "result": estimate(m, r["year"], r["condition"], r["asking_price"], made),
                            "asking": prices.asking_price(known, m["id"], prices.DEFAULT_PERIOD)})
        return render_template("value.html", models=models(), model=model, brand=brand, year=year, condition=condition,
                               asking=asking, result=result, shown=shown, history=history,
                               this_year=date.today().year, nav="value")

    @app.route("/how-it-works")
    def how():
        seen = {}
        for m in models():
            seen.setdefault(m["brand"], set()).add(m["seen_on"])
        return render_template("how.html", nav=None, count=len(models()),
                               seen={b: max(d for d in dates if d) for b, dates in seen.items() if any(dates)},
                               tier_examples=TIER_EXAMPLES)

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
