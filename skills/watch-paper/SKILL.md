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
