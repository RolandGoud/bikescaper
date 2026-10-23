"""Send a check report by email.

Set these on the server (in the NAS compose file, under environment):
    SMTP_HOST      e.g. smtp.gmail.com
    SMTP_PORT      587 (STARTTLS, the default) or 465 (SSL)
    SMTP_USER      the account's login
    SMTP_PASSWORD  its password (for Gmail: an app password)
    MAIL_FROM      the sender address, defaults to SMTP_USER
    NOTIFY_EMAIL   where to send a note when someone confirms their address for the photo review
Without SMTP_HOST the site doesn't offer email at all.
"""
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PER_ADDRESS_PER_HOUR = 3   # one visitor can't flood an inbox
PER_DAY = 50               # nor the whole site use the account to spam
_sent = []                 # (time, sender ip) of recent mails, in this process


def configured():
    return bool(os.environ.get("SMTP_HOST"))


def valid(address):
    return bool(address) and len(address) <= 254 and bool(EMAIL.match(address))


def allowed(ip, now=None):
    now = now or time.time()
    _sent[:] = [(t, a) for t, a in _sent if now - t < 24 * 3600]
    recent = sum(1 for t, a in _sent if a == ip and now - t < 3600)
    return recent < PER_ADDRESS_PER_HOUR and len(_sent) < PER_DAY


def send(to, subject, text, pdf=None, filename=None, ip=None):
    message = EmailMessage()
    message["From"] = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if pdf:
        message.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)

    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
    user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        server.starttls(context=ssl.create_default_context())
    with server:
        if user:
            server.login(user, password or "")
        server.send_message(message)
    _sent.append((time.time(), ip))
