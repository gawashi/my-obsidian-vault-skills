# 設計: 論文ウォッチ（定点観測）スキル `watch-paper`

- **日付**: 2026-06-28
- **ステータス**: 承認待ち（実装計画フェーズ手前）
- **対象**: arXiv の新着論文を、設定した複数テーマごとに定点観測し、関連度の高いものを「ダイジェスト」として抽出する Claude Code スキル。最初のテーマは「科学的発見の自動化（automated scientific discovery、例: ResearchAgent / The AI Scientist / AI Co-Scientist）」。
- **置き場所**: `C:\Users\010230240\work\my-obsidian-vault-skills`（スキルのソース・リポジトリ）配下の `skills/watch-paper/`

---

## 1. 背景・目的

ユーザーは「科学的発見の自動化」のような特定テーマの論文を**継続的にウォッチ**したい。現状は気づいたときに手で探すしかなく、見落としが起きる。

**自動化したいこと**: 「新着論文を抽出する」ところまでを仕組み化する。具体的には、テーマ定義（キーワード・代表論文）に基づいて arXiv の新着を集め、関連度で絞り込み、読むべき候補を**ダイジェスト**として書き出す。

### 核心方針

- **2段構え**で、決定的な処理（取得・重複排除）と判断（関連度評価・要約）を分離する。
  - 決定的な部分は **Python スクリプト**（`fetch_arxiv.py`、`uv run` で実行）。arXiv API は公式ラッパー **`arxiv`** ライブラリで叩く（`uv add arxiv` で vault の uv プロジェクトに追加）。vault の uv プロジェクト環境で動く。結果が再現的で安価。
  - 判断する部分は **LLM（スキル本体）**。候補のタイトル＋アブストを、テーマ定義とアンカー論文に照らして関連度スコアリングし、ダイジェストに整形する。
- **マルチテーマ**。テーマは `config.json` で複数定義でき、後から増減できる。最初のテーマは「科学的発見の自動化」。
- **各論文の評価は1回だけ**。一度評価した arXiv ID は合否に関わらず既読台帳に記録し、再評価でトークンを無駄にしない。

---

## 2. 確定した決定事項

| 論点 | 決定 |
|---|---|
| wiki との関係 | **完全分離**。ダイジェスト生成までが責務。Ingest はユーザー手動。 |
| 出力粒度 | **ダイジェストのみ**（タイトル＋一言要約＋スコア＋なぜ気になるか＋arXivリンク）。自動 Ingest はしない |
| 取得元 | **arXiv API 主軸**（`http://export.arxiv.org/api/query`）。新着順（`submittedDate` 降順） |
| 取得方式 | **Python スクリプト**（`fetch_arxiv.py`）を **uv で実行**。arXiv API は公式ラッパー **`arxiv`** ライブラリ（`uv add arxiv` で vault プロジェクトに追加）。vault の uv プロジェクト環境（Python 3.13）で `uv run` |
| 実行コマンド | `uv run --project "<vault>" "<skill>/fetch_arxiv.py"`。env=vault の uv プロジェクト、コード=スキル側。uv が起動時に env を自動 sync（`arxiv` 未導入なら install） |
| テーマ | **マルチテーマ**（`config.json` の `themes[]`）。初期テーマ=「科学的発見の自動化」。例として他テーマのスタブも同梱 |
| 関連度判定 | LLM がテーマ定義＋アンカー論文に照らし **0〜5 でスコアリング**。閾値 **3** 以上を採用 |
| 重複排除＋監査台帳 | **テーマごとの評価台帳** `state/seen-<theme-id>.csv`（追記専用・ヘッダ行あり、**vault データroot 配下**）。列 = `arxiv_id,score,title,evaluated,surfaced`。評価済みは合否問わず全件記録し、**弾いた論文もタイトル・スコア付きで残る**（監査・偽陰性救済が可能）。重複排除キーは `arxiv_id` 列 |
| 台帳書き込み | CSV はタイトルにカンマ等を含むため**決定的に書く**。`fetch_arxiv.py` の**コミットモード**が担当: スキル本体（LLM）は `{arxiv_id: score}` の対応表だけを出力し、スクリプトが `candidates.json`（タイトル保持）と突き合わせ Python `csv` で正しくクォートして追記。`surfaced`=`score≥threshold`、`evaluated`=実行日 |
| ダイジェスト | 1回の実行で **1つの日付ファイル** `digests/YYYY-MM-DD.md`（**vault データroot 配下**）。中をテーマ別セクションに分け、各テーマはスコア降順 |
| 遡及/初回 | 通常は遡及 **7日**。初回（台帳が空）は **過去30日**に制限して台帳をシード（初回フラッド防止） |
| 頻度 | **週1**（運用上の目安。`lookback_days=7` と整合。手動で任意のタイミング起動） |
| 役割分担（配置） | **スキル側（git管理）= 仕組み＋定義**（`SKILL.md`/`fetch_arxiv.py`/`config.json`/`README.md`）。**vault データroot = ランタイムデータ**（`digests/`/`state/`/`candidates.json`/`scores.json`）。スキルは1箇所のみで実行される前提 |
| vault データroot | `<vault>/watch-paper/`。`<vault>` は実行時の CWD として解決される（このマシンでは `C:\Users\010230240\OneDrive - OMRON\ドキュメント\Obsidian\My vault` だが、設定には焼き込まない）。wiki から独立した専用フォルダ |
| データroot の解決 | **実行時に解決**（`config.json` に絶対パスは持たない）。このスキルは **vault 上で起動した Claude** が実行するため、データroot = **カレントディレクトリ（=vault ルート）配下 `watch-paper/`**。スクリプトは既定で `Path.cwd()/"watch-paper"` を使い、任意で `--data-dir <path>` で上書きできる。vault の場所が環境依存でも壊れない |
| git 追跡 | スキル側（`config.json` 含む）は git 追跡。vault データroot（`digests/`/`state/`）は **vault が git リポジトリでないため追跡対象外**＝OneDrive 同期で端末間共有 |
| スキル置き場 | `skills/watch-paper/`。設計正本は本 spec、実装計画は `docs/plans/2026-06-28-watch-paper-skill.md` |

---

## 3. スコープ

### v1 でやること

1. `config.json` の全テーマについて、`fetch_arxiv.py`（`uv run`）が arXiv API を叩いて新着候補を取得し、テーマごとの既読台帳で重複排除して `candidates.json` を出力する。
2. スキル本体（LLM）が `candidates.json` の各候補を、当該テーマの定義＋アンカー論文に照らして関連度 0〜5 でスコアリングし、閾値（既定 3）以上を抽出する。
3. 抽出結果を `digests/YYYY-MM-DD.md` にテーマ別セクション・スコア降順で書き出す。
4. 評価した候補（合否問わず）を、各テーマの `state/seen-<theme-id>.csv` に `arxiv_id,score,title,evaluated,surfaced` 形式で追記する（`fetch_arxiv.py` コミットモード）。
5. 実行結果（テーマ別の評価件数・抽出件数、上位ピック、ダイジェストのパス）を報告する。
6. README に手動実行手順と前提（`uv`/`arxiv` 依存・CWD=vault・OneDrive 同期の注意）を記載する。

### v1 でやらないこと

- 抽出した論文の `wiki/` への Ingest や `raw/` への保存（**ユーザー手動**。スキルは関与しない）。
- arXiv 以外の取得元（Hugging Face Daily Papers、Semantic Scholar、会議録、X など）。
- 引用グラフを辿る発見（アンカー論文を引用する新着の探索など）。
- PDF 本文の取得・精読（判定はタイトル＋アブストのみ）。
- 自動実行・スケジューラ連携（v1 は手動 `/watch-paper` 起動のみ）。
- 通知連携（メール/Slack 等）。

---

## 4. 詳細設計

### 4.1 ファイル構成

**スキル側（リポジトリ・git管理）= 仕組み＋定義**

```
skills/watch-paper/
├─ SKILL.md            # frontmatter(name/description) ＋ 手順 ＋ ガードレール
├─ fetch_arxiv.py      # ①取得: arXiv→既読除外→candidates.json ②コミット: スコアを受けて seen-*.csv 追記（uv run で実行）
├─ config.json         # テーマ定義（defaults ＋ themes）。絶対パス（data_dir）は持たない
└─ README.md           # 手動実行手順・前提（uv/arxiv 依存・CWD=vault・OneDrive 同期の注意）
```

- `fetch_arxiv.py` は **vault の uv プロジェクト環境**で実行する（`uv run --project "<vault>" "<skill>/fetch_arxiv.py"`）。依存は **`arxiv`** ライブラリ（＋その推移的依存 `requests`/`feedparser`）。実装時に `uv add arxiv` で vault の `pyproject.toml` + `uv.lock` に追加する（現在 deps 空 → `arxiv` を追加）。
- スクリプトは自身の位置（`Path(__file__).parent`）の `config.json` を読み、**出力先は実行時のカレントディレクトリ（=vault ルート）配下 `watch-paper/`** に解決して書き出す（`--data-dir` 指定時はそれを優先）。

**vault データroot（実行時 CWD = vault ルート配下 `watch-paper/`。本書では `<data_dir>` と表記）= ランタイムデータ**

```
<vault>/watch-paper/
├─ candidates.json     # 取得モード → スキル本体 へ渡す一時ファイル（毎回上書き）
├─ scores.json         # スキル本体 → コミットモード へ渡すスコア対応表（毎回上書きの一時ファイル）
├─ state/
│   └─ seen-<theme-id>.csv   # テーマ別の評価台帳（追記専用・ヘッダ付き）。列: arxiv_id,score,title,evaluated,surfaced
└─ digests/
    └─ YYYY-MM-DD.md   # 生成ダイジェスト（Obsidian で閲覧・手動 Ingest の起点）
```

### 4.2 `config.json` スキーマ

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
        "automated scientific discovery", "AI scientist", "AI co-scientist",
        "research agent", "research idea generation", "research ideation",
        "hypothesis generation", "autonomous research", "automated experimentation"
      ],
      "anchors": [
        "ResearchAgent (Baek et al.)", "The AI Scientist (Sakana AI)",
        "AI Co-Scientist (Google)", "SciAgents", "Agent Laboratory"
      ]
    },
    {
      "id": "industrial-anomaly-detection",
      "name": "産業異常検知",
      "enabled": false,
      "keywords": ["industrial anomaly detection", "surface defect detection", "zero-shot anomaly detection", "few-shot anomaly detection"],
      "anchors": ["PatchCore", "SimpleNet", "DRAEM", "AnomalyCLIP"],
      "categories": ["cs.CV"]
    }
  ]
}
```

- **厳密 JSON**（コメント・末尾カンマ不可）。Python の `json.load` がそのまま読める形にする。
- `enabled`（省略時 `true`）が `false` のテーマはスクリプトがスキップする。上の `industrial-anomaly-detection` は**編集可能な例**（あなたの既存の関心から仮置き）。使うなら `enabled` を外す/`true` にし、不要なら丸ごと削除する。
- テーマ単位で `categories` / `threshold` を上書き可。未指定なら `defaults` を継承。
- `keywords` は arXiv のアブスト検索（`abs:`）に使う。複数語はフレーズ検索（引用符付き）。
- `anchors` は LLM の関連度判定の**キャリブレーション用基準**（同種の仕事か否かを測る物差し）。クエリには使わない。
- **カテゴリ絞りは AND のハードフィルタ**（`AND ( cat:... )`）。「科学的発見の自動化」テーマは `defaults` を継承して **cs.AI/cs.CL/cs.LG/cs.MA** で絞る（**精度重視**の決定）。代償として cs 外にクロスリストされた論文（自律実験・self-driving lab が physics/q-bio 等）は v1 の対象外。取りこぼしは LLM 関連度ではなく**クエリ段で発生**する点に留意（拾いたくなったら当該テーマの `categories` に cs 外（`physics.chem-ph`/`cond-mat`/`q-bio`/`eess`/`stat.ML` 等）を足す）。
- **カテゴリ絞りを無効化したいテーマ**は、そのテーマに `"categories": []`（空配列）を明示する。空ならスクリプトは `AND ( cat:... )` 句を付けずキーワードのみで検索する。

### 4.3 `fetch_arxiv.py`（決定的な取得＋台帳コミット・`arxiv` ライブラリ・uv 実行）

- **実行**: `uv run --project "<vault>" "<skill>/fetch_arxiv.py"`。vault の uv プロジェクト環境（Python 3.13）で動く。uv が起動時に env を自動 sync するため、`arxiv` 未導入でも install されて動く。`<vault>`/`<skill>` は実行時に解決される絶対パスで、ファイルには固定しない（CWD が vault なので `--project` は省略しても uv が vault プロジェクトを自動検出するが、明示しておく）。
- **依存**: `arxiv`（公式風ラッパー）。stdlib（`json`, `pathlib`, `datetime`, `time`, `argparse`）併用。
- **入力/出力（取得モード）**: 入力 `Path(__file__).parent / "config.json"`、出力 `<data_dir>/candidates.json`（`<data_dir>` = `--data-dir` 指定値、無指定なら `Path.cwd()/"watch-paper"`）。
- **入力/出力（コミットモード `--commit <scores.json>`）**: 入力 `scores.json` ＋ 同じ実行の `candidates.json`、出力 `<data_dir>/state/seen-<theme-id>.csv`（追記）。
- **終了コード**: 正常 0。`config.json` 読込・データroot 作成の致命的エラーは非0で終了（スキル本体が検知して中止）。

処理:

1. `config.json` を `json.load` で読む。**データroot を解決**（`--data-dir` 指定時はそれ、無指定なら `Path.cwd()/"watch-paper"`）し、解決した絶対パスを **stderr にログ出力**（誤った CWD での実行に気づけるように）。無ければ データroot・`<data_dir>/state`・`<data_dir>/digests` を `mkdir(parents=True, exist_ok=True)` で作成。`themes[]` のうち `enabled != False` のテーマを走査。
2. `arxiv.Client` を 1 つ用意（`page_size`, `delay_seconds=defaults.request_delay_seconds`, `num_retries`）。**rate-limit と retry はライブラリが内蔵**（手動 sleep/backoff 不要）。
3. テーマごとに arXiv 検索クエリ文字列を組む:
   - `query = (abs:"kw1" OR abs:"kw2" ...) AND (cat:c1 OR cat:c2 ...)`（キーワードはフレーズなので引用符）。
   - **実効カテゴリ**＝テーマの `categories`（未指定なら `defaults.categories`）。空配列 `[]` の場合は `AND ( cat:... )` 句を**付けない**（キーワードのみ）。
   - `search = arxiv.Search(query=query, max_results=<defaults.max_results>, sort_by=arxiv.SortCriterion.SubmittedDate, sort_order=arxiv.SortOrder.Descending)`。
4. `for r in client.results(search):` で `arxiv.Result` を列挙。各 `r` から抽出:
   - `arxiv_id`: `r.get_short_id()` からバージョン接尾辞 `vN` を除いた **base ID**（`entry_id` 末尾でも可）。
   - `title=r.title`, `abstract=r.summary`, `authors=[a.name for a in r.authors]`, `published=r.published`(tz-aware), `updated=r.updated`, `primary_category=r.primary_category`, `link=r.entry_id`(abs ページ URL)。
5. **遡及フィルタ**: 既読台帳 `<data_dir>/state/seen-<theme-id>.csv` が空（初回。ファイル無し or ヘッダ行のみ）なら cutoff = 今日 − `first_run_lookback_days`、そうでなければ cutoff = 今日 − `lookback_days`。`r.published >= cutoff` のみ残す（降順なので cutoff を下回ったら `break`）。比較は tz-aware（UTC）で行う。
6. **重複排除**: 当該テーマの既読台帳 CSV の `arxiv_id` 列（base ID の集合）に存在する ID を除外。CSV は `csv` モジュールで読む（タイトル列のカンマ・改行に対応）。
7. 取得失敗（`arxiv.UnexpectedEmptyPageError`/`arxiv.HTTPError` 等）はそのテーマをスキップし `candidates.json` に `"error"` を載せて続行（全体は止めない）。
8. `<data_dir>/candidates.json` を `json.dump`（`ensure_ascii=False`、`published` 等は ISO 文字列に変換）で出力:

```json
{
  "generated": "2026-06-28T09:00:00+09:00",
  "first_run": false,
  "themes": [
    {
      "id": "auto-sci-discovery",
      "name": "科学的発見の自動化",
      "threshold": 3,
      "anchors": ["ResearchAgent (Baek et al.)", "..."],
      "fetched": 37,
      "new": 12,
      "candidates": [
        {
          "arxiv_id": "2406.xxxxx",
          "title": "...",
          "abstract": "...",
          "authors": ["..."],
          "published": "2026-06-25",
          "primary_category": "cs.CL",
          "link": "https://arxiv.org/abs/2406.xxxxx"
        }
      ]
    }
  ]
}
```

- **取得モード（既定）は既読台帳を更新しない**（取得しただけで未評価の論文を既読にしないため。台帳の更新は評価後のコミットモードで行う）。

**コミットモード `fetch_arxiv.py --commit <scores.json>`**（スキル本体が評価後に呼ぶ）:

- `<scores.json>` は LLM が出力する小さな対応表 `{ "<theme-id>": { "<arxiv_id>": <score 0-5>, ... }, ... }`。
- スクリプトは同じ実行の `candidates.json` から各 `arxiv_id` の `title` を引き、各テーマの `seen-<theme-id>.csv` に行を**追記**する。
  - 列 `arxiv_id,score,title,evaluated,surfaced`。`surfaced = (score >= 実効threshold)`、`evaluated =` 実行日（`YYYY-MM-DD`）。
  - Python `csv.writer`（`QUOTE_MINIMAL` / `newline=''` / UTF-8）で書き、タイトルのカンマ・引用符・改行を安全に処理。ファイルが無ければ**ヘッダ行**を先に書く。
  - LLM は数値の対応表だけを出すので、CSV 破損・クォート事故が起きない。`candidates.json` に無い `arxiv_id` は無視（取得時に弾かれた論文を誤記録しない）。

### 4.4 スキル本体の処理フロー（`SKILL.md`）

```
1. fetch_arxiv.py を uv run で実行（`uv run --project "<vault>" "<skill>/fetch_arxiv.py"`）。<data_dir>/candidates.json を生成。データroot は実行時の CWD（=vault ルート）配下 watch-paper/（このスキルは vault 上で起動するので CWD=vault）。
   - 実行できない/権限拒否/非0終了なら理由を報告して中止。
2. <data_dir>/candidates.json を読む。new=0 のテーマは「該当なし」として記録。
3. テーマごとに、各候補の title＋abstract を anchors と照らして関連度 0〜5 を付与（§4.5 ルーブリック）。
   - 各候補に「一言要約（日本語）」と「なぜ気になるか（1行）」を生成。捏造しない（アブストの範囲で書く）。
4. 閾値（テーマの threshold）以上のみ採用し、スコア降順に並べる。
5. <data_dir>/digests/YYYY-MM-DD.md を生成（§4.6 書式）。日付は date +%F 等で取得（ハードコードしない）。
   - 同日に既存ファイルがあれば追記ではなく上書き前に確認（再実行時の二重生成防止）。
6. 評価したスコアを対応表 {theme-id: {arxiv_id: score}} として `<data_dir>/scores.json`（candidates.json と同じデータroot直下・毎回上書きの一時ファイル）に書き出し、`uv run --project "<vault>" "<skill>/fetch_arxiv.py" --commit "<data_dir>/scores.json"` を実行 → 各テーマの seen-<theme-id>.csv に arxiv_id,score,title,evaluated,surfaced を追記（合否問わず全件）。
7. 報告（§4.7）。
```

### 4.5 関連度ルーブリック（0〜5）

LLM はテーマの `anchors` を「同種の仕事の代表例」として基準化し、各候補を採点する:

- **5**: ど真ん中。アンカーと同種のシステム/手法/問題設定。
- **4**: 強く関連。隣接サブ問題、主要構成要素、明確な発展。
- **3**: 関連あり。応用・部分的に主題を扱う。**（採用閾値の既定）**
- **2**: 周辺。キーワードは当たるが主題が異なる。
- **0–1**: 無関係。キーワードの誤ヒット。

### 4.6 ダイジェスト書式（`<data_dir>/digests/YYYY-MM-DD.md`）

```markdown
---
generated: 2026-06-28
themes:
  - id: auto-sci-discovery
    evaluated: 12
    surfaced: 4
  - id: ai-agent-design
    evaluated: 20
    surfaced: 3
---

# 論文ウォッチ 2026-06-28

## 科学的発見の自動化  （評価12 / 抽出4）

### ⭐5 — [Title here](https://arxiv.org/abs/2406.xxxxx)
- arXiv: 2406.xxxxx ｜ cs.CL ｜ 2026-06-25
- 著者: A. Author, B. Author, …
- 要約: 〜（日本語1〜2文）
- なぜ気になるか: 〜（1行）

### 4 — [Another Title](https://arxiv.org/abs/2406.yyyyy)
- …

## AIエージェント設計  （評価20 / 抽出3）
- …

## 産業異常検知  （評価0 / 抽出0）
- 該当なし
```

### 4.7 報告

- テーマごとの「評価件数 / 抽出件数」。
- 各テーマの上位ピック（タイトル＋スコア）を数件。
- 生成したダイジェストのパス。
- スキップ/エラー（取得失敗テーマ、権限拒否等）。

## 5. エッジケース・注意点

- **初回実行（台帳が空）**: `first_run_lookback_days`（30日）で遡及を絞り、フラッドを防ぐ。初回は抽出も多めになりうる旨を報告。
- **arXiv 取得失敗**: 当該テーマをスキップし、他テーマは継続。`candidates.json` にエラーを記録し、報告で明示。
- **new=0 のテーマ**: ダイジェストに「該当なし」を記す（実行された証跡を残す）。
- **同日再実行**: 既存の `<data_dir>/digests/YYYY-MM-DD.md` を上書きする前に確認。既読台帳は追記専用なので二重評価は起きない（新規候補のみ評価）。
- **データroot 作成失敗 / 誤った CWD**: データroot を作成できない（権限なし等）場合は中止して理由を報告。スクリプトは解決した データroot をログ出力するので、**vault 以外で実行された**（CWD が vault でない）場合に気づける。その際は vault ルートで実行し直す（または `--data-dir` で明示）。
- **OneDrive 同期の競合**: vault データrootは OneDrive 配下。`state/*.csv` 追記中に別端末で同期が走ると競合コピーが生じうる。CSV も行末への単純追記に留め（既存行は書き換えない）、競合時は手動マージを促す（README に注記）。
- **複数テーマに該当する論文**: テーマごとに独立評価・独立台帳のため、複数テーマのセクションに重複して載りうる（仕様。異なる観点での関連として許容）。
- **偽陰性の救済**: AIが誤って弾いた論文も `seen-<theme-id>.csv` にスコア・タイトル付きで残る。該当行を手で削除すれば既読集合から外れ、次回実行で再評価される（閾値・キーワード改善後の拾い直しに使える）。CSV は Obsidian/Excel で開いてスコア順に並べれば「何を落としたか」を一覧できる。
- **arXiv ID のバージョン**: `2406.xxxxx`（バージョン `vN` を除いた base ID）で台帳管理し、改訂版を別物として再掲しない。
- **キーワードの過剰ヒット**: フレーズ検索（引用符）と関連度閾値で抑制。なお多すぎる場合は `threshold` を上げる/キーワードを絞る（config 編集）。
- **日付のハードコード禁止**: ダイジェストのファイル名・`generated` は実行日を動的取得。スクリプトの cutoff も `datetime`（UTC基準）で算出。
- **捏造防止**: 要約・「なぜ気になるか」はアブストの記述範囲で書く。アブストに無い性能数値・主張を足さない。
- **wiki に触れない**: `wiki/`・`raw/`・`schema.md` を読み書きしない（責務分離）。

---

## 6. 受け入れ基準（Acceptance Criteria）

1. `/watch-paper`（または「新着論文を調べて」系の起動）で、`fetch_arxiv.py` が `uv run` で実行され `config.json` の全テーマについて arXiv から新着候補が取得され、テーマごとの既読台帳で重複排除されて `<data_dir>/candidates.json` が生成される。
2. 各候補が当該テーマの定義＋アンカーに照らして 0〜5 でスコアリングされ、閾値（既定 3）以上のみが抽出される。
3. `<data_dir>/digests/YYYY-MM-DD.md` が生成され、テーマ別セクション・スコア降順で「タイトル(リンク)／arXiv ID・カテゴリ・投稿日／著者／一言要約／なぜ気になるか」が並ぶ。new=0 のテーマは「該当なし」と記される。
4. 評価された候補（合否問わず全件）が `<data_dir>/state/seen-<theme-id>.csv` に `arxiv_id,score,title,evaluated,surfaced` 形式で（`fetch_arxiv.py --commit` 経由で）追記され、弾いた論文もタイトル・スコア付きで確認でき、次回実行で再評価されない。
5. 初回実行（台帳が空）では遡及が `first_run_lookback_days` に絞られる。
6. arXiv 取得に失敗したテーマがあっても全体は止まらず、他テーマの処理が続行し、失敗が報告される。
7. 実行後、テーマ別の評価件数・抽出件数、上位ピック、ダイジェストのパスが報告される。
8. ランタイムデータ（`candidates.json`/`state/`/`digests/`）は **実行時 CWD（=vault ルート）配下 `watch-paper/`** にのみ書かれ、スキルフォルダ内には書かれない（`config.json` に絶対パスを持たない）。スキルは `wiki/`・`raw/`・`schema.md` を読み書きしない。
9. README に手動実行手順と前提（`uv`/`arxiv` 依存・CWD=vault・OneDrive 同期の注意）が記載される。
