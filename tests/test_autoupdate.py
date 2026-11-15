import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_the_nas_update_brings_the_photo_lists_the_site_reads():
    spec = importlib.util.spec_from_file_location("autoupdate", os.path.join(ROOT, "nas", "autoupdate.py"))
    autoupdate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(autoupdate)
    for path in ("data/galleries/Trek.json", "data/years/site/Trek.json", "images/Trek/gallery/x.jpg"):
        assert path.startswith(autoupdate.KEEP), path


def load():
    spec = importlib.util.spec_from_file_location("autoupdate", os.path.join(ROOT, "nas", "autoupdate.py"))
    autoupdate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(autoupdate)
    return autoupdate


class Answer:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_nas_reads_the_branch_head_from_githubs_git_server(monkeypatch):
    autoupdate = load()
    sent = []
    sha, other = "a" * 40, "b" * 40
    body = (autoupdate.pkt(f"{other} refs/heads/main-old\n") + autoupdate.pkt(f"{sha} refs/heads/main\n")
            + b"0000")

    def urlopen(req, timeout):
        sent.append(req)
        return Answer(body)

    monkeypatch.setattr(autoupdate.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("BRANCH", "main")
    assert autoupdate.git_head() == sha
    assert sent[0].full_url == "https://github.com/RolandGoud/bikescaper.git/git-upload-pack"
    assert sent[0].get_header("Git-protocol") == "version=2"
    assert b"ref-prefix refs/heads/main\n" in sent[0].data


def test_the_nas_falls_back_to_the_api_when_the_git_check_fails(monkeypatch):
    autoupdate = load()

    def broken():
        raise OSError("no route")

    monkeypatch.setattr(autoupdate, "git_head", broken)
    monkeypatch.setattr(autoupdate, "latest_commit", lambda: "c" * 40)
    assert autoupdate.head() == "c" * 40
