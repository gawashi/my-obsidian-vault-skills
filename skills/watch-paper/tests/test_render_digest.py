import json

import render_digest as rd


def _doc():
    return {
        "themes": [
            {
                "id": "t1",
                "name": "テーマ1",
                "threshold": 3,
                "new": 3,
                "candidates": [
                    {"arxiv_id": "2406.00001", "title": "Top, Paper",
                     "authors": ["A", "B"], "published": "2026-06-20",
                     "primary_category": "cs.CL",
                     "link": "https://arxiv.org/abs/2406.00001"},
                    {"arxiv_id": "2406.00002", "title": "Mid Paper",
                     "authors": ["C"], "published": "2026-06-25",
                     "primary_category": "cs.LG",
                     "link": "https://arxiv.org/abs/2406.00002"},
                    {"arxiv_id": "2406.00003", "title": "Below Threshold",
                     "authors": ["D"], "published": "2026-06-26",
                     "primary_category": "cs.AI",
                     "link": "https://arxiv.org/abs/2406.00003"},
                ],
            },
            {
                "id": "t2", "name": "テーマ2", "threshold": 3, "new": 0,
                "candidates": [],
            },
        ]
    }


def _scores():
    return {
        "t1": {
            "2406.00001": {"score": 5, "summary_ja": "ようやく", "why_ja": "ど真ん中"},
            "2406.00002": {"score": 4, "summary_ja": "良い", "why_ja": "隣接"},
            "2406.00003": {"score": 1, "summary_ja": "誤ヒット", "why_ja": "無関係"},
        }
    }


def test_counts_and_surfaced():
    md, meta = rd.build_digest(_doc(), _scores(), "2026-06-29")
    assert meta == [("t1", 3, 2), ("t2", 0, 0)]


def test_frontmatter_lists_themes():
    md, _ = rd.build_digest(_doc(), _scores(), "2026-06-29")
    assert md.startswith("---\n")
    assert "generated: 2026-06-29" in md
    assert "  - id: t1\n    evaluated: 3\n    surfaced: 2" in md
    assert "  - id: t2\n    evaluated: 0\n    surfaced: 0" in md


def test_heading_and_star_prefix_and_order():
    md, _ = rd.build_digest(_doc(), _scores(), "2026-06-29")
    # surfaced sorted score-desc: score 5 (⭐) before score 4
    i5 = md.index("### ⭐5 — [Top, Paper](https://arxiv.org/abs/2406.00001)")
    i4 = md.index("### 4 — [Mid Paper](https://arxiv.org/abs/2406.00002)")
    assert i5 < i4
    # below-threshold paper is not surfaced
    assert "Below Threshold" not in md


def test_meta_lines_use_fullwidth_separator():
    md, _ = rd.build_digest(_doc(), _scores(), "2026-06-29")
    assert "- arXiv: 2406.00001 ｜ cs.CL ｜ 2026-06-20" in md
    assert "- 要約: ようやく" in md
    assert "- なぜ気になるか: ど真ん中" in md


def test_empty_theme_shows_nashi():
    md, _ = rd.build_digest(_doc(), _scores(), "2026-06-29")
    assert "## テーマ2  （評価0 / 抽出0）" in md
    # the t2 section body is 該当なし
    t2 = md[md.index("## テーマ2"):]
    assert "- 該当なし" in t2


def test_all_below_threshold_shows_nashi():
    doc = _doc()
    scores = {"t1": {"2406.00003": {"score": 1, "summary_ja": "x", "why_ja": "y"}}}
    md, meta = rd.build_digest(doc, scores, "2026-06-29")
    # only one evaluated, zero surfaced -> 該当なし in t1
    assert meta[0] == ("t1", 1, 0)
    t1 = md[md.index("## テーマ1"):md.index("## テーマ2")]
    assert "- 該当なし" in t1


def test_fetch_error_theme_reports_error():
    doc = {"themes": [
        {"id": "t1", "name": "テーマ1", "threshold": 3,
         "error": "HTTPError: 503", "candidates": []}
    ]}
    md, meta = rd.build_digest(doc, {}, "2026-06-29")
    assert meta == [("t1", 0, 0)]
    assert "- 取得失敗: HTTPError: 503" in md


def test_authors_truncated_past_max():
    doc = _doc()
    doc["themes"][0]["candidates"][0]["authors"] = [f"A{i}" for i in range(10)]
    md, _ = rd.build_digest(doc, _scores(), "2026-06-29")
    # first MAX_AUTHORS shown, then an ellipsis
    assert "- 著者: A0, A1, A2, A3, A4, A5, …" in md


def test_main_writes_digest_file(tmp_path):
    data_dir = tmp_path / "watch-paper"
    (data_dir / "digests").mkdir(parents=True)
    (data_dir / "candidates.json").write_text(
        json.dumps(_doc(), ensure_ascii=False), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps(_scores(), ensure_ascii=False), encoding="utf-8")

    rc = rd.main(["--data-dir", str(data_dir), str(scores_path)])
    assert rc == 0
    digests = list((data_dir / "digests").glob("*.md"))
    assert len(digests) == 1
    text = digests[0].read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "# 論文ウォッチ " in text
    assert "### ⭐5 — [Top, Paper]" in text
