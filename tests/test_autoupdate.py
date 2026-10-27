import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_the_nas_update_brings_the_photo_lists_the_site_reads():
    spec = importlib.util.spec_from_file_location("autoupdate", os.path.join(ROOT, "nas", "autoupdate.py"))
    autoupdate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(autoupdate)
    for path in ("data/galleries/Trek.json", "data/years/site/Trek.json", "images/Trek/gallery/x.jpg"):
        assert path.startswith(autoupdate.KEEP), path
