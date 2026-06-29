import csv
import json
from datetime import datetime, timezone

import fetch_arxiv as fa


# ---- pure helpers ----

def test_base_arxiv_id_strips_version():
    assert fa.base_arxiv_id("2406.01234v2") == "2406.01234"
    assert fa.base_arxiv_id("2406.01234v10") == "2406.01234"


def test_base_arxiv_id_no_version():
    assert fa.base_arxiv_id("2406.01234") == "2406.01234"


def test_base_arxiv_id_old_style():
    assert fa.base_arxiv_id("cs/0501001v1") == "cs/0501001"


def test_base_arxiv_id_trailing_v_not_digits_kept():
    assert fa.base_arxiv_id("2406.0123vX") == "2406.0123vX"


def test_build_query_with_categories():
    q = fa.build_query(["ai scientist", "research agent"], ["cs.AI", "cs.LG"])
    assert q == '(abs:"ai scientist" OR abs:"research agent") AND (cat:cs.AI OR cat:cs.LG)'


def test_build_query_empty_categories_omits_clause():
    assert fa.build_query(["hypothesis generation"], []) == '(abs:"hypothesis generation")'


def test_effective_categories_theme_override():
    assert fa.effective_categories({"categories": ["cs.CV"]}, {"categories": ["cs.AI"]}) == ["cs.CV"]


def test_effective_categories_explicit_empty_disables():
    assert fa.effective_categories({"categories": []}, {"categories": ["cs.AI"]}) == []


def test_effective_categories_inherits_defaults():
    assert fa.effective_categories({}, {"categories": ["cs.AI"]}) == ["cs.AI"]


def test_effective_threshold():
    assert fa.effective_threshold({"threshold": 4}, {"threshold": 3}) == 4
    assert fa.effective_threshold({}, {"threshold": 3}) == 3


def test_lookback_days_first_run_vs_normal():
    defaults = {"lookback_days": 7, "first_run_lookback_days": 30}
    assert fa.lookback_days(True, {}, defaults) == 30
    assert fa.lookback_days(False, {}, defaults) == 7


def test_lookback_days_theme_override():
    defaults = {"lookback_days": 7, "first_run_lookback_days": 30}
    # theme-level keys take precedence over defaults
    assert fa.lookback_days(True, {"first_run_lookback_days": 365}, defaults) == 365
    assert fa.lookback_days(False, {"lookback_days": 14}, defaults) == 14
    # a theme override for one key does not affect the other branch
    assert fa.lookback_days(False, {"first_run_lookback_days": 365}, defaults) == 7


def test_cutoff_datetime():
    now = datetime(2026, 6, 28, tzinfo=timezone.utc)
    assert fa.cutoff_datetime(now, 7) == datetime(2026, 6, 21, tzinfo=timezone.utc)


def test_read_seen_ids_missing_file_is_empty(tmp_path):
    assert fa.read_seen_ids(tmp_path / "nope.csv") == set()


def test_read_seen_ids_header_only_is_empty(tmp_path):
    p = tmp_path / "seen.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(fa.CSV_HEADER)
    assert fa.read_seen_ids(p) == set()


def test_read_seen_ids_reads_ids_with_comma_titles(tmp_path):
    p = tmp_path / "seen.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fa.CSV_HEADER)
        w.writerow(["2406.00001", "5", "Foo, Bar: A Study", "2026-06-28", "true"])
        w.writerow(["2406.00002", "2", "Baz", "2026-06-28", "false"])
    assert fa.read_seen_ids(p) == {"2406.00001", "2406.00002"}


# ---- commit mode ----

def _candidates_doc():
    return {
        "themes": [
            {
                "id": "t1",
                "threshold": 3,
                "candidates": [
                    {"arxiv_id": "2406.00001", "title": "Foo, Bar: A Study"},
                    {"arxiv_id": "2406.00002", "title": "Plain Title"},
                ],
            }
        ]
    }


def test_titles_by_theme():
    t = fa.titles_by_theme(_candidates_doc())
    assert t["t1"]["2406.00001"] == "Foo, Bar: A Study"
    assert t["t1"]["2406.00002"] == "Plain Title"


def test_thresholds_by_theme():
    assert fa.thresholds_by_theme(_candidates_doc()) == {"t1": 3}


def test_commit_writes_header_and_rows_with_surfaced(tmp_path):
    titles = fa.titles_by_theme(_candidates_doc())
    thresholds = fa.thresholds_by_theme(_candidates_doc())
    scores = {"t1": {"2406.00001": 5, "2406.00002": 2}}
    appended = fa.commit_scores(scores, titles, thresholds, tmp_path, "2026-06-28")
    assert appended == {"t1": 2}

    csv_path = tmp_path / "state" / "seen-t1.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["arxiv_id"] for r in rows] == ["2406.00001", "2406.00002"]
    # comma-in-title survives the round-trip
    assert rows[0]["title"] == "Foo, Bar: A Study"
    assert rows[0]["surfaced"] == "true"   # 5 >= 3
    assert rows[1]["surfaced"] == "false"  # 2 < 3
    assert rows[0]["evaluated"] == "2026-06-28"


def test_commit_appends_without_duplicate_header(tmp_path):
    titles = fa.titles_by_theme(_candidates_doc())
    thresholds = fa.thresholds_by_theme(_candidates_doc())
    fa.commit_scores({"t1": {"2406.00001": 5}}, titles, thresholds, tmp_path, "2026-06-28")
    fa.commit_scores({"t1": {"2406.00002": 2}}, titles, thresholds, tmp_path, "2026-06-29")
    lines = (tmp_path / "state" / "seen-t1.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "arxiv_id,score,title,evaluated,surfaced"
    assert len([ln for ln in lines if ln.startswith("arxiv_id,")]) == 1


def test_commit_ignores_ids_absent_from_candidates(tmp_path):
    titles = fa.titles_by_theme(_candidates_doc())
    thresholds = fa.thresholds_by_theme(_candidates_doc())
    scores = {"t1": {"2406.00001": 4, "9999.99999": 5}}  # second id not in candidates
    appended = fa.commit_scores(scores, titles, thresholds, tmp_path, "2026-06-28")
    assert appended == {"t1": 1}
    assert fa.read_seen_ids(tmp_path / "state" / "seen-t1.csv") == {"2406.00001"}


# ---- CLI commit mode (no network: run_fetch is not invoked) ----

def test_main_commit_mode_writes_ledger(tmp_path):
    data_dir = tmp_path / "watch-paper"
    (data_dir / "state").mkdir(parents=True)
    candidates_doc = {
        "themes": [
            {
                "id": "t1",
                "threshold": 3,
                "candidates": [
                    {"arxiv_id": "2406.00001", "title": "Foo, Bar"},
                    {"arxiv_id": "2406.00002", "title": "Baz"},
                ],
            }
        ]
    }
    (data_dir / "candidates.json").write_text(
        json.dumps(candidates_doc, ensure_ascii=False), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(
        json.dumps({"t1": {"2406.00001": 4, "2406.00002": 1}}), encoding="utf-8")

    rc = fa.main(["--data-dir", str(data_dir), "--commit", str(scores_path)])
    assert rc == 0

    assert fa.read_seen_ids(data_dir / "state" / "seen-t1.csv") == {"2406.00001", "2406.00002"}
    with (data_dir / "state" / "seen-t1.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["arxiv_id"]: r for r in csv.DictReader(f)}
    assert rows["2406.00001"]["surfaced"] == "true"   # 4 >= 3
    assert rows["2406.00002"]["surfaced"] == "false"  # 1 < 3
    assert rows["2406.00001"]["title"] == "Foo, Bar"
