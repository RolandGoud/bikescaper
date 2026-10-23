"""Wayback Machine helper for the per-year spec sheets (stdlib only, runs on Windows too).

  python wayback.py cdx            -> cdx/<brand>.txt   (archived NL bike-page URLs, 2020-2026, one row per URL per month)
  python wayback.py fetch wanted.json  -> pages/<brand>/<slug>/<year>.html.gz  (resumable; skips files already there)
"""
import gzip, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIXES = {
    "Trek": ["trekbikes.com/nl/nl_NL/"],
    "Canyon": ["canyon.com/nl-nl/"],
    "Specialized": ["specialized.com/nl/nl/"],
    "Giant": ["giant-bicycles.com/nl/"],
    "Cannondale": ["cannondale.com/nl-nl/bikes/", "cannondale.com/nl_nl/"],
    "Cube": ["cube.eu/nl-nl/", "cube.eu/nl/"],
    "Factor": ["factorbikes.com/", "eu.factorbikes.com/"],
}
UA = {"User-Agent": "bikescaper-archive/1.0 (personal research)"}


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return e.code, b""
            wait = 20 * (i + 1) if e.code == 429 else 5 * (i + 1)
        except Exception:
            wait = 5 * (i + 1)
        time.sleep(wait)
    return None, b""


def cdx():
    os.makedirs(os.path.join(HERE, "cdx"), exist_ok=True)
    for brand, prefixes in PREFIXES.items():
        out = os.path.join(HERE, "cdx", brand + ".txt")
        if os.path.exists(out):
            print(brand, "already done"); continue
        rows = []
        for prefix in prefixes:
            key = None
            while True:
                q = {"url": prefix, "matchType": "prefix", "from": "2020", "to": "2026", "fl": "timestamp,original",
                     "filter": ["statuscode:200", "mimetype:text/html"], "collapse": "timestamp:6",
                     "limit": "20000", "showResumeKey": "true"}
                if key:
                    q["resumeKey"] = key
                status, body = get("https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(q, doseq=True))
                if status != 200:
                    print(brand, prefix, "CDX failed", status); break
                lines = body.decode("utf-8", "replace").splitlines()
                key = None
                if len(lines) >= 2 and lines[-2] == "":
                    key = lines[-1]; lines = lines[:-2]
                rows += [l for l in lines if l.strip()]
                print(brand, prefix, len(rows), flush=True)
                if not key:
                    break
                time.sleep(2)
        with open(out + ".tmp", "w", encoding="utf-8") as f:
            f.write("\n".join(rows))
        os.replace(out + ".tmp", out)


def fetch(wanted_path):
    wanted = json.load(open(wanted_path, encoding="utf-8"))
    done = failed = 0
    for i, w in enumerate(wanted):
        path = os.path.join(HERE, "pages", w["brand"], w["slug"], f"{w['year']}.html.gz")
        if os.path.exists(path):
            continue
        status, body = get(f"https://web.archive.org/web/{w['ts']}id_/{w['url']}")
        if status != 200 or not body:
            failed += 1; print("failed", status, w["url"], flush=True); continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(path, "wb") as f:
            f.write(body)
        with open(path[:-8] + ".json", "w") as f:
            json.dump(w, f)
        done += 1
        if done % 25 == 0:
            print(f"{i + 1}/{len(wanted)} fetched {done}, failed {failed}", flush=True)
        time.sleep(1.5)
    print("finished: fetched", done, "failed", failed)


if __name__ == "__main__":
    cdx() if sys.argv[1] == "cdx" else fetch(sys.argv[2])
