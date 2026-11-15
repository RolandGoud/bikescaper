import re

from webapp.app import create_app
from webapp.articles import ARTICLES
from webapp.i18n import NL


def test_every_article_line_has_a_dutch_translation():
    for a in ARTICLES:
        assert a["url"].startswith("https://")
        assert a["country"] in ("NL", "BE")
        for key in ("tag", "title", "text"):
            assert a[key] in NL, a[key]


def test_home_shows_the_articles_in_both_languages_opening_in_a_new_tab(tmp_path):
    client = create_app(str(tmp_path / "app.sqlite3")).test_client()
    for lang, heading, button in (("nl", "Gestolen fiets? Check voor je koopt", "Lees op rdw.nl"),
                                  ("en", "Don&#39;t buy a stolen bike", "Read on rdw.nl")):
        page = client.get(f"/?lang={lang}").get_data(as_text=True)
        assert heading in page and button in page
        links = re.findall(r'<a class="as-go" href="([^"]+)" target="_blank" rel="noopener">', page)
        assert links == [a["url"] for a in ARTICLES]
