# watch-paper スキル Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** arXiv の新着論文を `config.json` の複数テーマごとに定点観測し、LLM が関連度（0〜5）でスコアリングして閾値以上を日付付きダイジェストに抽出、評価済みは合否問わずテーマ別 CSV 台帳に記録する Claude Code スキル `watch-paper` を作る。

**Architecture:** 2段構え。決定的な取得・台帳書き込みは Python `fetch_arxiv.py`（`uv run` で vault の uv プロジェクト env 上で実行、arXiv 公式ラッパー `arxiv` ライブラリ使用）が担い、関連度判定・要約・ダイジェスト整形は LLM（`SKILL.md` の手順）が担う。`fetch_arxiv.py` は2モード — 既定=取得（→`candidates.json`）、`--commit`=評価後のスコアを受けて `seen-<theme>.csv` に追記。ランタイムデータは実行時 CWD（=vault ルート）配下 `watch-paper/` に解決し、設定に絶対パスを焼き込まない。

**Tech Stack:** Claude Code skill（`SKILL.md` 手順書）＋ Python 3.13（stdlib `csv`/`json`/`argparse`/`datetime`/`pathlib` ＋ `arxiv` ライブラリ）、`uv` 実行、Obsidian（ダイジェスト閲覧）。ロジックのテストは `pytest`。

## Global Constraints

- 設計の正本は `docs/specs/2026-06-28-paper-watch-skill-design.md`。本計画はその spec を実装する。受け入れ基準は spec §6。
- **2つの場所を扱う**:
  - **スキルリポジトリ（git管理）**: `C:\Users\010230240\work\my-obsidian-vault-skills`。`skills/watch-paper/`（`SKILL.md`/`fetch_arxiv.py`/`config.json`/`README.md`）・`tests/watch-paper/`・`docs/`・`skills/SOURCES.md` はここ。全 git 操作はこのリポジトリで行う。
  - **vault（uv プロジェクト・ランタイムデータ。git 非管理）**: `C:\Users\010230240\OneDrive - OMRON\ドキュメント\Obsidian\My vault`。`pyproject.toml`(`name=my-vault`, `requires-python>=3.13`, deps 空)・`uv.lock`・`.python-version`(3.13) がある。`arxiv` 依存はここに追加。ランタイムデータ `watch-paper/` もここに生成。
- **データrootの解決**: `config.json` に絶対パスを持たない。`fetch_arxiv.py` は既定で `Path.cwd()/"watch-paper"` を使い（CWD=vault ルート）、任意で `--data-dir <path>` で上書き。`config.json` は常に `Path(__file__).parent/"config.json"`（スクリプト自身の隣）から読む。
- **CSV 台帳**: `state/seen-<theme-id>.csv`、列 `arxiv_id,score,title,evaluated,surfaced`（ヘッダ付き・追記専用）。Python `csv` モジュール（`QUOTE_MINIMAL`/`newline=''`/UTF-8）で**決定的に書く**。LLM は `{theme-id:{arxiv_id:score}}` の対応表だけ出力。重複排除キーは `arxiv_id`（base ID、`vN` 接尾辞を除く）。`surfaced`=`score≥threshold`、`evaluated`=実行日。
- **厳密 JSON**: `config.json` はコメント・末尾カンマ不可（`json.load` がそのまま読める）。
- **arXiv lazy import**: `import arxiv` は `run_fetch()` 内でのみ行う。これにより `arxiv` 未導入でも純粋ヘルパーを `pytest` で検証できる。
- **日付ハードコード禁止**: ダイジェストのファイル名・`generated` は実行日を動的取得。スクリプトの cutoff は `datetime`(UTC) で算出。CSV の `evaluated` は実行日。
- **wiki 非干渉**: `wiki/`・`raw/`・`schema.md` を読み書きしない。
- **テスト実行コマンド**（スキルリポジトリルートから）:
  `uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v`
  （`--with pytest` でエフェメラルに pytest を導入。初回のみ pytest 取得にネットが要る＝以降は uv キャッシュからオフラインで走る。テスト対象コードは `arxiv` を lazy import するので arxiv は不要。）
- **ネットワーク**: ユニットテストは pytest の初回取得時のみネットを要する（以降キャッシュ）。`uv add arxiv` と live な arXiv 取得（Task 7）はネット必須。サンドボックスでネット不可なら、テスト実行と Task 7 はユーザーがネット可能な端末で実行する（`!` プレフィックスでこのセッションから依頼も可）。
- **git コミット**: 全コミットはスキルリポジトリで行う。最初のコミット前に、リポジトリがデフォルトブランチ（`main`/`master`）にいれば `feat/watch-paper` を切る。コミットメッセージ末尾に必ず:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: テーマ定義 `config.json` ＋ リポジトリ初期整備

**Files:**
- Create: `skills/watch-paper/config.json`
- Modify: `skills/SOURCES.md`（`watch-paper` 行を追加）
- Commit対象に含める: `docs/specs/2026-06-28-paper-watch-skill-design.md`, `docs/plans/2026-06-28-watch-paper-skill.md`

**Interfaces:**
- Produces: `config.json` — top-level `defaults`(`categories`/`threshold`/`lookback_days`/`first_run_lookback_days`/`max_results`/`request_delay_seconds`) ＋ `themes[]`（各 `id`/`name`/`enabled`/`keywords`/`anchors`、任意で `categories`/`threshold`）。後続タスクの `fetch_arxiv.py` がこのキー構造を読む。
- Consumes: なし（新規）。

- [ ] **Step 1: 必要ならブランチを切る**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git branch --show-current
# main / master なら:
git switch -c feat/watch-paper
```

- [ ] **Step 2: `config.json` を作成する**

ファイル `skills/watch-paper/config.json`:

```json
{
  "defaults": {
    "categories": ["cs.AI", "cs.CL", "cs.LG", "cs.MA"],
    "threshold": 3,
    "lookback_days": 7,
    "first_run_lookback_days": 30,
    "max_results": 120,
    "request_delay_seconds": 3
  },
  "themes": [
    {
      "id": "auto-sci-discovery",
      "name": "科学的発見の自動化",
      "enabled": true,
      "keywords": [
        "automated scientific discovery",
        "AI scientist",
        "AI co-scientist",
        "research agent",
        "research idea generation",
        "research ideation",
        "hypothesis generation",
        "autonomous research",
        "automated experimentation"
      ],
      "anchors": [
        "ResearchAgent (Baek et al.)",
        "The AI Scientist (Sakana AI)",
        "AI Co-Scientist (Google)",
        "SciAgents",
        "Agent Laboratory"
      ]
    },
    {
      "id": "industrial-anomaly-detection",
      "name": "産業異常検知",
      "enabled": false,
      "keywords": [
        "industrial anomaly detection",
        "surface defect detection",
        "zero-shot anomaly detection",
        "few-shot anomaly detection"
      ],
      "anchors": ["PatchCore", "SimpleNet", "DRAEM", "AnomalyCLIP"],
      "categories": ["cs.CV"]
    }
  ]
}
```

- [ ] **Step 3: JSON が厳密に読めることを検証する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --python 3.13 python -c "import json,sys; d=json.load(open('skills/watch-paper/config.json',encoding='utf-8')); assert d['defaults']['threshold']==3; assert [t['id'] for t in d['themes']]==['auto-sci-discovery','industrial-anomaly-detection']; assert d['themes'][0]['enabled'] is True and d['themes'][1]['enabled'] is False; print('config.json OK')"
```
Expected: `config.json OK`（例外・`JSONDecodeError` が出ないこと）

- [ ] **Step 4: `skills/SOURCES.md` に行を追加する**

`skills/SOURCES.md` の表（`| new-project | ... |` 行の下）に次の行を追加:

```
| watch-paper | self-authored                                  | -      | 2026-06-28 | Original. arXiv 新着をテーマ別に定点観測しダイジェスト抽出（wiki とは完全分離）。決定的取得＋台帳は `fetch_arxiv.py`（uv 実行・`arxiv` ライブラリ）、関連度判定は LLM。Design: `docs/specs/2026-06-28-paper-watch-skill-design.md`, plan: `docs/plans/2026-06-28-watch-paper-skill.md` |
```

- [ ] **Step 5: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/config.json skills/SOURCES.md docs/specs/2026-06-28-paper-watch-skill-design.md docs/plans/2026-06-28-watch-paper-skill.md
git commit -m "feat(watch-paper): add theme config + design spec/plan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `fetch_arxiv.py` — 純粋ヘルパー（取得ロジックの骨格）

**Files:**
- Create: `skills/watch-paper/fetch_arxiv.py`
- Create: `tests/watch-paper/conftest.py`（`fetch_arxiv` を import 可能にする sys.path シム）
- Create: `tests/watch-paper/test_fetch_arxiv.py`

**Interfaces:**
- Produces:
  - `base_arxiv_id(short_id: str) -> str`
  - `effective_categories(theme: dict, defaults: dict) -> list`
  - `effective_threshold(theme: dict, defaults: dict) -> int`
  - `build_query(keywords: list, categories: list) -> str`
  - `lookback_days(ledger_empty: bool, defaults: dict) -> int`
  - `cutoff_datetime(now_utc: datetime, days: int) -> datetime`
  - `resolve_data_dir(arg_data_dir: str | None) -> Path`
  - `read_seen_ids(csv_path: Path) -> set`
  - モジュール定数 `CONFIG_PATH = Path(__file__).parent/"config.json"`、`CSV_HEADER = ["arxiv_id","score","title","evaluated","surfaced"]`
- Consumes: Task 1 の `config.json` キー構造。

- [ ] **Step 1: pytest の sys.path シム（conftest.py）を作る**

ファイル `tests/watch-paper/conftest.py`:

```python
import sys
from pathlib import Path

# tests/watch-paper/ から見て ../../skills/watch-paper を import パスに追加（CWD 非依存）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "watch-paper"))
```

- [ ] **Step 2: 失敗するテストを書く**

ファイル `tests/watch-paper/test_fetch_arxiv.py`:

```python
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
```

- [ ] **Step 3: テストが失敗することを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: 収集エラー — `ModuleNotFoundError: No module named 'fetch_arxiv'`（まだ作っていない）

- [ ] **Step 4: `fetch_arxiv.py` を純粋ヘルパーまで実装する**

ファイル `skills/watch-paper/fetch_arxiv.py`:

```python
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
```

- [ ] **Step 5: テストが通ることを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: PASS（純粋ヘルパーの全ケース緑）

- [ ] **Step 6: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/fetch_arxiv.py tests/watch-paper/conftest.py tests/watch-paper/test_fetch_arxiv.py
git commit -m "feat(watch-paper): add fetch_arxiv pure helpers + pytest suite

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `fetch_arxiv.py` — 台帳コミットロジック

**Files:**
- Modify: `skills/watch-paper/fetch_arxiv.py`（Task 2 の純粋ヘルパーの**下に**追記）
- Modify: `tests/watch-paper/test_fetch_arxiv.py`（コミット系テストを末尾に追記）

**Interfaces:**
- Consumes: Task 2 の `CSV_HEADER`、`read_seen_ids`。
- Produces:
  - `titles_by_theme(candidates_doc: dict) -> dict`（`{theme_id: {arxiv_id: title}}`）
  - `thresholds_by_theme(candidates_doc: dict, default_threshold: int = 3) -> dict`（`{theme_id: int}`）
  - `commit_scores(scores: dict, titles: dict, thresholds: dict, data_dir: Path, evaluated_date: str) -> dict`
    - `scores`=`{theme_id:{arxiv_id:score}}`、戻り値=`{theme_id: rows_appended}`。`titles` に無い `arxiv_id` は無視。`<data_dir>/state/seen-<theme>.csv` に追記（無ければヘッダ行を先に書く）。

- [ ] **Step 1: 失敗するテストを末尾に追記する**

`tests/watch-paper/test_fetch_arxiv.py` の**末尾**に追加:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: FAIL — `AttributeError: module 'fetch_arxiv' has no attribute 'titles_by_theme'`（新規4テストが赤、既存は緑）

- [ ] **Step 3: コミットロジックを実装する**

`skills/watch-paper/fetch_arxiv.py` の `read_seen_ids` 関数の**下に**追記:

```python
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: PASS（純粋ヘルパー ＋ コミット系 全緑）

- [ ] **Step 5: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/fetch_arxiv.py tests/watch-paper/test_fetch_arxiv.py
git commit -m "feat(watch-paper): add deterministic CSV ledger commit logic + tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `fetch_arxiv.py` — 取得オーケストレーション ＋ CLI（2モード）

**Files:**
- Modify: `skills/watch-paper/fetch_arxiv.py`（`commit_scores` の下に追記）
- Modify: `tests/watch-paper/test_fetch_arxiv.py`（CLI コミットモードのテストを末尾に追記）

**Interfaces:**
- Consumes: Task 2/3 の全ヘルパー（`read_seen_ids`/`build_query`/`base_arxiv_id`/`cutoff_datetime`/`lookback_days`/`effective_*`/`resolve_data_dir`/`titles_by_theme`/`thresholds_by_theme`/`commit_scores`）、`CONFIG_PATH`。
- Produces:
  - `load_config(path: Path) -> dict`
  - `now_local_date() -> str`（`YYYY-MM-DD`）
  - `run_fetch(config: dict, data_dir: Path, now_utc: datetime) -> dict`（`candidates.json` ドキュメントを返す。`import arxiv` はこの中・ネットを叩く）
  - `main(argv=None) -> int`（CLI: `--data-dir` / `--commit`。取得モードは `candidates.json` を書く、コミットモードは `seen-*.csv` を書く。`config` 読込・データroot 作成の致命的失敗は 2、正常 0）
- `candidates.json` 形式: `{"generated":ISO,"first_run":bool,"themes":[{"id","name","threshold","anchors","fetched","new","candidates":[{"arxiv_id","title","abstract","authors","published","primary_category","link"}],("error")}]}`。

- [ ] **Step 1: 失敗するテスト（CLI コミットモード・オフライン）を末尾に追記する**

`tests/watch-paper/test_fetch_arxiv.py` の**末尾**に追加:

```python
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
```

> 注: このテストは `main` が `CONFIG_PATH`（実 `config.json`）を読む。Task 1 で作成済みのため通る。`--commit` 経路は `run_fetch`（＝`import arxiv`）を呼ばないのでネット不要。

- [ ] **Step 2: テストが失敗することを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: FAIL — `AttributeError: module 'fetch_arxiv' has no attribute 'main'`

- [ ] **Step 3: 取得＋CLI を実装する**

`skills/watch-paper/fetch_arxiv.py` の `commit_scores` の**下に**追記:

```python
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
            theme_out["new"] = len(theme_out["candidates"])
        except Exception as e:  # arxiv.UnexpectedEmptyPageError / HTTPError etc.
            theme_out["error"] = f"{type(e).__name__}: {e}"
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
```
Expected: PASS（純粋ヘルパー ＋ コミット系 ＋ CLI コミットモード 全緑）

- [ ] **Step 5: import の健全性を確認する（arxiv 未導入でも import できること）**

Run:
```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
uv run --no-project --python 3.13 python -c "import sys; sys.path.insert(0,'skills/watch-paper'); import fetch_arxiv; print('import OK; lazy arxiv:', 'arxiv' not in sys.modules)"
```
Expected: `import OK; lazy arxiv: True`（モジュール読込時点で `arxiv` を import していない＝lazy が効いている）

- [ ] **Step 6: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/fetch_arxiv.py tests/watch-paper/test_fetch_arxiv.py
git commit -m "feat(watch-paper): add fetch orchestration + two-mode CLI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: スキル本体 `SKILL.md`

**Files:**
- Create: `skills/watch-paper/SKILL.md`

**Interfaces:**
- Consumes: `fetch_arxiv.py`（取得モード／`--commit` モード）、`candidates.json` 形式（Task 4）、`config.json` の `threshold`/`anchors`。
- Produces: スキル `watch-paper`（`/watch-paper` 起動）。LLM が辿る手順書: 取得 → 0〜5 採点 → 抽出 → `digests/YYYY-MM-DD.md` 生成 → `scores.json` 書出し＋ `--commit` → 報告。

- [ ] **Step 1: `SKILL.md` を作成する**

ファイル `skills/watch-paper/SKILL.md`:

````markdown
---
name: watch-paper
description: arXiv の新着論文を config.json の複数テーマごとに定点観測し、関連度（0〜5）でスコアリングして閾値以上を日付付きダイジェストに抽出する。評価済み論文は合否問わずテーマ別 CSV 台帳に記録し再評価しない。wiki への Ingest はしない（ユーザー手動）。Use when the user wants to watch or track new papers, asks 論文ウォッチ／新着論文を調べて／定点観測／arXiv の新着／watch papers, or invokes /watch-paper.
---

# watch-paper

arXiv の新着を `config.json` のテーマごとに集め、関連度でスコアリングして「ダイジェスト」に抽出する定点観測スキル。決定的な取得・台帳更新は `fetch_arxiv.py`（`uv run`）が担い、関連度判定・要約は LLM（この手順）が担う。設計の正本はスキルリポジトリの `docs/specs/2026-06-28-paper-watch-skill-design.md`。

**責務の境界**: ダイジェスト生成までが責務。`wiki/`・`raw/`・`schema.md` は読み書きしない（Ingest はユーザーが Obsidian で手動）。

## 前提

- このスキルは **vault ルートで起動した Claude**（CWD = vault ルート）で実行する。ランタイムデータは CWD 配下 `watch-paper/` に書かれる。
- `fetch_arxiv.py` と `config.json` は**このスキル自身のディレクトリ**（起動時に表示されるスキルのベースディレクトリ）にある。以下 `<skill-dir>` と表記し、実行時の絶対パスを使う。
- 実行には `uv` と `arxiv` ライブラリが要る（`uv run` が vault の uv プロジェクト env を自動 sync する。初回は `arxiv` の install が走る）。

## 1. 取得（fetch モード）

- CWD が vault ルートであることを確認する（`pwd`）。実行日を取得する（`date +%F`。**ハードコードしない**）。
- 取得スクリプトを実行する:

  ```
  uv run --project . "<skill-dir>/fetch_arxiv.py"
  ```

  （`--project .` は CWD=vault の uv プロジェクト。`<skill-dir>` はこのスキルのベースディレクトリの絶対パス。）
- stderr に `[watch-paper] data_dir = ...` が出る。これが **vault ルート配下 `watch-paper/`** を指していることを確認する。別の場所を指していたら CWD が誤り → vault ルートで実行し直す。
- 非0終了・権限拒否・実行不能なら、stderr の理由を添えて**中止**する。
- 生成された `watch-paper/candidates.json` を読む。

## 2. スコアリング（テーマごと）

`candidates.json` の各テーマについて、`candidates[]` の各論文を採点する。`new` が 0 のテーマは「該当なし」として扱う（手順4でダイジェストに残す）。

各候補に対し、そのテーマの `anchors`（同種の仕事の代表例）を基準に **0〜5** を付ける:

- **5**: ど真ん中。アンカーと同種のシステム/手法/問題設定。
- **4**: 強く関連。隣接サブ問題・主要構成要素・明確な発展。
- **3**: 関連あり。応用・部分的に主題を扱う（**採用閾値の既定**）。
- **2**: 周辺。キーワードは当たるが主題が異なる。
- **0–1**: 無関係。キーワードの誤ヒット。

各候補に「一言要約（日本語1〜2文）」と「なぜ気になるか（1行）」を付ける。**アブスト（`abstract`）の範囲で書き、性能数値や主張を捏造しない。**

## 3. 抽出

各テーマの `threshold`（`candidates.json` の各テーマに格納済み）**以上**のみ採用し、スコア降順に並べる。

## 4. ダイジェストを書く

`watch-paper/digests/<実行日>.md` を次の書式で生成する。**同名ファイルが既にあれば上書き前に確認する**（再実行時の二重生成防止）。`evaluated`=そのテーマで採点した件数、`surfaced`=閾値以上で抽出した件数。

```markdown
---
generated: <実行日 YYYY-MM-DD>
themes:
  - id: auto-sci-discovery
    evaluated: 12
    surfaced: 4
---

# 論文ウォッチ <実行日>

## 科学的発見の自動化  （評価12 / 抽出4）

### ⭐5 — [Title here](https://arxiv.org/abs/2406.xxxxx)
- arXiv: 2406.xxxxx ｜ cs.CL ｜ 2026-06-25
- 著者: A. Author, B. Author, …
- 要約: 〜（日本語1〜2文）
- なぜ気になるか: 〜（1行）

### 4 — [Another Title](https://arxiv.org/abs/2406.yyyyy)
- …

## 産業異常検知  （評価0 / 抽出0）
- 該当なし
```

- テーマは `candidates.json` の順に1セクション。各セクションはスコア降順。
- `arXiv`/`カテゴリ`/`投稿日` は候補の `arxiv_id`/`primary_category`/`published`、リンクは `link`、著者は `authors` から。
- 取得失敗テーマ（候補に `error` あり）は「取得失敗: <error>」と明記する。

## 5. 台帳にコミット（commit モード）

評価したスコアを対応表 `{ "<theme-id>": { "<arxiv_id>": <score 0-5> } }` として `watch-paper/scores.json` に書き出す（合否問わず**採点した全件**を含める）。次にコミットを実行する:

```
uv run --project . "<skill-dir>/fetch_arxiv.py" --commit "watch-paper/scores.json"
```

これで各テーマの `watch-paper/state/seen-<theme-id>.csv` に `arxiv_id,score,title,evaluated,surfaced` が追記される（surfaced=score≥threshold、evaluated=実行日）。CSV はスクリプトが決定的に書くので、タイトルのカンマ等で壊れない。`candidates.json` に無い ID は無視される。

## 6. 報告

- テーマごとの「評価件数 / 抽出件数」。
- 各テーマの上位ピック（タイトル＋スコア）を数件。
- 生成したダイジェストのパス（`watch-paper/digests/<実行日>.md`）。
- スキップ/エラー（取得失敗テーマ、権限拒否等）。
- 初回実行（台帳が空だった）なら、遡及が `first_run_lookback_days`（30日）に絞られた旨と抽出が多めになりうる旨。

## ガードレール

- `wiki/`・`raw/`・`schema.md` を読み書きしない。
- 要約・「なぜ気になるか」はアブストの範囲で書く。アブストに無い性能数値・主張を足さない。
- 日付はハードコードしない（実行日を `date +%F` で取得）。
- 台帳 CSV は **`--commit` 経由でのみ**更新する（手で行を書き換えない／追記専用）。AIが誤って弾いた論文を拾い直したいときは、その行を手で削除すれば次回再評価される。
- ランタイムデータは CWD（=vault ルート）配下 `watch-paper/` にのみ書く。スキルフォルダには書かない。
- 取得に失敗したテーマがあっても中止せず、他テーマを続行・報告する（スクリプトがテーマ単位でエラーを `candidates.json` に載せる）。
- 同テーマ・複数テーマに該当する論文は、各テーマのセクションに重複して載りうる（仕様）。

See `README.md`（このファイルの隣）for 前提（uv/arxiv 依存）・生成ファイル一覧・OneDrive 同期の注意。
````

- [ ] **Step 2: spec の受け入れ基準と突き合わせる**

`SKILL.md` を読み返し、spec §6 と照合（ズレがあれば Step 1 を直す）:
- frontmatter `name: watch-paper` と起動意図を含む `description` がある。
- 手順が「取得 → 0〜5 採点 → 閾値抽出 → digests/YYYY-MM-DD.md 生成 → scores.json + `--commit` → 報告」を網羅（AC1–4, 7）。
- 採点ルーブリック（0〜5、閾値3）が spec §4.5 と一致（AC2）。
- ダイジェスト書式が spec §4.6 と一致（frontmatter evaluated/surfaced、テーマ別・スコア降順、new=0 は「該当なし」）（AC3）。
- 台帳更新は `--commit` 経由（CSV 5列）、合否問わず全件（AC4）。
- 取得失敗テーマでも継続・報告（AC6）。
- ランタイムデータは CWD 配下 `watch-paper/` のみ、wiki 非干渉（AC8）。
- 日付ハードコード禁止・捏造防止のガードレール。

- [ ] **Step 3: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/SKILL.md
git commit -m "feat(watch-paper): add SKILL.md skill procedure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `README.md`（前提・生成ファイル・運用）

**Files:**
- Create: `skills/watch-paper/README.md`

**Interfaces:**
- Consumes: なし（ドキュメント）。spec §6 AC9 を満たす。
- Produces: 手動実行手順・前提（uv/arxiv 依存・CWD=vault・OneDrive 同期の注意）・生成ファイル一覧・開発（テスト実行）の README。

- [ ] **Step 1: `README.md` を作成する**

ファイル `skills/watch-paper/README.md`:

````markdown
# watch-paper — README

arXiv の新着論文をテーマ別に定点観測し、関連度ダイジェストを生成する Claude Code スキル。

## これは何か / 何でないか

- **やること**: テーマ定義（`config.json`）に基づき arXiv 新着を取得 → LLM が 0〜5 で関連度採点 → 閾値以上を `watch-paper/digests/YYYY-MM-DD.md` に抽出。評価済みは合否問わず `watch-paper/state/seen-<theme>.csv` に記録。
- **やらないこと**: `wiki/` への Ingest・通知・スケジューラ連携・arXiv 以外の取得元（v1 スコープ外）。Ingest は Obsidian でダイジェストを見て手動で行う。

## 前提

- `uv`（Astral）がインストール済み。
- vault が uv プロジェクト（`pyproject.toml`、`requires-python >=3.13`）であること。依存 `arxiv` を追加する: **vault ルートで** `uv add arxiv`（初回のみ。以後 `uv run` が自動 sync）。
- このスキルは **vault ルートで起動した Claude** で実行する（ランタイムデータは CWD 配下 `watch-paper/` に書かれる）。

## 手動実行

1. Claude を vault ルートで起動する。
2. `/watch-paper` を実行（または「新着論文を調べて」等）。
3. 生成された `watch-paper/digests/YYYY-MM-DD.md` を Obsidian で開く。

スクリプト単体の動作確認（任意・取得のみ。`<skill-dir>` はこのスキルの絶対パス）:

```
uv run --project . "<skill-dir>/fetch_arxiv.py"        # 取得 → watch-paper/candidates.json
```

## 生成されるファイル（すべて vault ルート配下 `watch-paper/`）

| ファイル | 性質 |
|---|---|
| `candidates.json` | 一時（毎回上書き）。取得結果 |
| `scores.json` | 一時（毎回上書き）。LLM→commit のスコア対応表 |
| `state/seen-<theme>.csv` | 永続・追記専用。評価台帳（弾いた論文もタイトル・スコア付きで残る）。列 `arxiv_id,score,title,evaluated,surfaced` |
| `digests/YYYY-MM-DD.md` | 永続。ダイジェスト本体 |

スキル本体（`SKILL.md`/`fetch_arxiv.py`/`config.json`/`README.md`）は仕組みであり、実行では生成・変更されない。

## テーマの編集

`config.json` の `themes[]` を編集する（**厳密 JSON**、コメント・末尾カンマ不可）。

- `enabled: false` のテーマはスキップ。
- `categories: []`（空配列）でカテゴリ絞りを無効化（キーワードのみで検索）。未指定なら `defaults.categories` を継承。cs 外（`physics.chem-ph`/`q-bio`/`eess`/`stat.ML` 等）を拾いたければテーマの `categories` に足す。
- `keywords` はアブスト検索（`abs:`、フレーズ）。`anchors` は関連度判定の基準（クエリには使わない）。
- `threshold` をテーマ単位で上書き可（未指定なら `defaults.threshold`=3）。

## OneDrive 同期の注意

`watch-paper/` は OneDrive 配下になりうる。CSV 台帳は追記専用なので通常は安全だが、複数端末で同時実行すると競合コピーが生じうる。競合時は手で 1 本にマージする（行の重複は `arxiv_id` で判断）。AIが誤って弾いた論文を拾い直したいときは、`state/seen-<theme>.csv` の該当行を削除すれば次回実行で再評価される。

## 開発

- 設計の正本: スキルリポジトリの `docs/specs/2026-06-28-paper-watch-skill-design.md`
- 実装計画: `docs/plans/2026-06-28-watch-paper-skill.md`
- ロジックのテスト（スキルリポジトリルートから・pytest をエフェメラルに導入）:

  ```
  uv run --no-project --with pytest --python 3.13 pytest tests/watch-paper -v
  ```
````

- [ ] **Step 2: コミット**

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add skills/watch-paper/README.md
git commit -m "docs(watch-paper): add README (prereqs, generated files, ops)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: エンドツーエンド検証（ネット必須・実 arXiv で1回まわす）

> **ネットワーク必須**: このタスクは `uv add arxiv` と arXiv API アクセスを行う。サンドボックスでネット不可なら、ユーザーにネット可能な端末で実行してもらう（`!` プレフィックスでこのセッションから実行依頼も可）。前タスクまでのユニットテスト済みコアは既にコミット済み。

**Files:**
- Modify（vault・git 非管理）: `pyproject.toml` ＋ `uv.lock`（`uv add arxiv`）
- 一時生成（検証後に判断）: vault の `watch-paper/candidates.json` / `scores.json` / `state/seen-*.csv` / `digests/<実行日>.md`

**Interfaces:**
- Consumes: 完成した `fetch_arxiv.py` / `config.json` / `SKILL.md`。
- Produces: 実データでの動作確認。必要ならスキルの修正。

- [ ] **Step 1: vault に `arxiv` を追加する**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
uv add arxiv
uv run python -c "import arxiv; print('arxiv', arxiv.__version__)"
```
Expected: `pyproject.toml` の `dependencies` に `arxiv` が入り、バージョンが表示される。

- [ ] **Step 2: 取得モードを実 arXiv に対して実行する**

`<skill-dir>` はインストール済みプラグインの `skills/watch-paper` 絶対パス（開発リポジトリなら `C:/Users/010230240/work/my-obsidian-vault-skills/skills/watch-paper`）。

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
uv run --project . "<skill-dir>/fetch_arxiv.py"
echo "--- exit: $? ---"
```
Expected:
- stderr に `[watch-paper] data_dir = .../My vault/watch-paper` と `wrote .../candidates.json (N themes, M new)`。
- exit 0。
- `enabled:false` の `industrial-anomaly-detection` は処理されず、`auto-sci-discovery` のみ `candidates.json` に出る。

- [ ] **Step 3: `candidates.json` を検証する**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
uv run --no-project --python 3.13 python -c "import json; d=json.load(open('watch-paper/candidates.json',encoding='utf-8')); t=d['themes'][0]; print('first_run=',d['first_run'],'theme=',t['id'],'fetched=',t['fetched'],'new=',t['new']); c=(t['candidates'][0] if t['candidates'] else {}); print('keys=',sorted(c.keys())); print('id=',c.get('arxiv_id'),'cat=',c.get('primary_category'))"
```
Expected（候補が1件以上ある場合）:
- `first_run= True`（初回。台帳が空のため）。
- `keys=` に `['abstract','arxiv_id','authors','link','primary_category','published','title']`。
- `arxiv_id` に `vN` 接尾辞が無い（base ID）。

> 候補が 0 件でも異常ではない（その週に該当が無いだけ）。その場合は Step 4 を「該当なし」ダイジェストで通し、Step 5 のコミット検証は手元で作った小さな `scores.json`（`candidates.json` 内の実 ID 1件）で代替する。

- [ ] **Step 4: SKILL.md の手順どおりに採点 → ダイジェスト生成**

`SKILL.md` の手順 2–4 を実行する（このセッションの LLM が採点）:
- `candidates.json` の各候補を 0〜5 で採点し、要約・「なぜ気になるか」を付ける。
- 閾値（テーマの `threshold`=3）以上を抽出、スコア降順。
- `watch-paper/digests/<実行日>.md` を spec §4.6 書式で生成（実行日は `date +%F`）。

検証:
```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
ls -la watch-paper/digests/
head -30 "watch-paper/digests/$(date +%F).md"
```
Expected: frontmatter に `generated` とテーマ別 `evaluated`/`surfaced`、本文がテーマ別セクション・スコア降順。new=0 のテーマは「該当なし」。

- [ ] **Step 5: commit モードで台帳に追記し検証**

`SKILL.md` の手順5どおり、採点した全件を `watch-paper/scores.json` に書き出してからコミット:

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
uv run --project . "<skill-dir>/fetch_arxiv.py" --commit "watch-paper/scores.json"
echo "--- exit: $? ---"
echo "--- seen-auto-sci-discovery.csv (head) ---"
head -5 "watch-paper/state/seen-auto-sci-discovery.csv"
```
Expected:
- exit 0、stderr に `committed N rows`。
- CSV 1行目が `arxiv_id,score,title,evaluated,surfaced`。
- 採点した全件（合否問わず）が行として入り、`surfaced` が score≥3 で `true`/`false`。タイトルにカンマを含む行も壊れていない。

- [ ] **Step 6: 再実行で重複排除を確認**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
uv run --project . "<skill-dir>/fetch_arxiv.py"
uv run --no-project --python 3.13 python -c "import json; d=json.load(open('watch-paper/candidates.json',encoding='utf-8')); t=d['themes'][0]; print('first_run=',d['first_run'],'new=',t['new'])"
```
Expected: `first_run= False`（台帳が埋まった）。`new` が前回評価済み分だけ減る（直近で同じ候補が出れば `new=0` もありうる）。前回採点した ID が再び候補に出ないこと＝再評価されないことを確認。

- [ ] **Step 7: 受け入れ基準の最終チェックと修正**

spec §6 の AC1–9 を実データで確認する。特に:
- AC5: 初回 `first_run=True` で遡及が `first_run_lookback_days`(30) に絞られた（Step 3 で確認済み）。
- AC8: 生成物が vault の `watch-paper/` 配下にのみあり、`<skill-dir>`（スキルフォルダ）には何も書かれていない:
  ```bash
  ls "<skill-dir>"   # SKILL.md / fetch_arxiv.py / config.json / README.md のみ
  ```
- AC6: 取得失敗テーマがあっても他テーマが続行（任意・確認できれば）。

ズレがあれば該当タスクのファイルを直し、`tests/watch-paper` を再実行（`uv run --no-project --with pytest ...`）→ 必要な Step をやり直す。修正をコミット:

```bash
cd "C:/Users/010230240/work/my-obsidian-vault-skills"
git add -A skills/watch-paper tests/watch-paper
git commit -m "fix(watch-paper): adjust per end-to-end verification

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: ユーザーへ報告**

- 生成したダイジェストのパスを伝え、Obsidian で開くよう促す。
- `state/seen-auto-sci-discovery.csv` を Obsidian/Excel で開けば「弾いた論文」も確認でき、行を削除すれば再評価される旨を一言。
- vault の `pyproject.toml` に `arxiv` を追加した旨（vault は git 非管理なので OneDrive 同期で他端末へ伝播）。

---

## Self-Review

**1. Spec coverage（spec §6 受け入れ基準 → タスク対応）:**
- AC1（fetch→candidates.json、テーマ別重複排除）→ Task 4（`run_fetch`/`main`）/ Task 7 Step 2–3 ✓
- AC2（0〜5 採点・閾値3 抽出）→ Task 5（SKILL.md §2–3 ルーブリック）/ Task 7 Step 4 ✓
- AC3（digests/YYYY-MM-DD.md 書式・該当なし）→ Task 5（SKILL.md §4）/ Task 7 Step 4 ✓
- AC4（seen-*.csv 5列・`--commit`・合否全件・再評価なし）→ Task 3（`commit_scores`）/ Task 4（commit モード）/ Task 7 Step 5–6 ✓
- AC5（初回 first_run_lookback_days 遡及）→ Task 2（`lookback_days`）/ Task 4（`run_fetch`）/ Task 7 Step 3 ✓
- AC6（取得失敗でも継続・報告）→ Task 4（`run_fetch` の try/except・`error` 載せ）/ Task 5（報告・ガードレール）✓
- AC7（テーマ別件数・上位ピック・パス報告）→ Task 5（SKILL.md §6）/ Task 7 Step 8 ✓
- AC8（CWD/watch-paper のみ・config に絶対パス無し・wiki 非干渉）→ Task 2（`resolve_data_dir`）/ Task 4（`main` の mkdir/stderr ログ）/ Task 5（ガードレール）/ Task 7 Step 7 ✓
- AC9（README に手順・前提）→ Task 6 ✓

**2. Placeholder scan:** `<skill-dir>`/`<実行日>`/`<data_dir>` は「実行時に解決する具体値」と明示しており TBD ではない。コード片はすべて完全形（省略・「Task N と同様」なし）。テストは実コードで記載。

**3. Type consistency:** 関数シグネチャが全タスクで一貫 — `commit_scores(scores, titles, thresholds, data_dir, evaluated_date)` の引数順は Task 3 定義・Task 4 `_run_commit_mode` 呼出・Task 3/4 テストで一致。`titles_by_theme`/`thresholds_by_theme`/`read_seen_ids`/`build_query`/`base_arxiv_id`/`effective_categories`/`effective_threshold`/`lookback_days`/`cutoff_datetime`/`resolve_data_dir` の名称・引数が Interfaces とコードとテストで一致。`candidates.json` のキー（`arxiv_id`/`title`/`abstract`/`authors`/`published`/`primary_category`/`link`、テーマの `id`/`name`/`threshold`/`anchors`/`fetched`/`new`/`candidates`/`error`）が Task 4 出力・Task 5 消費・Task 7 検証で一致。CSV 列順 `arxiv_id,score,title,evaluated,surfaced` が `CSV_HEADER`・`commit_scores`・テスト・SKILL.md・README で一致。

**4. 既知の制約:** ① arXiv live 取得と `uv add arxiv` はネット必須（Task 7 のみ。サンドボックスでネット不可ならユーザー実行）。② ユニットテストは pytest を `uv run --with pytest` でエフェメラル導入 — pytest 取得に初回のみネットが要る（以降キャッシュ）。テスト対象コードは `arxiv` を lazy import するので arxiv は不要。③ LLM の採点・ダイジェスト整形は決定的テスト不可 → Task 7 で実データ目視検証。④ OneDrive 同時実行の競合は手動マージ（README に明記、コードでは追記専用に留める）。
