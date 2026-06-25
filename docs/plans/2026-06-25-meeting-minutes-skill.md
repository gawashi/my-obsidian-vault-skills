# meeting-minutes スキル 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `05-meeting/` のトランスクリプト付きミーティングノートから議事録を生成し、関連プロジェクトを推定・確認して `01-projects/.../LOG.md` と `INDEX.md` を更新する `meeting-minutes` スキル（単一 `SKILL.md`）を作る。

**Architecture:** 成果物は `.claude/skills/meeting-minutes/SKILL.md` のプロンプト/手順書1ファイル。実行時に Read / Glob / Edit / AskUserQuestion を用いる。コードではなくプロセス記述のため、検証は「サンドボックス（使い捨ての mtg ノート＋テストプロジェクト）に対し手順を実走し、受け入れ基準を満たすか確認 → 後始末」で行う。既存スキル `new-project`（`.claude/skills/new-project/SKILL.md`）の流儀・ファイル書式に合わせる。

**Tech Stack:** Markdown（YAML frontmatter）。Obsidian wikilink。実行時ツール: Read, Glob, Edit, AskUserQuestion, Bash(`date +%F`)。

## Global Constraints

- スキル配置: `.claude/skills/meeting-minutes/SKILL.md`（vault ルートからの相対。git リポジトリは `.claude/`）。
- 設計の正本: `.claude/docs/specs/2026-06-25-meeting-minutes-skill-design.md`。逸脱しないこと。
- プロジェクトの標準構成・ファイル書式は `new-project` スキルに従う（`CLAUDE.md` + `LOG.md` + `INDEX.md`、frontmatter `created`/`updated`、ログは新しいもの上）。
- 日付はハードコード禁止。会議日＝mtg ノート frontmatter `date`、`updated`＝処理日（`date +%F`）。
- ユーザー確認前に `LOG.md`/`INDEX.md` を書き換えない。トランスクリプト本文を削除しない。トランスクリプトに無い情報を捏造しない。
- mtg→プロジェクトの `project` リンクはパス修飾 wikilink（`[[01-projects/{type}/{name}/CLAUDE|{name}]]`）。全プロジェクトが同名 `CLAUDE.md` を持つため basename wikilink は使わない。
- `description` は日本語要約＋日本語/英語トリガーフレーズを含む（発見性のため）。

---

## File Structure

- `C:\Users\010230240\OneDrive - OMRON\ドキュメント\Obsidian\My vault\.claude\skills\meeting-minutes\SKILL.md`
  - 責務: スキルの全て（frontmatter による発見性 + 8 手順 + ガードレール）。唯一の成果物。

---

### Task 1: SKILL.md を作成する

**Files:**
- Create: `C:\Users\010230240\OneDrive - OMRON\ドキュメント\Obsidian\My vault\.claude\skills\meeting-minutes\SKILL.md`

**Interfaces:**
- Consumes: 設計 spec（§4 手順, §5 エッジケース, §6 受け入れ基準）、`new-project` の LOG/INDEX 書式。
- Produces: 実行可能なスキル手順書。Task 2 がこれを実走検証する。

- [ ] **Step 1: スキルディレクトリと SKILL.md を作成する**

下記の内容をそのまま `SKILL.md` に書き込む（プレースホルダ無し・完成形）:

````markdown
---
name: meeting-minutes
description: 05-meeting/ のミーティングノート（Teams トランスクリプト貼り付け済み）から議事録を生成し、内容から関連プロジェクトを推定・確認して 01-projects/ 配下の LOG.md と INDEX.md を更新する。Use when the user pastes a meeting transcript into 05-meeting/ and wants minutes generated, or asks 議事録を作って／トランスクリプトから議事録／ミーティングの議事録を生成して／"generate meeting minutes from the transcript", or invokes /meeting-minutes.
---

# meeting-minutes

`05-meeting/` のミーティングノートに貼られた Teams トランスクリプトから議事録を生成し、内容から関連プロジェクトを推定・**ユーザー確認**したうえで、そのプロジェクトの `LOG.md` / `INDEX.md` を更新する。ミーティングは「プロジェクトフリー」で保存されるため、このスキルが議事録化とプロジェクトへの紐づけを一手に担う。

設計の正本は `.claude/docs/specs/2026-06-25-meeting-minutes-skill-design.md`。プロジェクトの標準構成・ファイル書式は `new-project` スキルに従う。

**前提**: ミーティングノートは `_templates/meeting.md` 由来で、冒頭に構造化セクション（`# 会議情報` / `## 議題` / `## 決定事項` / `### アクションアイテム` / `### 次回の予定`）、末尾に `# Teamsトランスクリプト`（版によっては `# Teams議事録`）見出し＋トランスクリプト本文を持つ。

## 1. 対象ファイルを特定する

- 起動時の指示からファイル名・日付・タイトルを拾い、`05-meeting/` 内で対象ノートを特定する（Glob で照合）。
- 特定できなければ、`05-meeting/` で最も最近更新された `.md` を候補として提示し、「これを処理してよいか」を確認する。
- 対象ノートを Read する。

## 2. トランスクリプトを検証する

- `# Teamsトランスクリプト` または `# Teams議事録` 見出し以下にトランスクリプト本文があるか確認する。
- 本文が無い／見出しが無い → **中止**し、「トランスクリプトを貼り付けてから再実行してください」と伝える。`LOG`/`INDEX` には触れない。
- 冒頭の構造化セクションや `# 議事録` が既に内容で埋まっている → **上書き前にユーザー確認**する。

## 3. 議事録を生成する（ファイル内）

トランスクリプトを読み、以下を Edit でファイルに書き込む。**トランスクリプト本文は削除しない**。

- **`# 会議情報` の `参加者`**: トランスクリプトの話者行（`氏名 / 所属  時刻` の行頭氏名）を重複排除して列挙する。
- **`## 議題`**: 主要トピックを箇条書き。
- **`## 決定事項`**: 決まったことを箇条書き（テンプレの空 `- ` 行を置換）。
- **`### アクションアイテム`**: `- [ ] {担当}: {内容}（{期限}）` 形式。担当・期限が不明なら省略。
- **`### 次回の予定`**: 次回日程・宿題があれば記載。無ければ空のまま。
- **`# 議事録`**: ナラティブ本文。`05-meeting/2026-06-23-京都製作所.md` のスタイル（`■背景` / `■結論・今後のアクション` / 論点ごとの小見出し・箇条書き）に倣う。`# 議事録` 見出しが無ければ、トランスクリプト見出しの**直前**に挿入する。

**捏造しない**: トランスクリプトに無い決定・数値・固有名詞を補わない。読み取れないものは空欄/省略にする。

## 4. プロジェクトを推定する

- `01-projects/work/*/CLAUDE.md` と `01-projects/personal/*/CLAUDE.md` を Glob で列挙する（**ディレクトリ型プロジェクトのみ**。直下の単一 `.md` は対象外）。
- 各 `CLAUDE.md` の `## 概要` 本文と frontmatter `code`（例 `KT569`）を読む。
- 議事録の議題・決定事項・本文中のキーワード・固有名詞・`code` と照合し、関連度の高い順に候補を作る（信頼度: 高/中/低）。
- ここでは**確定しない**。次の手順で必ず確認する。

## 5. ユーザーに確認する

- AskUserQuestion（`multiSelect: true`）で候補プロジェクトを提示する。各候補を選択肢にし、信頼度を description に添える。加えて「該当なし」を選べるようにする。
- 「該当なし」または該当0件 → 手順6・7をスキップし、手順8で「議事録のみ生成、LOG/INDEX 更新はスキップ」を報告する。

## 6. LOG.md / INDEX.md を更新する

確認された各プロジェクト `01-projects/{type}/{name}/` について行う。当日日付は `date +%F` で取得する。会議日はミーティングノート frontmatter の `date` を使う。`{mtgノート名}` は拡張子なしのファイル名。

- `LOG.md` / `INDEX.md` が**無ければ**下記スケルトンで作成してから追記する。
- **LOG.md**: `## ログ` の直下（先頭・最新が上）に追記する:
  `- {会議日}: {会議の1行要約} → [[{mtgノート名}]]`
  今回の決定・次アクションが現状を動かすなら `## 現状 / 次の一手` も更新する。frontmatter `updated` を当日に更新する。
- **INDEX.md**: `## ミーティング` 見出しが無ければ末尾に作り、`- [[{mtgノート名}]]` を追加する（既出ならスキップ）。frontmatter `updated` を当日に更新する。

不在時に作成するスケルトン（`{name}`=プロジェクト名, `{today}`=当日）:

LOG.md
```markdown
---
created: {today}
updated: {today}
---

# {name} — ログ

## 現状 / 次の一手
- 

## ログ
```

INDEX.md
```markdown
---
created: {today}
updated: {today}
---

# {name} — INDEX

このフォルダ内の主要ノートへの索引。重要なノートが増えたら追記する。

## ミーティング
```

## 7. ミーティングノートに project リンクを追加する

- ミーティングノート frontmatter に `project` を追加する。値は各プロジェクトの `CLAUDE.md` を指す**パス修飾 wikilink**:
  `project: "[[01-projects/{type}/{name}/CLAUDE|{name}]]"`
  （全プロジェクトが同名 `CLAUDE.md` を持つため basename wikilink `[[CLAUDE]]` は曖昧。フルパス＋表示名で一意にする。）
- 複数該当時は YAML リストで複数持つ。既に `project` があればマージ（重複排除）。

## 8. 報告する

- 生成した議事録の要点（議題・主要決定・アクション数）。
- 更新したプロジェクトと編集ファイルのパス（`LOG.md`/`INDEX.md`、新規作成したか）。
- ミーティングノートに追加した `project` リンク。
- スキップした項目（該当プロジェクトなし、トランスクリプト未貼付け等）。

## ガードレール

- トランスクリプトが無ければ生成しない（手順2で中止）。
- **ユーザー確認前に `LOG.md`/`INDEX.md` を書き換えない**（誤プロジェクト汚染を防ぐ）。
- トランスクリプト本文を削除しない。
- トランスクリプトに無い情報を捏造しない。
- 日付はハードコードしない（会議日＝frontmatter `date`、`updated`＝当日 `date +%F`）。
- 既存議事録の上書きは確認してから。
- 既存プロジェクトの構成のばらつきは考慮しない（標準構成前提）。
````

- [ ] **Step 2: frontmatter と発見性を確認する**

`SKILL.md` を Read し、次を目視確認する:
- frontmatter が有効な YAML で `name: meeting-minutes`（ディレクトリ名と一致）。
- `description` に日本語要約＋トリガー（「議事録を作って」「トランスクリプトから議事録」「/meeting-minutes」「generate meeting minutes」）が含まれる。
- 手順 §1〜§8 ＋ ガードレールの見出しが全て存在する。

Expected: 全て満たす。

- [ ] **Step 3: プレースホルダ・スペル走査**

`SKILL.md` 内に `TBD`/`TODO`/`later`/`{name}` 等の未置換が**手順本文に残っていない**ことを確認する（スケルトン内の `{name}`/`{today}` は実行時置換のテンプレートなので可）。

Run: `grep -nE "TODO|TBD|後で|あとで" "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault/.claude/skills/meeting-minutes/SKILL.md"`
Expected: 一致なし（exit 1 / 出力なし）。

- [ ] **Step 4: コミット**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault/.claude"
git add skills/meeting-minutes/SKILL.md docs/specs/2026-06-25-meeting-minutes-skill-design.md docs/plans/2026-06-25-meeting-minutes-skill.md
git commit -m "feat(meeting-minutes): add minutes-generation skill + design docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: サンドボックスで実走検証する

**Files:**
- Create (一時): `…\My vault\05-meeting\__mm_test_meeting.md`
- Create (一時): `…\My vault\01-projects\work\__mm_test_project\CLAUDE.md`
- 検証後すべて削除する。

**Interfaces:**
- Consumes: Task 1 の `SKILL.md` 手順、受け入れ基準（spec §6）。
- Produces: 検証結果（合否）。必要なら `SKILL.md` への修正。

- [ ] **Step 1: テストプロジェクトを用意する**

`01-projects/work/__mm_test_project/CLAUDE.md` を作成（`LOG.md`/`INDEX.md` は**わざと作らない** = 不在時の自動作成を検証する）:

```markdown
---
tags:
  - project
  - work
status: active
created: 2026-06-25
updated: 2026-06-25
code: ZZ999
---

# __MM テスト案件（ZZ999）

## 概要
これは meeting-minutes スキル検証用のダミープロジェクト。テーマコードは ZZ999、キーワードは「バナナ検品ロボット」「ZZ999」。

## 関連リンク・リソース
- 
```

- [ ] **Step 2: テスト用ミーティングノートを用意する**

`05-meeting/__mm_test_meeting.md` を作成（短い疑似トランスクリプト付き。プロジェクト推定が `ZZ999` を一意に指すようにする）:

```markdown
---
title: __MM テスト会議
date: 2026-06-25
time: 10:00
tags:
  - meeting
  - work
---
# 会議情報

- **日付**: 2026-06-25 
- **参加者**: 

## 議題



## 決定事項

- 
- 

### アクションアイテム

- [ ] 

### 次回の予定



# Teamsトランスクリプト
__MM テスト会議-20260625-会議のトランスクリプト
2026年6月25日

Taro Yamada / TEST   0:01
ZZ999 のバナナ検品ロボットの件です。検品速度が要求に届いていないので、来週までに画像処理パラメータを見直します。

Hanako Suzuki / TEST   0:20
了解です。私はテストデータを 50 枚追加します。次回は 7月2日にレビューしましょう。
```

- [ ] **Step 3: SKILL.md の手順を実走する**

`SKILL.md` の手順 §1〜§8 を、対象ファイル `05-meeting/__mm_test_meeting.md` に対して実際に実行する（プロジェクト推定の確認は ZZ999 を選択した想定で進める）。実行後、次を Read で確認する。

- [ ] **Step 4: 受け入れ基準を検証する**

以下をすべて確認する（spec §6 対応）:
- `__mm_test_meeting.md`: 参加者に `Taro Yamada` / `Hanako Suzuki`、議題・決定事項・アクションアイテム（`- [ ]`）・`# 議事録` 本文が生成され、**`# Teamsトランスクリプト` 本文が残っている**。
- frontmatter に `project: "[[01-projects/work/__mm_test_project/CLAUDE|__MM テスト案件（ZZ999）]]"`（実プロジェクト名表示）が追加されている。
- `01-projects/work/__mm_test_project/LOG.md` が**新規作成**され、`## ログ` 先頭に `- 2026-06-25: …→ [[__mm_test_meeting]]` がある。`updated` が当日。
- `01-projects/work/__mm_test_project/INDEX.md` が新規作成され、`## ミーティング` に `- [[__mm_test_meeting]]` がある。`updated` が当日。

Run（リンク/見出しの存在確認）:
```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
grep -n "__mm_test_meeting" "01-projects/work/__mm_test_project/LOG.md" "01-projects/work/__mm_test_project/INDEX.md"
grep -n "Teamsトランスクリプト" "05-meeting/__mm_test_meeting.md"
```
Expected: LOG.md/INDEX.md に `[[__mm_test_meeting]]` がヒット、トランスクリプト見出しが残存。

- [ ] **Step 5: 不一致があれば SKILL.md を修正する**

検証で手順の曖昧さ・欠落（例: セクションが埋まらない、リンク形式が違う）が出たら、`SKILL.md` を Edit で修正し、Step 3〜4 を再実行する。

- [ ] **Step 6: テスト成果物を後始末する**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
rm -rf "01-projects/work/__mm_test_project"
rm -f "05-meeting/__mm_test_meeting.md"
```
Expected: テスト用ファイル/フォルダが消え、実データに変更が残らない（`git status` で `.claude/` 外の差分が無いこと、vault 側にテスト残骸が無いことを確認）。

- [ ] **Step 7: 修正があればコミットする**

Step 5 で `SKILL.md` を直した場合のみ:
```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault/.claude"
git add skills/meeting-minutes/SKILL.md
git commit -m "fix(meeting-minutes): refine procedure after sandbox verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage（spec §6 の受け入れ基準 → タスク対応）:**
- AC1（議事録生成＋トランスクリプト保持）→ Task1 §3 / Task2 Step4。
- AC2（トランスクリプト空で中止）→ Task1 §2 / ガードレール。
- AC3（プロジェクト推定＋確認、確認前に触らない）→ Task1 §4-§5 / ガードレール / Task2 Step3。
- AC4（LOG/INDEX 追記＋updated）→ Task1 §6 / Task2 Step4。
- AC5（LOG/INDEX 不在時の作成）→ Task1 §6 スケルトン / Task2（LOG/INDEX を作らず検証）。
- AC6（frontmatter project パス修飾）→ Task1 §7 / Task2 Step4。
- AC7（該当なしはスキップ報告）→ Task1 §5 / §8。
- AC8（処理結果の報告）→ Task1 §8。
  → 全 AC にタスクが対応。ギャップなし。

**2. Placeholder scan:** 手順本文に `TODO/TBD` なし。スケルトン内 `{name}`/`{today}`/`{type}`/`{会議日}`/`{mtgノート名}` は実行時置換用テンプレートで意図的（Task1 Step3 の grep 対象外）。

**3. Type consistency:** リンク形式は全箇所で統一 — LOG/INDEX→mtg は `[[{mtgノート名}]]`（basename）、mtg→project は `[[01-projects/{type}/{name}/CLAUDE|{name}]]`（パス修飾）。見出し名 `## ミーティング` / `## ログ` / `## 現状 / 次の一手` は spec と一致。
