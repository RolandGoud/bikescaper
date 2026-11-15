from flask import get_template_attribute, render_template_string

from webapp.app import create_app


def render(app, source):
    with app.test_request_context("/"):
        return render_template_string(source)


def test_each_site_shows_its_light_logo_without_a_pill(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    with app.test_request_context("/"):
        mark = get_template_attribute("_macros.html", "site_mark")
        for url, logo, name in [("https://www.marktplaats.nl/v/1", "marktplaats-light.svg", "Marktplaats"),
                                ("https://www.2dehands.be/v/2", "2dehands-light.svg", "2dehands"),
                                ("https://www.2ememain.be/v/3", "2dehands-light.svg", "2ememain")]:
            html = str(mark(url))
            assert 'class="site-mark"' in html and "/static/logos/" + logo in html and name in html
        assert str(mark("https://example.com/ad")).strip() == ""
        assert str(mark(None)).strip() == ""


def test_a_site_without_a_logo_shows_its_name(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    # the same macro over a site list with one logo-less site, as a new site would be added
    source = open(app.jinja_loader.searchpath[0] + "/_macros.html").read().replace(
        "('2ememain', '2ememain', '2dehands'),", "('2ememain', '2ememain', '2dehands'),\n  ('kleinanzeigen', 'Kleinanzeigen', None),")
    html = render(app, source + "{{ site_mark('https://www.kleinanzeigen.de/s-anzeige/1') }}")
    assert '<span class="site-mark text"' in html and ">Kleinanzeigen</span>" in html
