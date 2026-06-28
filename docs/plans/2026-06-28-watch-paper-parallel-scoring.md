# watch-paper per-paper 並列採点 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** watch-paper の採点ステップを「単一エージェント一括採点」から「1論文=1サブエージェントの並列採点＋メインのテーマ内正規化パス」に変更する。

**Architecture:** 変更は **`SKILL.md` のステップ2（採点）に閉じる**。メインエージェントが候補ごとにツールなしのサブエージェントを同時 K 件まで並列起動し、各サブが構造化 JSON（スコア＋要約＋根拠＋確信度）を返す。メインがテーマ内で境界事例を較正（正規化）し、既存の `scores.json` 契約どおり書き出す。`fetch_arxiv.py`・`tests/`・`--commit` フロー・ダイジェスト書式・台帳 CSV は不変。

**Tech Stack:** Markdown（SKILL.md / README.md）、JSON（config.json）。Python 3.13 + `uv`（既存テストの回帰確認のみ）。コード追加なし。

## Global Constraints

- 設計の正本: `docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`（元 spec `docs/specs/2026-06-28-paper-watch-skill-design.md` の §4.4 step3・§4.5 を上書きする差分）。
- **`fetch_arxiv.py` と `skills/watch-paper/tests/` は変更しない。**
- `scores.json` 契約（`{theme-id: {arxiv_id: score}}`）・`--commit` インターフェース・ダイジェスト書式・台帳 CSV 列（`arxiv_id,score,title,evaluated,surfaced`）は不変。
- `config.json` は **厳密 JSON**（コメント・末尾カンマ不可）。
- 採点はアブストのみ（PDF 本文を取らない）。要約・なぜ気になるかはアブストの範囲で書き、捏造しない。
- 同時実行上限 `K` の既定は **6**。`config.json` の `defaults.scoring_concurrency` で上書き可（任意キー。`fetch_arxiv.py` は未知キーを無視するためコード変更不要）。
- 正規化は **テーマ内のみ**（テーマ間では行わない）。

## File Structure

| ファイル | 責務 | 変更 |
|---|---|---|
| `skills/watch-paper/config.json` | テーマ定義＋defaults | `defaults.scoring_concurrency: 6` を追記 |
| `skills/watch-paper/SKILL.md` | 採点手順の正本（LLM 向け） | ステップ2を並列採点＋正規化に書き換え、ステップ6に報告項目追加、ガードレール1行追加、冒頭の設計doc参照を追記 |
| `skills/watch-paper/README.md` | 人間向け説明 | 並列採点の概要・`scoring_concurrency`・設計doc参照を注記 |
| `skills/watch-paper/fetch_arxiv.py` | 取得・コミット | **変更なし** |
| `skills/watch-paper/tests/**` | スクリプトの単体テスト | **変更なし**（回帰確認のみ） |

---

### Task 1: config.json に `scoring_concurrency` を追記

**Files:**
- Modify: `skills/watch-paper/config.json`（`defaults` ブロック）

**Interfaces:**
- Consumes: なし
- Produces: `config.json` の `defaults.scoring_concurrency`（整数、既定 6）。SKILL.md ステップ2（Task 2）がこの値を読む。

- [ ] **Step 1: `defaults` に `scoring_concurrency` を追加**

`skills/watch-paper/config.json` の `defaults` ブロックを、`request_delay_seconds` の後に `scoring_concurrency` を足した形に変更する。変更後の `defaults` は次のとおり:

```json
  "defaults": {
    "categories": ["cs.AI", "cs.CL", "cs.LG", "cs.MA"],
    "threshold": 3,
    "lookback_days": 7,
    "first_run_lookback_days": 30,
    "max_results": 120,
    "request_delay_seconds": 3,
    "scoring_concurrency": 6
  },
```

（`request_delay_seconds` の行末に `,` を付けてから新キーを追加する点に注意。`themes` 配列・他は一切変更しない。）

- [ ] **Step 2: JSON として妥当か・新キーがあるか検証**

Run:
```
uv run --no-project --python 3.13 python -c "import json; d=json.load(open('skills/watch-paper/config.json', encoding='utf-8')); assert d['defaults']['scoring_concurrency']==6; print('ok')"
```
Expected: `ok`（例外・AssertionError なく標準出力に `ok`）

- [ ] **Step 3: 既存テストが回帰していないことを確認**

Run:
```
uv run --no-project --with pytest --python 3.13 pytest skills/watch-paper/tests -v
```
Expected: 全テスト PASS（`fetch_arxiv.py` は `defaults` の特定キーしか読まず未知キーを無視するため、件数・結果は従来どおり全て緑）。

- [ ] **Step 4: コミット**

```
git add skills/watch-paper/config.json
git commit -m "feat(watch-paper): add defaults.scoring_concurrency knob (default 6)"
```

---

### Task 2: SKILL.md のステップ2を per-paper 並列採点＋正規化に書き換え

**Files:**
- Modify: `skills/watch-paper/SKILL.md`（セクション「## 2. スコアリング」全体、「## 6. 報告」、「## ガードレール」、冒頭の設計doc参照）

**Interfaces:**
- Consumes: `config.json` の `defaults.scoring_concurrency`（Task 1）。`candidates.json`（各テーマ `id/name/threshold/anchors/new/candidates[]`、候補は `arxiv_id/title/abstract/authors/published/primary_category/link`、取得失敗テーマは `error`）。
- Produces: 採点後の `scores.json`（`{theme-id: {arxiv_id: score}}`）。これはステップ5の `--commit` と既存契約が消費する（不変）。

- [ ] **Step 1: セクション2を全面置換**

`skills/watch-paper/SKILL.md` の現セクション（`## 2. スコアリング（テーマごと）` から、本文末尾「**アブスト（`abstract`）の範囲で書き、性能数値や主張を捏造しない。**」まで）を、次の内容に置き換える:

````markdown
## 2. スコアリング（テーマごと・1論文1サブエージェントで並列採点）

`candidates.json` の各テーマについて、`candidates[]` の各論文を採点する。`new` が 0 のテーマ、および `error` を持つテーマ（取得失敗）はサブエージェントを起動しない（手順4で「該当なし」/「取得失敗」として残す）。

採点は **1論文=1サブエージェント**で並列に行い、その後メイン（あなた）が**テーマ内で正規化**する（集中と一貫性の両立）。

### 2.1 並列ディスパッチ

- 同時実行の上限 `K` を決める: `<skill-dir>/config.json` の `defaults.scoring_concurrency` を読む。無ければ既定 **6**。
- enabled かつ `new>0` の各テーマの各候補について、**1候補=1サブエージェント**を起動する。同時に走らせるのは最大 `K` 件とし、波状にキューを消化する（K 件起動 → 返ってきた分だけ次を起動）。
- サブエージェントには**ツールを与えず**、採点に必要な情報を**すべてプロンプトに内包**する（隔離・安価）。1 サブエージェント＝1 候補に集中させる。

各サブエージェントへ渡すプロンプトに含める内容:

- テーマの `name` / `anchors`（同種の仕事の代表例）/ `threshold`。
- 関連度ルーブリック（0〜5）:
  - **5**: ど真ん中。アンカーと同種のシステム/手法/問題設定。
  - **4**: 強く関連。隣接サブ問題・主要構成要素・明確な発展。
  - **3**: 関連あり。応用・部分的に主題を扱う（採用閾値の既定）。
  - **2**: 周辺。キーワードは当たるが主題が異なる。
  - **0–1**: 無関係。キーワードの誤ヒット。
- 候補1件: `arxiv_id` / `title` / `abstract` / `authors` / `published` / `primary_category` / `link`。
- ガードレール: 「要約・なぜ気になるかは**アブストの範囲で書き、性能数値や主張を捏造しない**」。

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

- テーマ内の全候補を暫定スコア順に並べる。
- **境界事例**を重点的に見直す: `threshold` 周辺の境目（既定 `threshold=3` なら 2/3 と 3/4）と、`confidence: low` の候補。
- 対象候補の `abstract`（`candidates.json`）を読み直し、各サブの `rationale` を材料に、横並びの一貫性が出るようスコアを調整する。これは**再採点ではなく較正**。
- `summary_ja`/`why_ja` は原則サブの出力を採用し、明らかな誤りのみ軽修正する。
- 調整した件数を覚えておき手順6で報告する。

### 2.3 フォールバック

サブエージェントが失敗した／返ってきた JSON が壊れている／スキップされた候補は、**あなた自身が同じルーブリックでその1件をインライン採点する**（取りこぼして台帳から漏らさない）。フォールバックした件数を覚えておき手順6で報告する。
````

- [ ] **Step 2: セクション6（報告）に項目を追加**

現セクション6の箇条書きに、`スキップ/エラー…` の行の**直後**に次の3項目を挿入する:

```markdown
- ディスパッチしたサブエージェント数。
- 正規化パスでスコアを調整した件数。
- フォールバック採点した件数（サブエージェント失敗時）。
```

- [ ] **Step 3: ガードレールに1行追加**

`## ガードレール` の箇条書き末尾に次の1行を追加する:

```markdown
- サブエージェント採点に失敗した候補は必ずメインがインラインで採点し、未評価のまま台帳から漏らさない（漏れると次回再評価でトークンを無駄にする）。
```

- [ ] **Step 4: 冒頭の設計doc参照を更新**

セクション冒頭（`# watch-paper` 直下の段落）末尾の「設計の正本はスキルリポジトリの `docs/specs/2026-06-28-paper-watch-skill-design.md`。」を、次に置き換える:

```markdown
設計の正本はスキルリポジトリの `docs/specs/2026-06-28-paper-watch-skill-design.md`（採点の並列化差分は `docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`）。
```

- [ ] **Step 5: 内容を受け入れ基準に照らして検証（手動チェックリスト）**

`SKILL.md` を読み直し、次がすべて満たされることを確認する（自動テストなし。設計 spec §5 の受け入れ基準に対応）:

- [ ] ステップ2が「enabled かつ `new>0` の各候補に 1サブエージェント」「同時実行 `scoring_concurrency`（既定6）以下」を明記している（AC 1）。
- [ ] サブの入力が title+abstract のみで、出力 JSON が `{arxiv_id, score, summary_ja, why_ja, rationale, confidence}` である（AC 2）。
- [ ] 正規化パスが「テーマ内のみ」「threshold 周辺＋低 confidence を較正」と明記されている（AC 3）。
- [ ] 採点後に既存契約どおり `scores.json`（`{theme-id: {arxiv_id: score}}`）を書く流れ（ステップ5）が温存されている（AC 4）。
- [ ] `new=0`／取得失敗テーマの扱い（ディスパッチしない・該当なし/error）が残っている（AC 5）。
- [ ] フォールバック（サブ失敗→インライン採点）が明記されている（AC 6）。
- [ ] 報告に「ディスパッチ数／正規化調整件数／フォールバック件数」がある（AC 7）。
- [ ] `fetch_arxiv.py`・`tests/` への言及変更がなく、ステップ1/3/4/5 の既存フローが壊れていない（AC 8）。

Expected: 全項目チェック済み。未達があれば該当 Step に戻って修正。

- [ ] **Step 6: コミット**

```
git add skills/watch-paper/SKILL.md
git commit -m "feat(watch-paper): score candidates with one subagent per paper + in-theme normalization"
```

---

### Task 3: README.md に並列採点を注記

**Files:**
- Modify: `skills/watch-paper/README.md`（「これは何か / 何でないか」「テーマの編集」「開発」）

**Interfaces:**
- Consumes: `config.json` の `defaults.scoring_concurrency`（Task 1）、設計doc（Task 2 で参照追加済み）。
- Produces: なし（人間向けドキュメント）。

- [ ] **Step 1: 「やること」の採点説明を並列採点に更新**

`README.md` の「やること」行:

```markdown
- **やること**: テーマ定義（`config.json`）に基づき arXiv 新着を取得 → LLM が 0〜5 で関連度採点 → 閾値以上を `watch-paper/digests/YYYY-MM-DD.md` に抽出。評価済みは合否問わず `watch-paper/state/seen-<theme>.csv` に記録。
```

を次に置き換える:

```markdown
- **やること**: テーマ定義（`config.json`）に基づき arXiv 新着を取得 → **1論文=1サブエージェント**で 0〜5 の関連度を並列採点し、メインがテーマ内で正規化（較正）→ 閾値以上を `watch-paper/digests/YYYY-MM-DD.md` に抽出。評価済みは合否問わず `watch-paper/state/seen-<theme>.csv` に記録。
```

- [ ] **Step 2: 「テーマの編集」に `scoring_concurrency` の説明を追加**

「テーマの編集」セクションの箇条書き末尾（`threshold` の行の後）に次を追加する:

```markdown
- `defaults.scoring_concurrency`（既定 6）で、採点サブエージェントの同時実行数を調整できる。候補が多い日のコスト/レートを抑えたければ下げる。
```

- [ ] **Step 3: 「開発」の設計doc参照を追加**

「開発」セクションの `- 設計の正本: ...` 行の直後に次を追加する:

```markdown
- 採点の並列化差分: `docs/specs/2026-06-28-watch-paper-parallel-scoring-design.md`
```

- [ ] **Step 4: 整合性チェック**

`README.md` を読み直し、`scoring_concurrency` の既定値（6）と設計doc／`config.json`／`SKILL.md` の記述が一致していること、Markdown が壊れていないことを確認する。
Expected: 値・参照が一致。

- [ ] **Step 5: コミット**

```
git add skills/watch-paper/README.md
git commit -m "docs(watch-paper): document per-paper parallel scoring and scoring_concurrency"
```

---

## Self-Review（計画作成者による確認・実施済み）

- **Spec coverage**: 設計 spec §5 の AC 1〜8 を Task 2 Step 5 のチェックリストに1対1で対応付けた。AC（`scoring_concurrency` 既定6）は Task 1 で実装。README 注記は Task 3。`fetch_arxiv.py`/`tests` 不変は Global Constraints と Task 1 Step 3 の回帰確認で担保。
- **Placeholder scan**: TBD/TODO・「適切に処理」等の曖昧表現なし。各 Step に置換後の実テキスト／実コマンド／期待出力を記載済み。
- **Type consistency**: サブ出力フィールド名（`arxiv_id/score/summary_ja/why_ja/rationale/confidence`）は SKILL.md・設計doc・本計画で一致。`scoring_concurrency`（既定6）は config.json・SKILL.md・README で一致。`scores.json` 契約 `{theme-id: {arxiv_id: score}}` は不変。
