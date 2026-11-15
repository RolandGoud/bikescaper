# Before Bikecheck runs anywhere but the NAS

The NAS is a test setup. Before the site is hosted publicly (own domain, other server or cloud host),
go through this list. The privacy statement (/privacy), contact page (/contact) and affiliate
disclosure (/affiliate) are **incomplete until the first two are set**.

## Required settings

- [ ] `CONTACT_EMAIL`: the address shown on /contact and /privacy, for questions and AVG requests
      (inzage, correctie, verwijdering). Without it the pages fall back to NOTIFY_EMAIL, MAIL_FROM or
      SMTP_USER, and with none of those /contact says no address is set up yet.
- [ ] `SITE_OWNER`: your name or company (and KvK number if there is one). The AVG requires the
      privacy statement to name who is responsible for the data; without it the page only says "Bikecheck".
- [ ] `SECRET_KEY`: a long random value, so the session cookie isn't signed with a key derived from the
      admin password.

## Privacy gaps to close

- [ ] Host the Google Fonts on the site itself (webapp/templates/base.html), so visitors' IP addresses
      don't go to Google. Then drop the Google Fonts line from the privacy statement.
- [ ] Set a retention period for the web server's access log (gunicorn `--access-logfile`, the host's
      or proxy's logs), and state it under "Server log" in templates/legal/privacy.*.html.
- [ ] Re-read templates/legal/privacy.nl.html and .en.html against what the site stores by then, and
      update LEGAL_UPDATED in webapp/app.py when the text changes.
