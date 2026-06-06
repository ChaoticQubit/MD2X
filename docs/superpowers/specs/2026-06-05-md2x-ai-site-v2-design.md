# MD2X AI Site v2 — Design

Date: 2026-06-05
Status: Approved on paper (blocks model to be validated against real output)
Branch lineage: off `md2x-ai-site` (feature branch; not yet on `main`)

## Problem

`md2x site` produces "markdown on a webpage." `content.py` renders Markdown to a
verbatim pandoc HTML blob; `render.py` drops that blob into a fixed shell; the
page agent only bolts a one-sentence TL;DR + ≤4 takeaways on top. The AI never
shapes the page. For the `report` archetype the result is raw rendered markdown
plus a sentence — no reason to build an AI site over just reading the file.

Root cause is architectural, not prompt quality: `schemas.py` gives the model no
surface to design anything. The architect emits only nav order + index
title/intro + accent; the page agent emits only additive aids and is explicitly
forbidden from touching the body.

## Inspiration — Thariq Shihipar, "HTML is the new Markdown"

Anthropic Claude Code engineer. Thesis: a 1000-line markdown plan gets skimmed
or ignored; the fix is to "create a plan you actually want to read." The AI
**transforms** content into a polished, information-dense, scannable HTML
artifact — visual hierarchy, callouts, mockups, stat strips, interactive
sections — optimized for fast consumption, governed by an extracted **design
system** so output is coherent and on-brand. "The future of agent output isn't
more text. It's more readable interfaces."

Sources:
- https://www.chatprd.ai/how-i-ai/claude-code-anthropic-thariq-shihipar-on-replacing-markdown-with-html
- https://www.lennysnewsletter.com/p/how-i-ai-html-is-the-new-markdown

## Approach decision — typed blocks (not raw model HTML)

The page agent emits a **typed block tree** (hero, summary, stat-strip, callout,
card-grid, timeline, prose, figure, table, code, quote, raw_html escape-hatch);
`render.py` turns blocks into HTML using the design system. Chosen over having
the model emit raw HTML/CSS directly because this is a deploy-to-web static-site
CLI with a TDD test suite: render owns the HTML, so output is XSS-safe, valid,
escapable, on-brand, and assertable. Maximum-expressiveness raw HTML was
rejected on safety + testability grounds. The `raw_html` block remains as a
rare, sanitized escape hatch.

User decisions captured:
- Full fix: widen schema + render. (Approved; user will validate via real output
  before committing to the block vocabulary.)
- Add an opt-in **`synthesize`** fidelity tier that lets agents write net-new,
  clearly-labeled prose (exec summary, section abstracts, slide bullets, figure
  captions). Default tiers `preserve` / `light-enhance` keep author prose intact.
- Expand archetypes 7 → 11: add **resume/cv, changelog/release-notes, portfolio,
  academic/paper**.

## Delivery — three separate PRs (logging ships first)

### PR1 — Logging subsystem (this branch: `feat/site-logging`)
Independent, behavior-preserving, ships immediately.
- New `src/md2x/log.py`: stdlib `logging`, namespaced loggers under `md2x.*`,
  stderr handler, optional `--log-file` (file captures DEBUG regardless of
  console level), idempotent `setup_logging`.
- Level control: `-v/--verbose` (INFO→DEBUG), `--log-level`, `MD2X_LOG_LEVEL`
  env. Default INFO so every step is visible; `--quiet` → WARNING.
- Instrument every step across `cli`, `config`, `site/pipeline`, `site/cli`,
  `site/agents`, `site/models`, `site/render`, `deploy/vercel`: INFO for each
  pipeline step, DEBUG for model spec / prompt sizes / raw responses / timings /
  token usage, WARNING for every degradation or guardrail trip, ERROR for
  failures. Replaces existing `print()` / `stderr.write()`.
- Acceptance: `md2x site docs/ -v` streams a full step-by-step trace
  (config → N docs → per-doc build → architect → per-page → write → deploy);
  existing tests stay green.

### PR2 — Config / YAML documentation
- Comment every `ai.*` key in `md2x.yaml` and `config.py` defaults:
  `model`, `architect_model`, `page_model`, `temperature`, `max_tokens`,
  `concurrency`, `retries` — what each means and when to set it.
- Document the new `fidelity: synthesize` tier and any v2 design-system knobs.

### PR3 — AI site v2 (the core fix)
- `DesignSystem` schema + architect-derived design DNA (palette, type scale,
  density, components) → CSS variables reused across pages.
- `Block` / `PageDoc` schemas; page agent restructures content into a block
  tree designed for fast consumption (report → hero + synthesized summary +
  extracted stat-strip + finding callouts + section cards + preserved
  table/code/figure). `render.py` renders blocks; `preserve` fidelity falls back
  to today's verbatim path.
- 4 new archetypes; all system prompts rewritten on Thariq principles
  (information density, scannability, constrain-but-trust).
- `synthesize` fidelity tier gating net-new labeled prose.
- Guardrails — prompt layer (no fabricating facts absent from source, faithful
  meaning, real pages only, valid blocks) + code layer (schema-validate and
  repair-or-drop blocks, validate slugs/order cover all docs, sanitize all
  colors/CSS, HTML-escape every AI string, cap input/output sizes); each trip
  logs WARNING.
- PR3 gets its own `writing-plans` pass before implementation (largest surface).

## Data flow (v2, end state)

```text
inputs
  → build_doc (verbatim fragment + figure manifest)
  → architect agent → DesignSystem + SitePlan
  → [per page] page agent → PageDoc(block tree)
  → render(blocks, design system) → write_site
```
Logged end to end (PR1 instruments the existing flow; PR3 extends it).
