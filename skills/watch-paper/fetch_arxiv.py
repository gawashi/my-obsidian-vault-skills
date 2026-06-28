#!/usr/bin/env python3
"""watch-paper: deterministic arXiv fetch + ledger commit.

Modes:
  (default)              fetch new candidates  -> <data_dir>/candidates.json
  --commit <scores.json> append evaluated rows -> <data_dir>/state/seen-<theme>.csv

<data_dir> defaults to <cwd>/watch-paper (cwd == vault root); override with --data-dir.
`import arxiv` is lazy (inside run_fetch) so the pure helpers below stay unit-testable
without the dependency installed.
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
CSV_HEADER = ["arxiv_id", "score", "title", "evaluated", "surfaced"]


# --------------------------------------------------------------------------
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------

def base_arxiv_id(short_id):
    """Strip a trailing version suffix (vN) from an arXiv id.

    '2406.01234v2' -> '2406.01234'; '2406.01234' -> '2406.01234';
    'cs/0501001v1' -> 'cs/0501001'. A trailing 'v' not followed by digits is kept.
    """
    sid = short_id.strip()
    i = sid.rfind("v")
    if i > 0 and sid[i + 1:].isdigit():
        return sid[:i]
    return sid


def effective_categories(theme, defaults):
    """Theme `categories` override defaults; an explicit [] disables the filter."""
    if "categories" in theme:
        return theme["categories"]
    return defaults.get("categories", [])


def effective_threshold(theme, defaults):
    """Theme `threshold` overrides defaults; fallback 3."""
    return int(theme.get("threshold", defaults.get("threshold", 3)))


def build_query(keywords, categories):
    """Build an arXiv query: (abs:"kw" OR ...) AND (cat:c OR ...).

    Empty `categories` omits the AND(cat...) clause.
    """
    kw_clause = " OR ".join(f'abs:"{k}"' for k in keywords)
    query = f"({kw_clause})"
    if categories:
        cat_clause = " OR ".join(f"cat:{c}" for c in categories)
        query = f"{query} AND ({cat_clause})"
    return query


def lookback_days(ledger_empty, defaults):
    """First run (empty ledger) -> first_run_lookback_days; else lookback_days."""
    if ledger_empty:
        return int(defaults.get("first_run_lookback_days", 30))
    return int(defaults.get("lookback_days", 7))


def cutoff_datetime(now_utc, days):
    """The oldest `published` datetime to keep (tz-aware in, tz-aware out)."""
    return now_utc - timedelta(days=days)


def resolve_data_dir(arg_data_dir):
    """--data-dir if given, else <cwd>/watch-paper."""
    if arg_data_dir:
        return Path(arg_data_dir)
    return Path.cwd() / "watch-paper"


def read_seen_ids(csv_path):
    """Set of arxiv_id values already in the ledger CSV (empty if file absent)."""
    if not csv_path.exists():
        return set()
    seen = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            aid = (row.get("arxiv_id") or "").strip()
            if aid:
                seen.add(aid)
    return seen


# --------------------------------------------------------------------------
# Commit mode helpers (unit-tested)
# --------------------------------------------------------------------------

def titles_by_theme(candidates_doc):
    """{theme_id: {arxiv_id: title}} from a candidates.json document."""
    out = {}
    for theme in candidates_doc.get("themes", []):
        tid = theme.get("id")
        out[tid] = {c["arxiv_id"]: c.get("title", "")
                    for c in theme.get("candidates", [])}
    return out


def thresholds_by_theme(candidates_doc, default_threshold=3):
    """{theme_id: threshold} from a candidates.json document."""
    return {t.get("id"): int(t.get("threshold", default_threshold))
            for t in candidates_doc.get("themes", [])}


def commit_scores(scores, titles, thresholds, data_dir, evaluated_date):
    """Append evaluated rows to per-theme seen-<id>.csv ledgers.

    scores:     {theme_id: {arxiv_id: score}}
    titles:     {theme_id: {arxiv_id: title}}  (from this run's candidates.json)
    thresholds: {theme_id: int}
    Returns {theme_id: rows_appended}. arxiv_ids absent from `titles` are ignored.
    """
    state_dir = data_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    appended = {}
    for theme_id, id_scores in scores.items():
        theme_titles = titles.get(theme_id, {})
        threshold = thresholds.get(theme_id, 3)
        csv_path = state_dir / f"seen-{theme_id}.csv"
        write_header = (not csv_path.exists()) or csv_path.stat().st_size == 0
        n = 0
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(CSV_HEADER)
            for arxiv_id, score in id_scores.items():
                if arxiv_id not in theme_titles:
                    continue
                surfaced = "true" if int(score) >= threshold else "false"
                writer.writerow([arxiv_id, int(score), theme_titles[arxiv_id],
                                 evaluated_date, surfaced])
                n += 1
        appended[theme_id] = n
    return appended
