import csv
import json

import commit_ledger as cl
import fetch_arxiv as fa  # read_seen_ids stays in fetch_arxiv


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
    t = cl.titles_by_theme(_candidates_doc())
    assert t["t1"]["2406.00001"] == "Foo, Bar: A Study"
    assert t["t1"]["2406.00002"] == "Plain Title"


def test_thresholds_by_theme():
    assert cl.thresholds_by_theme(_candidates_doc()) == {"t1": 3}


def test_commit_enriched_scores_reads_score_field(tmp_path):
    titles = cl.titles_by_theme(_candidates_doc())
    thresholds = cl.thresholds_by_theme(_candidates_doc())
    scores = {"t1": {
        "2406.00001": {"score": 5, "summary_ja": "a", "why_ja": "b"},
        "2406.00002": {"score": 2, "summary_ja": "c", "why_ja": "d"},
    }}
    appended = cl.commit_scores(scores, titles, thresholds, tmp_path, "2026-06-29")
    assert appended == {"t1": 2}
    csv_path = tmp_path / "state" / "seen-t1.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["arxiv_id"] == "2406.00001"
    assert rows[0]["score"] == "5"
    assert rows[0]["title"] == "Foo, Bar: A Study"   # comma survives
    assert rows[0]["surfaced"] == "true"             # 5 >= 3
    assert rows[1]["surfaced"] == "false"            # 2 < 3
    assert rows[0]["evaluated"] == "2026-06-29"


def test_commit_tolerates_bare_int_scores(tmp_path):
    titles = cl.titles_by_theme(_candidates_doc())
    thresholds = cl.thresholds_by_theme(_candidates_doc())
    scores = {"t1": {"2406.00001": 4, "2406.00002": 1}}  # legacy bare-int form
    appended = cl.commit_scores(scores, titles, thresholds, tmp_path, "2026-06-29")
    assert appended == {"t1": 2}
    with (tmp_path / "state" / "seen-t1.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["arxiv_id"]: r for r in csv.DictReader(f)}
    assert rows["2406.00001"]["surfaced"] == "true"
    assert rows["2406.00002"]["surfaced"] == "false"


def test_commit_appends_without_duplicate_header(tmp_path):
    titles = cl.titles_by_theme(_candidates_doc())
    thresholds = cl.thresholds_by_theme(_candidates_doc())
    cl.commit_scores({"t1": {"2406.00001": {"score": 5}}}, titles, thresholds, tmp_path, "2026-06-28")
    cl.commit_scores({"t1": {"2406.00002": {"score": 2}}}, titles, thresholds, tmp_path, "2026-06-29")
    lines = (tmp_path / "state" / "seen-t1.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "arxiv_id,score,title,evaluated,surfaced"
    assert len([ln for ln in lines if ln.startswith("arxiv_id,")]) == 1


def test_commit_ignores_ids_absent_from_candidates(tmp_path):
    titles = cl.titles_by_theme(_candidates_doc())
    thresholds = cl.thresholds_by_theme(_candidates_doc())
    scores = {"t1": {"2406.00001": {"score": 4}, "9999.99999": {"score": 5}}}
    appended = cl.commit_scores(scores, titles, thresholds, tmp_path, "2026-06-28")
    assert appended == {"t1": 1}
    assert fa.read_seen_ids(tmp_path / "state" / "seen-t1.csv") == {"2406.00001"}


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
    scores_path.write_text(json.dumps({"t1": {
        "2406.00001": {"score": 4, "summary_ja": "x", "why_ja": "y"},
        "2406.00002": {"score": 1, "summary_ja": "x", "why_ja": "y"},
    }}), encoding="utf-8")

    rc = cl.main(["--data-dir", str(data_dir), str(scores_path)])
    assert rc == 0
    with (data_dir / "state" / "seen-t1.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["arxiv_id"]: r for r in csv.DictReader(f)}
    assert rows["2406.00001"]["surfaced"] == "true"   # 4 >= 3
    assert rows["2406.00002"]["surfaced"] == "false"  # 1 < 3
    assert rows["2406.00001"]["title"] == "Foo, Bar"
