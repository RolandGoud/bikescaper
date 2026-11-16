"""Privacy statement, contact page and affiliate disclosure (templates/legal/), in both languages."""
import pytest

from webapp.app import create_app


@pytest.fixture
def client(tmp_path):
    return create_app(str(tmp_path / "app.sqlite3")).test_client()


@pytest.mark.parametrize("path,nl,en", [
    ("/privacy", "Privacyverklaring", "Privacy statement"),
    ("/contact", "Waarover je ons kunt mailen", "What you can email us about"),
    ("/affiliate", "Hoe we geld verdienen", "How we make money"),
])
def test_pages_in_both_languages(client, path, nl, en):
    assert nl in client.get(path + "?lang=nl").get_data(as_text=True)
    assert en in client.get(path + "?lang=en").get_data(as_text=True)


def test_footer_links_every_page(client):
    page = client.get("/how-it-works?lang=nl").get_data(as_text=True)
    for href in ('href="/privacy"', 'href="/contact"', 'href="/affiliate"'):
        assert href in page
    assert "Affiliatelinks" in page


def test_contact_address_from_the_environment(client, monkeypatch):
    for k in ("CONTACT_EMAIL", "NOTIFY_EMAIL", "MAIL_FROM", "SMTP_USER"):
        monkeypatch.delenv(k, raising=False)
    assert "nog niet ingesteld" in client.get("/contact?lang=nl").get_data(as_text=True)
    monkeypatch.setenv("NOTIFY_EMAIL", "notify@example.nl")
    monkeypatch.setenv("CONTACT_EMAIL", "info@example.nl")
    page = client.get("/contact?lang=en").get_data(as_text=True)
    assert 'mailto:info@example.nl' in page and "notify@" not in page
    assert 'mailto:info@example.nl' in client.get("/privacy?lang=en").get_data(as_text=True)


def test_site_owner_named_in_privacy_statement(client, monkeypatch):
    monkeypatch.setenv("SITE_OWNER", "Voorbeeld BV")
    assert "Bikecheck (Voorbeeld BV)" in client.get("/privacy?lang=nl").get_data(as_text=True)


def test_how_it_works_has_no_prototype_limits(client):
    page = client.get("/how-it-works?lang=en").get_data(as_text=True)
    assert "Limits of this prototype" not in page
