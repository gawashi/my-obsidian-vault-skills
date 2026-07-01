---
name: update-project
description: Update an existing project under 01-projects/ when its files need to change — record progress, a requirement/goal change, a new important note, a new sizable sub-task, a new external resource, or a status milestone. Routes the event to LOG.md / INDEX.md / CLAUDE.md and, for substantial sub-tasks, creates a new note (or subfolder) then registers it in INDEX.md and logs it in LOG.md. Use when the user reports progress on, or a status change of, an existing 01-projects project; when you finish, complete, or wrap up a task tied to that project (proactively offer to record it); or when the user invokes /update-project.
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
| 作業した（進捗・次アクション） | **LOG.md** | `## 現状 / 次の一手` を最新化し、`## ログ` 先頭に `- {当日} {時刻}: 要点` を追記（新しいものが上） |
| 重要なノートができた/作った | **INDEX.md** | 索引に `[[ノート名]]` を追加（雑多なノートは索引しなくてよい） |
| 外部リソース（リンク/パス/リポジトリ）が増えた | **CLAUDE.md** | `## 関連リンク・リソース` に追記 |
| 目的・ゴール・要件の認識が変わった | **CLAUDE.md `## 概要`** を書き換え ＋ **LOG.md** に変更を1行記録 | 重要変更は両方に残す |
| 節目（着手/中断/完了/中止） | **CLAUDE.md** frontmatter `status`（`active`/`paused`/`done`/`cancelled`）＋ **LOG.md** に1行 | |
| 比較的作業量の多いサブタスク・独立した作業領域が生まれた | **新規ノート（必要ならサブフォルダ）を作成 → INDEX 登録 → LOG 記録**（→ 4節） | |

**共通ルール**: 編集した各固定ファイルの frontmatter `updated` を**当日日付**に更新する。日付・時刻はハードコードせず、実行時の値を使う（日付 `date +%F` → `{当日}`、時刻 `date +%H:%M` → `{時刻}`）。`## ログ` 行は `{当日} {時刻}` で記録し、frontmatter は `{当日}` のみ（時刻は付けない）。

## 4. 新規ノート/サブフォルダ（重いサブタスク時）

- **判断**: 追記で済む軽い更新は 3節で処理。比較的作業量の多いサブタスク・独立した作業領域のときに新規ノートを作る。
- **ファイル名**: `YYYY-MM-DD-{トピック}.md`（既存ノート例 `2026-06-01-評価画面再設計-design.md` の流儀）。既定はプロジェクト直下。
- **frontmatter**: `created: {当日}` / `updated: {当日}` の2つだけ。**`project` タグは付けない**（台帳 `projects.base` に出さないため）。
- **本文**: `# {タイトル}` ＋ 目的を示す1行程度の薄い雛形のみ seed する。ユーザーが内容を渡せば反映。中身を勝手に膨らませない。
- **サブフォルダ**: そのサブタスクが複数ノート/添付を抱えるのが明らかなときだけ作る。名前に Windows 禁止文字 `\ / : * ? " < > |` を含めない。新規ノートはその中に置く。
- **作成後の整合（必須）**: INDEX.md に `[[リンク]]` を追加し、LOG.md に `- {当日} {時刻}: {サブタスク}（{ノート名}）` を1行記録。INDEX.md / LOG.md の `updated` を当日へ。

## 5. 計画を提示して適用する

1. 1〜4で決めた変更を、**ファイルごとの計画**として箇条書きで提示する（編集内容・新規作成するファイル/フォルダを明示）。
2. 承認を得てから一括適用する。触れた固定ファイルの `updated` を当日へ。新規ノートは必ず INDEX 登録＋ LOG 記録まで完了させる。

## 6. 報告する

変更・作成したパスを列挙して報告し、Obsidian で開く案内を一言添える。

## エッジケース

- **新スキーマでない（CLAUDE.md が無い）**: 勝手に scaffold しない。報告し、`/new-project` で初期化するか欠けている固定ファイルだけ作るかを尋ねる。
- **固定ファイルが空/見出しが無い**: CLAUDE.md はあるが LOG.md / INDEX.md が空、または期待する見出しを欠く場合は、`new-project` の標準骨組みを補完してから編集する（LOG.md: frontmatter ＋ `# {プロジェクト名} — ログ` ＋ `## 現状 / 次の一手` ＋ `## ログ`／INDEX.md: frontmatter ＋ `# {プロジェクト名} — INDEX` ＋ 索引の導入行＋リスト）。この骨組み補完を計画に明示し、承認後に適用する。
- **対象が曖昧/複数候補**: 候補を列挙して選ばせる（1節）。
- **新規ノート名の衝突**: 同名 `YYYY-MM-DD-{トピック}.md` が既存なら、連番/補足語を付けるか上書き回避を確認する。
- **禁止文字**: ノート/サブフォルダ名に Windows 禁止文字があれば指摘して調整する。
- **写像できない/実質変更が無い**: 推測で書かず、「何を・どこに記録したいか」を確認する。
- **対象外**: 旧 `META.md` プロジェクト・`projects.base` のスキーマは変更しない。完了は `status: done` を付けるだけでフォルダ移動はしない。
