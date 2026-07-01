#!/usr/bin/env python3
"""watch-paper: append evaluated rows to the per-theme seen-<theme>.csv ledgers.

Input: a scores.json ({theme: {arxiv_id: {"score": int, ...}}}, bare int also
accepted) plus this run's candidates.json. Output: appended ledger rows.
Append-only — run exactly once per run.
"""
import argparse
import csv
import json
import sys

from _common import (config_path, load_config, load_run_inputs,
                     now_local_date, setup_data_dir)

CSV_HEADER = ["arxiv_id", "score", "title", "evaluated", "surfaced"]


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


def _score_of(entry):
    """Accept the enriched dict form ({"score": n, ...}) or a bare int."""
    return entry["score"] if isinstance(entry, dict) else entry


def commit_scores(scores, titles, thresholds, data_dir, evaluated_date):
    """Append evaluated rows to per-theme seen-<id>.csv ledgers.

    scores:     {theme_id: {arxiv_id: {"score": int, ...} | int}}
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
            for arxiv_id, entry in id_scores.items():
                if arxiv_id not in theme_titles:
                    continue
                score = int(_score_of(entry))
                surfaced = "true" if score >= threshold else "false"
                writer.writerow([arxiv_id, score, theme_titles[arxiv_id],
                                 evaluated_date, surfaced])
                n += 1
        appended[theme_id] = n
    return appended


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="watch-paper ledger commit")
    parser.add_argument("scores_json", help="path to scores.json")
    parser.add_argument("--data-dir", default=None,
                        help="data root (default: <cwd>/watch-paper)")
    args = parser.parse_args(argv)

    try:
        data_dir = setup_data_dir(args.data_dir)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot create data dir: {e}", file=sys.stderr)
        return 2

    candidates_doc, scores = load_run_inputs(data_dir, args.scores_json)
    if candidates_doc is None:
        return 2

    default_thr = 3
    cfg_path = config_path(data_dir)
    try:
        config = load_config(cfg_path)
        default_thr = int(config.get("defaults", {}).get("threshold", 3))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] WARN: config not read ({cfg_path}): {e}; "
              f"using default threshold {default_thr}", file=sys.stderr)
    titles = titles_by_theme(candidates_doc)
    thresholds = thresholds_by_theme(candidates_doc, default_thr)
    appended = commit_scores(scores, titles, thresholds, data_dir, now_local_date())
    print(f"[watch-paper] committed {sum(appended.values())} rows: {appended}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
