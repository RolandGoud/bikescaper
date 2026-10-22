"""Read a second-hand ad from its link.

Marktplaats and its Belgian sites (2dehands, 2ememain) render the whole ad server-side: the
listing data sits in `window.__CONFIG__` as JSON, and the description and the "Kenmerken" list are
plain HTML. One request per link a visitor pastes, so this is a link preview, not a crawler.
Only those hosts are fetched, so a pasted link can't make the server call into the home network.
"""
import html as html_lib
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

HOSTS = ("marktplaats.nl", "2dehands.be", "2ememain.be")
USER_AGENT = "Mozilla/5.0 (compatible; BikeCompare/1.0; link preview)"
TIMEOUT = 10
MAX_BYTES = 3_000_000


class FetchError(Exception):
    """The ad couldn't be read; the message says why, in English (translated by the caller)."""


def supported(url):
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in HOSTS)


def with_scheme(url):
    """People often copy a link without "https://"; the form and the fetch both need one."""
    url = (url or "").strip()
    return url if re.match(r"https?://", url, re.I) else "https://" + url


class _SameSitesRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the supported sites, checked before the request is sent."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not supported(newurl):
            raise FetchError("We can only read links from Marktplaats and 2dehands for now.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameSitesRedirects)


def clean_url(url):
    """The ad's own address, without tracking parameters."""
    parts = urlsplit(url.strip())
    return urlunsplit(("https", parts.netloc.lower(), parts.path, "", ""))


def fetch_listing(url):
    url = with_scheme(url)
    if not supported(url):
        raise FetchError("We can only read links from Marktplaats and 2dehands for now.")
    url = clean_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "nl"})
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            html = response.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise FetchError("That ad no longer exists.") from e
        raise FetchError("The site didn't let us read the ad.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError("The site didn't answer in time.") from e
    listing = parse_listing(html)
    listing["listing_url"] = url
    return listing


def ad_id(url):
    """The ad's number, e.g. "a1512951815" (or an old "m..." id), from any of its links."""
    m = re.search(r"/([am]\d{6,})(?:[-./?#]|$)", urlsplit(with_scheme(url)).path + "/")
    return m.group(1) if m else None


def ad_status(url):
    """"live", "removed", or None when we couldn't tell (site down, blocked, not an ad link).

    Asks for the short link (https://www.marktplaats.nl/a123...): it redirects to the ad wherever
    the site files it now, and a saved long link can 404 after the site renames a category.
    """
    item = ad_id(url)
    if not item or not supported(with_scheme(url)):
        return None
    short = f"https://{urlsplit(with_scheme(url)).hostname.lower()}/{item}"
    request = urllib.request.Request(short, headers={"User-Agent": USER_AGENT, "Accept-Language": "nl"})
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            # Sent somewhere that isn't this ad (a category page, the home page): it's gone.
            return "live" if item in response.geturl() else "removed"
    except urllib.error.HTTPError as e:
        return "removed" if e.code in (404, 410) else None
    except (FetchError, urllib.error.URLError, TimeoutError, OSError):
        return None


def ad_key(row):
    """What makes two checks the same ad: the ad number for a link from Marktplaats or 2dehands
    (so any form of the link counts), otherwise exactly the same title and asking price."""
    url = row["listing_url"]
    if url and supported(with_scheme(url)) and ad_id(url):
        host = (urlsplit(with_scheme(url)).hostname or "").lower()
        site = "marktplaats" if "marktplaats" in host else "2dehands"
        return f"{site}:{ad_id(url)}"
    return "typed:" + " ".join((row["title"] or "").lower().split()) + f"|{row['asking_price']}"


def parse_listing(html):
    config = _config(html)
    data = config.get("listing") or {}
    title = data.get("title") or _meta(html, "og:title")
    if not title:
        raise FetchError("That link doesn't look like an ad.")
    price = (data.get("priceInfo") or {}).get("priceCents")
    location = ((data.get("seller") or {}).get("location") or {}).get("cityName")
    photos = ["https:" + u.replace("eps_#", "eps_85") if u.startswith("//") else u
              for u in (data.get("gallery") or {}).get("imageUrls") or []]
    text = _Section("Description-module-description")
    text.feed(html)
    attrs = _Attributes()
    attrs.feed(html)
    description = text.text() or _meta(html, "og:description") or ""
    pairs = [(k, v) for k, v in attrs.pairs if v and "fabrikant" not in k.lower()]  # skip the maker's address fields
    if pairs:
        # Appended as "Label: value" so the checks read condition, material and so on like ad text.
        description += "\n\n" + "\n".join(f"{k}: {v}" for k, v in pairs)
    return {"title": title.strip(), "description": description.strip(),
            "asking_price": price / 100 if price else None,
            "location": location, "photos": photos}


def _config(html):
    start = html.find("window.__CONFIG__")
    brace = html.find("{", start) if start >= 0 else -1
    if brace < 0:
        return {}
    try:
        return json.JSONDecoder().raw_decode(html, brace)[0]
    except ValueError:
        return {}


def _meta(html, prop):
    m = re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % re.escape(prop), html)
    return html_lib.unescape(m.group(1)) if m else None


class _Section(HTMLParser):
    """Text of the first element with the given class, with line breaks at blocks and list items."""
    BLOCKS = {"p", "li", "br", "div", "ul", "ol", "h2", "h3", "h4", "tr"}
    VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}

    def __init__(self, cls):
        super().__init__()
        self.cls, self.depth, self.done, self.parts = cls, 0, False, []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if self.depth:
            if tag not in self.VOID:
                self.depth += 1
            if tag in self.BLOCKS:
                self.parts.append("\n- " if tag == "li" else "\n")
        elif self.cls in (dict(attrs).get("class") or "").split():
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag not in self.VOID:
            self.depth -= 1
            if not self.depth:
                self.done = True
            elif tag in self.BLOCKS:
                self.parts.append("\n")

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def text(self):
        lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(self.parts).splitlines()]
        text = re.sub(r"(?m)^-\n+", "- ", "\n".join(lines))  # "<li><p>" leaves the bullet on its own line
        text = re.sub(r"(?m)^(- .*)\n\n+(?=- )", r"\1\n", text)  # no gaps inside a list
        return re.sub(r"\n{3,}", "\n\n", text).strip()


class _Attributes(HTMLParser):
    """The ad's "Kenmerken" list as (label, value) pairs."""

    def __init__(self):
        super().__init__()
        self.pairs, self.field, self.depth, self.buf = [], None, 0, []

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get("class") or "").split()
        if self.field:
            self.depth += 1
        elif "Attributes-module-label" in cls or "Attributes-module-value" in cls:
            self.field, self.depth, self.buf = ("label" if "Attributes-module-label" in cls else "value"), 1, []

    def handle_endtag(self, tag):
        if not self.field:
            return
        self.depth -= 1
        if self.depth:
            return
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if self.field == "label":
            self.pairs.append([text, ""])
        elif self.pairs and not self.pairs[-1][1]:
            self.pairs[-1][1] = text
        self.field = None

    def handle_data(self, data):
        if self.field:
            self.buf.append(data)
