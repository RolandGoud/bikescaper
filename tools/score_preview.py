"""Score every ad the site shows with the old and the stricter photo and ad rules, side by side, as JSON.

Read-only: opens the database read-only and uses each check's stored report. Run inside the app's folder:
    python tools/score_preview.py /data/bikecompare.sqlite3 > preview.json
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())
from webapp import ad_photos, bike_fit, checks, db, fetch_ad, stored_checks  # noqa: E402
from webapp.scores import missing, BAD, WARN  # noqa: E402
from webapp import scores as new  # noqa: E402

def old_ad_score(listing, report):
    """(score out of 10, [(points lost, reason key, detail)])."""
    lost = []
    gaps = [k for k in missing(report, listing) if k in ("year", "size", "groupset", "condition")]
    for key in gaps[:4]:
        lost.append((1, "no_" + key, None))
    if not report.get("model"):
        return min(4, 10 - len(lost)), lost + [(0, "no_model", None)]
    clashes = (report.get("name_check") or {}).get("conflicts") or []
    if clashes:
        lost.append((3, "name_clash", " / ".join(f"{ours} ↔ {theirs}" for ours, theirs in clashes[:2])))
    if (report.get("age") or {}).get("status") == BAD or report.get("material_alert"):
        lost.append((2, "impossible", None))
    down = [r for r in (report.get("specs") or {}).get("rows", []) if r.get("step", 0) < 0]
    if down:
        lost.append((min(2, len(down)), "downgraded", ", ".join(str(r["part"]) for r in down[:2])))
    value = report.get("value") or {}
    asking, high = listing.get("asking_price"), value.get("high")
    if value.get("status") == BAD or (value.get("status") == WARN and asking and high and asking > 1.25 * high):
        lost.append((1, "price", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


def old_photo_score(n, paths):
    """(score out of 10, [(points lost, reason key, detail)]) for an ad with n photos, of which paths are the
    files we stored (the others only count), or (None, []) for an ad typed in without photos."""
    if not n:
        return None, []
    looks = [q for q in (bike_fit.photo_quality(p) for p in paths) if q]
    lost = []
    if n < 6:
        lost.append((5 if n == 1 else 3 if n <= 3 else 1, "few_photos", str(n)))
    if looks:
        if not any(q["side"] for q in looks):
            lost.append((2, "no_side", None))
        if sum(1 for q in looks if not q["side"]) < 2:
            lost.append((2, "no_details", None))
        half = len(looks) / 2
        for key in ("blurry", "dark", "small"):
            if sum(1 for q in looks if q[key]) > half:
                lost.append((1, key, None))
        if any(q["stock"] for q in looks):
            lost.append((3, "stock", None))
    return max(0, 10 - sum(p for p, _k, _d in lost)), lost


def group(rows):
    seen = {}
    for r in rows:  # newest first
        seen.setdefault(fetch_ad.ad_key(r), dict(r))
    return list(seen.values())


def main(path):
    if not hasattr(new, "AD_GAPS"):  # the app here still has the old rules: load the stricter ones beside it
        import importlib.util
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores_new.py")
        spec = importlib.util.spec_from_file_location("webapp.scores_new", here)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        globals()["new"] = mod
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    models = db.all_models(conn)
    folder = ad_photos.folder(path)
    rows = conn.execute(f"SELECT * FROM checks WHERE {db.PUBLISHED} ORDER BY id DESC").fetchall()
    out = []
    for row in group(rows):
        stored = conn.execute("SELECT result FROM check_results WHERE check_id = ?", (row["id"],)).fetchone()
        try:
            report = stored_checks.load(stored["result"], models) if stored else None
        except Exception:
            report = None
        if report is None:
            report = checks.run_check(models, row, None)
        photos = json.loads(row["photos"]) if row["photos"] else []
        paths = [os.path.join(folder, p) for p in photos if ad_photos.is_stored(p)][:12]
        listing = dict(row)
        oa, _ = old_ad_score(listing, report)
        na, na_lost = new.ad_score(listing, report)
        op, _ = old_photo_score(len(photos), paths)
        np_, np_lost = new.photo_score(len(photos), paths)
        out.append({"id": row["id"], "title": row["title"], "photos": len(photos), "stored": len(paths),
                    "brand": (report.get("model") or {}).get("brand") or report["claims"].get("brand"),
                    "ad": [oa, na], "photo": [op, np_], "ad_lost": na_lost, "photo_lost": np_lost})
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else db.DB_PATH)
