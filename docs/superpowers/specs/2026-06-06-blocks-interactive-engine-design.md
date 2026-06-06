# Blocks Interactive Engine — Design

**Date:** 2026-06-06
**Status:** Approved (build greenlit)
**Mode of work:** execution fix on a locked design (no re-brainstorm of *what* — see
`2026-06-06-md2x-living-site-design.md` for the north star)

## Problem

`md2x site` output is static prose with no JavaScript, no animation, no state — the
opposite of the Thariq "HTML is the new Markdown" bar the project committed to. Root
causes, confirmed in code:

1. `md2x.yaml` runs `render_mode: full`, the one mode where md2x injects **zero** JS
   and the LLM authors the whole page — and the LLM defaults to a wall of prose
   (`site/fdet-charter.html`: 166 KB, **0** `<script>` tags).
2. Even `blocks`/`hybrid` mode ships only trivial JS (smooth-scroll, tab-click,
   scroll-spy) and a flat, GitHub-grey visual layer. No animation system, no client
   state, no real `.js` file — interactivity is inlined per page.

The design intent (interactive, animated, scannable, on-brand, end-with-export) is
correct and locked. The gap is **execution**.

## Decision

**Option 1 — md2x owns the system.** Upgrade `blocks` mode into a real engine: a
themeable, animated design system plus a genuine shared `assets/site.js` with client
state. Quality becomes deterministic code, not an LLM dice-roll. The LLM's job shrinks
to mapping content → typed blocks (it already does this); `--no-ai` still produces a
polished site. This is also the shared foundation of Option 3 (sandboxed artifacts on
top), so it forecloses nothing.

Rejected: Option 2 (model authors per page) — no quality floor, burns tokens every
render, and is the path already failing.

## Architecture

New module `src/md2x/site/theme.py` owns two shared assets:

- `SITE_CSS` — semantic token layer (`--ds-*` → `--accent`/`--bg`/`--card`/…),
  refined typography + depth (shadows, surfaces), the full component design system,
  animation primitives (`[data-reveal]` stagger, chart bar-grow), dark mode, and
  `prefers-reduced-motion` off-switch.
- `SITE_JS` — one vanilla IIFE, no deps, feature-detected and reduced-motion aware,
  built from small named **state functions** around a `createStore(initial, render)`
  primitive:
  - `revealOnScroll` — IntersectionObserver fade/rise, JS-assigned `--i` stagger
  - `countUp` — animate `[data-count]` numbers (parses prefix/number/suffix)
  - `scrollSpy` — active sidebar section
  - `tabs` — store-backed active panel
  - `sortableTables` — store-backed `{col,dir}`, `aria-sort`, chevrons
  - `copyButtons` — copy code to clipboard
  - `themeToggle` — light/dark/auto, persisted in `localStorage`, `data-theme` on `<html>`
  - `readingProgress` — top bar tracks scroll
  - `smoothAnchors`, `hybridBroker` (moved from inline)

`blocks_render.py` changes:

- `write_blocks_site` emits `assets/site.css` + `assets/site.js` **once**; doc + index
  pages link them (`<link>` / `<script src>`). Per-site `--ds-*` tokens stay **inline**
  in each page `<head>` (so the accent travels and `--ds-accent` stays assertable).
  `design-system.html` stays fully self-contained.
- Renderer hooks (markup only, render stays XSS-safe): `data-reveal` on component
  roots, `data-count` on KPI values, a copy button + wrapper on code, `data-sortable`
  on tables.

`full` mode, `blocks_agent` prompts, and caged artifacts are **out of scope** here.

## Data flow

`generate_site` → (blocks/hybrid) → `write_blocks_site` → writes shared assets, then
per-doc `_render_doc_page` (links assets, inlines tokens, renders typed blocks with
hooks). Unchanged: plan, enhancement, section-aware split, diagram copy.

## Safety

Self-contained, no network (relative asset links only; no CDN). All AI/derived strings
still HTML-escaped in render; `Prose`/`DiagramSvg`/`RawHtml` sanitized as today. JS is
defensive (try/catch, feature-detect, no `eval`). Animations disabled under
`prefers-reduced-motion`.

## Testing

- New `tests/test_site_theme.py`: `SITE_JS`/`SITE_CSS` contain the documented features,
  contain no `http`/`https`, expose `createStore` + reveal + count-up.
- Extend blocks-render tests: `write_blocks_site` writes `assets/site.{css,js}`, pages
  link them and keep tokens inline; renderer hooks (`data-reveal`, `data-count`, copy,
  `data-sortable`) present; existing escape/no-network asserts stay green.
- Full suite must stay green.

## Verification

Regenerate `~/Documents/FDET_Charter.md` in `blocks` mode (`--no-ai` first: fast, free,
proves the design floor; then with AI for block restructuring) and open it — real
reveal animations, scroll-spy, reading progress, theme toggle, a linked `site.js`.

## Out of scope (later, staged)

`full`-mode rework; richer `blocks_agent` prompting with Thariq exemplars; sandboxed
model-authored `artifact` widgets (Option 3); per-archetype composition recipes.
