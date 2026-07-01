---
name: watch-paper
description: Watch arXiv for new papers across the themes defined in watch-paper/config.json, score each candidate 0–5 for relevance, and surface those at or above each theme's threshold into a dated digest. Evaluated papers (kept or dropped) are recorded in per-theme CSV ledgers and never re-scored. Use when the user wants to watch or track new papers, asks 新着論文を調べて／arXiv の新着／watch papers, or invokes /watch-paper.
---

# watch-paper

arXiv の新着を `watch-paper/config.json` のテーマごとに集め、関連度でスコアリングして「ダイジェスト」に抽出する定点観測スキル。決定的な処理は3つのスクリプト（`uv run`）が担う: **取得** `fetch_arxiv.py`、**ダイジェスト描画** `render_digest.py`、**台帳更新** `commit_ledger.py`。関連度判定・要約は LLM が担う。

## 前提

- ランタイムデータは CWD 配下 `watch-paper/` に書かれる
- スクリプト（`fetch_arxiv.py` / `render_digest.py` / `commit_ledger.py` / 共有 `_common.py`）と**設定テンプレート `config.example.json`** は**このスキル自身のディレクトリ**（起動時に表示されるスキルのベースディレクトリ）にある。以下 `<skill-dir>` と表記し、実行時の絶対パスを使う
- **実設定 `config.json` は実行時データ dir（CWD 配下 `watch-paper/config.json`）にある**。無い場合は初回の `fetch_arxiv.py` 実行時に `config.example.json` から自動生成される（後述）。テーマ編集はこの `watch-paper/config.json` に対して行う
- 実行には `uv` と `arxiv` 依存が要る（`uv run --project .` が env を自動 sync）

## 1. 取得（fetch_arxiv.py）

- CWD が意図した作業ディレクトリ（`watch-paper/` を作りたい場所）であることを確認する
- 実行日（`YYYY-MM-DD`）を取得する（bash: `date +%F` / PowerShell: `Get-Date -Format "yyyy-MM-dd"`。）。
- 取得スクリプトを実行する:

  ```
  uv run --project . "<skill-dir>/fetch_arxiv.py"
  ```

- stderr に `[watch-paper] data_dir = ...` が出る。これが **CWD 配下 `watch-paper/`** を指していることを確認する。別の場所を指していたら CWD が誤り → 正しい作業ディレクトリで実行し直す
- 非0終了・権限拒否・実行不能なら、stderr の理由を添えて**中止**する
- **初回（`watch-paper/config.json` が無いとき）**: スクリプトはテンプレートを `watch-paper/config.json` にコピーし、stderr に `created ... from template` と `edit the themes ... and re-run` を出して**取得せず終了する（rc=0）**。この場合はユーザーに「`watch-paper/config.json` のテーマを編集して再実行」を促し、手順を中断する
- 生成された `watch-paper/candidates.json` を読む

## 2. スコアリング（テーマごと・1論文1サブエージェントで並列採点）

`candidates.json` の各テーマについて、`candidates[]` の各論文を採点する。`new` が 0 のテーマ、および `error` を持つテーマ（取得失敗）はサブエージェントを起動しない（手順3で「該当なし」/「取得失敗」として残す）。

採点は **1論文=1サブエージェント**で並列に行い、その後メイン（あなた）が**テーマ内で正規化**する。

### 2.1 並列ディスパッチ

- 同時実行の上限 `K` を決める: `watch-paper/config.json` の `defaults.scoring_concurrency` を読む
- enabled かつ `new>0` の各テーマの各候補について、**1候補=1サブエージェント**を起動する。同時に走らせるのは最大 `K` 件とし、波状にキューを消化する（常時最大 `K` 件が走る状態を保ち、1 件完了するたびに次の候補を1 件起動する。K 件まとめて終わるのを待たない。）
- サブエージェントにはツールを与えず、採点に必要な情報を**すべてプロンプトに内包**する（隔離・安価）
- 各サブエージェントは **Sonnet** で起動する（サブエージェント起動時に `model` へ `sonnet` を指定）

各サブエージェントへ渡すプロンプトに含める内容:

- テーマの `name` / `anchors`（同種の仕事の代表例）/ `threshold`
- 関連度ルーブリック（0〜5）:
  - **5**: 一致。アンカーと同種のシステム/手法/問題設定
  - **4**: 強く関連。隣接サブ問題・主要構成要素・明確な発展
  - **3**: 関連あり。応用・部分的に主題を扱う（採用閾値の既定）
  - **2**: 周辺。キーワードは当たるが主題が異なる
  - **0–1**: 無関係。キーワードの誤ヒット
- 候補1件: `arxiv_id` / `title` / `abstract` / `authors` / `published` / `primary_category` / `link`
  - 関連度の判断に使うのは `title` と `abstract`。他フィールド（`arxiv_id` / `authors` / `published` / `primary_category` / `link`）は返却の突き合わせと引用のために渡す
- ガードレール: 「要約・なぜ気になるかは**アブストの範囲で書き、性能数値や主張を捏造しない**」

各サブエージェントには、**次の JSON オブジェクトだけを返す**よう指示する:

```json
{
  "arxiv_id": "<候補の arxiv_id>",
  "score": 0,
  "summary_ja": "一言要約（日本語1〜2文）",
  "why_ja": "なぜ気になるか（1行）",
  "rationale": "このスコアの理由・どのアンカー/バンドに当たるか（1行）",
  "confidence": "low|med|high"
}
```

`score` は 0〜5 の整数。`rationale`/`confidence` は次の正規化パス用（ダイジェストには出さない）。返却を `arxiv_id` で候補に突き合わせる。

### 2.2 正規化パス（テーマ内のみ）

サブの暫定スコアを、メイン（あなた）が**テーマごとに**較正する。テーマ間は混ぜない（anchors が異なり 0〜5 はテーマ相対のため）。

- テーマ内の全候補を暫定スコア順に並べる
- **境界事例**を重点的に見直す: `threshold` 周辺の境目（既定 `threshold=3` なら 2/3 と 3/4）と、`confidence: low` の候補
- 境界事例・低 confidence 以外の候補は、原則サブエージェントの暫定スコアをそのまま採用する（全件を再採点しない）
- 対象候補の `abstract`（`candidates.json`）を読み直し、各サブの `rationale` を材料に、横並びの一貫性が出るようスコアを調整する。これは**再採点ではなく較正**
- `summary_ja`/`why_ja` は原則サブの出力を採用し、明らかな誤りのみ軽修正する
- 較正後、採点した**全件**を enriched 形式 `{ "<theme-id>": { "<arxiv_id>": { "score": <0-5>, "summary_ja": "...", "why_ja": "..." } } }` で `watch-paper/scores.json` に書き出す（合否問わず全件。`render_digest.py` と `commit_ledger.py` の共通入力）
- 調整した件数を覚えておき手順5で報告する

### 2.3 フォールバック

サブエージェントが失敗した／返ってきた JSON が壊れている／スキップされた候補は、**あなた自身が同じルーブリックでその1件をインライン採点する**（取りこぼして台帳から漏らさない）。フォールバックした件数を覚えておき手順5で報告する。

## 3. ダイジェストを描画（render_digest.py）

抽出（`threshold` 以上のフィルタ）・降順ソート・件数集計・Markdown 整形は**スクリプトが決定的に行う**。手作業で並べ替え・数え上げ・転記をしない。

```
uv run --project . "<skill-dir>/render_digest.py" "watch-paper/scores.json"
```

- 入力は `watch-paper/scores.json`（手順2で書いた enriched 形式）と `watch-paper/candidates.json`出力は `watch-paper/digests/<実行日>.md`（日付はスクリプトが導出）
- stderr にテーマ別 `evaluated` / `surfaced` 件数が出る（手順5の報告でこれを引用する）
- 再実行は同名ダイジェストを上書きする（冪等）。既存の同名ファイルを意図せず壊したくない場合は、実行前にユーザーへ確認する
- `threshold` 以上のみ・スコア降順（同点は新しい投稿が上）。スコア5は `⭐5`、他は素の数値
- 取得失敗テーマ（候補に `error`）は `- 取得失敗: <error>` と明記。`new=0` テーマは `- 該当なし`

## 4. 台帳にコミット（commit_ledger.py）

`watch-paper/scores.json`をコミットする:

```
uv run --project . "<skill-dir>/commit_ledger.py" "watch-paper/scores.json"
```

これで各テーマの `watch-paper/state/seen-<theme-id>.csv` に `arxiv_id,score,title,evaluated,surfaced` が追記される（surfaced=score≥threshold、evaluated=実行日）。`candidates.json` に無い ID は無視される。`commit_ledger.py` は `.score` のみ参照する（`summary_ja`/`why_ja` は無視）。台帳は**追記専用**なので**1回だけ**実行する。

## 5. 報告

- テーマごとの「評価件数 / 抽出件数」（`render_digest.py` の stderr 出力を引用。数え直さない）。
- 各テーマの上位ピック（タイトル＋スコア）を数件
- 生成したダイジェストのパス（`watch-paper/digests/<実行日>.md`）
- スキップ/エラー（取得失敗テーマ、権限拒否等）
- フォールバック採点した件数（サブエージェント失敗時）

## ガードレール（要点。詳細は各手順を参照）

- ランタイムデータは CWD 配下 `watch-paper/` にのみ書く
- 要約・「なぜ気になるか」はアブストの範囲で書く（アブストに無い性能数値・主張を足さない）
- 日付は `render_digest.py` が導出する（手順1の実行日確認以外でハードコードしない）
- 台帳 CSV は **`commit_ledger.py` 経由でのみ**更新する（追記専用・1回だけ）。AI が誤って弾いた論文を拾い直したいときは `state/seen-<theme>.csv` の該当行を手で削除すれば次回再評価される
- 取得に失敗したテーマがあっても中止せず、他テーマを続行・報告する
- 同テーマ・複数テーマに該当する論文は各テーマのセクションに重複して載りうる（仕様）
- サブエージェント採点に失敗した候補は必ずメインがインライン採点し、台帳から漏らさない（漏れると次回再評価でトークンを無駄にする）

前提（uv/arxiv 依存）・生成ファイル一覧・テーマ編集の詳細は `README.md` を参照。
