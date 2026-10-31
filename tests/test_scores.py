from PIL import Image

from webapp import checks, db, scores, seed
from webapp.app import create_app


def test_a_complete_ad_that_adds_up_scores_full_marks_and_a_bare_one_loses_a_point_per_gap(tmp_path):
    conn = db.connect(str(tmp_path / "s.sqlite3"))
    seed.load(conn)
    models = db.all_models(conn)
    full = {"title": "Trek Domane SL 6 Gen 4 2023 maat 56 zwart", "asking_price": 2900,
            "description": "Shimano 105 Di2, in nette staat, aankoopbewijs aanwezig"}
    bare = {"title": "Trek Domane SL 6 Gen 4", "asking_price": 2900, "description": ""}
    score, lost = scores.ad_score(full, checks.run_check(models, full))
    assert score >= 9, lost
    score_bare, lost_bare = scores.ad_score(bare, checks.run_check(models, bare))
    assert {k for _p, k, _d in lost_bare} >= {"no_year", "no_size", "no_condition"}
    assert score_bare <= score - 3


def test_an_ad_without_a_model_scores_at_most_4():
    report = {"claims": {"year": 2022, "size": "56", "groupset": {"key": "105"}, "condition": "good", "brand": None},
              "model": None}
    score, _lost = scores.ad_score({"title": "racefiets carbon 105"}, report)
    assert score <= 4
    assert scores.match_problems(report) == ["brand"]


def test_one_dark_photo_scores_low(tmp_path):
    path = tmp_path / "1.jpg"
    Image.new("RGB", (500, 300), (10, 10, 10)).save(path)
    score, lost = scores.photo_score(1, [str(path)])
    keys = {k for _p, k, _d in lost}
    assert score <= 3 and {"few_photos", "dark", "small"} <= keys
    assert scores.photo_score(0, []) == (None, [])


def test_admin_page_shows_the_stats_and_the_period_charts(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    conn = db.connect(app.config["DB_PATH"])
    seed.load(conn)
    conn.execute("INSERT INTO checks (title, asking_price, created_at) VALUES (?, ?, ?)",
                 ("Trek Domane SL 6 Gen 4 2023 maat 56", 2900, "2026-09-01 10:00:00"))
    conn.execute("INSERT INTO checks (title, asking_price, created_at) VALUES (?, ?, ?)",
                 ("racefiets carbon zgan", 900, "2026-10-20 10:00:00"))
    conn.commit()
    page = app.test_client().get("/admin?lang=en").get_data(as_text=True)
    assert "What ads leave out" in page and "Where matching goes wrong" in page
    assert 'data-view="week"' in page and 'data-view="month"' in page and 'id="admin-data"' in page
    assert "racefiets carbon zgan" in page  # among the lowest scores
    stats = page[page.index('id="admin-data">'):]
    assert "2026-09" in stats and "2026-10" in stats
    assert "Bikes matched to a model" in page and 'data-chart="matched"' in page and '"unmatched"' in stats


def test_carbon_is_no_proof_of_purchase_and_a_year_photo_without_colour_is_no_colour():
    report = {"claims": {"year": 2022, "size": "56", "groupset": None, "condition": None},
              "photo_year": {"year": 2022, "colour": None}, "colourway": None}
    gaps = scores.missing(report, {"title": "Trek Domane carbon 2022 maat 56", "description": "carbon frame"})
    assert "proof" in gaps and "colour" in gaps
    assert "proof" not in scores.missing(report, {"title": "Trek Domane", "description": "bon aanwezig"})
