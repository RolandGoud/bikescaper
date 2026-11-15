"""What the NAS's updates put live: noted by nas/autoupdate.py, shown to the admin by the site."""
import datetime
import importlib.util
import json
import os

from webapp.app import create_app

ROOT = os.path.dirname(os.path.dirname(__file__))


def autoupdate():
    spec = importlib.util.spec_from_file_location("autoupdate", os.path.join(ROOT, "nas", "autoupdate.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def commit(sha, message, *parents):
    return {"sha": sha, "html_url": f"https://github.com/c/{sha}", "commit": {"message": message},
            "parents": [{"sha": p} for p in parents]}


def test_each_merged_pr_counts_once_with_its_check_page(monkeypatch):
    au = autoupdate()
    commits = [  # oldest first, as GitHub's compare lists them
        commit("b1", "Ad card: tiles stack\n\nCheck: /listings", "o"),
        commit("m1", "Merge pull request #406 from RolandGoud/tiles\n\nAd card: tiles stack together", "o", "b1"),
        commit("s1", "Groupsets chart: grey out (#405)\n\nClaude-Session: x", "m1"),
        commit("d1", "Fix a typo", "s1"),
    ]
    asked = []

    def api(path):
        asked.append(path)
        if path.startswith("compare/"):
            return {"commits": commits}
        if path == "pulls/405":
            return {"body": "Greys the tiles.\n\nCheck: /groupsets?from=105"}
        raise AssertionError(path)

    monkeypatch.setattr(au, "api", api)
    changes = au.changes_between("o", "d1")
    assert changes == [
        {"title": "Fix a typo", "pr": None, "url": "https://github.com/c/d1", "check": None},
        {"title": "Groupsets chart: grey out", "pr": 405, "url": "https://github.com/RolandGoud/bikescaper/pull/405",
         "check": "/groupsets?from=105"},
        {"title": "Ad card: tiles stack together", "pr": 406,
         "url": "https://github.com/RolandGoud/bikescaper/pull/406", "check": "/listings"},
    ]
    assert "pulls/406" not in asked  # its own commit already named the page


def test_the_check_line_needs_a_path():
    au = autoupdate()
    assert au.check_at("Check: /models/trek-domane.") == "/models/trek-domane"
    assert au.check_at("Check: <!-- the page where the change shows -->") is None
    assert au.check_at("Check: tests pass") is None


def test_an_update_is_noted_even_when_github_cant_say_what_changed(monkeypatch, tmp_path):
    au = autoupdate()
    monkeypatch.setattr(au, "UPDATES_FILE", str(tmp_path / "updates.json"))

    def broken(path):
        raise OSError("rate limited")

    monkeypatch.setattr(au, "api", broken)
    au.record("a" * 40, "b" * 40)
    au.record("b" * 40, "c" * 40)
    saved = json.loads((tmp_path / "updates.json").read_text())
    assert [u["sha"][0] for u in saved] == ["c", "b"]
    assert saved[0]["changes"] == []


def site(tmp_path, monkeypatch, updates):
    monkeypatch.setenv("UPDATES_FILE", str(tmp_path / "updates.json"))
    (tmp_path / "updates.json").write_text(json.dumps(updates))
    app = create_app(str(tmp_path / "app.sqlite3"))
    app.config["ADMIN_PASSWORD"] = "test"
    return app.test_client()


def test_the_admin_sees_what_just_went_live_with_links_in_a_new_tab(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    client = site(tmp_path, monkeypatch, [
        {"sha": "c" * 40, "time": now.isoformat(), "changes": [
            {"title": "Ad card: tiles stack", "pr": 406, "url": "https://github.com/RolandGoud/bikescaper/pull/406",
             "check": "/listings"}]},
        {"sha": "a" * 40, "time": (now - datetime.timedelta(days=9)).isoformat(),
         "changes": [{"title": "Long ago", "pr": 1, "url": "u", "check": None}]}])
    assert "live-note" not in client.get("/how-it-works?lang=en", follow_redirects=True).get_data(as_text=True)  # a visitor: nothing
    with client.session_transaction() as s:
        s["admin"] = True
    page = client.get("/how-it-works?lang=en", follow_redirects=True).get_data(as_text=True)
    assert '<span class="live-badge" hidden></span>' in page  # live-note.js fills in the count
    note = page.split('<div class="live-note"')[1].split("</ol>")[0]
    assert "Ad card: tiles stack" in note and "Long ago" not in note
    assert '<a class="live-check" href="/listings" target="_blank" rel="noopener">' in note
    assert 'href="https://github.com/RolandGoud/bikescaper/pull/406" target="_blank"' in note
    history = client.get("/admin?lang=en", follow_redirects=True).get_data(as_text=True)
    assert "Updates on the site" in history and "Long ago" in history


def test_no_note_without_updates(tmp_path, monkeypatch):
    client = site(tmp_path, monkeypatch, [])
    with client.session_transaction() as s:
        s["admin"] = True
    page = client.get("/how-it-works", follow_redirects=True).get_data(as_text=True)
    assert '<div class="live-inner" data-shas="" data-updating="">' in page  # empty, so hidden by its CSS
    assert "<li data-sha" not in page


def test_while_the_nas_installs_the_admin_sees_a_spinner(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    client = site(tmp_path, monkeypatch, [])
    (tmp_path / "updating.json").write_text(json.dumps({"sha": "d" * 40, "since": now.isoformat(), "changes": [
        {"title": "Show what changed", "pr": 410, "url": "https://github.com/RolandGoud/bikescaper/pull/410"}]}))
    assert client.get("/admin/live").status_code == 302  # a visitor: to the login
    with client.session_transaction() as s:
        s["admin"] = True
    page = client.get("/how-it-works?lang=en", follow_redirects=True).get_data(as_text=True)
    assert 'class="live-spin" aria-label="Update in progress" title="Update in progress">' in page  # shown, not hidden
    part = client.get("/admin/live?lang=en").get_data(as_text=True)
    assert f'data-updating="{"d" * 40}"' in part and "Installing on the site" in part and "Show what changed" in part
    # An old flag is left over from an update that was cut off: no spinner.
    (tmp_path / "updating.json").write_text(json.dumps(
        {"sha": "d" * 40, "since": (now - datetime.timedelta(hours=1)).isoformat(), "changes": []}))
    assert 'data-updating=""' in client.get("/admin/live").get_data(as_text=True)


def test_the_nas_raises_and_clears_the_installing_flag(monkeypatch, tmp_path):
    au = autoupdate()
    monkeypatch.setattr(au, "UPDATING_FILE", str(tmp_path / "updating.json"))
    au.installing("d" * 40, [{"title": "x"}])
    assert json.loads((tmp_path / "updating.json").read_text())["sha"] == "d" * 40
    au.installing(None, None)
    au.installing(None, None)  # already gone: fine
    assert not (tmp_path / "updating.json").exists()


def test_the_menu_shows_four_changes_and_links_the_rest(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    client = site(tmp_path, monkeypatch, [
        {"sha": f"{i}" * 40, "time": now, "changes": [{"title": f"Change {i}", "pr": i, "url": "u", "check": None}]}
        for i in range(1, 7)])
    with client.session_transaction() as s:
        s["admin"] = True
    part = client.get("/admin/live?lang=en").get_data(as_text=True)
    assert part.count("<li data-sha") == 6 and part.count(" hidden>") == 2  # all counted, two out of sight
    assert 'href="/admin#updates"' in part and "See more (2)" in part
