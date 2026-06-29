# watch-paper Script Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the watch-paper skill's deterministic work (digest extraction + rendering) out of the AI and into single-responsibility scripts, and split `fetch_arxiv.py`'s fetch+commit roles into separate scripts.

**Architecture:** Replace the one-script-two-modes design (`fetch_arxiv.py` with a `--commit` flag) with four files: `_common.py` (shared plumbing), `fetch_arxiv.py` (fetch only), `commit_ledger.py` (ledger append only), and `render_digest.py` (digest rendering only, new). The AI emits an enriched `scores.json` (`{theme:{id:{score,summary_ja,why_ja}}}`); the renderer joins it with `candidates.json` to produce the dated digest deterministically — filtering by threshold, sorting, counting, and formatting in Python instead of by hand.

**Tech Stack:** Python 3.13, stdlib only (`argparse`, `csv`, `json`, `datetime`, `pathlib`); `arxiv` + optional `truststore` are lazy-imported inside fetch only. Tests use `pytest` run ephemerally via `uv`.

## Global Constraints

- Python floor: `requires-python >=3.13` (vault is a uv project). Stdlib only in `_common.py`, `commit_ledger.py`, `render_digest.py`; `arxiv`/`truststore` stay lazy-imported inside `fetch_arxiv.run_fetch`.
- All scripts launched as `uv run --project . "<skill-dir>/<script>.py"`; data dir defaults to `<cwd>/watch-paper`, overridable with `--data-dir`.
- Runtime data is written only under `<data_dir>` (`candidates.json`, `scores.json`, `digests/`, `state/`). Scripts never touch `wiki/`, `raw/`, or `schema.md`.
- Ledger CSV columns are exactly `arxiv_id,score,title,evaluated,surfaced`; the ledger is append-only; `surfaced = "true" if score >= threshold else "false"`.
- `scores.json` schema is `{ "<theme-id>": { "<arxiv_id>": { "score": <int 0-5>, "summary_ja": <str>, "why_ja": <str> } } }`. `commit` reads `.score` (tolerating a bare int for back-compat); `render` reads all three fields.
- Digest dates (`generated`, filename, heading) are derived by `render_digest.py` via `now_local_date()` — never passed in by the AI.
- Tests live in `skills/watch-paper/tests/`; `conftest.py` already puts `skills/watch-paper` on `sys.path`. Run the suite with:
  `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`

---

## File Structure

| File | Responsibility |
|---|---|
| `skills/watch-paper/_common.py` | Shared plumbing: `CONFIG_PATH`, `resolve_data_dir`, `load_config`, `now_local_date`, `setup_data_dir`, `load_run_inputs` |
| `skills/watch-paper/fetch_arxiv.py` | Fetch only: query arXiv per theme → `candidates.json` |
| `skills/watch-paper/commit_ledger.py` | Commit only: `scores.json` + `candidates.json` → append `state/seen-<theme>.csv` |
| `skills/watch-paper/render_digest.py` | Render only: `scores.json` + `candidates.json` → `digests/<today>.md` |
| `skills/watch-paper/tests/test_common.py` | Tests for `_common.py` |
| `skills/watch-paper/tests/test_fetch_arxiv.py` | Tests for fetch helpers (commit tests removed) |
| `skills/watch-paper/tests/test_commit_ledger.py` | Tests for commit (moved + enriched-schema cases) |
| `skills/watch-paper/tests/test_render_digest.py` | Tests for the renderer (new) |
| `skills/watch-paper/SKILL.md` | Operational contract — steps 3/4/5/6 rewritten |
| `skills/watch-paper/README.md` | Script list, `scores.json` schema, smoke commands |

---

## Task 1: Extract shared plumbing into `_common.py`

Move data-dir / config / date helpers out of `fetch_arxiv.py` into `_common.py`, add two new helpers (`setup_data_dir`, `load_run_inputs`), and rewire `fetch_arxiv.py` to import them. Commit mode stays in `fetch_arxiv.py` for now (removed in Task 2) but is switched to use `load_run_inputs`, so the existing commit CLI test exercises the new reader.

**Files:**
- Create: `skills/watch-paper/_common.py`
- Create: `skills/watch-paper/tests/test_common.py`
- Modify: `skills/watch-paper/fetch_arxiv.py`
- Modify: `skills/watch-paper/tests/test_fetch_arxiv.py`

**Interfaces:**
- Produces:
  - `CONFIG_PATH: Path` — `<skill-dir>/config.json`
  - `resolve_data_dir(arg_data_dir: str | None) -> Path`
  - `load_config(path: Path) -> dict`
  - `now_local_date() -> str` (`"YYYY-MM-DD"`)
  - `setup_data_dir(arg_data_dir: str | None) -> Path` — resolves dir, prints `[watch-paper] data_dir = ...` to stderr, creates `state/` and `digests/`; raises `OSError` on mkdir failure
  - `load_run_inputs(data_dir: Path, scores_path: str) -> tuple[dict | None, dict | None]` — returns `(candidates_doc, scores)`, or `(None, None)` after logging on read error
- Consumes (later tasks): all four helpers above.

- [ ] **Step 1: Write the failing tests for `_common`**

Create `skills/watch-paper/tests/test_common.py`:

```python
import json
from pathlib import Path

import _common as cm


def test_resolve_data_dir_default_is_cwd_watch_paper():
    assert cm.resolve_data_dir(None) == Path.cwd() / "watch-paper"


def test_resolve_data_dir_override():
    assert cm.resolve_data_dir("/tmp/foo") == Path("/tmp/foo")


def test_now_local_date_is_iso_yyyy_mm_dd():
    s = cm.now_local_date()
    # YYYY-MM-DD: three dash-separated numeric parts of widths 4-2-2
    parts = s.split("-")
    assert len(parts) == 3
    assert [len(p) for p in parts] == [4, 2, 2]
    assert all(p.isdigit() for p in parts)


def test_setup_data_dir_creates_state_and_digests(tmp_path):
    data_dir = cm.setup_data_dir(str(tmp_path / "wp"))
    assert data_dir == tmp_path / "wp"
    assert (data_dir / "state").is_dir()
    assert (data_dir / "digests").is_dir()


def test_load_run_inputs_reads_both(tmp_path):
    data_dir = tmp_path / "wp"
    (data_dir).mkdir()
    (data_dir / "candidates.json").write_text(
        json.dumps({"themes": [{"id": "t1"}]}), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps({"t1": {}}), encoding="utf-8")
    candidates_doc, scores = cm.load_run_inputs(data_dir, str(scores_path))
    assert candidates_doc == {"themes": [{"id": "t1"}]}
    assert scores == {"t1": {}}


def test_load_run_inputs_missing_file_returns_none(tmp_path):
    data_dir = tmp_path / "wp"
    data_dir.mkdir()
    candidates_doc, scores = cm.load_run_inputs(data_dir, str(tmp_path / "nope.json"))
    assert candidates_doc is None
    assert scores is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_common.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named '_common'`.

- [ ] **Step 3: Create `_common.py`**

Create `skills/watch-paper/_common.py`:

```python
#!/usr/bin/env python3
"""watch-paper: shared plumbing for the fetch / render / commit scripts.

Kept dependency-free (stdlib only) so every script and the unit tests can
import it without the `arxiv` dependency installed.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


def resolve_data_dir(arg_data_dir):
    """--data-dir if given, else <cwd>/watch-paper."""
    if arg_data_dir:
        return Path(arg_data_dir)
    return Path.cwd() / "watch-paper"


def load_config(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def now_local_date():
    return datetime.now().date().isoformat()


def setup_data_dir(arg_data_dir):
    """Resolve the data dir, print the banner, ensure state/ and digests/ exist.

    Raises OSError if the directories cannot be created (caller returns rc=2).
    """
    data_dir = resolve_data_dir(arg_data_dir)
    print(f"[watch-paper] data_dir = {data_dir}", file=sys.stderr)
    (data_dir / "state").mkdir(parents=True, exist_ok=True)
    (data_dir / "digests").mkdir(parents=True, exist_ok=True)
    return data_dir


def load_run_inputs(data_dir, scores_path):
    """Read scores.json + candidates.json for render/commit.

    Returns (candidates_doc, scores); (None, None) on read/parse error (logged).
    """
    try:
        with open(scores_path, "r", encoding="utf-8") as f:
            scores = json.load(f)
        with (data_dir / "candidates.json").open("r", encoding="utf-8") as f:
            candidates_doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read scores/candidates: {e}",
              file=sys.stderr)
        return None, None
    return candidates_doc, scores
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_common.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Rewire `fetch_arxiv.py` to import from `_common`**

In `skills/watch-paper/fetch_arxiv.py`, replace the module docstring's imports block. Change the top of the file from:

```python
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
CSV_HEADER = ["arxiv_id", "score", "title", "evaluated", "surfaced"]
```

to:

```python
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import CONFIG_PATH, load_config, load_run_inputs, setup_data_dir

CSV_HEADER = ["arxiv_id", "score", "title", "evaluated", "surfaced"]
```

Then delete the now-duplicated helper definitions from `fetch_arxiv.py`: remove the entire `resolve_data_dir` function, the entire `load_config` function, and the entire `now_local_date` function (their bodies now live in `_common.py`). Leave `base_arxiv_id`, `effective_categories`, `effective_threshold`, `build_query`, `lookback_days`, `cutoff_datetime`, `read_seen_ids`, the commit-mode helpers, and `run_fetch` untouched.

- [ ] **Step 6: Switch `fetch_arxiv.py` commit reader and `main` to the shared helpers**

In `fetch_arxiv.py`, replace `_run_commit_mode` with a version that uses `load_run_inputs`:

```python
def _run_commit_mode(args, data_dir, config):
    candidates_doc, scores = load_run_inputs(data_dir, args.commit)
    if candidates_doc is None:
        return 2
    titles = titles_by_theme(candidates_doc)
    default_thr = effective_threshold({}, config.get("defaults", {}))
    thresholds = thresholds_by_theme(candidates_doc, default_thr)
    appended = commit_scores(scores, titles, thresholds, data_dir, now_local_date())
    print(f"[watch-paper] committed {sum(appended.values())} rows: {appended}",
          file=sys.stderr)
    return 0
```

Note `now_local_date` is no longer defined locally — add it to the import line so this keeps working in Task 1:

Change the import line to:

```python
from _common import (CONFIG_PATH, load_config, load_run_inputs,
                     now_local_date, setup_data_dir)
```

Then replace the `main` function's data-dir/mkdir block. Change `main` from:

```python
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
```

to:

```python
    try:
        data_dir = setup_data_dir(args.data_dir)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot create data dir: {e}", file=sys.stderr)
        return 2

    try:
        config = load_config(CONFIG_PATH)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read config {CONFIG_PATH}: {e}",
              file=sys.stderr)
        return 2
```

- [ ] **Step 7: Remove the moved `resolve_data_dir` tests from `test_fetch_arxiv.py`**

In `skills/watch-paper/tests/test_fetch_arxiv.py`, delete these two tests (now covered in `test_common.py`):

```python
def test_resolve_data_dir_default_is_cwd_watch_paper():
    assert fa.resolve_data_dir(None) == Path.cwd() / "watch-paper"


def test_resolve_data_dir_override():
    assert fa.resolve_data_dir("/tmp/foo") == Path("/tmp/foo")
```

These were the only users of `Path` in this file, so also remove the now-unused `from pathlib import Path` import line from the top of `test_fetch_arxiv.py`.

- [ ] **Step 8: Run the full suite to verify everything passes**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`
Expected: PASS. Fetch helpers, the existing commit tests (still in `fetch_arxiv`, now exercising `load_run_inputs`), and the new `_common` tests all green.

- [ ] **Step 9: Commit**

```bash
git add skills/watch-paper/_common.py skills/watch-paper/fetch_arxiv.py skills/watch-paper/tests/test_common.py skills/watch-paper/tests/test_fetch_arxiv.py
git commit -m "refactor(watch-paper): extract shared plumbing into _common.py"
```

---

## Task 2: Move commit into `commit_ledger.py` (+ enriched scores schema)

Move the ledger-commit code out of `fetch_arxiv.py` into a new `commit_ledger.py`, make `commit_scores` accept the enriched `scores.json` (dict-per-id) while tolerating a bare int, and reduce `fetch_arxiv.py` to fetch-only.

**Files:**
- Create: `skills/watch-paper/commit_ledger.py`
- Create: `skills/watch-paper/tests/test_commit_ledger.py`
- Modify: `skills/watch-paper/fetch_arxiv.py`
- Modify: `skills/watch-paper/tests/test_fetch_arxiv.py`

**Interfaces:**
- Consumes: `setup_data_dir`, `load_run_inputs`, `load_config`, `now_local_date`, `CONFIG_PATH` (from `_common`).
- Produces:
  - `CSV_HEADER: list[str]`
  - `titles_by_theme(candidates_doc: dict) -> dict[str, dict[str, str]]`
  - `thresholds_by_theme(candidates_doc: dict, default_threshold: int = 3) -> dict[str, int]`
  - `commit_scores(scores, titles, thresholds, data_dir, evaluated_date) -> dict[str, int]` — `scores[theme][id]` may be `{"score": int, ...}` (enriched) or a bare int
  - `main(argv=None) -> int` — CLI: positional `scores_json`, `--data-dir`

- [ ] **Step 1: Write the new commit tests (moved + enriched cases)**

Create `skills/watch-paper/tests/test_commit_ledger.py`:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_commit_ledger.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'commit_ledger'`.

- [ ] **Step 3: Create `commit_ledger.py`**

Create `skills/watch-paper/commit_ledger.py`:

```python
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

from _common import (CONFIG_PATH, load_config, load_run_inputs,
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

    try:
        config = load_config(CONFIG_PATH)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read config {CONFIG_PATH}: {e}",
              file=sys.stderr)
        return 2

    default_thr = int(config.get("defaults", {}).get("threshold", 3))
    titles = titles_by_theme(candidates_doc)
    thresholds = thresholds_by_theme(candidates_doc, default_thr)
    appended = commit_scores(scores, titles, thresholds, data_dir, now_local_date())
    print(f"[watch-paper] committed {sum(appended.values())} rows: {appended}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_commit_ledger.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Reduce `fetch_arxiv.py` to fetch-only**

In `skills/watch-paper/fetch_arxiv.py`:

(a) Delete the commit-mode helper block — the entire functions `titles_by_theme`, `thresholds_by_theme`, and `commit_scores`, plus the `# Commit mode helpers` section comment.

(b) Delete the `_run_commit_mode` function entirely.

(c) Delete the `CSV_HEADER = [...]` line (now lives in `commit_ledger.py`; `read_seen_ids` does not use it).

(d) Trim the import line back to drop the now-unused `load_run_inputs` and `now_local_date`:

```python
from _common import CONFIG_PATH, load_config, setup_data_dir
```

(e) Update the module docstring to fetch-only:

```python
"""watch-paper: deterministic arXiv fetch -> <data_dir>/candidates.json.

<data_dir> defaults to <cwd>/watch-paper (cwd == vault root); override with
--data-dir. `import arxiv` is lazy (inside run_fetch) so the pure helpers below
stay unit-testable without the dependency installed.
"""
```

(f) Replace `main` so it no longer has a `--commit` branch:

```python
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="watch-paper arXiv fetch")
    parser.add_argument("--data-dir", default=None,
                        help="data root (default: <cwd>/watch-paper)")
    args = parser.parse_args(argv)

    try:
        data_dir = setup_data_dir(args.data_dir)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot create data dir: {e}", file=sys.stderr)
        return 2

    try:
        config = load_config(CONFIG_PATH)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read config {CONFIG_PATH}: {e}",
              file=sys.stderr)
        return 2

    return _run_fetch_mode(data_dir, config)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Remove the moved commit tests from `test_fetch_arxiv.py`**

In `skills/watch-paper/tests/test_fetch_arxiv.py`:

(a) Delete the entire `# ---- commit mode ----` section: the `_candidates_doc` helper, `test_titles_by_theme`, `test_thresholds_by_theme`, `test_commit_writes_header_and_rows_with_surfaced`, `test_commit_appends_without_duplicate_header`, and `test_commit_ignores_ids_absent_from_candidates`.

(b) Delete the entire `# ---- CLI commit mode ... ----` section: `test_main_commit_mode_writes_ledger`.

(c) The two `read_seen_ids` tests reference `fa.CSV_HEADER`, which no longer exists in `fetch_arxiv`. Replace those references with a literal header. Change:

```python
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

to:

```python
_LEDGER_HEADER = ["arxiv_id", "score", "title", "evaluated", "surfaced"]


def test_read_seen_ids_header_only_is_empty(tmp_path):
    p = tmp_path / "seen.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(_LEDGER_HEADER)
    assert fa.read_seen_ids(p) == set()


def test_read_seen_ids_reads_ids_with_comma_titles(tmp_path):
    p = tmp_path / "seen.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_LEDGER_HEADER)
        w.writerow(["2406.00001", "5", "Foo, Bar: A Study", "2026-06-28", "true"])
        w.writerow(["2406.00002", "2", "Baz", "2026-06-28", "false"])
    assert fa.read_seen_ids(p) == {"2406.00001", "2406.00002"}
```

(d) If `json` is now unused in `test_fetch_arxiv.py` after removing the CLI commit test, remove `import json` from its imports. (Keep `import csv` — still used by the `read_seen_ids` tests.)

- [ ] **Step 7: Run the full suite to verify everything passes**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`
Expected: PASS. `fetch_arxiv` is fetch-only; commit lives in `commit_ledger` with both enriched and bare-int coverage.

- [ ] **Step 8: Commit**

```bash
git add skills/watch-paper/commit_ledger.py skills/watch-paper/fetch_arxiv.py skills/watch-paper/tests/test_commit_ledger.py skills/watch-paper/tests/test_fetch_arxiv.py
git commit -m "refactor(watch-paper): move commit into commit_ledger.py with enriched scores schema"
```

---

## Task 3: Add `render_digest.py` (deterministic digest rendering)

New script that joins `scores.json` (enriched) with `candidates.json` to produce the dated digest — threshold filter, score-desc/published-desc sort, evaluated/surfaced counts, `⭐5` prefix, `該当なし`, `取得失敗`, author truncation — and prints per-theme counts to stderr.

**Files:**
- Create: `skills/watch-paper/render_digest.py`
- Create: `skills/watch-paper/tests/test_render_digest.py`

**Interfaces:**
- Consumes: `setup_data_dir`, `load_run_inputs`, `now_local_date` (from `_common`).
- Produces:
  - `MAX_AUTHORS: int` (= 6)
  - `build_digest(candidates_doc: dict, scores: dict, today: str) -> tuple[str, list[tuple[str, int, int]]]` — returns `(markdown, [(theme_id, evaluated, surfaced), ...])`
  - `main(argv=None) -> int` — CLI: positional `scores_json`, `--data-dir`

- [ ] **Step 1: Write the failing tests for the renderer**

Create `skills/watch-paper/tests/test_render_digest.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_render_digest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'render_digest'`.

- [ ] **Step 3: Create `render_digest.py`**

Create `skills/watch-paper/render_digest.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_render_digest.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`
Expected: PASS (all tests across `_common`, fetch, commit, render).

- [ ] **Step 6: Commit**

```bash
git add skills/watch-paper/render_digest.py skills/watch-paper/tests/test_render_digest.py
git commit -m "feat(watch-paper): add render_digest.py for deterministic digest rendering"
```

---

## Task 4: Update `SKILL.md`

Rewrite the operational contract so the AI writes an enriched `scores.json`, runs the renderer, and runs the committer — no hand extraction, hand counting, or hand markdown.

**Files:**
- Modify: `skills/watch-paper/SKILL.md`

**Interfaces:**
- Consumes: the three script CLIs and the enriched `scores.json` schema from Tasks 1–3.

- [ ] **Step 1: Update the intro and scope sentence**

In `skills/watch-paper/SKILL.md`, replace the first body paragraph (the `arXiv の新着を ...` sentence) so it names the three scripts:

```markdown
arXiv の新着を `config.json` のテーマごとに集め、関連度でスコアリングして「ダイジェスト」に抽出する定点観測スキル。決定的な処理は3つのスクリプト（`uv run`）が担う: **取得** `fetch_arxiv.py`、**ダイジェスト描画** `render_digest.py`、**台帳更新** `commit_ledger.py`。関連度判定・要約は LLM（この手順）が担う。設計の正本はスキルリポジトリの `docs/specs/2026-06-28-paper-watch-skill-design.md`（採点の並列化は `docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`、スクリプト分割は `docs/specs/2026-06-29-watch-paper-script-split-design.md`）。
```

- [ ] **Step 2: Update the "前提" bullet that names the script files**

Replace the bullet starting `- `fetch_arxiv.py` と `config.json` は...` with:

```markdown
- スクリプト（`fetch_arxiv.py` / `render_digest.py` / `commit_ledger.py` / 共有 `_common.py`）と `config.json` は**このスキル自身のディレクトリ**（起動時に表示されるスキルのベースディレクトリ）にある。以下 `<skill-dir>` と表記し、実行時の絶対パスを使う。
```

- [ ] **Step 3: Update step 2.2's scores.json write-out to the enriched schema**

In section `### 2.2 正規化パス（テーマ内のみ）`, change the line about `summary_ja`/`why_ja` adoption so it ends by stating the enriched output, and ensure the reader knows the main writes the enriched file. Replace the bullet:

```markdown
- `summary_ja`/`why_ja` は原則サブの出力を採用し、明らかな誤りのみ軽修正する。
```

with:

```markdown
- `summary_ja`/`why_ja` は原則サブの出力を採用し、明らかな誤りのみ軽修正する。
- 較正後、採点した**全件**を enriched 形式 `{ "<theme-id>": { "<arxiv_id>": { "score": <0-5>, "summary_ja": "...", "why_ja": "..." } } }` で `watch-paper/scores.json` に書き出す（合否問わず全件。`render_digest.py` と `commit_ledger.py` の共通入力）。
```

- [ ] **Step 4: Delete step 3 (抽出) and rewrite step 4 (ダイジェスト)**

Replace the whole `## 3. 抽出` section AND the whole `## 4. ダイジェストを書く` section (from `## 3. 抽出` up to but not including `## 5. 台帳にコミット`) with a single new step 3:

```markdown
## 3. ダイジェストを描画（render_digest.py）

抽出（`threshold` 以上のフィルタ）・降順ソート・件数集計・Markdown 整形は**スクリプトが決定的に行う**。手作業で並べ替え・数え上げ・転記をしない。

```
uv run --project . "<skill-dir>/render_digest.py" "watch-paper/scores.json"
```

- 入力は `watch-paper/scores.json`（手順2で書いた enriched 形式）と `watch-paper/candidates.json`。出力は `watch-paper/digests/<実行日>.md`（日付はスクリプトが導出）。
- stderr にテーマ別 `evaluated` / `surfaced` 件数が出る（手順5の報告でこれを引用する）。
- 再実行は同名ダイジェストを上書きする（冪等）。既存の同名ファイルを意図せず壊したくない場合は、実行前にユーザーへ確認する。

生成される書式（正本は `render_digest.py`。参考）:

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

## 産業異常検知  （評価0 / 抽出0）
- 該当なし
```

- スコア5は `⭐5`、それ以外は素の数値。`threshold` 以上のみ・スコア降順（同点は新しい投稿が上）。
- 取得失敗テーマ（候補に `error`）は `- 取得失敗: <error>` と明記される。`new=0` テーマは `- 該当なし`。
```

- [ ] **Step 5: Update step 5 (commit) to call `commit_ledger.py`**

In `## 5. 台帳にコミット（commit モード）`, replace the body so the `scores.json` write is already done (in step 2) and the command is the new script. Change the section to:

```markdown
## 4. 台帳にコミット（commit_ledger.py）

`watch-paper/scores.json`（手順2で書いた enriched 形式・採点した全件）をコミットする:

```
uv run --project . "<skill-dir>/commit_ledger.py" "watch-paper/scores.json"
```

これで各テーマの `watch-paper/state/seen-<theme-id>.csv` に `arxiv_id,score,title,evaluated,surfaced` が追記される（surfaced=score≥threshold、evaluated=実行日）。CSV はスクリプトが決定的に書くので、タイトルのカンマ等で壊れない。`candidates.json` に無い ID は無視される。`commit_ledger.py` は `.score` のみ参照する（`summary_ja`/`why_ja` は無視）。台帳は**追記専用**なので**1回だけ**実行する。
```

(Renumber the subsequent `## 6. 報告` to `## 5. 報告` in the next step.)

- [ ] **Step 6: Update the 報告 section to quote the renderer's counts**

Renumber `## 6. 報告` to `## 5. 報告` and replace its first two bullets:

```markdown
- テーマごとの「評価件数 / 抽出件数」。
- 各テーマの上位ピック（タイトル＋スコア）を数件。
```

with:

```markdown
- テーマごとの「評価件数 / 抽出件数」（`render_digest.py` の stderr 出力を引用。数え直さない）。
- 各テーマの上位ピック（タイトル＋スコア）を数件。
```

- [ ] **Step 7: Relax the date guardrail**

In `## ガードレール`, replace:

```markdown
- 日付はハードコードしない（実行日を `date +%F`（bash）または `Get-Date -Format "yyyy-MM-dd"`（PowerShell）で取得）。
```

with:

```markdown
- ダイジェストの日付は `render_digest.py` が導出する（AI は日付を扱わない）。手順1で実行日を確認する用途以外でハードコードしない。
```

- [ ] **Step 8: Rename the step-1 heading and fix internal step cross-references**

In `skills/watch-paper/SKILL.md` (these shift because old step 3 was deleted and 4/5/6 renumbered to 3/4/5):

(a) Rename the heading `## 1. 取得（fetch モード）` to `## 1. 取得（fetch_arxiv.py）`.

(b) In the step 2 intro paragraph, change `（手順4で「該当なし」/「取得失敗」として残す）` to `（手順3で「該当なし」/「取得失敗」として残す）`.

(c) In `### 2.2 正規化パス（テーマ内のみ）`, change `調整した件数を覚えておき手順6で報告する。` to `調整した件数を覚えておき手順5で報告する。`

(d) In `### 2.3 フォールバック`, change `フォールバックした件数を覚えておき手順6で報告する。` to `フォールバックした件数を覚えておき手順5で報告する。`

- [ ] **Step 9: Update the commit-only guardrail**

In `## ガードレール`, replace:

```markdown
- 台帳 CSV は **`--commit` 経由でのみ**更新する（手で行を書き換えない／追記専用）。AIが誤って弾いた論文を拾い直したいときは、その行を手で削除すれば次回再評価される。
```

with:

```markdown
- 台帳 CSV は **`commit_ledger.py` 経由でのみ**更新する（手で行を書き換えない／追記専用）。AIが誤って弾いた論文を拾い直したいときは、その行を手で削除すれば次回再評価される。
```

- [ ] **Step 10: Verify the file reads coherently**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`
Expected: PASS (docs change doesn't affect tests; this confirms nothing else broke). Then read `skills/watch-paper/SKILL.md` start-to-finish and confirm step numbers run 1→5 with no dangling references to a `--commit` flag, to `手順6`, or to hand-written extraction.

- [ ] **Step 11: Commit**

```bash
git add skills/watch-paper/SKILL.md
git commit -m "docs(watch-paper): SKILL.md uses render_digest.py and commit_ledger.py"
```

---

## Task 5: Update `README.md`

Bring the README in line with the three-script layout and the enriched `scores.json`.

**Files:**
- Modify: `skills/watch-paper/README.md`

- [ ] **Step 1: Update the "やること" bullet**

In `skills/watch-paper/README.md`, replace the `**やること**` bullet so rendering is attributed to the script:

```markdown
- **やること**: テーマ定義（`config.json`）に基づき arXiv 新着を取得（`fetch_arxiv.py`）→ **1論文=1サブエージェント**で 0〜5 の関連度を並列採点し、メインがテーマ内で正規化（較正）→ enriched `scores.json` を書き、`render_digest.py` が閾値以上を `watch-paper/digests/YYYY-MM-DD.md` に決定的に描画。評価済みは合否問わず `commit_ledger.py` が `watch-paper/state/seen-<theme>.csv` に記録。
```

- [ ] **Step 2: Update the script smoke-test block**

Replace the `スクリプト単体の動作確認 ...` block and its single command with all three scripts:

```markdown
スクリプト単体の動作確認（任意。`<skill-dir>` はこのスキルの絶対パス）:

```
uv run --project . "<skill-dir>/fetch_arxiv.py"                        # 取得 → watch-paper/candidates.json
uv run --project . "<skill-dir>/render_digest.py" "watch-paper/scores.json"   # 描画 → watch-paper/digests/<日付>.md
uv run --project . "<skill-dir>/commit_ledger.py" "watch-paper/scores.json"   # 台帳追記（1回のみ）
```
```

- [ ] **Step 3: Update the generated-files table's `scores.json` row**

In the 生成されるファイル table, replace the `scores.json` row:

```markdown
| `scores.json` | 一時（毎回上書き）。LLM→commit のスコア対応表 |
```

with:

```markdown
| `scores.json` | 一時（毎回上書き）。LLM の採点結果 `{theme:{id:{score,summary_ja,why_ja}}}`。`render_digest.py`/`commit_ledger.py` の共通入力 |
```

- [ ] **Step 4: Update the skill-body file list**

Replace:

```markdown
スキル本体（`SKILL.md`/`fetch_arxiv.py`/`config.json`/`README.md`）は仕組みであり、実行では生成・変更されない。
```

with:

```markdown
スキル本体（`SKILL.md`/`fetch_arxiv.py`/`render_digest.py`/`commit_ledger.py`/`_common.py`/`config.json`/`README.md`）は仕組みであり、実行では生成・変更されない。
```

- [ ] **Step 5: Add the script-split spec to the 開発 section**

In `## 開発`, after the `採点の並列化差分` line, add:

```markdown
- スクリプト分割（fetch/render/commit）: `docs/specs/2026-06-29-watch-paper-script-split-design.md`
```

- [ ] **Step 6: Verify and commit**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -q`
Expected: PASS. Read `README.md` once to confirm no remaining reference to `fetch_arxiv.py --commit`.

```bash
git add skills/watch-paper/README.md
git commit -m "docs(watch-paper): README for three-script layout and enriched scores.json"
```

---

## Final Verification

- [ ] **Run the whole suite once more**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v`
Expected: all tests pass (fetch helpers, `_common`, commit including enriched + bare-int, render including counts/sort/該当なし/取得失敗/author-truncation/CLI).

- [ ] **Grep for stale references**

Run: `git grep -n "fetch_arxiv.py --commit"` and `git grep -n "fa.CSV_HEADER"` inside `skills/watch-paper/`.
Expected: no matches (the `--commit` flag and the old `CSV_HEADER` test reference are gone).
```
