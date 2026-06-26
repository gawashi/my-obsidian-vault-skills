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
更新は `/plugin marketplace update` → `/plugin update vault`。

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

リポジトリのルートで `--plugin-dir` を付けて起動すると、スキルを**その場で**読み込む。

```bash
claude --plugin-dir .
```

> marketplace 経由の install はプラグインをキャッシュへコピーするため編集が反映されない。
> dogfooding には必ず `--plugin-dir .` を使う。

### バリデーション

```bash
claude plugin validate .
```

`version` 未指定の警告は意図的。

### 外部スキルの同期

外部から取り込んだスキル（`handoff`, `grill-me` など）の更新手順は `skills/SOURCES.md` の
「Update workflow」に従う。上流の `SKILL.md` を再取得 → ローカルの意図的な変更をマージ →
`Commit` / `Fetched` 列を更新する。
