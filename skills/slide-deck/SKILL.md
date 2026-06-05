---
name: slide-deck
description: 発表スライド（プレゼン資料）を reveal.js 自己完結デッキとして作る。OMRON 配色の雛形を新フォルダへ展開し、手元の素材（ノート/アウトライン/要点）からスライドを起こす。Use when the user wants to create presentation slides, build a slide deck, or プレゼン資料/発表資料を作る.
---

# slide-deck

Scaffold an OMRON-themed, offline, self-contained reveal.js deck into a target folder, then fill its slides from the user's material. The deck needs no build step and no internet: a bundled `vendor/` (reveal.js) plus a zero-dependency Node server (`present.cmd` → `serve.mjs`) drives the presenter view.

This skill owns the **production mechanism**, not content design. It turns material the user already has into slides. It does not run a goals/audience/story-arc design interview.

## Bundled template

`template/` next to this file is the canonical kit. It contains `index.html` (skeleton + component gallery), `theme.css` (OMRON tokens), `present.cmd`, `serve.mjs`, `vendor/`, `assets/`, and `編集ガイド.md`. Treat it as read-only source — copy it, never edit the template when building a deck.

## Workflow

1. **Confirm inputs.** Establish two things, asking only if not already clear:
   - **Output location** — where the deck folder goes. Default to a `slides/` subfolder of the relevant project (e.g. `01-projects/work/<topic>/slides/`). 
   - **Material** — the content to turn into slides: a path to an existing note, a pasted outline, or a topic plus key points. If there is no material, ask for it; never invent content.
2. **Propose an outline (checkpoint).** From the material, list the slides you intend to produce: title slide, then one line per slide giving its gist and which component it will use (見出し+本文 / 2カラム+callout / lead / code / placeholder / table / badge). Keep it short. Get a yes before generating HTML — this prevents rework.
3. **Scaffold.** Copy the entire `template/` folder to `<output>/slides/`. If a non-empty `slides/` already exists there, DO NOT overwrite — ask for a different folder name or explicit confirmation. Leave `vendor/`, `serve.mjs`, `present.cmd` untouched.
4. **Fill `index.html`.** Replace the gallery `<section>`s with the real slides, using the component classes (see below). Put narration/talking points in `<aside class="notes">`. For images not yet captured, leave a `placeholder` block stating what to capture. Keep the cover slide; fill its title/date/eyebrow.
5. **Respect the density discipline.** Body text stays at the kit's size (27px canvas). If a slide overflows, split it or use `class="fragment"` for progressive reveal — never shrink the font.
6. **Hand off.** Tell the user, in a few lines: present via `present.cmd` → Chrome → `S` for presenter view; edit by following `編集ガイド.md`; export PDF via `?print-pdf`; and that **Node.js is required** for `present.cmd`.

## Component conventions (material → class)

| Material shape | Component | Markup |
|---|---|---|
| Section title | heading | `<h2>…</h2><hr class="rule">` |
| Prose / bullets | body | `<p>…</p>` / `<ul><li>…</li></ul>` |
| Two parallel ideas | 2-column | `<div class="cols"><div class="col">…</div><div class="col">…</div></div>` |
| Key takeaway / caution | callout | `<p class="callout">…</p>` (add ` warn` for a red caution band) |
| One big statement | lead | `<p class="lead">…</p>` |
| Config / code | code block | `<pre class="code"><code>…</code></pre>` (escape `<` as `&lt;`) |
| Screenshot to capture later | placeholder | `<div class="placeholder"><div class="ph-title">🎬 …</div><div class="ph-spec">…</div></div>` |
| A short tag on a heading | badge | `<div class="headrow"><span class="badge">…</span><h2>…</h2></div>` |
| Comparison / mapping | table | `<table class="cmp"><tr><th>…</th>…</tr>…<tr class="root">…</tr></table>` |
| Speaker notes | notes | `<aside class="notes">…</aside>` |

Cover slide: `<p class="eyebrow">…</p><h1>…</h1><hr class="rule"><p class="src">日付 ｜ 発表者</p>`.

## Theme

The deck ships with the OMRON palette (white background, navy `#003366` headings, OMRON-blue `#005EB8` accent, red `#B40000` for caution, Meiryo UI). To re-theme, edit the `:root` tokens in the deck's `theme.css` — do not hard-code colors in `index.html`.

## Guardrails

- Do not edit files under `template/` while building a user deck — only the copy under `<output>/slides/`.
- Do not add CDN links or external dependencies; the deck must stay offline.
- Do not overwrite an existing non-empty `slides/` without confirmation.
- Do not fabricate content the user did not provide; ask for material instead.

See `README.md` (next to this file) for prerequisites (Node) and maintenance.
