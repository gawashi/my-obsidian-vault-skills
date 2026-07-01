# watch-paper — README

arXiv の新着論文をテーマ別に定点観測し、関連度ダイジェストを生成する Claude Code スキル。

## 概要

設定したテーマで arXiv 新着を取得 → 各論文を関連度 0〜5 で採点 → 閾値以上を日付き Markdown ダイジェストに抽出する。評価済みはテーマ別 CSV 台帳に記録し、再採点しない。

## 前提

- `uv`がインストール済み
- 実行する作業ディレクトリ（CWD）が uv プロジェクト（`pyproject.toml`）であること。`arxiv` を追加する
- このスキルは **作業ディレクトリ（CWD）で起動した Claude** で実行する（ランタイムデータは CWD 配下 `watch-paper/` に書かれる）。

## 手動実行

1. Claude を作業ディレクトリ（CWD）で起動する。
2. `/watch-paper` を実行（または「新着論文を調べて」等）。

## 生成されるファイル（すべて CWD 配下 `watch-paper/`）

| ファイル | 性質 |
|---|---|
| `config.json` | 永続・ユーザー編集。テーマ定義（初回に `config.example.json` から生成）。列/キーは `defaults` と `themes[]` |
| `candidates.json` | 一時（毎回上書き）。取得結果 |
| `scores.json` | 一時（毎回上書き）。LLM の採点結果 `{theme:{id:{score,summary_ja,why_ja}}}` |
| `state/seen-<theme>.csv` | 永続・追記専用。評価台帳（弾いた論文もタイトル・スコア付きで残る） |
| `digests/YYYY-MM-DD.md` | 永続。ダイジェスト本体 |

## テーマの編集

観測するテーマは `watch-paper/config.json` で決める。**初回に `fetch_arxiv.py` を実行すると、同梱の `config.example.json` からこのファイルが自動生成される**（このときは取得せずに終了する）。生成されたら、下記を参考に `themes[]` を自分の関心事に書き換えて、もう一度実行する。

`config.json` は 2 つのブロックからなる。

- `defaults` … 全テーマ共通の既定値。
- `themes[]` … テーマの配列。**1 テーマ = 1 オブジェクト**。ここを増やす／書き換えるのが基本の作業。

### テーマを追加する

`themes[]` の `[ ... ]` の中に、次のブロックを追加する。`id` はテーマごとに重複しない値にする。

```json
{
    "id": "llm-agent",
    "name": "LLM agent",
    "enabled": true,
    "keywords": ["LLM agent", "language model agent", "agentic workflow"],
    "anchors": ["ReAct", "AutoGPT"]
}
```

### `themes[]` の項目

| キー | 要否 | 意味・書き方 |
|---|---|---|
| `id` | 必須 | テーマの識別子。台帳ファイル名 `state/seen-<id>.csv` に使う。**一意・英数字/ハイフン推奨**。後から変えると別テーマ扱いになり過去分を再評価してしまうので、最初に決める |
| `name` | 推奨 | 表示名（ダイジェストの見出し）。省略すると `id` が使われる |
| `keywords` | 必須 | arXiv アブストの検索語。フレーズごとに `abs:"..."` で OR 検索する。ここで候補を絞り込むので、拾いたい語を具体的に並べる |
| `anchors` | 推奨 | 関連度採点の基準例（代表的な手法・システム名）。検索クエリには使わず、LLM が「このテーマらしさ」を判断する基準に使う。充実させるほど採点が安定する |
| `enabled` | 任意 | `false` にするとそのテーマをスキップ（消さずに一時停止できる）。省略時 `true` |
| `categories` | 任意 | arXiv カテゴリで絞る。未指定なら `defaults.categories` を継承する。`[]`（空配列）にすると絞りを外し、全分野をキーワードだけで検索する |
| `threshold` | 任意 | このテーマだけ採用閾値を変える（未指定なら `defaults.threshold`） |
| `lookback_days` / `first_run_lookback_days` | 任意 | このテーマだけ遡り日数を変える（未指定なら `defaults` を継承） |

### `defaults` の項目（全テーマ共通の既定値）

| キー | 既定 | 意味 |
|---|---|---|
| `categories` | `["cs.AI","cs.CL","cs.LG"]` | テーマが `categories` を指定しないときの絞り込み対象 |
| `threshold` | `3` | 採用閾値。関連度が **この値以上（0〜5）** の論文だけダイジェストに出す |
| `lookback_days` | `14` | 2 回目以降の実行で、何日前まで遡って新着を見るか |
| `first_run_lookback_days` | `60` | 台帳が空（初回）のときに遡る日数。最初にまとめて拾う用 |
| `max_results` | `120` | 1 テーマあたり arXiv から取る最大件数 |
| `request_delay_seconds` | `3` | arXiv へのリクエスト間隔（秒）。レート制限対策 |
| `scoring_concurrency` | `6` | 採点サブエージェントの同時実行数。候補が多い日のコスト/レートを抑えたければ下げる |
