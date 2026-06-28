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


# --------------------------------------------------------------------------
# Fetch mode (network) + CLI
# --------------------------------------------------------------------------

def load_config(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def now_local_date():
    return datetime.now().date().isoformat()


def run_fetch(config, data_dir, now_utc):
    """Query arXiv per enabled theme; return the candidates.json document."""
    import arxiv  # lazy: keep module importable for unit tests without the dep

    defaults = config.get("defaults", {})
    client = arxiv.Client(
        page_size=100,
        delay_seconds=defaults.get("request_delay_seconds", 3),
        num_retries=3,
    )
    doc = {"generated": now_utc.astimezone().isoformat(),
           "first_run": False, "themes": []}
    any_first_run = False

    for theme in config.get("themes", []):
        if theme.get("enabled", True) is False:
            continue
        tid = theme["id"]
        seen = read_seen_ids(data_dir / "state" / f"seen-{tid}.csv")
        is_empty = len(seen) == 0
        any_first_run = any_first_run or is_empty
        cutoff = cutoff_datetime(now_utc, lookback_days(is_empty, defaults))
        cats = effective_categories(theme, defaults)
        query = build_query(theme.get("keywords", []), cats)
        search = arxiv.Search(
            query=query,
            max_results=defaults.get("max_results", 120),
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        theme_out = {
            "id": tid,
            "name": theme.get("name", tid),
            "threshold": effective_threshold(theme, defaults),
            "anchors": theme.get("anchors", []),
            "fetched": 0, "new": 0, "candidates": [],
        }
        try:
            for r in client.results(search):
                theme_out["fetched"] += 1
                if r.published < cutoff:
                    break  # descending order: nothing older qualifies
                aid = base_arxiv_id(r.get_short_id())
                if aid in seen:
                    continue
                theme_out["candidates"].append({
                    "arxiv_id": aid,
                    "title": r.title,
                    "abstract": r.summary,
                    "authors": [a.name for a in r.authors],
                    "published": r.published.date().isoformat(),
                    "primary_category": r.primary_category,
                    "link": r.entry_id,
                })
        except Exception as e:  # arxiv.UnexpectedEmptyPageError / HTTPError etc.
            theme_out["error"] = f"{type(e).__name__}: {e}"
        # Set 'new' after the try/except so a partial fetch (exception mid-loop)
        # still reports however many candidates were collected, not 0.
        theme_out["new"] = len(theme_out["candidates"])
        doc["themes"].append(theme_out)

    doc["first_run"] = any_first_run
    return doc


def _run_commit_mode(args, data_dir, config):
    try:
        with open(args.commit, "r", encoding="utf-8") as f:
            scores = json.load(f)
        with (data_dir / "candidates.json").open("r", encoding="utf-8") as f:
            candidates_doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read scores/candidates: {e}", file=sys.stderr)
        return 2
    titles = titles_by_theme(candidates_doc)
    default_thr = effective_threshold({}, config.get("defaults", {}))
    thresholds = thresholds_by_theme(candidates_doc, default_thr)
    appended = commit_scores(scores, titles, thresholds, data_dir, now_local_date())
    print(f"[watch-paper] committed {sum(appended.values())} rows: {appended}",
          file=sys.stderr)
    return 0


def _run_fetch_mode(data_dir, config):
    now_utc = datetime.now(timezone.utc)
    doc = run_fetch(config, data_dir, now_utc)
    out_path = data_dir / "candidates.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    n_new = sum(t.get("new", 0) for t in doc["themes"])
    print(f"[watch-paper] wrote {out_path} ({len(doc['themes'])} themes, {n_new} new)",
          file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="watch-paper arXiv fetch / ledger commit")
    parser.add_argument("--data-dir", default=None,
                        help="data root (default: <cwd>/watch-paper)")
    parser.add_argument("--commit", default=None, metavar="SCORES_JSON",
                        help="commit mode: append evaluated rows from scores.json")
    args = parser.parse_args(argv)

    data_dir = resolve_data_dir(args.data_dir)
    print(f"[watch-paper] data_dir = {data_dir}", file=sys.stderr)
    try:
        (data_dir / "state").mkdir(parents=True, exist_ok=True)
        (data_dir / "digests").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot create data dir: {e}", file=sys.stderr)
        return 2

    try:
        config = load_config(CONFIG_PATH)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read config {CONFIG_PATH}: {e}",
              file=sys.stderr)
        return 2

    if args.commit:
        return _run_commit_mode(args, data_dir, config)
    return _run_fetch_mode(data_dir, config)


if __name__ == "__main__":
    sys.exit(main())
