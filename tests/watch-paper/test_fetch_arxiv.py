import csv
import json
from datetime import datetime, timezone
from pathlib import Path

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
    assert fa.lookback_days(True, defaults) == 30
    assert fa.lookback_days(False, defaults) == 7


def test_cutoff_datetime():
    now = datetime(2026, 6, 28, tzinfo=timezone.utc)
    assert fa.cutoff_datetime(now, 7) == datetime(2026, 6, 21, tzinfo=timezone.utc)


def test_resolve_data_dir_default_is_cwd_watch_paper():
    assert fa.resolve_data_dir(None) == Path.cwd() / "watch-paper"


def test_resolve_data_dir_override():
    assert fa.resolve_data_dir("/tmp/foo") == Path("/tmp/foo")


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
