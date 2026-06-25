# new-project スキル Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `01-projects/{personal|work}/` 配下に標準構成（CLAUDE.md + LOG.md + INDEX.md）の新規プロジェクトを作成・初期化し、`01-projects/projects.base` 台帳を用意する Claude Code スキルを作る。

**Architecture:** 実行コードは無く、Claude が辿る手順書 `SKILL.md` 一枚で完結する。SKILL.md は (1) 入力を対話取得し (2) 検証し (3) フォルダと3つのテンプレートファイルを当日日付で生成し (4) projects.base が無ければ作る。テンプレートと .base の中身は SKILL.md に埋め込む。

**Tech Stack:** Claude Code skill（Markdown 手順書）、Obsidian（frontmatter Properties / Bases `.base` YAML）。

## Global Constraints

- 設計の正本は `.claude/docs/specs/2026-06-25-new-project-skill-design.md`。本計画はその spec を実装する。
- スキル設置先: `.claude/skills/new-project/SKILL.md`（家の既存スキルと同じ流儀: frontmatter `name`/`description` + 命令形セクション）。
- 生成物の正本パス: `01-projects/{personal|work}/{プロジェクト名}/` 直下に `CLAUDE.md` / `LOG.md` / `INDEX.md`、および `01-projects/projects.base`。
- 日付はハードコードせず実行時の現在日付（`currentDate` / `date +%F`）を使う。作成時は `created` と `updated` を同じ当日日付にする。
- `project` タグを持つのは CLAUDE.md のみ（LOG.md / INDEX.md には付けない＝台帳に出さない）。
- 既存フォルダがあれば**上書きせず中止**。Windows 禁止文字 `\ / : * ? " < > |` を名前に含む場合は中止。
- CLAUDE↔LOG↔INDEX 間に自動 wikilink を張らない（vault 全体で basename 衝突するため）。
- **制約（重要）**: 実装エージェントは Obsidian を起動して Bases を目視レンダリングできない。`.base` は本計画に記載した「ドキュメントで確認済みの構文」のみを用い、ソート/フィルタ別ビュー等の追加調整は Obsidian の Base GUI で行う前提とする。`.base` の最終的なレンダリング確認はユーザーが Obsidian で行う。

---

### Task 1: `new-project` スキル本体（SKILL.md）を作成

**Files:**
- Create: `.claude/skills/new-project/SKILL.md`
- Commit対象に含める（docs）: `.claude/docs/specs/2026-06-25-new-project-skill-design.md`, `.claude/docs/plans/2026-06-25-new-project-skill.md`

**Interfaces:**
- Produces: スキル `new-project`（`/new-project` で起動）。実行時に `01-projects/{type}/{name}/{CLAUDE,LOG,INDEX}.md` と `01-projects/projects.base` を生成する手順書。
- Consumes: なし（新規）。

- [ ] **Step 1: SKILL.md を以下の内容で作成する**

ファイル `.claude/skills/new-project/SKILL.md`:

````markdown
---
name: new-project
description: Create and initialize a new project folder under 01-projects/ (personal or work) with a standardized CLAUDE.md + LOG.md + INDEX.md, and ensure the 01-projects/projects.base dashboard exists. Use when the user wants to start, create, scaffold, or set up a new project under 01-projects, or says "新規プロジェクト" / "プロジェクトを作って" / invokes /new-project.
---

# New Project

`01-projects/` 配下に標準構成の新規プロジェクトを作成・初期化する。目的は「どのプロジェクトも同じ構成で始まり、育っても迷わない」こと。設計の正本は `.claude/docs/specs/2026-06-25-new-project-skill-design.md`。

生成する標準構成:

```
01-projects/{personal|work}/{プロジェクト名}/
├─ CLAUDE.md   安定アンカー（概要＋外部リンク。Claude が作業時に自動ロード）
├─ LOG.md      現状/次の一手＋時系列ログ
└─ INDEX.md    フォルダ内ノートの索引（MOC）
```

加えて、横断台帳 `01-projects/projects.base` が無ければ作成する。

## 1. 入力を集める

呼び出し時の文章から拾えるものは拾い、不足分だけ AskUserQuestion で確認する（まとめて聞いてよい）。

- **プロジェクト名**（必須）: フォルダ名になる。日本語可。
- **区分**（必須）: `personal` か `work`。
- **概要**（任意）: 目的・ゴールを1行。未入力ならプレースホルダのままにする。
- **code**（任意）: テーマコード等（例 `KT569`）。`work` のときだけ尋ねる。無ければ付けない。

## 2. 検証する

- プロジェクト名に Windows 禁止文字 `\ / : * ? " < > |` が含まれていたら**中止**し、使えない文字を指摘する。
- 当日日付を取得する（`date +%F`、形式 `YYYY-MM-DD`）。
- 作成先パスを決める: `01-projects/{区分}/{プロジェクト名}/`。
- そのフォルダが**既に存在したら、上書きせず中止**し、既存である旨を報告する（中の確認だけ案内する）。

## 3. ファイルを生成する

フォルダ `01-projects/{区分}/{プロジェクト名}/` を作り、以下3ファイルを書き出す。`{名前}` `{区分}` `{概要}` `{当日}` `{code}` は実際の値に置換する。

**CLAUDE.md**（`code` が無ければ `code:` 行ごと削除する）:

```markdown
---
tags:
  - project
  - {区分}
status: active
created: {当日}
updated: {当日}
code: {code}
---
<!-- 運用: 現状/次の一手と経緯は LOG.md、ノート索引は INDEX.md に記録する。CLAUDE.md（概要・外部リンク・status）は内容が変わったときだけ更新する。編集したファイルは frontmatter の updated を当日日付に更新する。 -->

# {名前}

## 概要
{概要があればそれ。無ければ次の1行をそのまま置く}
（目的・ゴールを1〜数行）

## 関連リンク・リソース
- 
```

**LOG.md**:

```markdown
---
created: {当日}
updated: {当日}
---

# {名前} — ログ

## 現状 / 次の一手
- 

## ログ
- {当日}: プロジェクト作成
```

**INDEX.md**:

```markdown
---
created: {当日}
updated: {当日}
---

# {名前} — INDEX

このフォルダ内の主要ノートへの索引。重要なノートが増えたら追記する。

- 
```

## 4. 台帳 projects.base を用意する

`01-projects/projects.base` が**存在しなければ**、次の内容で作成する（存在すれば触らない）。

```yaml
filters:
  and:
    - file.hasTag("project")
properties:
  file.folder:
    displayName: Project
  status:
    displayName: Status
  created:
    displayName: Created
  updated:
    displayName: Updated
  code:
    displayName: Code
views:
  - type: table
    name: All Projects
    order:
      - file.folder
      - status
      - created
      - updated
      - code
```

> 注: ソートや「active のみ」ビューは Obsidian の Base GUI で追加する。`.base` のレンダリングは Obsidian でのみ確認できる。

## 5. 報告する

作成したフォルダとファイルのパスを列挙し、projects.base を作ったかどうかも伝える。Obsidian で CLAUDE.md を開くよう一言添える。

## 運用メモ（プロジェクトが育つとき）

- 作業したら → **LOG.md** の「現状 / 次の一手」を更新し「ログ」に `- {当日}: 要点` を1行（新しいものを上に）。
- 重要なノートを作ったら → **INDEX.md** に `[[リンク]]` を追加。
- 外部リソースが増えたら → **CLAUDE.md** の「関連リンク・リソース」に追記。
- 目的が変わったら → **CLAUDE.md** の「概要」を書き換え。
- 節目（着手/中断/完了）→ **CLAUDE.md** frontmatter の `status` を `active`/`paused`/`done` に。
- 共通: 編集したファイルの frontmatter `updated` を当日日付に更新する。
````

- [ ] **Step 2: SKILL.md を読み返し、spec の受け入れ基準 §6 と突き合わせる**

確認項目（すべて満たすこと）:
- frontmatter `name: new-project` と、起動意図を含む `description` がある。
- 入力（名前/区分/概要/code）取得、禁止文字チェック、既存フォルダ衝突で中止、の手順がある。
- CLAUDE.md テンプレートが spec §4.2 と一致（tags[project,{区分}] / status: active / created / updated / 任意 code / 隠しコメント / `# 名前` / `## 概要` / `## 関連リンク・リソース`）。
- LOG.md / INDEX.md テンプレートが spec §4.2 と一致（frontmatter created/updated、LOG は現状＋ログ＋作成エントリ、INDEX は索引プレースホルダ）。
- projects.base が `file.hasTag("project")` フィルタ＋ table ビューを持つ。

ズレがあれば Step 1 の内容を直す。

- [ ] **Step 3: コミット**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault/.claude"
git add skills/new-project/SKILL.md docs/specs/2026-06-25-new-project-skill-design.md docs/plans/2026-06-25-new-project-skill.md
git commit -m "feat(new-project): add project scaffold skill + design spec/plan

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: エンドツーエンド検証（使い捨てプロジェクトで実行→検証→片付け）

**Files:**
- 一時生成（検証後に削除）: `01-projects/personal/_scratch-test/`（および中の3ファイル）
- 生成・残す: `01-projects/projects.base`

**Interfaces:**
- Consumes: Task 1 の `SKILL.md`。
- Produces: 検証結果レポート。必要なら SKILL.md の修正。

- [ ] **Step 1: スキルの手順に従い、使い捨てプロジェクトを作る**

入力: 名前 `_scratch-test` / 区分 `personal` / 概要 `動作確認用の使い捨て` / code なし。
SKILL.md の手順どおりに `01-projects/personal/_scratch-test/` を作り、CLAUDE.md / LOG.md / INDEX.md を生成し、`01-projects/projects.base` が無ければ作る。

- [ ] **Step 2: 生成物を検証する**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
ls -la "01-projects/personal/_scratch-test"
echo "--- CLAUDE.md ---"; cat "01-projects/personal/_scratch-test/CLAUDE.md"
echo "--- LOG.md ---";    cat "01-projects/personal/_scratch-test/LOG.md"
echo "--- INDEX.md ---";  cat "01-projects/personal/_scratch-test/INDEX.md"
echo "--- projects.base ---"; cat "01-projects/projects.base"
```

Expected（spec §6 と照合）:
- 3ファイルが存在する。
- CLAUDE.md: `tags` に `project` と `personal`、`status: active`、`created`=`updated`=当日、概要が反映、`code:` 行が無い、隠しコメントと3見出し（概要/関連リンク・リソース）がある。
- LOG.md: frontmatter created/updated=当日、`## 現状 / 次の一手`、`## ログ` に `- {当日}: プロジェクト作成`。
- INDEX.md: frontmatter created/updated=当日、索引プレースホルダ。
- projects.base: `file.hasTag("project")` フィルタ＋ table ビュー。

ズレがあれば Task 1 の SKILL.md を直し、`_scratch-test` を削除して本 Step をやり直す。

- [ ] **Step 3: 既存フォルダ衝突の挙動を確認する**

もう一度同じ入力（`_scratch-test` / personal）でスキル手順を実行し、**「既に存在するため中止」**と報告され、ファイルが上書きされないことを確認する（CLAUDE.md の中身が変わっていないこと）。

- [ ] **Step 4: 使い捨てプロジェクトを片付ける**

```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault"
rm -rf "01-projects/personal/_scratch-test"
ls "01-projects/personal"
```
`projects.base` は残す（ユーザーが望んだ台帳。中身は live クエリなので、テストプロジェクト削除後は行が消えるだけ）。

- [ ] **Step 5: ユーザーに Obsidian での最終確認を依頼**

`01-projects/projects.base` を Obsidian で開き、テーブルが表示されること、必要なら GUI でソート（updated 降順）や「active のみ」ビューを追加できることを確認してもらう。Bases のレンダリングはエージェントからは確認できないため、この確認はユーザーが行う。

- [ ] **Step 6: 修正があればコミット**

SKILL.md を直した場合のみ:
```bash
cd "C:/Users/010230240/OneDrive - OMRON/ドキュメント/Obsidian/My vault/.claude"
git add skills/new-project/SKILL.md
git commit -m "fix(new-project): adjust skill per end-to-end verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage（spec §6 受け入れ基準 → タスク対応）:**
- AC1（3ファイル生成）→ Task1 Step1 / Task2 Step1-2 ✓
- AC2（CLAUDE.md テンプレ一致）→ Task1 Step1-2 / Task2 Step2 ✓
- AC3（LOG.md / INDEX.md）→ Task1 Step1 / Task2 Step2 ✓
- AC4（既存衝突で中止）→ Task1 Step1(§2) / Task2 Step3 ✓
- AC5（projects.base 生成・1行/プロジェクト）→ Task1 Step1(§4) / Task2 Step2,5 ✓
- AC6（既存 META.md 不変更）→ スキルは新規パスのみ作成、既存に触れない（Task1 §2 で衝突中止）✓
- AC7（運用フロー明文化＋隠しコメント誘導）→ SKILL.md「運用メモ」＋ CLAUDE.md 隠しコメント ✓

**2. Placeholder scan:** プレースホルダ（TBD/TODO 等）なし。テンプレ内の `{名前}` 等は「実値へ置換」と明示済み。`.base` のソート/別ビューは「GUI で追加」と意図的にスコープ外化（制約に明記）。

**3. Type consistency:** ファイル名（CLAUDE.md/LOG.md/INDEX.md/projects.base）、frontmatter キー（tags/status/created/updated/code）、`project` タグの所在（CLAUDE.md のみ）が全タスクで一貫。

**既知の制約:** Bases の目視レンダリング確認はエージェント不可 → ユーザーが Obsidian で実施（Task2 Step5、Global Constraints）。
