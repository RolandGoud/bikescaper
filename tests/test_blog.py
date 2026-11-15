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
    assert "<h2>Kop</h2>" in html and "<strong>vet</strong>" in html
    assert '<a href="/value">link</a>' in html and 'href="https://rdw.nl" target="_blank" rel="noopener"' in html
    assert "<ul><li>een</li><li>twee</li></ul>" in html
    assert '<td class="num">€1.000</td>' in html and "<th>A</th>" in html
    assert "blog-callout" in html and "&lt;script&gt;" in html


def test_list_and_article_pages_in_both_languages(client):
    for lang, heading, read in (("nl", "Blog", "min lezen"), ("en", "Blog", "min read")):
        page = client.get(f"/blog?lang={lang}").get_data(as_text=True)
        assert heading in page and read in page
        assert page.count('class="blog-card') == len(blog.published(blog.load(), lang))
    page = client.get("/blog?category=models&lang=en").get_data(as_text=True)
    assert page.count('class="blog-card') == 3 and "Trek Domane" in page
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
