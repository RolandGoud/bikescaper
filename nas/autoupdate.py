"""Keep the NAS copy of Bikecheck on the latest commit of a GitHub branch.

Used by nas/docker-compose.yml, which runs it in two ways:

  python autoupdate.py --now     download the latest code into /app (on container start)
  python autoupdate.py --watch   every CHECK_SECONDS (default 30), check GitHub for a new commit and,
                                 if there is one, install it and reload gunicorn without stopping the site

The check asks GitHub's git server for the branch's commit id only (git's "ls-refs", one small
request, the same as `git ls-remote`), which isn't counted against the API's limit of 60 requests an
hour, so a merge is live within a minute or two. If that fails it falls back to the API, sending the
last answer's ETag. UPDATE_MINUTES "0" still turns checking off. Saved checks
are in /data and are never touched. If anything goes wrong the site keeps running the code it
has, and the next check tries again.

For the admin's account menu on the site it also writes, next to the database: updating.json while an
update installs (a spinner), and updates.json with each update's PRs, their links and the page to check
(from a "Check: /path" line in the PR), shown as "Just live on the site".
"""
import datetime
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

REPO = "RolandGoud/bikescaper"
APP = "/app"
VERSION_FILE = os.path.join(APP, ".version")
BRANDS = ("Trek", "Canyon", "Specialized", "Giant", "Cannondale", "Cube", "Factor", "Scott", "Orbea", "Lapierre",
          "Bianchi", "BMC", "Cervelo", "Ridley", "Rose", "Wilier")
KEEP = ("webapp/", "images/", "nas/", "data/years/", "data/galleries/") + tuple(f"data/{b}/" for b in BRANDS)
DIRS = ("webapp", "data", "images", "nas")

UPDATES_FILE = os.environ.get("UPDATES_FILE") or os.path.join(
    os.path.dirname(os.environ.get("BIKECOMPARE_DB") or "/data/x"), "updates.json")
UPDATING_FILE = os.path.join(os.path.dirname(UPDATES_FILE), "updating.json")  # there while an update installs
KEEP_UPDATES = 60
CHECK_LINE = re.compile(r"^\s*(?:check|check at|check-at|where to check)\s*:\s*(/\S*|https?://\S+)", re.I | re.M)
MERGE = re.compile(r"^Merge pull request #(\d+) from \S+")
SQUASH = re.compile(r"^(.*?)\s*\(#(\d+)\)\s*$")

etag = None
failed = {}  # commit id -> failed tries, so a broken commit isn't downloaded forever


def log(msg):
    print(f"[autoupdate] {msg}", flush=True)


def branch():
    return os.environ.get("BRANCH") or "main"


def pkt(line):
    data = line.encode()
    return f"{len(data) + 4:04x}".encode() + data


def git_head():
    """The branch's newest commit id, asked from GitHub's git server (git protocol v2 ls-refs)."""
    ref = f"refs/heads/{branch()}"
    body = pkt("command=ls-refs\n") + b"0001" + pkt(f"ref-prefix {ref}\n") + b"0000"
    req = urllib.request.Request(f"https://github.com/{REPO}.git/git-upload-pack", data=body,
                                 headers={"Content-Type": "application/x-git-upload-pack-request",
                                          "Accept": "application/x-git-upload-pack-result",
                                          "Git-Protocol": "version=2",
                                          "User-Agent": "git/2 bikecompare-nas"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        answer = resp.read().decode("ascii", "replace")
    for line in answer.split("\n"):
        parts = line[4:].split() if len(line) > 4 else []  # drop the pkt-line length
        if len(parts) >= 2 and parts[1] == ref and len(parts[0]) == 40:
            return parts[0]
    raise RuntimeError(f"{ref} not in GitHub's answer")


def head():
    """The branch's newest commit id; None only when the API fallback says it is unchanged."""
    try:
        return git_head()
    except Exception as exc:
        log(f"git check failed ({exc}); asking the API")
        return latest_commit()


def latest_commit():
    """The branch's newest commit id, or None when it hasn't changed since the last ask."""
    global etag
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/commits/{branch()}",
                                 headers={"Accept": "application/vnd.github.sha",
                                          "User-Agent": "bikecompare-nas"})
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            etag = resp.headers.get("ETag")
            return resp.read().decode().strip()
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None
        raise


def installed_commit():
    try:
        with open(VERSION_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return None


def download(ref, into):
    """Unpack the parts of the repo the site needs, at commit or branch `ref`, into folder `into`."""
    url = f"https://codeload.github.com/{REPO}/tar.gz/{ref}"
    data = urllib.request.urlopen(url, timeout=300).read()
    tar = tarfile.open(fileobj=io.BytesIO(data))
    members = [m for m in tar.getmembers() if m.isfile() and m.name.split("/", 1)[-1].startswith(KEEP)]
    for m in members:
        m.name = m.name.split("/", 1)[1]
    tar.extractall(into, members=members, filter="data")


def swap_in(staging):
    """Replace the code folders in /app with the ones in `staging` (same disk, so each is a rename)."""
    for d in DIRS:
        new, cur, old = os.path.join(staging, d), os.path.join(APP, d), os.path.join(staging, d + ".old")
        if os.path.exists(cur):
            os.rename(cur, old)
        if os.path.exists(new):
            os.rename(new, cur)


def api(path):
    """GET one GitHub API answer as JSON (with GITHUB_TOKEN when set, for a higher limit)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "bikecompare-nas"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def check_at(text):
    """The page to look at, from a "Check: /models/..." line in a PR or commit message, or None."""
    found = CHECK_LINE.search(text or "")
    return found.group(1).rstrip(".,)") if found else None


def changes_between(old, new):
    """What came in between commit `old` and `new`: one item per merged PR (or direct commit), newest
    first, as {title, pr, url, check}. Follows main's first parents, so a PR's own commits count once."""
    if old:
        commits = api(f"compare/{old}...{new}")["commits"]
    else:
        commits = [api(f"commits/{new}")]
    by_sha = {c["sha"]: c for c in commits}
    line, sha = [], new
    while sha in by_sha and sha != old:
        line.append(by_sha[sha])
        parents = by_sha[sha]["parents"]
        sha = parents[0]["sha"] if parents else None
    on_line = {c["sha"] for c in line}
    changes = []
    for c in line[:30]:
        message = c["commit"]["message"]
        subject, _, body = message.partition("\n")
        title, pr = subject.strip(), None
        merge, squash = MERGE.match(subject), SQUASH.match(subject)
        texts = [message]
        if merge:
            pr = int(merge.group(1))
            title = next((ln.strip() for ln in body.splitlines() if ln.strip()), title)
            # The PR's own commits (behind the merge's second parent) may carry the "Check:" line.
            todo = [p["sha"] for p in c["parents"][1:]]
            while todo:
                s = todo.pop()
                if s in by_sha and s not in on_line:
                    texts.append(by_sha[s]["commit"]["message"])
                    todo += [p["sha"] for p in by_sha[s]["parents"]]
                    on_line.add(s)
        elif squash:
            title, pr = squash.group(1), int(squash.group(2))
        check = next((x for x in map(check_at, texts) if x), None)
        if pr and not check:
            try:
                check = check_at(api(f"pulls/{pr}").get("body"))
            except Exception as exc:
                log(f"could not read PR #{pr} ({exc})")
        url = f"https://github.com/{REPO}/pull/{pr}" if pr else c.get("html_url")
        changes.append({"title": title[:200], "pr": pr, "url": url, "check": check})
    return changes


def what_changed(old, new):
    """changes_between, or [] when GitHub can't say: never stops an update."""
    try:
        return changes_between(old, new)
    except Exception as exc:
        log(f"could not list what changed ({exc})")
        return []


def installing(sha, changes):
    """Tell the site an update is being installed (it shows a spinner to the admin); None when it's over."""
    try:
        if sha is None:
            os.remove(UPDATING_FILE)
            return
        tmp = UPDATING_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"sha": sha, "changes": changes,
                       "since": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, fh)
        os.replace(tmp, UPDATING_FILE)
    except OSError:
        pass


def record(old, new, changes=None):
    """Add what just went live to UPDATES_FILE, for the site's "Just live" list for the admin."""
    if changes is None:
        changes = what_changed(old, new)
    try:
        with open(UPDATES_FILE) as fh:
            updates = json.load(fh)
    except (OSError, ValueError):
        updates = []
    updates.insert(0, {"sha": new, "from": old,
                       "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "changes": changes})
    try:
        tmp = UPDATES_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(updates[:KEEP_UPDATES], fh, indent=1)
        os.replace(tmp, UPDATES_FILE)
    except OSError as exc:
        log(f"could not save the update note ({exc})")


def run(*cmd, cwd=APP, **env):
    subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, **env})


def install(sha):
    """Download commit `sha`, test that it starts, then put it live. Returns True when done."""
    staging = tempfile.mkdtemp(prefix=".update-", dir=APP)
    try:
        download(sha, staging)
        run(sys.executable, "-m", "pip", "install", "--no-cache-dir", "--quiet",
            "--root-user-action=ignore", "-r", "webapp/requirements.txt", cwd=staging)
        # Import the new app against a throwaway database, so a broken commit never goes live.
        with tempfile.TemporaryDirectory() as tmp:
            run(sys.executable, "-c", "import webapp.app", cwd=staging,
                BIKECOMPARE_DB=os.path.join(tmp, "test.sqlite3"))
        swap_in(staging)
        with open(VERSION_FILE, "w") as fh:
            fh.write(sha)
        return True
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def now():
    """On container start: get the latest code. Keep last time's code if GitHub can't be reached."""
    installing(None, None)  # a spinner left over from an update that was cut off
    for name in os.listdir(APP):  # left over from an update that was cut off
        if name.startswith(".update-"):
            shutil.rmtree(os.path.join(APP, name), ignore_errors=True)
    try:
        sha = head()
        if sha and sha == installed_commit() and os.path.exists(os.path.join(APP, "webapp", "app.py")):
            log(f"already on {sha[:7]}")
            return
        staging = tempfile.mkdtemp(prefix=".update-", dir=APP)
        try:
            download(sha or branch(), staging)
            swap_in(staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        old = installed_commit()
        if sha:
            with open(VERSION_FILE, "w") as fh:
                fh.write(sha)
            if old:
                record(old, sha)
        log(f"downloaded {branch()} at {(sha or '?')[:7]}")
    except Exception as exc:
        if not os.path.exists(os.path.join(APP, "webapp", "app.py")):
            raise
        log(f"download failed ({exc}); starting the code from last time")


def watch():
    global etag
    if float(os.environ.get("UPDATE_MINUTES") or 1) <= 0:
        log("UPDATE_MINUTES is 0, not checking for updates")
        return
    seconds = max(10.0, float(os.environ.get("CHECK_SECONDS") or 30))
    log(f"checking {REPO} {branch()} for new commits every {seconds:g} seconds")
    while True:
        time.sleep(seconds)
        sha = None
        try:
            sha = head()
            if not sha or sha == installed_commit() or failed.get(sha, 0) >= 3:
                continue
            log(f"new commit {sha[:7]}, installing")
            old = installed_commit()
            changes = what_changed(old, sha)
            installing(sha, changes)
            install(sha)
            # The new code is on disk now, so reload even if the seed fails (say, a busy database):
            # the next update or restart seeds again.
            try:
                run(sys.executable, "-m", "webapp.seed", "--if-empty")
            except Exception as exc:
                log(f"seeding the catalogue failed ({exc}); reloading anyway")
            os.kill(1, signal.SIGHUP)  # gunicorn: start workers on the new code, then stop the old ones
            log(f"now running {sha[:7]}")
            record(old, sha, changes)
            installing(None, None)
            # Carry on with this file's new version, in case the updater itself changed.
            shutil.copy(os.path.join(APP, "nas", "autoupdate.py"), os.path.join(APP, "autoupdate.py"))
            os.execv(sys.executable, [sys.executable, os.path.join(APP, "autoupdate.py"), "--watch"])
        except Exception as exc:
            installing(None, None)
            etag = None  # ask again next time instead of getting "unchanged"
            if sha:
                failed[sha] = failed.get(sha, 0) + 1
            log(f"update failed ({exc}); still running {(installed_commit() or '?')[:7]}")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        now()
