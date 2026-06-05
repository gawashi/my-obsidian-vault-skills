# slide-deck — skill maintenance & prerequisites

A Claude skill that scaffolds an OMRON-themed, offline reveal.js deck and fills it from provided material. See `SKILL.md` for the skill's behavior; this file is for whoever maintains or deploys the skill.

## What it produces

Invoking the skill copies `template/` into `<target>/slides/`:

```
slides/
├── index.html   ← the slides (1 <section> = 1 slide)
├── theme.css    ← OMRON theme tokens + component styles
├── present.cmd  ← double-click launcher
├── serve.mjs    ← zero-dependency local server (auto-picks a free port)
├── vendor/      ← reveal.js + Notes plugin (bundled, offline)
├── assets/      ← screenshots
└── 編集ガイド.md  ← how to self-edit the deck
```

## Prerequisites

- **Node.js** — required by `present.cmd` / `serve.mjs` (the presenter view needs a local HTTP server). Currently installed at `C:\Program Files\nodejs`.
- **Chrome** — recommended (launcher targets Chrome, falls back to the default browser).
- **Windows** — the launcher is a `.cmd`. On macOS/Linux, run `node serve.mjs` directly.

## Caveats

- **If Node is not installed:** `present.cmd` will fail to open the deck. Fix by installing Node.js. Without it you can still open `index.html` directly to read the content, **but the presenter view (S key) will NOT work** from `file://` — reveal.js requires the local server (`present.cmd`) for the speaker window.
- **Offline & self-contained:** `vendor/` is bundled, so there are zero CDN/network calls. Keep it that way — do not add external `<link>`/`<script>` URLs.
- **Existing `slides/`:** the skill must not overwrite a non-empty target; it asks first.
- **PDF export:** open `…/index.html?print-pdf` in Chrome → Print → Save as PDF (enable "Background graphics").

## Maintenance

- **reveal.js version:** `vendor/` holds a pinned reveal.js 5.x (`reveal.css`, `reveal.js`, `notes/notes.js`, `notes/speaker-view.html`). To update, replace those four files with a newer pinned build and re-run the render check in the implementation plan.
- **Re-theming:** edit `template/theme.css` `:root` tokens. Colors come from the OMRON "Gihon FY2023" PowerPoint theme (accent `#005EB8`, navy `#003366`, caution `#B40000`).
- **Portability:** this skill lives in the `.claude` git repo (`my-obsidian-vault-skills`), so it deploys to other machines via `git pull`. `vendor/` (~250 KB) is committed intentionally for offline self-containment.

## Provenance

Derived from the FY26 生成AI利活用 tutorial deck (`01-projects/work/FY26生成AI利活用/slides/`). The reveal engine (`serve.mjs`, `present.cmd`, `vendor/`) is reused as-is; `theme.css` was re-themed to OMRON and stripped to generic components; `index.html` and `編集ガイド.md` were generalized (FY26-specific diagrams and symbol rules removed). Locally authored — not an external upstream skill, so it is intentionally absent from `skills/SOURCES.md`.
