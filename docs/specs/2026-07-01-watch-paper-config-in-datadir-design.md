# 設計: watch-paper の config.json を実行時データ dir（vault の `watch-paper/`）へ移し、スキルには汎用テンプレートを同梱する

- **日付**: 2026-07-01
- **ステータス**: 承認済み（実装計画フェーズ手前）
- **対象**: `skills/watch-paper/`。現状スキルフォルダに同梱している `config.json`（個人テーマ入り）を、実行時データ dir（`<cwd>/watch-paper/`、通常は vault ルート配下）へ移す。スキルフォルダには汎用の**テンプレート** `config.example.json` のみを同梱し、初回に vault へブートストラップする。
- **元 spec**: `docs/specs/2026-06-28-paper-watch-skill-design.md`（取得・台帳・責務境界）、`docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`（並列採点）、`docs/specs/2026-06-29-watch-paper-script-split-design.md`（fetch/render/commit 分割・`_common.py`）。本書はそれらの **config.json の配置・読み込み経路** を上書きする差分。取得・採点・描画・台帳のロジック、`scores.json` 契約、責務境界はすべて不変。

---

## 1. 背景・動機

現状、`config.json` は**スキル自身のディレクトリ**（`skills/watch-paper/config.json`）に置かれ、`_common.py` の `CONFIG_PATH = Path(__file__).parent / "config.json"` を通じて `fetch_arxiv.py` と `commit_ledger.py` が読む。

このリポジトリは Claude **プラグイン**（`.claude-plugin/marketplace.json`・`plugin.json` あり）であり、スキルフォルダは**配布物**＝インストール時にプラグインキャッシュ（`~/.claude/plugins/cache/...`）へ展開される「仕組み」である。ここに個人の `config.json` を置くと 2 つの問題がある:

1. **実行時に設定変更しづらい**: 実設定がプラグインキャッシュ側にあり、ユーザーが自然に編集する場所（vault）と離れている。プラグイン更新で上書きされる懸念もある。
2. **配布に個人テーマが混ざる**: リポジトリを配布すると、作者個人のテーマ（産業異常検知・科学的発見の自動化）が同梱される。

一方、実行時データ（`candidates.json`・`scores.json`・`state/`・`digests/`）はすでに `<cwd>/watch-paper/`（vault ルート配下・永続・編集可能）に書かれている。**config.json はユーザーデータ（テーマ定義）であり、実行時データ dir に置くのが自然**である。

要望: **config.json を vault の `watch-paper/` に置き、(1) 実行時に編集可能・プラグイン更新に非破壊、(2) スキルは仕組み＋汎用テンプレートだけを配布、を実現する。**

---

## 2. 確定した決定事項

| 論点 | 決定 |
|---|---|
| 実設定の配置 | `<cwd>/watch-paper/config.json`（データ dir 配下）。`--data-dir` 指定時はその配下。永続・編集対象 |
| 同梱物 | スキルフォルダに **`config.example.json`（汎用テンプレート・配布物）** を置く。実設定 `config.json` は同梱しない |
| 初回（未設定時）の挙動 | `watch-paper/config.json` が無ければ、`config.example.json` を **コピーして案内を出し、取得せず rc=0 で停止**（例テーマのまま走らせない） |
| テンプレートの中身 | **「LLM agent」1 テーマ**＋現状の `defaults`（ユーザー判断） |
| 実テーマの保全 | 作者の実テーマは vault へコピー済み。リポジトリから外す（git 履歴には残る）。移行手当ては不要（ユーザー確認済み） |
| config 読み込み経路 | `_common.py` の skill-dir 固定 `CONFIG_PATH` を廃止し、`config_path(data_dir) = data_dir / "config.json"` に変更。テンプレは `TEMPLATE_PATH = <skill-dir>/config.example.json` |
| commit の config 依存 | `commit_ledger.py` は `defaults.threshold` フォールバックのため config を読むが、**通常は fetch がブートストラップ済みで存在**する。万一欠けても致命終了せず threshold=3 にフォールバック（`candidates.json` が既にテーマ別 threshold を持つため実害なし） |

---

## 3. スコープ

### この変更でやること

1. `_common.py`: skill-dir 固定 `CONFIG_PATH` を廃止。`TEMPLATE_PATH`・`config_path(data_dir)`・`ensure_config(data_dir)` を追加。
2. `fetch_arxiv.py`: `setup_data_dir` の後に `ensure_config`。テンプレをコピーした（＝初回）なら案内を出して rc=0 で停止。既存なら `load_config(config_path(data_dir))` で従来どおり取得。
3. `commit_ledger.py`: config を `config_path(data_dir)` から読む。欠けていれば threshold=3 にフォールバック（非致命）。
4. `config.example.json`（新規・同梱）: 「LLM agent」1 テーマ＋現状の `defaults`。厳密 JSON。
5. `config.json`（現行・個人テーマ）をリポジトリから削除。`.gitignore` に `watch-paper/`（実行時データ dir）を追加するかは §4.6 で判断。
6. SKILL.md 更新（前提・手順1・生成ファイル記述・ガードレール）。
7. README.md 更新（テーマ編集節・生成ファイル表・スキル本体一覧・設計リンク）。
8. テスト更新（`test_common.py` に `ensure_config`/`config_path` を追加。`fetch`/`commit` テストが skill-dir config 非依存であることを担保）。

### この変更でやらないこと

- 取得（fetch）・採点（per-paper 並列＋正規化）・描画（`render_digest.py`）・台帳（`commit_ledger.py` の CSV 列・追記専用）ロジックの変更。
- `scores.json` / `candidates.json` スキーマの変更。
- 責務境界の変更（`wiki/`・`raw/`・`schema.md` には触れない）。
- config のスキーマ（`defaults` / `themes[]` のキー）変更。フィールドは不変で、置き場所だけが変わる。
- スケジューラ連携・通知・arXiv 以外の取得元（v1 スコープ外）。

---

## 4. 詳細設計

### 4.1 ファイルレイアウト

```
skills/watch-paper/
  fetch_arxiv.py       # FETCH: config(data_dir) → watch-paper/candidates.json (network)
  render_digest.py     # RENDER: 不変（config 非依存）
  commit_ledger.py     # COMMIT: config(data_dir) の defaults.threshold をフォールバックに使用
  _common.py           # 共有: data_dir 解決 / config 解決＋ブートストラップ / ローカル日付 / 入力ローダ
  config.example.json  # 新規・同梱テンプレート（配布物）。「LLM agent」1 テーマ
  (config.json は削除 — 実設定は vault の watch-paper/config.json へ)

<cwd>/watch-paper/                 # 実行時データ dir（vault ルート配下・永続）
  config.json          # 実設定（初回に config.example.json からブートストラップ、以後ユーザー編集）
  candidates.json / scores.json / state/ / digests/   # 既存（不変）
```

### 4.2 `_common.py`（config 経路の変更）

現行:

```python
CONFIG_PATH = Path(__file__).parent / "config.json"   # skill-dir 固定（廃止）
```

変更後:

```python
TEMPLATE_PATH = Path(__file__).parent / "config.example.json"   # 同梱テンプレ（コピー元）

def config_path(data_dir):
    """実設定のパス: <data_dir>/config.json"""
    return Path(data_dir) / "config.json"

def ensure_config(data_dir):
    """実設定が無ければテンプレをコピーする。

    Returns (path, created):
      created=True  … テンプレをコピーして新規作成した（呼び出し側は停止すべき）
      created=False … 既存の config.json がある（そのまま読める）
    テンプレが読めない/コピーできない場合は OSError を送出（呼び出し側が rc=2）。
    """
    dst = config_path(data_dir)
    if dst.exists():
        return dst, False
    shutil.copyfile(TEMPLATE_PATH, dst)     # data_dir は setup_data_dir で mkdir 済み
    print(f"[watch-paper] created {dst} from template", file=sys.stderr)
    return dst, True
```

- `load_config(path)`・`resolve_data_dir`・`setup_data_dir`・`now_local_date`・`load_run_inputs` は不変。
- `import shutil` を追加。`_common.py` は引き続き stdlib のみ（`arxiv` 非依存）。
- `setup_data_dir` が `data_dir` 本体（`state/`・`digests/`）を作るため、`ensure_config` を呼ぶ時点で `data_dir` は存在する。

### 4.3 `fetch_arxiv.py`（ブートストラップ＋読み込み経路）

`main()` の config 取得部を差し替える:

```python
from _common import (TEMPLATE_PATH, config_path, ensure_config,
                     load_config, setup_data_dir)   # CONFIG_PATH は import しない
...
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
    print(f"[watch-paper] {cfg_path} を作成しました（テンプレート）。"
          f"テーマを編集してから再実行してください。", file=sys.stderr)
    return 0   # 例テーマのまま取得しない

try:
    config = load_config(cfg_path)
except (OSError, json.JSONDecodeError) as e:
    print(f"[watch-paper] FATAL: cannot read config {cfg_path}: {e}",
          file=sys.stderr)
    return 2

return _run_fetch_mode(data_dir, config)
```

- 取得ロジック（`run_fetch`・クエリ・カテゴリ/閾値/lookback・`candidates.json` 出力）は**完全に不変**。
- 起動コマンドも不変: `uv run --project . "<skill-dir>/fetch_arxiv.py"`。
- stderr のバナー `[watch-paper] data_dir = ...` は不変（SKILL の確認手順で使う）。初回はそれに続いて `created ...` と案内が出て停止する。

### 4.4 `commit_ledger.py`（config 経路の変更・非致命フォールバック）

現行は skill-dir の `CONFIG_PATH` を読み、失敗を rc=2 の致命扱いにしている。変更後:

```python
from _common import (config_path, load_config, load_run_inputs,
                     now_local_date, setup_data_dir)   # CONFIG_PATH は import しない
...
default_thr = 3
cfg_path = config_path(data_dir)
try:
    config = load_config(cfg_path)
    default_thr = int(config.get("defaults", {}).get("threshold", 3))
except (OSError, json.JSONDecodeError) as e:
    print(f"[watch-paper] WARN: config not read ({cfg_path}): {e}; "
          f"using default threshold {default_thr}", file=sys.stderr)
```

- `thresholds_by_theme(candidates_doc, default_thr)` 以降は不変。`candidates.json` は各テーマの `threshold` を持つため、`default_thr` はテーマに threshold が無い異例時のフォールバックにすぎず、致命扱いをやめても実害はない。
- 通常フロー（fetch → 採点 → render → commit）では config は既に存在するため、この WARN 経路には入らない。
- CSV 列・追記専用・`surfaced=score≥threshold`・候補外 ID 無視は**不変**。

### 4.5 `config.example.json`（同梱テンプレート）

「LLM agent」1 テーマ＋現状の `defaults`。厳密 JSON（コメント・末尾カンマ不可）。

```json
{
    "defaults": {
        "categories": ["cs.AI", "cs.CL", "cs.LG", "cs.MA"],
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
                "autonomous agent",
                "tool use",
                "agentic workflow"
            ],
            "anchors": [
                "ReAct",
                "Reflexion",
                "Toolformer",
                "AutoGPT"
            ]
        }
    ]
}
```

- `defaults` は現行 `config.json` と同一値。
- anchors/keywords は「LLM agent」領域の代表例（配布時の出発点・ユーザーが編集する前提）。

### 4.6 リポジトリからの config.json 削除 と .gitignore

- `skills/watch-paper/config.json`（個人テーマ）を **`git rm`** で削除する。実テーマは vault にコピー済み（§2）。git 履歴からは復元可能。
- `.gitignore`: 現状 `settings.local.json` / `.superpowers` / `__pycache__`。実行時データ dir `watch-paper/` はこのリポジトリ（vault ではない）には通常生成されないため、追加は必須ではない。ただしリポジトリ内でスクリプトを CWD 実行して生成された `watch-paper/` を誤コミットしないよう、防御的に **`/watch-paper/` を `.gitignore` に追加する**（config.json を含む実行時データがリポジトリに混ざるのを防ぐ）。

### 4.7 SKILL.md の変更

- **前提**（14〜15 行目付近）:
  - 「スクリプト…と `config.json` は**このスキル自身のディレクトリ**にある」を、「**スクリプトと `config.example.json`（テンプレート）はスキル自身のディレクトリ**（`<skill-dir>`）にある。**実設定 `config.json` は実行時データ dir `watch-paper/config.json`（CWD 配下・vault ルート）にあり、初回はテンプレートから自動生成される**」に更新。
  - `<skill-dir>/config.json` を参照している箇所（手順 2.1 の `scoring_concurrency` 読み取り）を **`watch-paper/config.json`** に修正。
- **手順1（取得）**: `fetch_arxiv.py` 実行後、初回は「`watch-paper/config.json` をテンプレートから作成し、取得せず終了する」旨と「テーマを編集して再実行する」案内が stderr に出ることを明記。既存設定があれば従来どおり `candidates.json` を生成。
- **生成ファイル/責務**: 「ランタイムデータは `watch-paper/` にのみ書く。スキルフォルダには書かない」は不変。config が `watch-paper/` 側に加わる点を反映。
- **ガードレール**: 変更なし（config の置き場所変更のみで、AI の手順制約は不変）。

### 4.8 README.md の変更

- **やること**（7 行目）: 「テーマ定義（`config.json`）」→「テーマ定義（`watch-paper/config.json`。初回はスキル同梱 `config.example.json` から自動生成）」。
- **生成ファイル表**（33〜40 行目）: `config.json`（vault 側・永続・ユーザー編集）を行として追加。「スキル本体」一覧（40 行目）から `config.json` を外し、`config.example.json` を加える。
- **テーマの編集**（44 行目〜）: 「`config.json` の `themes[]` を編集」→「`watch-paper/config.json` の `themes[]` を編集（初回実行で `config.example.json` から生成される）」。以降のキー説明は不変。
- **開発**: 設計正本リンクに本 spec を追加。

### 4.9 テストの変更

| ファイル | 内容 |
|---|---|
| `tests/test_common.py` | 追加: (a) `config_path(data_dir) == data_dir / "config.json"`。(b) `ensure_config`: config 不在の `tmp_path` で呼ぶと `created=True` かつ `config.json` が生成され中身がテンプレートと一致する。(c) 既存 config があるとき `created=False` かつ中身が変わらない（テンプレで上書きしない） |
| `tests/test_fetch_arxiv.py` | 変更なし（純ヘルパのみをテストしており skill-dir config に非依存）。念のため `CONFIG_PATH` 参照が無いことを確認 |
| `tests/test_commit_ledger.py` | 既存 CLI テスト（`--data-dir` にテスト用 `candidates.json`/`scores.json` を置く）に、**同じ `--data-dir` へ最小 `config.json` を置く**か、**config 不在でも rc=0（threshold=3 フォールバック）で通る**ことを確認。skill-dir config への依存を除去 |

テスト実行（不変）:

```
uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v
```

### 4.10 ファイル変更一覧（実装フェーズ）

| ファイル | 変更 |
|---|---|
| `skills/watch-paper/_common.py` | `CONFIG_PATH` 廃止。`TEMPLATE_PATH`・`config_path`・`ensure_config` 追加。`import shutil` |
| `skills/watch-paper/fetch_arxiv.py` | `setup_data_dir` 後に `ensure_config`。初回はコピー＋案内で rc=0 停止。既存は `load_config(config_path(...))` で従来取得 |
| `skills/watch-paper/commit_ledger.py` | config を `config_path(data_dir)` から読む。欠けても致命化せず threshold=3 フォールバック |
| `skills/watch-paper/config.example.json` | 新規。「LLM agent」1 テーマ＋現状 `defaults` |
| `skills/watch-paper/config.json` | 削除（`git rm`）。実テーマは vault へコピー済み |
| `.gitignore` | `/watch-paper/` を追加（実行時データの誤コミット防止） |
| `skills/watch-paper/SKILL.md` | 前提・`config.json` 参照・手順1 の初回挙動を更新 |
| `skills/watch-paper/README.md` | やること・生成ファイル表・スキル本体一覧・テーマ編集節・設計リンク更新 |
| `skills/watch-paper/tests/test_common.py` | `config_path`/`ensure_config` テスト追加 |
| `skills/watch-paper/tests/test_commit_ledger.py` | skill-dir config 非依存化（config を `--data-dir` に置く or フォールバック確認） |

---

## 5. 受け入れ基準（Acceptance Criteria）

1. `watch-paper/config.json` が無い状態で `fetch_arxiv.py` を実行すると、`config.example.json` が `watch-paper/config.json` にコピーされ、「作成した・編集して再実行」案内が stderr に出て、**取得せず rc=0 で終了**する（`candidates.json` を書かない）。
2. `watch-paper/config.json` が存在する状態では、`fetch_arxiv.py` はそれを読んで従来どおり `candidates.json` を生成する（取得・クエリ・カテゴリ/閾値/lookback 挙動は現行と同一）。
3. 実設定は `<cwd>/watch-paper/config.json`（`--data-dir` 指定時はその配下）から読まれ、skill-dir の `config.json` には依存しない。`_common.py` に skill-dir 固定の `CONFIG_PATH` が残っていない。
4. スキルフォルダには `config.example.json`（「LLM agent」1 テーマ＋現状 `defaults`・厳密 JSON）が同梱され、個人テーマ入りの `config.json` は含まれない。
5. `ensure_config` は config 不在時にテンプレをコピーして `created=True` を返し、既存時は上書きせず `created=False` を返す。
6. `commit_ledger.py` は `watch-paper/config.json` の `defaults.threshold` をフォールバックに使い、config が欠けても致命終了せず threshold=3 で追記する。CSV 列・追記専用・`surfaced=score≥threshold`・候補外 ID 無視は不変。
7. SKILL.md・README.md が新しい config 配置（実設定は `watch-paper/config.json`、同梱は `config.example.json`、初回ブートストラップ）を正しく記述する。
8. 取得・採点・描画・台帳のロジック、`scores.json`/`candidates.json` スキーマ、責務境界（wiki に触れない）は不変。
9. テストが `config_path`/`ensure_config` を検証し、fetch/commit のテストが skill-dir config に依存しない。既存の取得・描画・コミット挙動に回帰がない。

---

## 6. リスク・留意点

- **初回停止 UX**: 初回は「コピーして停止」するため、ユーザーは 2 回実行する（作成→編集→再実行）。案内文を stderr に明示し、SKILL の手順1 でも説明することで迷いを防ぐ。
- **既存ユーザーの移行**: すでに skill-dir 側 `config.json` で運用していたユーザーは、次回実行時に vault 側が無ければテンプレ（LLM agent）が生成される。作者本人は実テーマを vault にコピー済み（§2）。他の既存利用者向けには README に「旧 config を `watch-paper/config.json` にコピーすれば維持できる」を一文添える（任意）。
- **config を data_dir に置くことの同期**: `watch-paper/` は OneDrive 配下になりうる（既存 README の注意参照）。config.json も同期対象になるが、追記でなく単一ファイルの編集のため、複数端末同時編集時のみ競合しうる。既存の OneDrive 注意の範囲内。
- **commit の config 依存を残す判断**: `commit_ledger.py` は `default_threshold` のためだけに config を読む。将来的に candidates.json の threshold のみを信頼して config 依存を撤廃する余地はあるが、本 spec では「非致命フォールバック化」に留め、挙動の後方互換を優先する。
- **テンプレの陳腐化**: `config.example.json` の anchors/keywords は例であり、ユーザーが編集する前提。テンプレは最小（1 テーマ）に保ち、メンテコストを抑える。
