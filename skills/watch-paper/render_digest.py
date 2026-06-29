#!/usr/bin/env python3
"""watch-paper: render the dated digest from scores.json + candidates.json.

Deterministic join: filter score >= theme threshold, sort score-desc then
published-desc, count evaluated/surfaced, format Markdown. The date (filename,
frontmatter, heading) is derived here via now_local_date(). Idempotent —
overwrites <data_dir>/digests/<today>.md.
"""
import argparse
import sys

from _common import load_run_inputs, now_local_date, setup_data_dir

MAX_AUTHORS = 6


def _format_authors(authors):
    if len(authors) > MAX_AUTHORS:
        return ", ".join(authors[:MAX_AUTHORS]) + ", …"
    return ", ".join(authors)


def _theme_records(theme, theme_scores):
    """Join a theme's candidates with its scores into evaluated records."""
    records = []
    for c in theme.get("candidates", []):
        aid = c.get("arxiv_id")
        entry = theme_scores.get(aid)
        if entry is None:
            continue
        records.append({
            "arxiv_id": aid,
            "title": c.get("title", ""),
            "link": c.get("link", ""),
            "primary_category": c.get("primary_category", ""),
            "published": c.get("published", ""),
            "authors": c.get("authors", []),
            "score": int(entry["score"]),
            "summary_ja": entry.get("summary_ja", ""),
            "why_ja": entry.get("why_ja", ""),
        })
    return records


def _theme_section(theme, records):
    """Return (lines, evaluated, surfaced) for one theme."""
    name = theme.get("name", theme.get("id", ""))
    threshold = int(theme.get("threshold", 3))
    evaluated = len(records)

    surfaced_records = [r for r in records if r["score"] >= threshold]
    # stable two-pass sort: published desc, then score desc (score wins)
    surfaced_records.sort(key=lambda r: r["published"], reverse=True)
    surfaced_records.sort(key=lambda r: r["score"], reverse=True)
    surfaced = len(surfaced_records)

    lines = [f"## {name}  （評価{evaluated} / 抽出{surfaced}）", ""]
    if theme.get("error"):
        lines.append(f"- 取得失敗: {theme['error']}")
        lines.append("")
    elif surfaced == 0:
        lines.append("- 該当なし")
        lines.append("")
    else:
        for r in surfaced_records:
            head = f"⭐{r['score']}" if r["score"] == 5 else str(r["score"])
            lines.append(f"### {head} — [{r['title']}]({r['link']})")
            lines.append(
                f"- arXiv: {r['arxiv_id']} ｜ {r['primary_category']} ｜ {r['published']}")
            lines.append(f"- 著者: {_format_authors(r['authors'])}")
            lines.append(f"- 要約: {r['summary_ja']}")
            lines.append(f"- なぜ気になるか: {r['why_ja']}")
            lines.append("")
    return lines, evaluated, surfaced


def build_digest(candidates_doc, scores, today):
    """Return (markdown_str, [(theme_id, evaluated, surfaced), ...])."""
    theme_meta = []
    body = []
    for theme in candidates_doc.get("themes", []):
        tid = theme.get("id")
        records = _theme_records(theme, scores.get(tid, {}))
        lines, evaluated, surfaced = _theme_section(theme, records)
        theme_meta.append((tid, evaluated, surfaced))
        body.extend(lines)

    fm = ["---", f"generated: {today}", "themes:"]
    for tid, ev, su in theme_meta:
        fm += [f"  - id: {tid}", f"    evaluated: {ev}", f"    surfaced: {su}"]
    fm += ["---", ""]
    header = [f"# 論文ウォッチ {today}", ""]
    md = "\n".join(fm + header + body).rstrip() + "\n"
    return md, theme_meta


def main(argv=None):
    parser = argparse.ArgumentParser(description="watch-paper digest renderer")
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

    today = now_local_date()
    md, theme_meta = build_digest(candidates_doc, scores, today)
    out_path = data_dir / "digests" / f"{today}.md"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(md)

    total_ev = sum(ev for _, ev, _ in theme_meta)
    total_su = sum(su for _, _, su in theme_meta)
    print(f"[watch-paper] rendered {out_path} "
          f"(themes={len(theme_meta)}, evaluated={total_ev}, surfaced={total_su})",
          file=sys.stderr)
    for tid, ev, su in theme_meta:
        print(f"[watch-paper]   {tid}: evaluated={ev} surfaced={su}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
