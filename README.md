# my-obsidian-vault-skills

個人のObsidian vault作業を支援するための [Claude Code](https://code.claude.com/) プラグイン。

## 収録スキル

| Skill | 概要 |
|-------|------|
| `new-project` | `01-projects/` 配下に標準構成（CLAUDE.md + LOG.md + INDEX.md）の新規プロジェクトを作成 |
| `update-project` | 既存の `01-projects` プロジェクトを育てる |
| `meeting-minutes` | 議事録を生成する |
| `handoff` | 作業の引き継ぎ用ドキュメントを作成する |
| `slide-deck` | スライドデッキを作成する |
| `grill-me` | 自己クイズで理解度を確認する |

## インストール（利用者向け）

```bash
/plugin marketplace add gawashi/my-obsidian-vault-skills
/plugin install vault@vault-skills
```

導入後は `/vault:<skill名>`（例: `/vault:new-project`）で呼び出せる。
更新は `/plugin marketplace update vault-skills`（マーケットプレイス単位で auto-update が効く）。

---

## For contributors（開発者向け）

### リポジトリ構成

```
.
├── .claude-plugin/
│   ├── plugin.json        # プラグイン定義（name: vault）
│   └── marketplace.json   # 配布カタログ（name: vault-skills, source: "./"）
├── skills/
│   ├── <skill-name>/
│   │   └── SKILL.md       # スキル本体（必須）
│   │   └── ...            # template/ scripts/ reference.md など補助ファイル（任意）
│   └── SOURCES.md         # 各スキルの出自（外部/自作）を管理
└── docs/
    ├── specs/             # 設計仕様（正本）
    └── plans/             # 実装計画
```

### 開発ループ（dogfooding）

用途に応じて 2 通り。

#### 方式A: `--plugin-dir .`（リポジトリ内で即時反映）

リポジトリのルートで `--plugin-dir` を付けて起動すると、スキルを**その場で**読み込む。
編集はそのまま反映されるが、claude を**このリポジトリのディレクトリで起動**する必要がある。

```bash
claude --plugin-dir .
```

#### 方式B: ローカルマーケットプレイス（実際の vault の中で試す）

「テスト対象の vault で実際に呼び出して動作確認したい」場合はこちら。
GitHub 版マーケットプレイスを外し、**ローカルのリポジトリパス**を登録し直す。

```bash
# 1. GitHub 版を外す（入っている場合）
/plugin marketplace remove vault-skills
# 2. ローカルのクローンを登録（パスは各自の clone 先に置き換え）
/plugin marketplace add path\to\my-obsidian-vault-skills
# 3. インストールして反映
/plugin install vault@vault-skills
/reload-plugins
```

以降、`skills/` を編集したら再 sync する:

```bash
/plugin marketplace update vault-skills   # マーケットプレイスを再取得
/reload-plugins                           # 反映（再起動不要）。反映されない場合はセッション再起動、または uninstall→install
```

> **注意**: marketplace 経由の install はプラグインをキャッシュ（`~/.claude/plugins/cache/`）へ
> コピーするため、ソースを編集しただけでは反映されない。方式B では編集後に上記の再 sync が要る。
> 編集→即反映を重視するなら方式A、実 vault での挙動確認を重視するなら方式B。

### バリデーション

Claude Code プラグインの構造が正しいかをチェックする。

```bash
claude plugin validate .
```

`version` 未指定の警告は意図的。

### 外部スキルの同期

外部から取り込んだスキル（`handoff`, `grill-me` など）の更新手順は `skills/SOURCES.md` の
「Update workflow」に従う。上流の `SKILL.md` を再取得 → ローカルの意図的な変更をマージ →
`Commit` / `Fetched` 列を更新する。
