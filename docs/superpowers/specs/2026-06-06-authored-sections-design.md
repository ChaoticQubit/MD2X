# Authored Sections — full-author render mode with a hard design-system contract

Date: 2026-06-06
Status: approved (brainstorm)

## Problem

`md2x site` (blocks mode) produces a coherent but *samey* page: the AI picks block
*type + content*, but every behavior — sortable, searchable, card links, layout,
animation — is a renderer default, not a per-section design choice. Result reads as
one repeating template, not the varied, glance-able, "majestic" feel of a
hand-authored Thariq page.

## Goal

A new opt-in render mode where the AI **authors each section's own components and
layout**, while a top-down **design-system contract** keeps every section sharing
one visual DNA (palette, fonts, spacing, radius) so the page stays seamless — not
choppy. Sections differ in *components/layout*; they share *style*.

## Non-goals

- Not replacing `blocks` mode — `blocks` stays the default and untouched.
- No LLM in the assembler.
- No raw model JS in the main document.
- Not a multi-page redesign — single seamless page per doc, as today.

## Decisions (locked in brainstorm)

1. **Full-author per section** — the AI writes real HTML/CSS (and JS only inside an
   iframe), not just typed blocks.
2. **Mixed container** — inline scoped HTML+CSS by default (one seamless scroll);
   a section needing custom JS is authored as a sandboxed CSP iframe instead.
3. **Hard enforcement** — md2x lints + rewrites every section's CSS: scope to the
   section root, allow only `var(--ds-*)` + the spacing/type scale, strip raw
   hex/rgb and off-scale px. Drift is impossible, not merely discouraged.
4. **Designer is per-PAGE, not per-section** — it sees all sections at once so it
   can merge/split/add/reorder coherently; keeps total calls ≈ N+2, not 2N+2.
5. **Assembler is deterministic Python** — stitch, scope, sanitize, inject assets,
   wire nav. No LLM.
6. **Inline sections carry ZERO JS** — keeps the safety surface to iframes only.
   Inline animation rides the existing engine hooks (`data-reveal`, `data-count`
   + IntersectionObserver in `assets/site.js`).

## Pipeline (4 stages)

```
docs ─▶ ARCHITECT (1 call) ─▶ SitePlan + DesignSystem(+spacing/type scales = CONTRACT)
     ─▶ DESIGNER  (1 call/page) ─▶ DesignTree: ordered list of SectionSpec
     ─▶ BUILDER   (N calls, parallel) ─▶ BuiltSection per spec
     ─▶ ASSEMBLER (0 calls, deterministic) ─▶ one seamless page
```

## IR — DesignTree

New dataclasses in `design_tree.py` (pydantic mirror lives in the designer agent):

```
SectionSpec:
  anchor: str            # stable id
  title: str             # heading
  intent: str            # 1-line: what this section must convey
  realization: str       # "inline" | "artifact"
  layout: str            # stack | grid | split | feature | table-led
  components: list[str]  # hints: "table:sortable,search", "cards:links,cols=3",
                         #        "kpis", "steps", "timeline", "callout", "chart"
  source_anchors: list[str]   # which doc H2(s) it draws from (merge/split trace)

DesignTree:
  slug: str
  sections: list[SectionSpec]
```

## Build outputs + the two realizations

- **inline** → new block `AuthoredSection(anchor, title, html, css)`.
  Renders `<section id="sec-{anchor}"><style>{scoped css}</style>{sanitized html}</section>`.
  Seamless, shares the page DOM, no JS.
- **artifact** → reuses the **existing** `Artifact` block (CSP iframe,
  `sanitize_artifact_html`). Zero new isolation code; this is the only place model
  JS runs.

## Hard-enforcement engine (`css_contract.py`)

- `scope_css(css, "#sec-{anchor}")` — prefix every selector so a section's CSS
  cannot reach outside its root.
- `lint_css(css, contract)` — keep declarations whose values use only
  `var(--ds-*)`, the spacing/type scale tokens, and an allowlisted set of
  props/units; **drop** declarations with raw hex/rgb or off-scale px (logged).
- `sanitize_inline_html(html)` — strip `<script>`, `on*=` handlers, `javascript:`
  URLs, stray `<style>`/`<iframe>`. Extends `sanitize.py`.

## Contract from the architect

Extend `DesignSystem` with explicit scales the builder must use:

- `space_scale`: e.g. `["0","4px","8px","12px","16px","24px","32px","48px","64px"]`
  → emitted as `--ds-space-*` tokens.
- `type_scale`: e.g. `["12px","14px","16px","20px","26px","34px","44px"]`
  → `--ds-fs-*` tokens.

The builder prompt receives the token + scale list and is told: style only via
these; the linter enforces it regardless.

## Safety net (never amputate)

- Designer fails/times out → mirror the doc's H2s 1:1 as inline specs
  (deterministic).
- A builder fails/times out → fall back to today's `run_section_blocks` typed
  render for that one section; if that also fails, condensed verbatim.
- Worst case for the whole page = the current deterministic render. No section is
  ever lost.

## Config

- New `site.render_mode: authored` (opt-in). `blocks` stays default.
- Reuses existing `ai:` knobs (model, concurrency, retries, timeout). `page_model`
  may override the builder model (raw HTML/CSS authoring may want a stronger model
  than llama-70b).

## New / changed files

New:
- `src/md2x/site/design_tree.py` — IR dataclasses.
- `src/md2x/site/section_designer.py` — per-page designer agent → DesignTree.
- `src/md2x/site/section_builder.py` — per-section builder agent → BuiltSection.
- `src/md2x/site/css_contract.py` — scope + lint + inline-HTML sanitize.

Changed:
- `blocks.py` — add `AuthoredSection` block.
- `blocks_render.py` — render `AuthoredSection`; `authored` assembler path.
- `agents.py` / `schemas.py` — architect emits spacing/type scales.
- `sanitize.py` — `sanitize_inline_html`.
- `theme.py` — emit `--ds-space-*` / `--ds-fs-*` tokens.
- config defaults + docs.

## Testing

- `css_contract`: scoping prefixes every selector; lint drops raw hex/px, keeps
  `var(--ds-*)`; sanitize strips script/on*/javascript:.
- `design_tree`: dataclass round-trip; pydantic→dataclass conversion.
- `section_builder`: inline output renders scoped+sanitized; artifact output maps
  to `Artifact`; fallback-on-failure path hits typed render.
- `AuthoredSection` renderer: emits `<section id>`, inlines scoped `<style>`, no
  `<script>`.
- Integration: `authored` mode end-to-end with `--no-ai` falls back deterministically;
  with a stub model produces a contract-clean page.
- Live smoke: FDET charter, assert one seamless page, varied sections, 0 raw hex
  leaks, 0 amputated sections.

## Risks

- **Linter over-strips** legit styles → sections look bare. Mitigate: generous but
  safe prop/unit allowlist; log every drop; smoke-test visually.
- **Builder on a weak model** writes ugly/broken HTML → worse than blocks. Mitigate:
  `page_model` override; typed fallback always available.
- **Token/time cost** up (builders write more output). Mitigate: per-page designer
  keeps call count flat; concurrency + timeout already tuned.
