---
name: new-project
description: Create and initialize a new project folder under 01-projects/ (personal or work) with a standardized CLAUDE.md + LOG.md + INDEX.md, and ensure the 01-projects/projects.base dashboard exists. Use when the user wants to start, create, scaffold, or set up a new project under 01-projects, or invokes /new-project.
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
