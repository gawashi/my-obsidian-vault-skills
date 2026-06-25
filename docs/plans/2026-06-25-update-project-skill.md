# update-project Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author a single `update-project` skill that keeps an existing `01-projects/` project's files in sync with what happened — routing progress / requirement changes / new sub-tasks / external resources / milestones to LOG.md / INDEX.md / CLAUDE.md, and creating new notes (or subfolders) for substantial sub-tasks.

**Architecture:** One self-contained `SKILL.md` at `.claude/skills/update-project/` (sibling to `new-project`). The skill body is a procedure: identify target → read current state → route the event to one-or-more fixed files (and create a new note/subfolder when warranted) → present a per-file plan → apply on approval → bump `updated` → report. No code, no runtime; the "implementation" is the prose + routing table the skill follows. Verification is a read-only dry-run against a real project plus a writing-skills self-check.

**Tech Stack:** Markdown skill file (Claude Code skill format: YAML frontmatter `name`/`description` + body). Obsidian vault conventions. No build/test tooling.

## Global Constraints

These apply to every task. Values copied verbatim from `docs/specs/2026-06-25-update-project-skill-design.md`.

- Skill location: `.claude/skills/update-project/SKILL.md` (single file).
- Target must be a **new-schema project** — a folder under `01-projects/{personal,work}/` that contains `CLAUDE.md`. Never operate on old `META.md` projects; never modify `projects.base`.
- Target identification is **hybrid**: explicit name/path > infer from context + confirm once > list `CLAUDE.md`-bearing folders (`status: active` first) and let the user pick.
- Confirmation model: **plan-then-apply** — present a per-file list of changes (including any new files/folders) and apply only after approval.
- New note filename: `YYYY-MM-DD-{トピック}.md`; frontmatter is **`created` + `updated` only**; **no `project` tag** (only CLAUDE.md carries it, so notes stay out of the `projects.base` ledger).
- Subfolder only when a sub-task clearly holds multiple notes/attachments; names must avoid Windows-forbidden chars `\ / : * ? " < > |`.
- After any new note/subfolder: register it in `INDEX.md` (`[[link]]`) **and** record a line in `LOG.md` — never leave it unlinked.
- On every edited fixed file: set frontmatter `updated` to today. **Never hardcode dates** — use the current date at run time.
- Out of scope: initial scaffold (new-project's job), META.md migration, projects.base schema/view changes, archiving done projects.

---

### Task 1: Author the `update-project` SKILL.md

**Files:**
- Create: `.claude/skills/update-project/SKILL.md`

**Interfaces:**
- Consumes: the standard files produced by `new-project` — `CLAUDE.md` (frontmatter `tags`/`status`/`created`/`updated`/optional `code`, sections `## 概要` + `## 関連リンク・リソース`), `LOG.md` (`## 現状 / 次の一手` + `## ログ`), `INDEX.md` (index list). Reads `docs/specs/2026-06-25-new-project-skill-design.md` §4.3 as the canonical routing source.
- Produces: a skill named `update-project` that other workflows / `/update-project` can trigger. No code symbols.

- [ ] **Step 1: Create the file with frontmatter + body (write verbatim)**

Create `.claude/skills/update-project/SKILL.md` with exactly this content:

````markdown
---
name: update-project
description: Update an existing project under 01-projects/ (created by new-project) when its files need to change — record progress, a requirement/goal change, a new important note, a new sizable sub-task, a new external resource, or a status milestone. Routes the event to LOG.md / INDEX.md / CLAUDE.md and, for substantial sub-tasks, creates a new note (or subfolder) then registers it in INDEX.md and logs it in LOG.md. Use when the user reports progress on, a requirement/scope change to, new notes/work in, or a status change of an existing 01-projects project, or invokes /update-project.
---

# Update Project

`new-project` で作った `01-projects/` 配下のプロジェクトを「育てる」。起きたことに応じて固定3ファイル（CLAUDE.md / LOG.md / INDEX.md）へ追記・編集し、比較的作業量の多いサブタスクには新規ノート（必要ならサブフォルダ）を作り、INDEX 登録＋ LOG 記録まで整合させる。設計の正本は `.claude/docs/specs/2026-06-25-update-project-skill-design.md`。

固定ファイルの役割（new-project と共通。CLAUDE.md は Claude が自動ロードするため薄く保つ）:

- **CLAUDE.md** = 安定アンカー（概要・外部リンク・status）。
- **LOG.md** = 作業日誌（現状/次の一手＋時系列ログ）。
- **INDEX.md** = フォルダ内ノートの索引（MOC）。

## 1. 対象プロジェクトを特定する

1. 呼び出し文にプロジェクト名/パスがあればそれを採用する。
2. 無ければ会話の文脈・直近で触れたファイルから推測し、**1回だけ確認**する（例:「対象=`work/FHV7-AI向け良品学習アルゴ商品化支援` でいい？」）。
3. 曖昧/不明なら、`01-projects/{personal,work}` 配下で **CLAUDE.md を持つフォルダ**を候補に列挙し（frontmatter `status: active` を上位）、選んでもらう。
4. 対象に CLAUDE.md が無ければ新スキーマではない。**勝手に scaffold せず**、`/new-project` での初期化を促すか、欠けている固定ファイルだけ作るかを尋ねる（→ エッジケース）。

## 2. 現状を把握する

対象の **CLAUDE.md / LOG.md / INDEX.md を読む**（`status`、現状/次の一手、既存索引、既存の外部リンク）。これに基づいて編集内容を決める。

## 3. 起きたことをルーティングする

ユーザーの「起きたこと」記述（＋直近の会話）を解釈し、下表へ写像する。**1つの出来事が複数ファイルに波及してよい**。

| 起きたこと | 更新先 | 操作 |
|---|---|---|
| 作業した（進捗・次アクション） | **LOG.md** | `## 現状 / 次の一手` を最新化し、`## ログ` 先頭に `- {当日}: 要点` を追記（新しいものが上） |
| 重要なノートができた/作った | **INDEX.md** | 索引に `[[ノート名]]` を追加（雑多なノートは索引しなくてよい） |
| 外部リソース（リンク/パス/リポジトリ）が増えた | **CLAUDE.md** | `## 関連リンク・リソース` に追記 |
| 目的・ゴール・要件の認識が変わった | **CLAUDE.md `## 概要`** を書き換え ＋ **LOG.md** に変更を1行記録 | 重要変更は両方に残す |
| 節目（着手/中断/完了/中止） | **CLAUDE.md** frontmatter `status`（`active`/`paused`/`done`/`cancelled`）＋ **LOG.md** に1行 | |
| 比較的作業量の多いサブタスク・独立した作業領域が生まれた | **新規ノート（必要ならサブフォルダ）を作成 → INDEX 登録 → LOG 記録**（→ 4節） | |

**共通ルール**: 編集した各固定ファイルの frontmatter `updated` を**当日日付**に更新する。日付はハードコードせず、実行時の現在日付を使う。

## 4. 新規ノート/サブフォルダ（重いサブタスク時）

- **判断**: 追記で済む軽い更新は 3節で処理。比較的作業量の多いサブタスク・独立した作業領域のときに新規ノートを作る。
- **ファイル名**: `YYYY-MM-DD-{トピック}.md`（既存ノート例 `2026-06-01-評価画面再設計-design.md` の流儀）。既定はプロジェクト直下。
- **frontmatter**: `created: {当日}` / `updated: {当日}` の2つだけ。**`project` タグは付けない**（台帳 `projects.base` に出さないため）。
- **本文**: `# {タイトル}` ＋ 目的を示す1行程度の薄い雛形のみ seed する。ユーザーが内容を渡せば反映。中身を勝手に膨らませない。
- **サブフォルダ**: そのサブタスクが複数ノート/添付を抱えるのが明らかなときだけ作る。名前に Windows 禁止文字 `\ / : * ? " < > |` を含めない。新規ノートはその中に置く。
- **作成後の整合（必須）**: INDEX.md に `[[リンク]]` を追加し、LOG.md に `- {当日}: {サブタスク}（{ノート名}）` を1行記録。INDEX.md / LOG.md の `updated` を当日へ。

## 5. 計画を提示して適用する

1. 1〜4で決めた変更を、**ファイルごとの計画**として箇条書きで提示する（編集内容・新規作成するファイル/フォルダを明示）。
2. 承認を得てから一括適用する。触れた固定ファイルの `updated` を当日へ。新規ノートは必ず INDEX 登録＋ LOG 記録まで完了させる。

## 6. 報告する

変更・作成したパスを列挙して報告し、Obsidian で開く案内を一言添える。

## エッジケース

- **新スキーマでない（CLAUDE.md が無い）**: 勝手に scaffold しない。報告し、`/new-project` で初期化するか欠けている固定ファイルだけ作るかを尋ねる。
- **対象が曖昧/複数候補**: 候補を列挙して選ばせる（1節）。
- **新規ノート名の衝突**: 同名 `YYYY-MM-DD-{トピック}.md` が既存なら、連番/補足語を付けるか上書き回避を確認する。
- **禁止文字**: ノート/サブフォルダ名に Windows 禁止文字があれば指摘して調整する。
- **写像できない/実質変更が無い**: 推測で書かず、「何を・どこに記録したいか」を確認する。
- **対象外**: 旧 `META.md` プロジェクト・`projects.base` のスキーマは変更しない。完了は `status: done` を付けるだけでフォルダ移動はしない。
````

- [ ] **Step 2: Verify the file matches the new-project skill conventions**

Read `.claude/skills/new-project/SKILL.md` and confirm the new file follows the same shape: YAML frontmatter with `name` + `description`, an `#` H1 title, numbered procedure sections, and a trailing edge-case/notes section. Confirm the `description` contains explicit trigger phrases (progress, requirement/goal change, new note/sub-task, external resource, status, `/update-project`).

Expected: structure matches; no missing frontmatter keys.

- [ ] **Step 3: Self-check against the spec's acceptance criteria**

Open `docs/specs/2026-06-25-update-project-skill-design.md` §6 and confirm each of the 8 acceptance criteria is addressed by a section in the new SKILL.md:
1. Hybrid identification → §1
2. Progress → LOG (現状/次の一手 + ログ + updated) → routing row 1 + §5
3. Requirement/goal change → CLAUDE 概要 + LOG → routing row 4
4. External resource → CLAUDE links; milestone → CLAUDE status → rows 3 & 5
5. Heavy sub-task → new note (`created`/`updated` only, no `project` tag) + INDEX + LOG; subfolder when warranted → §4
6. Plan-then-apply → §5
7. No CLAUDE.md → report, don't scaffold → §1.4 + edge cases
8. META.md / projects.base untouched → edge cases / global constraints

Expected: every criterion maps to a section. Fix any gap inline.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/update-project/SKILL.md
git commit -m "feat(update-project): add skill to update existing 01-projects projects

Routes progress / requirement changes / new sub-tasks / external
resources / milestones to LOG.md / INDEX.md / CLAUDE.md, and creates
new notes (or subfolders) for substantial sub-tasks then registers
them in INDEX.md and logs them in LOG.md. Plan-then-apply confirmation.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Note: run `git` from the repo root (`.claude/`). The path above is repo-relative.

---

### Task 2: Verify the skill behaves correctly (dry-run + writing-skills check)

**Files:**
- (No file changes unless the dry-run surfaces a fix to `.claude/skills/update-project/SKILL.md`)

**Interfaces:**
- Consumes: the SKILL.md from Task 1; the real project `01-projects/work/FHV7-AI向け良品学習アルゴ商品化支援/` (has CLAUDE.md/LOG.md/INDEX.md) as a read-only fixture.

- [ ] **Step 1: Writing-skills self-check**

Invoke the `superpowers:writing-skills` skill and run its verification guidance against `.claude/skills/update-project/SKILL.md` (description triggering quality, body clarity, no dangling references). Note any recommended fixes.

Expected: skill passes the checklist, or yields a concrete list of fixes.

- [ ] **Step 2: Dry-run — progress event (read-only)**

Without writing any files, walk the skill against this input: *"FHV7 の良品学習しきい値検証が一通り終わった。次は帳票設計のレビュー。"* Confirm the skill would:
- identify target `work/FHV7-AI向け良品学習アルゴ商品化支援` (explicit name in input),
- read its CLAUDE/LOG/INDEX,
- produce a plan that updates `LOG.md` `現状 / 次の一手` + prepends a `- {today}: …` log line + bumps `LOG.md` `updated`,
- and present that plan before applying.

Expected: the produced plan matches acceptance criterion 2. No files written during the dry-run.

- [ ] **Step 3: Dry-run — heavy sub-task event (read-only)**

Walk the skill against: *"FHV7 に新しく『帳票出力の性能改善』という重めのサブタスクが追加された。"* Confirm the plan would:
- propose a new note `YYYY-MM-DD-帳票出力の性能改善.md` (frontmatter `created`/`updated` only, no `project` tag),
- consider a subfolder only if multiple notes/attachments are expected,
- register it in `INDEX.md` and add a `LOG.md` line,
- bump `updated` on INDEX.md and LOG.md,
- and present the per-file plan first.

Expected: matches acceptance criterion 5. No files written.

- [ ] **Step 4: Dry-run — no-CLAUDE.md edge case (read-only)**

Walk the skill against an old-schema target: *"FY26目標設定 に進捗を記録して"* (that folder has `META.md`, no `CLAUDE.md`). Confirm the skill reports it is not a new-schema project and offers to initialize via `/new-project` or create the missing fixed files — and does **not** scaffold automatically or touch `META.md`.

Expected: matches acceptance criterion 7 + global constraints. No files written.

- [ ] **Step 5: Apply fixes if any, then commit**

If Steps 1–4 surfaced fixes, edit `.claude/skills/update-project/SKILL.md` and commit:

```bash
git add .claude/skills/update-project/SKILL.md
git commit -m "fix(update-project): refine skill after dry-run verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

If no fixes were needed, skip the commit and note "verified, no changes required."

---

## Self-Review

**1. Spec coverage:** All 8 acceptance criteria (spec §6) are mapped in Task 1 Step 3 and re-exercised as dry-runs in Task 2 (criteria 2, 5, 7 explicitly; 1/3/4/6/8 covered by the SKILL.md sections + global constraints). Scope-out items (spec §3 "やらないこと") are encoded in Global Constraints + the SKILL.md edge-case section. No gaps.

**2. Placeholder scan:** The SKILL.md content is embedded verbatim in Task 1 Step 1 — no "TBD"/"implement later". Date tokens `{当日}` / `YYYY-MM-DD` / `{today}` are intentional run-time placeholders (the skill must not hardcode dates), not plan placeholders.

**3. Type consistency:** Not code, so no signatures. Cross-references are consistent: section numbers referenced in routing ("→ 4節", "→ §5") match the headings; file/section names (`## 現状 / 次の一手`, `## ログ`, `## 概要`, `## 関連リンク・リソース`, frontmatter `status`/`updated`/`created`/`tags`) match the new-project schema in `docs/specs/2026-06-25-new-project-skill-design.md`.
