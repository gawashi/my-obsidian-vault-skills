# watch-paper — README

arXiv の新着論文をテーマ別に定点観測し、関連度ダイジェストを生成する Claude Code スキル。

## これは何か / 何でないか

- **やること**: テーマ定義（`config.json`）に基づき arXiv 新着を取得 → LLM が 0〜5 で関連度採点 → 閾値以上を `watch-paper/digests/YYYY-MM-DD.md` に抽出。評価済みは合否問わず `watch-paper/state/seen-<theme>.csv` に記録。
- **やらないこと**: `wiki/` への Ingest・通知・スケジューラ連携・arXiv 以外の取得元（v1 スコープ外）。Ingest は Obsidian でダイジェストを見て手動で行う。

## 前提

- `uv`（Astral）がインストール済み。
- vault が uv プロジェクト（`pyproject.toml`、`requires-python >=3.13`）であること。依存 `arxiv` を追加する: **vault ルートで** `uv add arxiv`（初回のみ。以後 `uv run` が自動 sync）。
- このスキルは **vault ルートで起動した Claude** で実行する（ランタイムデータは CWD 配下 `watch-paper/` に書かれる）。
- **TLS 傍受プロキシ環境（Zscaler 等）の場合**: ① プロキシを通す（`HTTPS_PROXY`/`HTTP_PROXY` を設定。環境変数はプロセス起動時に読まれるので、設定後はホストアプリを再起動するか実行直前に渡す）。② `uv add truststore` を追加する（`fetch_arxiv.py` が検出すると OS 証明書ストアで TLS 検証し、傍受された証明書を通せる。未導入なら無視され、素通し環境では `arxiv` の certifi で検証）。傍受されない通常ネットワークでは①②とも不要。

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
- テストはスキル内（`skills/watch-paper/tests/`）に同梱。ロジックのテスト（スキルリポジトリルートから・pytest をエフェメラルに導入）:

  ```
  uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v
  ```
