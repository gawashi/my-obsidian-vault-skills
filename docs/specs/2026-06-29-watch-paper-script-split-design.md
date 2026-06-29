# 設計: watch-paper の決定的処理を単一責務スクリプトに分割し、ダイジェスト描画をスクリプト化

- **日付**: 2026-06-29
- **ステータス**: 承認待ち（実装計画フェーズ手前）
- **対象**: `skills/watch-paper/`。現状 AI（メインエージェント）が手作業で行っている**抽出（閾値フィルタ＋降順ソート）とダイジェスト Markdown 生成**をスクリプトに移し、あわせて `fetch_arxiv.py` に同居している **fetch と commit の2責務を単一責務スクリプトに分割**する。
- **元 spec**: `docs/specs/2026-06-28-paper-watch-skill-design.md`（取得・台帳・責務境界）、`docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`（並列採点）。本書はそれらの **ステップ3（抽出）・ステップ4（ダイジェスト描画）・スクリプト構成・`scores.json` 契約** を上書きする差分。採点（per-paper 並列＋正規化）・取得ロジック・台帳 CSV 列・責務境界（wiki に触れない）は不変。

---

## 1. 背景・動機

現状の責務分担:

| ステップ | 担当 | 本質的に AI が要るか |
|---|---|---|
| 1. 取得 → `candidates.json` | `fetch_arxiv.py` | — （既にスクリプト） |
| 2. 採点（0〜5 ＋ `summary_ja`/`why_ja`） | AI サブエージェント | ✅ 要る（関連度判断） |
| 2.2 正規化（較正） | AI メイン | ✅ 要る |
| **3. 抽出（閾値フィルタ・降順ソート）** | **AI メイン** | ❌ **純粋なロジック** |
| **4. ダイジェスト Markdown 生成** | **AI メイン** | ❌ **ほぼテンプレート描画** |
| 5. 台帳コミット | `fetch_arxiv.py --commit` | — （既にスクリプト） |
| 6. 報告（件数） | AI メイン | 一部（件数は導出可能） |

問題意識（ユーザー報告）:

- ステップ3・4は AI が手作業でやっているが、**採点結果（score・summary_ja・why_ja）と `candidates.json` のメタデータを結合するだけの決定的処理**である。AI が手で並べ替え・閾値判定・件数集計・`arxiv_id`/`title`/`category`/`published`/`authors`/`link` の Markdown への転記を行うのは**トークンが重く、ミスを生みやすい**（件数の数え間違い・ソート崩れ・転記ドリフト）。
- さらに `fetch_arxiv.py` が **fetch と commit の2責務を `--commit` フラグで分岐**して同居しており、責務が過剰。ここにダイジェスト描画まで足すのは設計として誤り。**フラグ分岐ではなくスクリプト自体を分ける**べき。

要望: **AI を使わずスクリプト実行で済む処理（抽出＋ダイジェスト描画）を最適化し、`fetch_arxiv.py` の責務過多を単一責務スクリプトへの分割で解消する。**

---

## 2. 確定した決定事項

| 論点 | 決定 |
|---|---|
| 最適化対象 | **抽出（ステップ3）＋ダイジェスト描画（ステップ4）をスクリプト化**。採点・要約生成・正規化は AI のまま |
| 分割方式 | **`--render`/`--commit` のフラグ分岐ではなく、スクリプト自体を単一責務に分ける**（ユーザー判断） |
| スクリプト構成 | `fetch_arxiv.py`（fetch のみ）／`render_digest.py`（描画・新規）／`commit_ledger.py`（commit・`fetch_arxiv.py` から移設）／`_common.py`（共有プラミング） |
| `scores.json` スキーマ | `{theme: {id: score}}` → **`{theme: {id: {score, summary_ja, why_ja}}}`** に拡張。render は3フィールド、commit は `.score` のみ参照 |
| ダイジェスト書式の正本 | SKILL.md の散文 → **`render_digest.py` のテンプレート**（単一の正本）。SKILL/README には短い参照例のみ残す |
| 日付の扱い | render が `now_local_date()` で `<today>` を自前導出（AI は日付を扱わない） |
| 件数の出所 | render が `evaluated`/`surfaced` を計算し stderr に出力。AI の報告（ステップ6）はそれを引用（数え直さない） |
| 冪等性 | render は冪等（同名ダイジェストを上書き、再実行安全）。commit は追記専用（1回のみ）。両者を別スクリプトにすることで再描画と再コミットを独立させる |
| 共有方式 | 重複 ~12 行を3スクリプトに複製せず `_common.py` に集約（`resolve_data_dir`/`load_config`/`now_local_date`/バナー＋mkdir） |

---

## 3. スコープ

### この変更でやること

1. `fetch_arxiv.py` を **fetch 専用**に縮約（`_run_commit_mode`・commit 系ヘルパを移設、`--commit` フラグ廃止）。
2. **`commit_ledger.py`**（新規・実体は移設）: `scores.json` ＋ `candidates.json` → `state/seen-<theme>.csv` 追記。
3. **`render_digest.py`**（新規）: `scores.json` ＋ `candidates.json` → `digests/<today>.md` を決定的に描画。`evaluated`/`surfaced` を計算し stderr に出力。
4. **`_common.py`**（新規）: 共有プラミング（data_dir 解決・config 読み込み・ローカル日付・バナー＋ディレクトリ作成）。
5. `scores.json` スキーマを `{theme: {id: {score, summary_ja, why_ja}}}` に拡張。
6. SKILL.md を更新（ステップ3削除、ステップ4を「enriched scores.json を書く→`render_digest.py`」に、ステップ5を `commit_ledger.py` に、ステップ6を「render の stderr 件数を引用」に、ガードレールの日付項を緩和）。
7. README を更新（スクリプト構成・生成ファイル・`scores.json` スキーマ）。
8. テストを分割（`test_fetch_arxiv.py` を縮約、`test_commit_ledger.py` に commit テスト移設、`test_render_digest.py` 新規、必要なら `test_common.py`）。

### この変更でやらないこと

- 採点ロジック（per-paper 並列＋正規化）の変更。`summary_ja`/`why_ja` を返す既存のサブエージェント I/O 契約は不変（メインが集約時に enriched `scores.json` に書く点のみ変わる）。
- 取得（fetch）の挙動・クエリ・カテゴリ/閾値/lookback ロジックの変更。
- 台帳 CSV の列（`arxiv_id,score,title,evaluated,surfaced`）・追記専用・`surfaced=score≥threshold` 算出の変更。
- 責務境界の変更（`wiki/`・`raw/`・`schema.md` には引き続き触れない）。
- スケジューラ連携・通知・arXiv 以外の取得元（v1 スコープ外）。

---

## 4. 詳細設計

### 4.1 スクリプト構成（ファイルレイアウト）

```
skills/watch-paper/
  fetch_arxiv.py     # FETCH のみ:  config.json        → watch-paper/candidates.json   (network)
  render_digest.py   # RENDER のみ: candidates + scores → watch-paper/digests/<date>.md (新規)
  commit_ledger.py   # COMMIT のみ: candidates + scores → state/seen-<theme>.csv (追記)
  _common.py         # 共有: resolve_data_dir / load_config / now_local_date / バナー＋mkdir
```

各スクリプトは `uv run --project . "<skill-dir>/<script>.py"` で起動。`tests/conftest.py` が `skills/watch-paper` を import パスに追加済みのため、各スクリプトは兄弟 `_common` を import できる。

### 4.2 `_common.py`（共有プラミング）

`fetch_arxiv.py` から以下を移設・集約する（現行と同一挙動）:

- `resolve_data_dir(arg_data_dir)` — `--data-dir` 指定 or `<cwd>/watch-paper`。
- `load_config(path)` ＋ `CONFIG_PATH`（`<skill-dir>/config.json`）。
- `now_local_date()` — ローカル日付 `YYYY-MM-DD`。
- `setup_data_dir(args_data_dir)` — data_dir を解決し、`[watch-paper] data_dir = ...` バナーを stderr に出し、`state/`・`digests/` を mkdir する共通前処理。失敗時は `FATAL` を出して例外（各 main が rc=2 を返す）。
- `load_run_inputs(data_dir, scores_path)` — `scores.json` と `candidates.json` を読み、`(candidates_doc, scores)` を返す共通ローダ（render と commit が共用）。読めなければ `FATAL` を stderr に出して None を返す（呼び出し側が rc=2）。

> `_common.py` は「共有 I/O プラミング」という単一責務を持つ。3スクリプトに ~12 行を複製してロジックがドリフトする事故を防ぐ。

### 4.3 `fetch_arxiv.py`（fetch 専用に縮約）

- **入力**: `config.json`。**出力**: `watch-paper/candidates.json`。ネットワークあり。
- 残すもの: `base_arxiv_id`・`effective_categories`・`effective_threshold`・`build_query`・`lookback_days`・`cutoff_datetime`・`read_seen_ids`・`run_fetch`・`_run_fetch_mode`。
- 取り除くもの: `_run_commit_mode`・`titles_by_theme`・`thresholds_by_theme`・`commit_scores`・`CSV_HEADER`・`--commit` 引数。
- `setup_data_dir`/`load_config`/`CONFIG_PATH` は `_common` から import（`now_local_date`/`load_run_inputs` は不要 — fetch は内部で UTC の `datetime.now(timezone.utc)` を使い `generated` に入れる、現行どおり）。
- `main()`: `--data-dir` のみ。`_common.setup_data_dir()` → `load_config` → `run_fetch` → `candidates.json` 書き出し → stderr に `wrote ... (themes, new)`。
- 起動コマンド（不変）: `uv run --project . "<skill-dir>/fetch_arxiv.py"`。
- 名前が実態（fetch のみ）と一致するようになる。

### 4.4 `commit_ledger.py`（commit を移設）

- **入力**: `scores.json` ＋ `candidates.json`。**出力**: `state/seen-<theme>.csv` 追記。
- `fetch_arxiv.py` から移設: `titles_by_theme`・`thresholds_by_theme`・`commit_scores`・`CSV_HEADER`、および `_run_commit_mode` 相当のロジック。
- **`scores.json` の新スキーマ対応**: `commit_scores` 内のスコア取得を `score = entry["score"] if isinstance(entry, dict) else int(entry)` とし、enriched 形式（dict）を主、素の int を後方互換として許容する。それ以外の挙動（タイトル突き合わせ・`surfaced=score≥threshold`・追記専用・ヘッダ書き込み・候補に無い ID 無視）は**完全に不変**。
- `main(argv)`: 位置引数 `scores_json`（必須）＋ `--data-dir`。`_common.setup_data_dir()` → `_common.load_run_inputs()` → `load_config`（既定 threshold 用）→ `commit_scores` → stderr に `committed N rows: {...}`。
- 起動コマンド: `uv run --project . "<skill-dir>/commit_ledger.py" "watch-paper/scores.json"`。
- CSV 列・追記専用・コミットフローは**不変**。

### 4.5 `render_digest.py`（新規・描画）

**入力**: `scores.json`（enriched）＋ `candidates.json`。**出力**: `digests/<today>.md`。ネットワークなし。冪等（上書き）。

**描画ロジック（純関数として実装・単体テスト対象）**:

`build_digest(candidates_doc, scores, today)` → Markdown 文字列。

`candidates.json` のテーマ順に走査し、各テーマで:

1. テーマの `name` / `threshold` / `new` / `error` を取得。
2. **評価レコード**を構築: `theme.candidates[]` の各候補について、`scores[theme_id][arxiv_id]` があれば `{arxiv_id, title, link, primary_category, published, authors, score, summary_ja, why_ja}` を作る（scores に無い候補はスキップ）。
3. `evaluated = len(評価レコード)`。
4. `surfaced_records = [r for r in レコード if r.score >= threshold]`。
5. ソートキー **`(score 降順, published 降順)`** で `surfaced_records` を並べる（同点は新しい投稿を上に）。
6. `surfaced = len(surfaced_records)`。

**Markdown 書式（現行 SKILL.md の例を踏襲。正本はこの関数）**:

```markdown
---
generated: <today YYYY-MM-DD>
themes:
  - id: <theme-id>
    evaluated: <N>
    surfaced: <M>
---

# 論文ウォッチ <today>

## <theme name>  （評価<evaluated> / 抽出<surfaced>）

### ⭐5 — [Title](link)
- arXiv: <arxiv_id> ｜ <primary_category> ｜ <published>
- 著者: <authors を最大 MAX_AUTHORS 名、超過時は末尾に「…」>
- 要約: <summary_ja>
- なぜ気になるか: <why_ja>

### 4 — [Another Title](link)
- …
```

- 見出し: `score == 5` のみ `⭐5`、それ以外は素の数値（`### 4 — …`）。現行例の挙動を踏襲。
- `error` を持つテーマ: 見出し下に `- 取得失敗: <error>`（`evaluated 0 / 抽出 0`）。
- `surfaced == 0`（かつ error なし）: `- 該当なし`。
- 著者: `MAX_AUTHORS`（既定 6）を超えたら先頭 6 名＋`…`。digest の肥大化防止。
- `generated` と見出しの日付・ファイル名はすべて `today`（`_common.now_local_date()`）。

**`main(argv)`**: 位置引数 `scores_json`（必須）＋ `--data-dir`。`_common.setup_data_dir()` → `_common.load_run_inputs()` → `now_local_date()` → `build_digest()` → `digests/<today>.md` 書き出し（上書き）→ stderr に件数サマリ:

```
[watch-paper] rendered watch-paper/digests/2026-06-29.md (themes=2, evaluated=12, surfaced=4)
[watch-paper]   auto-sci-discovery: evaluated=12 surfaced=4
[watch-paper]   industrial-anomaly-detection: evaluated=0 surfaced=0
```

- 起動コマンド: `uv run --project . "<skill-dir>/render_digest.py" "watch-paper/scores.json"`。
- 同名ダイジェストの上書き確認は **SKILL レベル**で行う（render 自体は黙って上書き。再描画を安全にするため冪等を優先）。

### 4.6 `scores.json` スキーマ（拡張・共有契約）

```json
{
  "<theme-id>": {
    "<arxiv_id>": { "score": 4, "summary_ja": "…", "why_ja": "…" }
  }
}
```

- `score`: 0〜5 の整数。`summary_ja`/`why_ja`: 採点サブの出力（正規化後にメインが確定）。
- `render_digest.py` は3フィールドすべてを使う。`commit_ledger.py` は `.score` のみ参照。
- 後方互換: commit は素の int も許容（4.4）。render は dict 前提（描画に summary/why が必須のため）。
- メインエージェントは採点・正規化後にこの形で `watch-paper/scores.json` を書く（従来は score だけだった）。

### 4.7 SKILL.md の変更

- 冒頭: 「決定的な取得・**描画**・台帳更新は3つのスクリプト（`fetch_arxiv.py`/`render_digest.py`/`commit_ledger.py`）が担い、関連度判定・要約は LLM が担う」に更新。
- ステップ1（取得）: 不変（`fetch_arxiv.py`）。
- ステップ2（採点）: 不変。ただし 2.2 末尾の「`scores.json` への書き出し」を **enriched 形式**（`{theme:{id:{score,summary_ja,why_ja}}}`）に更新。サブの返却 JSON は既に `summary_ja`/`why_ja` を含むため I/O 契約は不変。
- ステップ3（抽出）: **削除**（render が閾値フィルタ＋降順ソートを担う）。
- ステップ4（ダイジェスト）: 「enriched `scores.json` を `watch-paper/scores.json` に書く → `uv run --project . "<skill-dir>/render_digest.py" "watch-paper/scores.json"` を実行」に置換。書式の散文は短い参照例に縮約し「描画はスクリプトが決定的に行う」と明記。同名ダイジェストがあれば上書き前に確認（再描画は安全だが二重生成の注意喚起）。
- ステップ5（コミット）: `uv run --project . "<skill-dir>/commit_ledger.py" "watch-paper/scores.json"` に置換。
- ステップ6（報告）: `evaluated`/`surfaced` は **render の stderr を引用**（数え直さない）。
- ガードレール: 「日付はハードコードしない」を「日付は各スクリプトが導出する（AI はダイジェストの日付を扱わない）」に緩和。「ランタイムデータは `watch-paper/` のみ」「台帳は commit 経由でのみ更新」は不変。

### 4.8 README の変更

- 「やること」のスクリプト列挙を3スクリプト構成に更新。
- 生成ファイル表に変更なし（`candidates.json`/`scores.json`/`state/seen-*.csv`/`digests/*.md`）。ただし `scores.json` の「性質」を enriched スキーマ（score＋summary_ja＋why_ja）に更新。
- スクリプト単体動作確認の例に `render_digest.py`・`commit_ledger.py` を追記。
- 開発セクションの設計正本リンクに本 spec を追加。

### 4.9 テストの変更

| ファイル | 内容 |
|---|---|
| `tests/test_fetch_arxiv.py` | fetch 系ヘルパ（`base_arxiv_id`/`build_query`/`effective_*`/`lookback_days`/`cutoff_datetime`/`read_seen_ids`）。commit テストは移設して削る |
| `tests/test_commit_ledger.py` | 移設した commit テスト（`titles_by_theme`/`thresholds_by_theme`/`commit_scores`/CLI commit）＋ **enriched `scores.json`（dict 形式）からの score 取得** と **素 int 後方互換** の追加ケース |
| `tests/test_render_digest.py` | 新規。`build_digest` のゴールデン的検証: 件数（evaluated/surfaced）・降順ソート・⭐5 接頭・`該当なし`・`取得失敗: <error>`・著者トランケート・frontmatter の themes リスト・タイトルの特殊文字（カンマ等）が壊れない |
| `tests/test_common.py` | 任意。`resolve_data_dir`/`now_local_date` の最小確認（既存 `resolve_data_dir` テストの移設で足りる） |

テスト実行（不変）:

```
uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v
```

### 4.10 ファイル変更一覧（実装フェーズ）

| ファイル | 変更 |
|---|---|
| `skills/watch-paper/fetch_arxiv.py` | fetch 専用に縮約。commit 系を `commit_ledger.py` へ移設、`--commit` 廃止、共有を `_common` から import |
| `skills/watch-paper/_common.py` | 新規。共有プラミング |
| `skills/watch-paper/render_digest.py` | 新規。ダイジェスト描画 |
| `skills/watch-paper/commit_ledger.py` | 新規。commit 移設＋ enriched スキーマ対応 |
| `skills/watch-paper/SKILL.md` | ステップ3削除、4を render 化、5を commit_ledger 化、6を stderr 引用、2.2 を enriched scores.json に、ガードレール緩和 |
| `skills/watch-paper/README.md` | スクリプト構成・`scores.json` スキーマ・動作確認例・設計リンク更新 |
| `skills/watch-paper/tests/*` | fetch/commit/render に分割。render テスト新規 |

---

## 5. 受け入れ基準（Acceptance Criteria）

1. `fetch_arxiv.py` は fetch のみを行い、`--commit` フラグと commit 系コードを持たない。`candidates.json` の出力挙動は現行と同一。
2. `commit_ledger.py` が `scores.json`＋`candidates.json` を入力に台帳 CSV へ追記し、列（`arxiv_id,score,title,evaluated,surfaced`）・`surfaced=score≥threshold`・追記専用・候補外 ID 無視が現行と同一。enriched（dict）と素 int の両 `scores.json` 形式を受理する。
3. `render_digest.py` が `scores.json`＋`candidates.json` から `digests/<today>.md` を決定的に生成し、閾値フィルタ・`(score 降順, published 降順)` ソート・`evaluated`/`surfaced` 計算・⭐5 接頭・`該当なし`・`取得失敗: <error>`・著者トランケートを行う。再実行で同名ファイルを上書きできる（冪等）。
4. `render_digest.py` が `evaluated`/`surfaced` をテーマ別に stderr へ出力し、SKILL のステップ6 はそれを引用する（AI は件数を数え直さない）。
5. `scores.json` は `{theme:{id:{score,summary_ja,why_ja}}}` 形式で、render が3フィールド・commit が `.score` を参照する。
6. 日付（`generated`・ファイル名・見出し）は `render_digest.py` が `now_local_date()` で導出し、AI はダイジェストの日付を扱わない。
7. `_common.py` に `resolve_data_dir`/`load_config`/`now_local_date`/バナー＋mkdir/入力ローダが集約され、3スクリプトが import する。
8. 採点（per-paper 並列＋正規化）・取得ロジック・台帳 CSV 列・責務境界（wiki に触れない）は不変。
9. テストが fetch/commit/render に分割され、`render_digest.py` の描画ロジック（件数・ソート・各表記・著者トランケート・特殊文字）が単体テストで検証される。既存の取得・コミット挙動の回帰がない。

---

## 6. リスク・留意点

- **`scores.json` スキーマ変更の波及**: commit が旧 `{theme:{id:score}}` を前提にしていた。dict/int 両対応で後方互換を確保し、テストで両形式を固定する。
- **描画書式の正本移動**: 書式が散文（SKILL.md）から Python（`render_digest.py`）へ移る。書式変更は今後コード編集になるが、テンプレートは小さく、`build_digest` の単体テストがゴールデンとして機能する。SKILL/README には短い参照例のみ残し乖離を防ぐ。
- **共有モジュール導入**: `_common.py` への import 依存が増える。`conftest.py` が import パスを通すためテストは問題なし。実行時も `uv run <script>` がスクリプトのディレクトリを `sys.path[0]` に入れるため兄弟 import は解決する。
- **冪等性とコミットの非対称**: render は冪等・commit は追記専用。両者を別スクリプトにすることで「ダイジェストだけ作り直す」が CSV を二重追記せず安全に行える。commit を 2 回叩くと二重追記する点は現行同様で、SKILL が「1回のみ」を明示する。
- **トークン削減効果**: AI がメタデータを Markdown へ転記しなくなり、抽出・件数集計・ソートも手放すため、ダイジェスト生成のトークンとミス（数え間違い・転記ドリフト）が削減される。AI に残るのは採点・要約・正規化という不可分の判断のみ。
