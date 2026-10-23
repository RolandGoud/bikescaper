from webapp import db, mail, seed
from webapp.app import create_app


def make_app(tmp_path):
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["STORE_AD_PHOTOS"] = False
    seed.load(db.connect(app.config["DB_PATH"]))
    client = app.test_client()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56 Ultegra", "asking_price": "2450",
                                "rider_height": "180"})
    return app, client


def test_pdf_download(tmp_path):
    _, client = make_app(tmp_path)
    resp = client.get("/check/1/report.pdf?height=180&lang=nl")
    assert resp.status_code == 200 and resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF") and len(resp.data) > 2000
    assert "bike-compare-1-trek-domane-sl6" in resp.headers["Content-Disposition"]
    assert client.get("/check/99/report.pdf").status_code == 404


def test_pdf_and_mail_offered_only_with_a_height(tmp_path, monkeypatch):
    _, client = make_app(tmp_path)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    page = client.get("/check/1?lang=en").data.decode()
    assert "Download as PDF" in page and "Mail me this report" not in page  # no mail settings
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    assert "Mail me this report" in client.get("/check/1?lang=en").data.decode()
    client.post("/check", data={"title": "Trek Domane SL6 2022 maat 56 Ultegra"})  # no height given
    assert "Download as PDF" not in client.get("/check/2?lang=en").data.decode()


def test_email_report(tmp_path, monkeypatch):
    _, client = make_app(tmp_path)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    mail._sent.clear()
    sent = []
    monkeypatch.setattr(mail, "send", lambda to, subject, text, pdf, name, ip=None:
                        (sent.append((to, subject, text, pdf[:4], name)), mail._sent.append((0 or __import__("time").time(), ip))))

    resp = client.post("/check/1/email?lang=nl", data={"email": "jan@example.nl", "height": "180"})
    assert resp.status_code == 302 and "mailed=sent" in resp.headers["Location"]
    to, subject, text, head, name = sent[0]
    assert to == "jan@example.nl" and subject.startswith("Je Bike Compare-check") and head == b"%PDF"
    assert "gecheckt op" in text and "/check/1?height=180" in text
    assert "Verstuurd" in client.get(resp.headers["Location"]).data.decode()

    assert "mailed=invalid" in client.post("/check/1/email", data={"email": "nope", "height": "180"}).headers["Location"]
    for _ in range(2):
        client.post("/check/1/email", data={"email": "jan@example.nl", "height": "180"})
    assert "mailed=limit" in client.post("/check/1/email", data={"email": "jan@example.nl", "height": "180"}).headers["Location"]
    # a made-up forwarding header doesn't get around the limit
    spoofed = client.post("/check/1/email", data={"email": "jan@example.nl", "height": "180"},
                          headers={"X-Forwarded-For": "203.0.113.9"})
    assert "mailed=limit" in spoofed.headers["Location"]
    assert len(sent) == 3


def test_email_needs_mail_settings(tmp_path, monkeypatch):
    _, client = make_app(tmp_path)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert client.post("/check/1/email", data={"email": "jan@example.nl"}).status_code == 404
