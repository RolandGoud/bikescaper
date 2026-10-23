"""A Fetcher look-alike that loads pages in the locally installed Chrome, for sites that turn away plain requests.

Scott (Imperva) and Orbea (Cloudflare) answer requests and headless browsers with a
403 challenge page, but serve a normal, visible Chrome window. Pages are opened in
one tab; XML, JSON and other files on the same site are fetched from inside that
tab so they carry its cookies. Needs `pip install playwright` and Google Chrome.
"""
import base64
import time
from urllib.parse import urlparse

from .common import log

CHALLENGE_MARKS = ("Just a moment...", "_Incapsula_Resource", "Request unsuccessful. Incapsula")


class BrowserFetcher:
    def __init__(self, delay=2.0, delays=None, headless=False):
        self.delay = delay
        self.delays = delays or {}
        self.headless = headless
        self._last = {}
        self._pw = self._browser = self._page = None

    def _start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless)
        self._page = self._browser.new_page(locale="nl-NL", viewport={"width": 1400, "height": 900})

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()
        self._pw = self._browser = self._page = None

    def _wait(self, url):
        host = urlparse(url).netloc
        wait = self.delays.get(host, self.delay) - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.time()

    def _on_site(self, url):
        cur = urlparse(self._page.url) if self._page and self._page.url.startswith("http") else None
        return cur is not None and cur.netloc == urlparse(url).netloc

    def get(self, url, binary=False, page=True):
        """The rendered HTML of a page, or (page=False / binary) the raw body fetched from within the site's tab."""
        if not self._page:
            self._start()
        for attempt in range(3):
            self._wait(url)
            try:
                if binary or not page:
                    if not self._on_site(url):
                        home = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
                        self._page.goto(home, wait_until="domcontentloaded", timeout=90000)
                        self._settle()
                    result = self._page.evaluate(
                        """async ([u, bin]) => {
                            const r = await fetch(u, {credentials: 'include'});
                            if (!bin) return [r.status, await r.text()];
                            const b = new Uint8Array(await r.arrayBuffer());
                            let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode(...b.subarray(i, i + 32768));
                            return [r.status, btoa(s)];
                        }""", [url, binary])
                    status, body = result
                    if status == 404:
                        return None
                    if status >= 400:
                        raise RuntimeError(f"HTTP {status}")
                    return base64.b64decode(body) if binary else body
                resp = self._page.goto(url, wait_until="domcontentloaded", timeout=90000)
                self._settle()
                if resp and resp.status == 404:
                    return None
                html = self._page.content()
                if any(mark in html[:20000] for mark in CHALLENGE_MARKS):
                    raise RuntimeError("challenge page")
                return html
            except Exception as exc:
                log.warning("%s (attempt %d): %s", url, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
        return None

    def _settle(self):
        """Let a challenge page hand over to the real one and late scripts fill in the data."""
        for _ in range(20):
            try:
                self._page.wait_for_load_state("load", timeout=15000)
                html = self._page.content()
            except Exception:
                time.sleep(1)
                continue
            if not any(mark in html[:20000] for mark in CHALLENGE_MARKS):
                return
            time.sleep(1.5)
