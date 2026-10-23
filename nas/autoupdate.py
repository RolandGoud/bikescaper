"""Keep the NAS copy of Bike Compare on the latest commit of a GitHub branch.

Used by nas/docker-compose.yml, which runs it in two ways:

  python autoupdate.py --now     download the latest code into /app (on container start)
  python autoupdate.py --watch   every UPDATE_MINUTES, check GitHub for a new commit and, if there
                                 is one, install it and reload gunicorn without stopping the site

The check asks the GitHub API only for the branch's commit id and sends the last answer's ETag,
so an unchanged branch costs nothing against GitHub's limit of 60 requests an hour. Saved checks
are in /data and are never touched. If anything goes wrong the site keeps running the code it
has, and the next check tries again.
"""
import io
import os
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
BRANDS = ("Trek", "Canyon", "Specialized", "Giant", "Cannondale", "Cube", "Factor", "Scott", "Orbea")
KEEP = ("webapp/", "images/", "nas/") + tuple(f"data/{b}/" for b in BRANDS)
DIRS = ("webapp", "data", "images", "nas")

etag = None
failed = {}  # commit id -> failed tries, so a broken commit isn't downloaded forever


def log(msg):
    print(f"[autoupdate] {msg}", flush=True)


def branch():
    return os.environ.get("BRANCH") or "main"


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
    for name in os.listdir(APP):  # left over from an update that was cut off
        if name.startswith(".update-"):
            shutil.rmtree(os.path.join(APP, name), ignore_errors=True)
    try:
        sha = latest_commit()
        if sha and sha == installed_commit() and os.path.exists(os.path.join(APP, "webapp", "app.py")):
            log(f"already on {sha[:7]}")
            return
        staging = tempfile.mkdtemp(prefix=".update-", dir=APP)
        try:
            download(sha or branch(), staging)
            swap_in(staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        if sha:
            with open(VERSION_FILE, "w") as fh:
                fh.write(sha)
        log(f"downloaded {branch()} at {(sha or '?')[:7]}")
    except Exception as exc:
        if not os.path.exists(os.path.join(APP, "webapp", "app.py")):
            raise
        log(f"download failed ({exc}); starting the code from last time")


def watch():
    global etag
    minutes = float(os.environ.get("UPDATE_MINUTES") or 10)
    if minutes <= 0:
        log("UPDATE_MINUTES is 0, not checking for updates")
        return
    log(f"checking {REPO} {branch()} for new commits every {minutes:g} minutes")
    while True:
        time.sleep(minutes * 60)
        sha = None
        try:
            sha = latest_commit()
            if not sha or sha == installed_commit() or failed.get(sha, 0) >= 3:
                continue
            log(f"new commit {sha[:7]}, installing")
            install(sha)
            # The new code is on disk now, so reload even if the seed fails (say, a busy database):
            # the next update or restart seeds again.
            try:
                run(sys.executable, "-m", "webapp.seed", "--if-empty")
            except Exception as exc:
                log(f"seeding the catalogue failed ({exc}); reloading anyway")
            os.kill(1, signal.SIGHUP)  # gunicorn: start workers on the new code, then stop the old ones
            log(f"now running {sha[:7]}")
            # Carry on with this file's new version, in case the updater itself changed.
            shutil.copy(os.path.join(APP, "nas", "autoupdate.py"), os.path.join(APP, "autoupdate.py"))
            os.execv(sys.executable, [sys.executable, os.path.join(APP, "autoupdate.py"), "--watch"])
        except Exception as exc:
            etag = None  # ask again next time instead of getting "unchanged"
            if sha:
                failed[sha] = failed.get(sha, 0) + 1
            log(f"update failed ({exc}); still running {(installed_commit() or '?')[:7]}")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        now()
