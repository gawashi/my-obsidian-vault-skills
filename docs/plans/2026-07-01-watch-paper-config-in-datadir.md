# watch-paper: config.json を実行時データ dir へ移す Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** watch-paper の `config.json` をスキルフォルダから実行時データ dir（`<cwd>/watch-paper/config.json`）へ移し、スキルには汎用テンプレート `config.example.json` を同梱して初回にブートストラップする。

**Architecture:** `_common.py` に「テンプレの場所」「実設定のパス解決」「初回コピー」を集約する。`fetch_arxiv.py` は初回にテンプレをコピーして案内を出し取得せず停止、既存設定なら従来どおり取得。`commit_ledger.py` は実設定 dir から config を読むが、欠けても致命化せず threshold=3 にフォールバック。取得・採点・描画・台帳のロジックは一切変えない。

**Tech Stack:** Python 3.13（uv プロジェクト）、標準ライブラリのみ（`_common.py`）、pytest（エフェメラル導入）。

## Global Constraints

- Python `>=3.13`（vault の uv プロジェクト）。`_common.py` は **stdlib のみ**（`arxiv` 非依存を維持）。
- `config.example.json` は **厳密 JSON**（コメント・末尾カンマ不可）。インデントは既存 `config.json` に合わせ **4 スペース**。
- **コメント・docstring・stderr メッセージはすべて英語**。SKILL.md・README.md の散文は日本語のまま。config の値（`name` 等）はユーザーデータなので対象外。
- **自明なコメントは付けない**（import 行への説明コメント等を足さない）。
- テスト実行コマンド（リポジトリルートから）: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v`
- 配置: 実設定 = `<data_dir>/config.json`（`<data_dir>` は `--data-dir` 指定 or `<cwd>/watch-paper`）。テンプレ = `<skill-dir>/config.example.json`。
- 設計正本: `docs/specs/2026-07-01-watch-paper-config-in-datadir-design.md`。
- 各コミットメッセージ末尾に `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` を付ける。

---

## File Structure

| ファイル | 役割 | 本計画での扱い |
|---|---|---|
| `skills/watch-paper/config.example.json` | 配布用テンプレート（1 テーマ）。初回コピー元 | **新規**（Task 1） |
| `skills/watch-paper/config.json` | 個人テーマ入り実設定 | **削除**（Task 5・`git rm`） |
| `skills/watch-paper/_common.py` | 共有プラミング。config の場所解決＋ブートストラップ | 変更（Task 2 で追加、Task 5 で `CONFIG_PATH` 撤去） |
| `skills/watch-paper/commit_ledger.py` | 台帳追記。`defaults.threshold` フォールバックのため config を読む | 変更（Task 3） |
| `skills/watch-paper/fetch_arxiv.py` | 取得。初回ブートストラップ＋実設定読み込み | 変更（Task 4） |
| `skills/watch-paper/render_digest.py` | 描画。config 非依存 | **不変** |
| `.gitignore` | 実行時データの誤コミット防止 | 変更（Task 1） |
| `skills/watch-paper/SKILL.md` | 手順書 | 変更（Task 6） |
| `skills/watch-paper/README.md` | 説明書 | 変更（Task 6） |
| `skills/watch-paper/tests/test_common.py` | `_common` のテスト | 変更（Task 2） |
| `skills/watch-paper/tests/test_commit_ledger.py` | commit のテスト | 変更（Task 3） |
| `skills/watch-paper/tests/test_fetch_arxiv.py` | fetch のテスト | 変更（Task 4） |

**タスク順序の理由**: テンプレ（Task 1）は Task 2/4 のテストが実ファイルをコピーするため先に作る。`_common` の `CONFIG_PATH` 撤去と個人 `config.json` 削除は、`fetch`/`commit` が `CONFIG_PATH` を import しなくなる Task 3・4 の**後**（Task 5）に行い、各タスク完了時点でテストが常にグリーンになるようにする。

---

### Task 1: 同梱テンプレート `config.example.json` を追加し、`.gitignore` を更新

**Files:**
- Create: `skills/watch-paper/config.example.json`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: なし
- Produces: `skills/watch-paper/config.example.json`（Task 2 の `ensure_config` テストと Task 4 の bootstrap テストがこのファイルをコピー元として使う）

- [ ] **Step 1: テンプレートファイルを作成する**

Create `skills/watch-paper/config.example.json`:

```json
{
    "defaults": {
        "categories": ["cs.AI", "cs.CL", "cs.LG"],
        "threshold": 3,
        "lookback_days": 14,
        "first_run_lookback_days": 60,
        "max_results": 120,
        "request_delay_seconds": 3,
        "scoring_concurrency": 6
    },
    "themes": [
        {
            "id": "llm-agent",
            "name": "LLM agent",
            "enabled": true,
            "keywords": [
                "LLM agent",
                "language model agent",
                "agentic workflow"
            ],
            "anchors": ["ReAct", "AutoGPT"]
        }
    ]
}
```

- [ ] **Step 2: 厳密 JSON として妥当か検証する**

Run: `uv run --no-project --python 3.13 python -c "import json; json.load(open('skills/watch-paper/config.example.json', encoding='utf-8')); print('ok')"`
Expected: `ok`（例外なく標準出力に `ok`）

- [ ] **Step 3: `.gitignore` に実行時データ dir を追加する**

Modify `.gitignore` — 末尾に 1 行追加する（既存の `settings.local.json` / `.superpowers` / `__pycache__` は残す）:

```gitignore
settings.local.json
.superpowers

__pycache__

/watch-paper/
```

- [ ] **Step 4: コミット**

```bash
git add skills/watch-paper/config.example.json .gitignore
git commit -m "$(cat <<'EOF'
feat(watch-paper): add bundled config.example.json template + ignore runtime dir

Ship a generic single-theme (LLM agent) template that fetch bootstraps into
the runtime data dir; ignore /watch-paper/ so runtime data is never committed.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `_common.py` に `TEMPLATE_PATH` / `config_path` / `ensure_config` を追加

`CONFIG_PATH` は Task 5 まで残す（`fetch`/`commit` がまだ import しているため）。

**Files:**
- Modify: `skills/watch-paper/_common.py`
- Test: `skills/watch-paper/tests/test_common.py`

**Interfaces:**
- Consumes: `skills/watch-paper/config.example.json`（Task 1）
- Produces:
  - `config_path(data_dir) -> pathlib.Path` … `Path(data_dir) / "config.json"`
  - `ensure_config(data_dir) -> tuple[pathlib.Path, bool]` … `(path, created)`。config 不在ならテンプレをコピーして `created=True`、存在すれば `created=False`。コピー失敗時は `OSError` を送出。
  - `TEMPLATE_PATH: pathlib.Path` … `<skill-dir>/config.example.json`

- [ ] **Step 1: 失敗するテストを書く**

Append to `skills/watch-paper/tests/test_common.py`:

```python
def test_config_path_is_data_dir_config_json(tmp_path):
    assert cm.config_path(tmp_path) == tmp_path / "config.json"


def test_ensure_config_copies_template_when_absent(tmp_path):
    path, created = cm.ensure_config(tmp_path)
    assert created is True
    assert path == tmp_path / "config.json"
    assert path.read_text(encoding="utf-8") == cm.TEMPLATE_PATH.read_text(encoding="utf-8")


def test_ensure_config_is_noop_when_present(tmp_path):
    existing = tmp_path / "config.json"
    existing.write_text('{"defaults": {}, "themes": []}', encoding="utf-8")
    path, created = cm.ensure_config(tmp_path)
    assert created is False
    assert path == existing
    assert path.read_text(encoding="utf-8") == '{"defaults": {}, "themes": []}'
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_common.py -v`
Expected: FAIL（`AttributeError: module '_common' has no attribute 'config_path'` / `ensure_config` / `TEMPLATE_PATH`）

- [ ] **Step 3: 最小実装を書く**

Modify `skills/watch-paper/_common.py`:

1. `import shutil` を追加（先頭の import 群に）:

```python
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
```

2. 既存の `CONFIG_PATH = Path(__file__).parent / "config.json"` の**直後**に追加（`CONFIG_PATH` はまだ消さない）:

```python
TEMPLATE_PATH = Path(__file__).parent / "config.example.json"
```

3. `resolve_data_dir` の**直前**に 2 関数を追加:

```python
def config_path(data_dir):
    """Path of the live config: <data_dir>/config.json."""
    return Path(data_dir) / "config.json"


def ensure_config(data_dir):
    """Copy the bundled template into the data dir if no live config exists.

    Returns (path, created): created is True when the template was copied to
    create a new config (the caller should stop and let the user edit it),
    False when an existing config.json is already present. Raises OSError if
    the template cannot be read or copied.
    """
    dst = config_path(data_dir)
    if dst.exists():
        return dst, False
    shutil.copyfile(TEMPLATE_PATH, dst)
    print(f"[watch-paper] created {dst} from template", file=sys.stderr)
    return dst, True
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_common.py -v`
Expected: PASS（新規 3 件を含む全件）

- [ ] **Step 5: コミット**

```bash
git add skills/watch-paper/_common.py skills/watch-paper/tests/test_common.py
git commit -m "$(cat <<'EOF'
feat(watch-paper): add config_path/ensure_config to _common

Resolve the live config under the data dir and bootstrap it from the bundled
template on first use. CONFIG_PATH kept until callers stop importing it.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `commit_ledger.py` を実設定 dir 読み込み＋非致命フォールバックに変更

**Files:**
- Modify: `skills/watch-paper/commit_ledger.py:13-14`（import）, `skills/watch-paper/commit_ledger.py:91-98`（config 読み込み）
- Test: `skills/watch-paper/tests/test_commit_ledger.py`

**Interfaces:**
- Consumes: `config_path` / `load_config`（Task 2）
- Produces: 変更なし（`commit_scores` 等の公開関数のシグネチャは不変）

- [ ] **Step 1: 失敗するテストを書く**

Append to `skills/watch-paper/tests/test_commit_ledger.py`:

```python
def test_main_uses_config_default_threshold_for_theme_without_threshold(tmp_path):
    data_dir = tmp_path / "watch-paper"
    (data_dir / "state").mkdir(parents=True)
    # theme has NO "threshold" key -> commit must fall back to config defaults
    candidates_doc = {"themes": [
        {"id": "t1", "candidates": [{"arxiv_id": "2406.00001", "title": "Foo"}]}
    ]}
    (data_dir / "candidates.json").write_text(
        json.dumps(candidates_doc, ensure_ascii=False), encoding="utf-8")
    (data_dir / "config.json").write_text(
        json.dumps({"defaults": {"threshold": 5}, "themes": []}), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps({"t1": {"2406.00001": {"score": 4}}}),
                           encoding="utf-8")

    rc = cl.main(["--data-dir", str(data_dir), str(scores_path)])
    assert rc == 0
    with (data_dir / "state" / "seen-t1.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["arxiv_id"]: r for r in csv.DictReader(f)}
    assert rows["2406.00001"]["surfaced"] == "false"  # 4 < 5 (config default)


def test_main_without_config_falls_back_to_threshold_3(tmp_path):
    data_dir = tmp_path / "watch-paper"
    (data_dir / "state").mkdir(parents=True)
    # theme has NO "threshold" and there is NO config.json -> default 3, non-fatal
    candidates_doc = {"themes": [
        {"id": "t1", "candidates": [{"arxiv_id": "2406.00001", "title": "Foo"}]}
    ]}
    (data_dir / "candidates.json").write_text(
        json.dumps(candidates_doc, ensure_ascii=False), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps({"t1": {"2406.00001": {"score": 3}}}),
                           encoding="utf-8")

    rc = cl.main(["--data-dir", str(data_dir), str(scores_path)])
    assert rc == 0
    with (data_dir / "state" / "seen-t1.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["arxiv_id"]: r for r in csv.DictReader(f)}
    assert rows["2406.00001"]["surfaced"] == "true"  # 3 >= 3 (fallback default)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_commit_ledger.py -v`
Expected: FAIL — `test_main_uses_config_default_threshold_for_theme_without_threshold` は現行が skill-dir `config.json`（`defaults.threshold=3`）を読むため `surfaced == "true"` となり不一致で落ちる（`test_main_without_config_...` は現状も 3 で通りうるが、変更後の意図を固定する）。

- [ ] **Step 3: 実装を変更する**

Modify `skills/watch-paper/commit_ledger.py` の import（13-14 行目）:

```python
from _common import (config_path, load_config, load_run_inputs,
                     now_local_date, setup_data_dir)
```

Modify `main()` の config 読み込みブロック（現行 91-98 行目の `try: config = load_config(CONFIG_PATH) ... return 2` と直後の `default_thr = ...` 行）を、次に置き換える:

```python
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
```

（`titles`/`thresholds` 以降は現行のまま。現行の `default_thr = int(config.get(...))` 行は上のブロックに吸収されるので重複させない。）

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_commit_ledger.py -v`
Expected: PASS（既存 CLI テストは data_dir に config が無く fallback=3・candidates の threshold=3 で従来同結果、新規 2 件も PASS）

- [ ] **Step 5: コミット**

```bash
git add skills/watch-paper/commit_ledger.py skills/watch-paper/tests/test_commit_ledger.py
git commit -m "$(cat <<'EOF'
refactor(watch-paper): read config from data dir in commit_ledger

Read defaults.threshold from <data_dir>/config.json instead of the skill dir;
fall back to threshold 3 (non-fatal) when the config is absent, since
candidates.json already carries per-theme thresholds.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `fetch_arxiv.py` を初回ブートストラップ＋実設定 dir 読み込みに変更

**Files:**
- Modify: `skills/watch-paper/fetch_arxiv.py:15`（import）, `skills/watch-paper/fetch_arxiv.py:188-201`（`main()` の config 取得部）
- Test: `skills/watch-paper/tests/test_fetch_arxiv.py`

**Interfaces:**
- Consumes: `ensure_config` / `load_config` / `setup_data_dir`（Task 2）
- Produces: 変更なし（`run_fetch` 等の公開関数は不変）

- [ ] **Step 1: 失敗するテストを書く**

Append to `skills/watch-paper/tests/test_fetch_arxiv.py`:

```python
def test_main_bootstraps_config_and_stops(tmp_path):
    data_dir = tmp_path / "watch-paper"
    rc = fa.main(["--data-dir", str(data_dir)])
    assert rc == 0
    # template was copied into the data dir...
    assert (data_dir / "config.json").exists()
    # ...and fetch did not run (no network, no candidates.json)
    assert not (data_dir / "candidates.json").exists()
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_fetch_arxiv.py::test_main_bootstraps_config_and_stops -v`
Expected: FAIL — 現行 `main()` は `load_config(CONFIG_PATH)`（skill-dir config が存在）→ `_run_fetch_mode` へ進みネットワークを叩く（`arxiv` 未導入なら ImportError、導入済みなら実ネットワークで `candidates.json` を書く）。いずれにせよ assertion 前で分岐が異なり FAIL。

- [ ] **Step 3: 実装を変更する**

Modify `skills/watch-paper/fetch_arxiv.py` の import（15 行目）:

```python
from _common import ensure_config, load_config, setup_data_dir
```

Modify `main()` の `setup_data_dir` 以降（現行 188-201 行目）を次に置き換える:

```python
    try:
        data_dir = setup_data_dir(args.data_dir)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot create data dir: {e}", file=sys.stderr)
        return 2

    try:
        cfg_path, created = ensure_config(data_dir)
    except OSError as e:
        print(f"[watch-paper] FATAL: cannot bootstrap config from template: {e}",
              file=sys.stderr)
        return 2

    if created:
        print(f"[watch-paper] edit the themes in {cfg_path} and re-run.",
              file=sys.stderr)
        return 0

    try:
        config = load_config(cfg_path)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read config {cfg_path}: {e}",
              file=sys.stderr)
        return 2

    return _run_fetch_mode(data_dir, config)
```

（`ensure_config` が `created` 時に `[watch-paper] created ... from template` を出すので、ここでは行動喚起の 1 行のみを足し重複させない。取得ロジック `_run_fetch_mode`/`run_fetch` は不変。）

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests/test_fetch_arxiv.py -v`
Expected: PASS（純ヘルパ群 + 新規 bootstrap テスト。ネットワーク・`arxiv` 依存なし＝`created` で早期 return するため）

- [ ] **Step 5: コミット**

```bash
git add skills/watch-paper/fetch_arxiv.py skills/watch-paper/tests/test_fetch_arxiv.py
git commit -m "$(cat <<'EOF'
feat(watch-paper): bootstrap config on first fetch, read from data dir

fetch_arxiv now copies config.example.json into <data_dir>/config.json on the
first run and stops with guidance instead of fetching with example themes;
subsequent runs read the live config from the data dir.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 個人 `config.json` を削除し、`_common.py` の未使用 `CONFIG_PATH` を撤去

この時点で `fetch`/`commit`/tests のいずれも `CONFIG_PATH` を import しない。

**Files:**
- Delete: `skills/watch-paper/config.json`
- Modify: `skills/watch-paper/_common.py`（`CONFIG_PATH` 行を削除）

**Interfaces:**
- Consumes: なし
- Produces: なし（クリーンアップ）

- [ ] **Step 1: `CONFIG_PATH` の残存参照が無いことを確認する**

Run: `git grep -n "CONFIG_PATH" -- skills/watch-paper`
Expected: `skills/watch-paper/_common.py` の定義行のみがヒットする（`fetch_arxiv.py`/`commit_ledger.py`/`tests/` にヒットが無い）。もし他にヒットしたら、その参照を先に解消する。

- [ ] **Step 2: 個人 `config.json` を削除する**

```bash
git rm skills/watch-paper/config.json
```

- [ ] **Step 3: `_common.py` から `CONFIG_PATH` を削除する**

Modify `skills/watch-paper/_common.py` — 次の 1 行を削除する（`TEMPLATE_PATH` の定義は残す）:

```python
CONFIG_PATH = Path(__file__).parent / "config.json"
```

- [ ] **Step 4: 全テストがグリーンであることを確認する**

Run: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v`
Expected: PASS（全ファイル）。加えて `git grep -n "CONFIG_PATH" -- skills/watch-paper` が**何もヒットしない**ことを確認する。

- [ ] **Step 5: コミット**

```bash
git add skills/watch-paper/_common.py
git commit -m "$(cat <<'EOF'
chore(watch-paper): drop skill-dir config.json and unused CONFIG_PATH

The live config now lives in the runtime data dir; remove the personal
config.json (recoverable from history) and the now-dead CONFIG_PATH constant.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: ドキュメント（SKILL.md / README.md）を新しい config 配置に更新

**Files:**
- Modify: `skills/watch-paper/SKILL.md`
- Modify: `skills/watch-paper/README.md`

**Interfaces:**
- Consumes: なし
- Produces: なし（ドキュメント）

- [ ] **Step 1: SKILL.md「前提」を更新する**

Modify `skills/watch-paper/SKILL.md` — 「前提」の該当箇条書き（現行 15 行目）を次に置き換える:

置換前:
```
- スクリプト（`fetch_arxiv.py` / `render_digest.py` / `commit_ledger.py` / 共有 `_common.py`）と `config.json` は**このスキル自身のディレクトリ**（起動時に表示されるスキルのベースディレクトリ）にある。以下 `<skill-dir>` と表記し、実行時の絶対パスを使う。
```

置換後:
```
- スクリプト（`fetch_arxiv.py` / `render_digest.py` / `commit_ledger.py` / 共有 `_common.py`）と**設定テンプレート `config.example.json`** は**このスキル自身のディレクトリ**（起動時に表示されるスキルのベースディレクトリ）にある。以下 `<skill-dir>` と表記し、実行時の絶対パスを使う。
- **実設定 `config.json` は実行時データ dir（CWD 配下 `watch-paper/config.json`）にある**。無い場合は初回の `fetch_arxiv.py` 実行時に `config.example.json` から自動生成される（後述）。テーマ編集はこの `watch-paper/config.json` に対して行う。
```

- [ ] **Step 2: SKILL.md 手順1（取得）に初回ブートストラップの注記を足す**

Modify `skills/watch-paper/SKILL.md` — 「## 1. 取得（fetch_arxiv.py）」の `- 生成された `watch-paper/candidates.json` を読む。`（現行 30 行目）の**直前**に次の箇条書きを挿入する:

```
- **初回（`watch-paper/config.json` が無いとき）**: スクリプトはテンプレートを `watch-paper/config.json` にコピーし、stderr に `created ... from template` と `edit the themes ... and re-run` を出して**取得せず終了する（rc=0）**。この場合はユーザーに「`watch-paper/config.json` のテーマを編集して再実行」を促し、手順を中断する（`candidates.json` は生成されない）。
```

- [ ] **Step 3: SKILL.md 手順2.1 の config 参照パスを修正する**

Modify `skills/watch-paper/SKILL.md` — 手順 2.1（現行 40 行目）:

置換前:
```
- 同時実行の上限 `K` を決める: `<skill-dir>/config.json` の `defaults.scoring_concurrency` を読む。無ければ既定 **6**。
```

置換後:
```
- 同時実行の上限 `K` を決める: `watch-paper/config.json` の `defaults.scoring_concurrency` を読む。無ければ既定 **6**。
```

- [ ] **Step 4: README.md「やること」と生成ファイル表・スキル本体一覧を更新する**

Modify `skills/watch-paper/README.md`（現行 7 行目）— 「テーマ定義（`config.json`）に基づき」を「テーマ定義（`watch-paper/config.json`。初回はスキル同梱 `config.example.json` から自動生成）に基づき」へ置換。

Modify 生成ファイル表（現行 33-38 行目）— `| candidates.json | ...` 行の**前**に次の行を追加:

```
| `config.json` | 永続・ユーザー編集。テーマ定義（初回に `config.example.json` から生成）。列/キーは `defaults` と `themes[]` |
```

Modify スキル本体の列挙（現行 40 行目）:

置換前:
```
スキル本体（`SKILL.md`/`fetch_arxiv.py`/`render_digest.py`/`commit_ledger.py`/`_common.py`/`config.json`/`README.md`）は仕組みであり、実行では生成・変更されない。
```

置換後:
```
スキル本体（`SKILL.md`/`fetch_arxiv.py`/`render_digest.py`/`commit_ledger.py`/`_common.py`/`config.example.json`/`README.md`）は仕組みであり、実行では生成・変更されない。実設定 `config.json` は実行時データ dir 側（`watch-paper/config.json`）にある。
```

- [ ] **Step 5: README.md「テーマの編集」と「開発」を更新する**

Modify `skills/watch-paper/README.md` — 「## テーマの編集」冒頭（現行 44 行目）:

置換前:
```
`config.json` の `themes[]` を編集する（**厳密 JSON**、コメント・末尾カンマ不可）。
```

置換後:
```
`watch-paper/config.json` の `themes[]` を編集する（**厳密 JSON**、コメント・末尾カンマ不可）。初回実行時にスキル同梱 `config.example.json` から生成される。旧バージョンからの移行は、従来の設定を `watch-paper/config.json` にコピーすれば維持できる。
```

Modify 「## 開発」の設計正本リンク群（現行 58-60 行目付近）に 1 行追加:

```
- config の実行時 dir 移設: `docs/specs/2026-07-01-watch-paper-config-in-datadir-design.md`
```

- [ ] **Step 6: ドキュメントの整合を目視確認する**

Run: `git grep -n "config.json" -- skills/watch-paper/SKILL.md skills/watch-paper/README.md`
Expected: `<skill-dir>/config.json` を指す残存記述が無い（`watch-paper/config.json` または `config.example.json` を指す記述のみ）。取りこぼしがあれば修正する。

- [ ] **Step 7: コミット**

```bash
git add skills/watch-paper/SKILL.md skills/watch-paper/README.md
git commit -m "$(cat <<'EOF'
docs(watch-paper): document config in runtime data dir + first-run bootstrap

SKILL.md/README now point to watch-paper/config.json as the live config,
describe the bundled config.example.json template, and note the first-run
copy-and-stop behavior.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 最終確認

- [ ] **全テスト通過**: `uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v` が全件 PASS。
- [ ] **CONFIG_PATH 消滅**: `git grep -n "CONFIG_PATH" -- skills/watch-paper` が空。
- [ ] **スキルに個人設定が残らない**: `ls skills/watch-paper/config.json` が「無い」、`config.example.json` が「ある」。
