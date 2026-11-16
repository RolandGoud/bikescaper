import re
from datetime import date

import pytest

from webapp import blog, db, seed
from webapp.app import create_app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(str(tmp_path_factory.mktemp("blog") / "app.sqlite3"))
    seed.load(db.connect(app.config["DB_PATH"]))  # the model pages the articles link to
    return app.test_client()


def test_every_article_is_in_both_languages_with_a_known_category():
    posts = blog.load()
    assert len(posts) >= 12
    for slug, versions in posts.items():
        assert set(versions) == {"nl", "en"}, slug
        nl, en = versions["nl"], versions["en"]
        assert nl["date"] == en["date"] and nl["category"] == en["category"], slug
        assert nl["category"] in blog.CATEGORIES, slug
        for v in (nl, en):
            assert v["title"] and v["summary"] and len(v["body"].split()) > 250, (slug, v["lang"])
    # the launch: three per category
    by_cat = {}
    for versions in posts.values():
        by_cat.setdefault(versions["nl"]["category"], []).append(versions["nl"]["date"])
    assert {c: len(d) for c, d in by_cat.items()} == {c: 3 for c in blog.CATEGORIES}


def test_future_articles_stay_hidden():
    posts = {"a": {"nl": {"slug": "a", "date": date(2026, 1, 2), "category": "market"}},
             "b": {"nl": {"slug": "b", "date": date(2026, 1, 9), "category": "market"}}}
    assert [p["slug"] for p in blog.published(posts, "en", today=date(2026, 1, 5))] == ["a"]


def test_render_handles_tables_lists_callouts_and_links():
    html = blog.render("## Kop\n\nTekst met **vet** en [link](/value) en [extern](https://rdw.nl).\n\n"
                       "- een\n- twee\n\n| A | Prijs |\n|---|---|\n| x | €1.000 |\n\n> Let op <script>")
    assert '<td>x</td>' in html  # text stays left-aligned, numbers go right
    assert "<h2>Kop</h2>" in html and "<strong>vet</strong>" in html
    assert '<a href="/value">link</a>' in html and 'href="https://rdw.nl" target="_blank" rel="noopener"' in html
    assert "<ul><li>een</li><li>twee</li></ul>" in html
    assert '<td class="num">€1.000</td>' in html and "<th>A</th>" in html
    assert "blog-callout" in html and "&lt;script&gt;" in html


def test_list_and_article_pages_in_both_languages(client):
    for lang, heading, read in (("nl", "Blog", "In cijfers"), ("en", "Blog", "In numbers")):
        page = client.get(f"/blog?lang={lang}").get_data(as_text=True)
        assert heading in page and read in page
        assert page.count('<article class="brick') == len(blog.published(blog.load(), lang))
    page = client.get("/blog?category=models&lang=en").get_data(as_text=True)
    assert page.count('<article class="brick') == 3 and "Trek Domane" in page
    assert page.count('class="brick big') == 1 and page.count('class="brick wide') == 2  # closes the grid
    nl = client.get("/blog/trek-domane?lang=nl").get_data(as_text=True)
    en = client.get("/blog/trek-domane?lang=en").get_data(as_text=True)
    assert "tweedehands" in nl and "second-hand" in en
    assert client.get("/blog/no-such-article").status_code == 404


def test_the_menu_links_the_blog(client):
    page = client.get("/?lang=nl").get_data(as_text=True)
    assert 'href="/blog"' in page


def test_every_link_in_an_article_works(client):
    for slug, versions in blog.load().items():
        for v in versions.values():
            for url in re.findall(r"\]\((/[^)\s]*)\)", v["body"]):
                path = url.split("#")[0]
                assert client.get(path).status_code == 200, (slug, v["lang"], url)


def test_every_article_has_a_hero_a_number_and_its_charts(client):
    for slug, versions in blog.load().items():
        for v in versions.values():
            assert v["hero"] and v.get("stat") and v.get("stat_label"), (slug, v["lang"])
            for chart in re.findall(r"\(chart:([a-z0-9-]+)\)", v["body"]):
                html = blog.render(f"![x](chart:{chart})", v["lang"])
                assert "<svg" in html, (slug, chart)
        page = client.get(f"/blog/{slug}?lang=nl").get_data(as_text=True)
        assert f"blog/heroes/{slug}.jpg" in page
        assert client.get(f"/static/blog/heroes/{slug}.jpg").status_code == 200


def test_charts_come_in_the_article_language():
    nl = blog.render("![](chart:value-curve)", "nl")
    en = blog.render("![](chart:value-curve)", "en")
    assert "jaar oud" in nl and "years old" in en


def test_tables_use_the_site_tier_badges_and_logos():
    html = blog.render("| Niveau | Shimano | SRAM |\n|---|---|---|\n| {tier:3} | 105 Di2 | Rival |\n| {tier:5} | GRX 825 | x |", "nl")
    assert '<span class="tier t3 small">Midden</span>' in html and '<span class="tier t5 small">Top</span>' in html
    assert "logos/groupsets/105.svg" in html and "logos/groupsets/rival.svg" in html
    assert "logos/groupsets/grx-800.svg" in html and '<span class="blog-logo-rest">Di2</span>' in html
    assert blog.with_logos("microSHIFT Sword") is None and "logos/sram.svg" in blog.with_logos("SRAM Red")
    assert "Basic" in blog.render("{tier:1}", "en")


def test_a_table_and_its_chart_share_a_toggle_with_the_chart_first():
    for slug in blog.load():
        for v in blog.load()[slug].values():
            html = blog.render(v["body"], v["lang"])
            for block in html.split('<div class="blog-switch">')[1:]:
                chart_at, table_at = block.index("blog-switch-chart"), block.index("blog-switch-table")
                assert chart_at < table_at and re.search(r'value="chart" checked', block), slug
    html = blog.render(blog.load()["how-fast-bikes-lose-value"]["nl"]["body"], "nl")
    assert html.count('<div class="blog-switch">') == 2
    assert 'data-live="value-curve"' in html and 'name="age"' in html and 'data-live="price-rises"' in html
    assert "data-series=" in html  # the price lines' data, for static/blog.js


def test_hero_credits_and_focus(client):
    page = client.get("/blog/spotting-a-stolen-bike?lang=en").get_data(as_text=True)
    # Unsplash's attribution: the photographer and Unsplash, both linked with the referral parameters
    assert "Abdulrahman Alhaidari</a> on <a href=\"https://unsplash.com/?utm_source=bikecheck&amp;utm_medium=referral\"" in page
    assert "utm_source=bikecheck" in page.split("Abdulrahman Alhaidari")[0].rsplit("<a ", 1)[1]
    page = client.get("/blog/trek-domane?lang=nl").get_data(as_text=True)
    # a model article: the brand's own photo, staged in front of the article's Unsplash scene; both credited
    assert "productfoto van Trek" in page and "Achtergrond: <a" in page and "Ben Guernsey</a> op <a" in page
    assert "object-position" in client.get("/blog?lang=nl").get_data(as_text=True)
    assert client.get("/static/blog.js").status_code == 200

def test_home_shows_the_newest_posts_instead_of_outside_articles(client):
    for lang, heading in (("nl", "Uit het blog"), ("en", "From the blog")):
        page = client.get(f"/?lang={lang}").get_data(as_text=True)
        assert heading in page and "article-slides" not in page
        newest = blog.published(blog.load(), lang)[:3]
        for p in newest:
            assert f'href="/blog/{p["slug"]}"' in page
        assert page.count('<article class="brick') == 3 and "blog/heroes/" in page


def test_a_report_links_the_article_on_its_model_first():
    posts = blog.load()
    domane = {"brand": "Trek", "name": "Domane SL 6 Gen 4"}
    assert [p["slug"] for p in blog.for_report(posts, "en", domane)] == \
        ["trek-domane", "spotting-a-stolen-bike", "reading-a-bike-ad"]
    tcr = {"brand": "Giant", "name": "TCR Advanced Pro 1"}
    assert blog.for_report(posts, "nl", tcr)[0]["slug"] == "giant-tcr-advanced"
    other = {"brand": "Trek", "name": "Madone SL 6"}
    assert [p["slug"] for p in blog.for_report(posts, "en", other)] == blog.REPORT_READS
    assert [p["slug"] for p in blog.for_report(posts, "en", None)] == blog.REPORT_READS


def test_a_report_page_shows_the_reads(client):
    app = client.application
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO checks (title, asking_price) VALUES (?, ?)", ("Trek Domane AL 4 Gen 4 2024", 1050))
    conn.commit()
    check_id = conn.execute("SELECT max(id) FROM checks").fetchone()[0]
    page = client.get(f"/check/{check_id}?lang=en").get_data(as_text=True)
    assert "Read before you buy" in page
    assert 'href="/blog/spotting-a-stolen-bike"' in page and 'href="/blog/trek-domane"' in page


def test_charts_show_logos_and_the_live_ones_have_their_inputs():
    html = blog.render("![](chart:brand-prices)", "nl")
    assert "foreignObject" in html and "logos/trek.svg" in html
    assert "logos/groupsets/ultegra.svg" in blog.render("![](chart:groupset-prices)", "en")
    zones = blog.render("![](chart:price-zones)", "nl")
    assert 'data-live="price-zones"' in zones and 'name="asking"' in zones
    winter = blog.render("![](chart:winter-values)", "en")
    assert 'data-live="winter-values"' in winter and 'name="age"' in winter and "data-tpl=" in winter
    assert "logos/canyon.svg" in blog.render("![](chart:price-rises)", "en")  # the bike picks


def test_the_value_curve_goes_back_no_further_than_the_catalogue():
    from webapp.reference import FIRST_YEAR
    html = blog.render("![](chart:value-curve)", "nl")
    assert f'name="age" value="4" min="0" max="{date.today().year - FIRST_YEAR}"' in html


def test_the_wall_filters_in_place_with_its_transition(client):
    page = client.get("/blog?lang=nl").get_data(as_text=True)
    assert "blog-wall.js" in page and client.get("/static/blog-wall.js").status_code == 200
    assert 'href="/blog?category=models"' in page  # the pills stay real links without JavaScript
