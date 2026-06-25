# 設計: プロジェクト初期セットアップ＆運用スキル `new-project`

- **日付**: 2026-06-25
- **ステータス**: 承認待ち（実装計画フェーズ手前。frontmatter / `updated` 方針を反映して改訂）
- **対象**: Obsidian vault（PARA 構成）の `01-projects/` 配下に新規プロジェクトを作成・初期化する Claude Code スキル、および**プロジェクトが育つ過程の運用ルール**

---

## 1. 背景・目的

`01-projects/` は `personal/` と `work/` に分かれているが、各プロジェクトの構成がバラバラ（単一 `.md` のもの、`META.md`＋多数ノートのフォルダ型など）。`META.md` の形式も不統一。

**主目的は「構造の一貫性」** — どのプロジェクトも同じ標準構成で始まり、育っても「どこに何があるか」を迷わない状態を作る。

### 核心方針
Obsidian のプロジェクトは放置すると自由なノートが溜まる。ノートの山に構造を強制すると摩擦が出るため、一貫性は**役割ごとに分離した少数の固定ファイル**に宿らせる。各ファイルは単一目的・更新頻度別に分け、「どこに何を書く/探すか」を迷わせない:

- **CLAUDE.md** = 安定したアンカー（このプロジェクトは何か・どこに外部リソースがあるか）。**Claude が作業時に自動ロード**するため薄く保つ。
- **LOG.md** = 動的な作業日誌（今どこにいるか・何が起きたか）。
- **INDEX.md** = フォルダ内ノートのナビゲーション索引（MOC）。

「最初から3ファイル揃える」ことで、“いつ作るか・どこに書くか”の判断とルール記憶を不要にする（作成コストはスキルが負担し実質ゼロ）。

---

## 2. 確定した決定事項

| 論点 | 決定 |
|---|---|
| 最重視する価値 | 構造の一貫性（育っても迷わない） |
| 標準スケルトン | `CLAUDE.md` + `LOG.md` + `INDEX.md`（最初から全部作る） |
| 概要ファイル名 | **`CLAUDE.md`**（Claude が作業時に自動ロードする利点を優先） |
| CLAUDE.md の役割 | 安定アンカー。**最小・低頻度更新**。`概要` ＋ `関連リンク・リソース`（**外部リソース専用**） |
| LOG.md の役割 | `現状 / 次の一手`（最新状態）＋ `ログ`（時系列・新しいもの上） |
| INDEX.md の役割 | フォルダ内の重要ノートへの `[[…]]` 索引（MOC） |
| frontmatter | **3ファイルすべてに持たせる**。共通: `created` + `updated`。CLAUDE.md のみ追加で `tags`(`project`+`work`/`personal`) / `status` / `code`(任意) |
| `updated` の意味 | **そのファイルを編集した日**（編集時に当日日付へ更新）。LOG.md の `updated` が実質「最後に作業した日」 |
| ライフサイクル/アーカイブ | 今は決めない。`status` 欄は持つが done→archive の操作は将来 |
| 既存 META.md の扱い | 触らない。新規のみ（必要時に個別移行） |
| 横断台帳 (Bases) | v1 に含める（`01-projects/projects.base`）。CLAUDE.md を1行として `status`/`created`/`updated` で俯瞰 |
| スキル置き場 | `.claude/skills/new-project/` |

---

## 3. スコープ

### v1 でやること
1. 新規プロジェクトのフォルダ作成（`personal`/`work` 振り分け）
2. 3つの標準ファイルを生成：`CLAUDE.md`（当日日付・概要を反映）/ `LOG.md`（`作成` を seed）/ `INDEX.md`（プレースホルダ）。3ファイルとも `created`/`updated` を当日日付で初期化
3. 既存フォルダ衝突時の安全な中止
4. 横断台帳 `01-projects/projects.base` の用意
5. 運用ルール（育つ過程での更新作法）の spec 明文化（§4.3）

### v1 でやらないこと（将来の拡張）
- 既存 `META.md` プロジェクトの移行
- `LOG.md` 追記やステータス・`updated` 更新を自動化する別スキル
- `_templates/project.md`（Templater）の同期
- projects.base の高度なビュー（カード表示等）／ LOG.md を対象にした「最近の活動」横断ビュー

---

## 4. 詳細設計

### 4.1 生成スケルトン
```
01-projects/{personal|work}/{プロジェクト名}/
├─ CLAUDE.md     ← 安定アンカー（人 + Obsidian + Claude 自動文脈）
├─ LOG.md        ← 作業日誌（現状 + 時系列ログ）
└─ INDEX.md      ← フォルダ内ノートの索引（MOC）
```
- 上記以外のノートはトップ階層に自由追加。重要なものは `INDEX.md` から索引する。

### 4.2 ファイルテンプレート

**CLAUDE.md**（安定・最小）
```markdown
---
tags:
  - project
  - work            # personal の場合は personal
status: active      # active / paused / done / cancelled
created: 2026-06-25 # スキルが当日日付を自動挿入
updated: 2026-06-25 # アンカー（概要/外部リンク/status）を変えたら当日日付へ
code:               # 任意（KT569 等。値が無ければこの行を削除）
---
<!-- 運用: 現状/次の一手と経緯は LOG.md、ノート索引は INDEX.md に記録する。CLAUDE.md（概要・外部リンク・status）は内容が変わったときだけ更新する。編集したファイルは frontmatter の updated を当日日付に更新する。 -->

# {プロジェクト名}

## 概要
{入力された概要。未入力ならプレースホルダ「（目的・ゴールを1〜数行）」}

## 関連リンク・リソース
- （外部リソースのみ：SharePoint / ネットワークパス / リポジトリ など）
```

**LOG.md**（動的・作業のたびに更新）
```markdown
---
created: 2026-06-25
updated: 2026-06-25  # 作業して追記したら当日日付へ
---

# {プロジェクト名} — ログ

## 現状 / 次の一手
- （今どこにいるか／次にやること）

## ログ
- 2026-06-25: プロジェクト作成
```
- `ログ` は新しいエントリを上に追記（`- YYYY-MM-DD: 要点`）。

**INDEX.md**（ナビゲーション索引）
```markdown
---
created: 2026-06-25
updated: 2026-06-25  # 索引を更新したら当日日付へ
---

# {プロジェクト名} — INDEX

このフォルダ内の主要ノートへの索引。重要なノートが増えたら追記する。

- （例：[[ノート名]]）
```

**frontmatter フィールド定義**

| キー | 対象ファイル | 必須 | 値 | 備考 |
|---|---|---|---|---|
| `created` | 3ファイル共通 | ○ | `YYYY-MM-DD` | スキル実行日（Claude が currentDate から挿入） |
| `updated` | 3ファイル共通 | ○ | `YYYY-MM-DD` | そのファイルを編集した日。作成時は `created` と同じ |
| `tags` | CLAUDE.md のみ | ○ | `project` + (`work`\|`personal`) | `project` で全プロジェクト抽出。LOG.md/INDEX.md は `project` タグを持たない（台帳に出さない） |
| `status` | CLAUDE.md のみ | ○ | `active` / `paused` / `done` | 新規作成時は `active`。節目で更新 |
| `code` | CLAUDE.md のみ | × | 任意文字列（例 `KT569`） | 値が無ければ行ごと削除して生成 |

> `updated` は手動更新のため放置すると古くなりうるが、「編集と同時に当日日付へ」という単純ルール＋ CLAUDE.md 隠しコメントの誘導＋ Claude による自動更新で維持する。最近の活動は LOG.md の `updated`（＝最後に作業した日）が最も正確。

### 4.3 運用フロー（プロジェクトが育つ過程）
更新先を役割で固定し、「どこに書くか」を迷わせない。CLAUDE.md 冒頭の隠しコメントでも誘導する。

| 起きたこと | 書く場所 | updated |
|---|---|---|
| 作業した（進捗・次アクション） | **LOG.md**：`現状 / 次の一手` を更新し、`ログ` に1行追記 | LOG.md を当日日付へ |
| 重要なノートを作った | **INDEX.md**：`[[リンク]]` を追加（雑多なノートは索引しなくてよい） | INDEX.md を当日日付へ |
| 外部リソース（リンク/パス/リポジトリ）が増えた | **CLAUDE.md**：`関連リンク・リソース` に追記 | CLAUDE.md を当日日付へ |
| 目的・ゴールの認識が変わった | **CLAUDE.md**：`概要` を書き換え | CLAUDE.md を当日日付へ |
| 節目（着手/中断/完了） | **CLAUDE.md**：frontmatter `status` を更新 | CLAUDE.md を当日日付へ |

> 共通ルール: **編集したファイルの `updated` を当日日付に更新する**。CLAUDE.md は Claude が自動ロードするため薄く安定に保ち、現状・経緯・索引は同フォルダの `LOG.md` / `INDEX.md` を参照する。

### 4.4 横断台帳 `01-projects/projects.base`
- **目的**: プロジェクト横断で「どこに何があるか／ステータス／いつ更新したか」を1枚で俯瞰する自動更新台帳。
- **フィルタ**: `tags` に `project` を含むノート → 1 プロジェクト＝1 行（`project` タグを持つのは CLAUDE.md のみ。LOG.md/INDEX.md は出ない）。
- **列**: プロジェクト名（親フォルダ名）/ type / `status` / `created` / `updated` / `code`
- **ビュー**: 基本テーブル。「全件」＋「active のみ」を想定。既定ソートは `updated` 降順。
- **注意点（明記）**: 台帳の `updated` は CLAUDE.md（アンカー）の更新日。プロジェクトの最後の“作業”は各 `LOG.md` の `updated` が正確（横断ビューは将来拡張）。フィルタが `tags: project` のため、台帳に出るのは新規スキーマのプロジェクトのみ（既存 META.md は移行するまで出ない）。
- **実装上の注意**: `.base` の正確な YAML 構文・関数（`file.hasTag` / `file.folder` 等）は実装時にインストール済み Obsidian 版で検証する。

### 4.5 スキルの挙動
**起動**: `/new-project`（および「01-projects にプロジェクトを新規作成」等の意図）

**入力**（呼び出し時に指定が無ければ AskUserQuestion で対話確認）
- プロジェクト名（必須）
- 区分: `personal` / `work`（必須）
- 概要 1 行（任意 — 未入力ならプレースホルダ）
- `code`（任意）

**処理フロー**
1. 入力を取得・確定する。
2. ファイル名に使えない文字 `\ / : * ? " < > |` を含む名前を検出したら中止して指摘する。
3. パス `01-projects/{type}/{プロジェクト名}/` を算出する。
4. **同名フォルダが既に存在する場合は上書きせず中止し、その旨を報告する**（安全側）。
5. フォルダ + `CLAUDE.md` + `LOG.md` + `INDEX.md` を生成する（3ファイルの `created`/`updated` を当日日付、概要を反映、`LOG.md` に作成エントリ）。
6. 初回のみ（存在しなければ）`01-projects/projects.base` を生成する。既存なら触らない。
7. 作成したパスを報告し、Obsidian で開く案内を添える。

### 4.6 スキルファイル構成
```
.claude/skills/new-project/
└─ SKILL.md        ← フロントマター(name/description) + 手順
```
- 既存スキル（grill-me / handoff / slide-deck）の流儀に合わせる。
- `description` は「01-projects に新規プロジェクトを作成・初期化したいとき」を含むトリガー文にする。

---

## 5. エッジケース・注意点
- **既存フォルダ衝突**: 上書きしない。中止して報告（4.5 step 4）。
- **名前の不正文字**: Windows 禁止文字を検出して中止（4.5 step 2）。日本語名は許容。
- **新旧混在**: 既存 META.md プロジェクトは projects.base に出ない（4.4 注意点）。意図どおり。
- **`updated` の陳腐化**: 手動更新のため放置リスクあり。「編集と同時に当日日付へ」を徹底（4.3 共通ルール）。台帳の「最近の活動」は LOG.md の `updated` がより正確。
- **ファイル名の重複（vault 全体）**: 全プロジェクトが同名の `CLAUDE.md` / `LOG.md` / `INDEX.md` を持つため、`[[LOG]]` 等の basename wikilink は vault 全体で曖昧。テンプレートでは CLAUDE↔LOG↔INDEX 間の自動 wikilink を張らない（同フォルダ内の兄弟ファイルとして辿る／Claude は相対パスで参照）。Quick Switcher 等ではパス表示で区別する。
- **日付**: ハードコードせず、実行時の現在日付を用いる。

---

## 6. 受け入れ基準（Acceptance Criteria）
1. `/new-project` 実行で名前・区分・概要を確認のうえ、`01-projects/{type}/{name}/` に `CLAUDE.md` / `LOG.md` / `INDEX.md` が生成される。
2. `CLAUDE.md` が 4.2 のテンプレート（frontmatter `tags`/`status`/`created`/`updated`（+任意 `code`）+ 隠しコメント + `概要` + `関連リンク・リソース`）に一致し、`created`=`updated`=実行日、`status: active`、概要が反映されている（`code` 未指定時はその行が無い）。
3. `LOG.md` が frontmatter（`created`/`updated`=実行日）＋ `## 現状 / 次の一手` ＋ `## ログ`（`- {created}: プロジェクト作成`）を持つ。`INDEX.md` が frontmatter（`created`/`updated`=実行日）＋索引プレースホルダを持つ。
4. 同名フォルダが既存の場合、上書きせず中止し理由を報告する。
5. `01-projects/projects.base` が存在しなければ生成され、`tags: project` を持つ新規プロジェクト（CLAUDE.md）が status/created/updated とともにテーブルに1行として現れる。LOG.md/INDEX.md は行として出ない。
6. 既存の `META.md` プロジェクトは一切変更されない。
7. 運用フロー（§4.3）が spec に明文化され、CLAUDE.md の隠しコメントが「更新先の分担」と「updated の更新」を誘導している。

---

## 7. 将来の拡張（参考）
- `LOG.md` 追記・`updated`/`status` 更新を支援する `/project-log` 的スキル
- 既存 META.md → 新スキーマ移行スキル
- projects.base のビュー拡充（status 別グループ、カードビュー）／ LOG.md を対象にした「最近の活動」横断ビュー
- `_templates/project.md` の同期（Obsidian 手動作成でも同じ構成が出る）
- `LOG.md` / `INDEX.md` が肥大化した場合の分割運用ガイド
