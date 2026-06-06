# MD2X Living Site — Design

Date: 2026-06-06
Status: Approved (brainstorming complete; drives an 8-PR rebuild)
Branch lineage: off `main` (which now carries the merged `md2x-ai-site` work)
Supersedes the open questions in `2026-06-05-md2x-ai-site-v2-design.md` (this is the v3 direction)

---

## Problem

`md2x site` is supposed to **transform** Markdown into a polished, living website —
not re-render the Markdown with chrome bolted on. Today it does the latter, by design:

- The whole pipeline runs at `fidelity: preserve | light-enhance`. The contract is
  literally "pandoc renders the body verbatim; the AI only builds design, navigation,
  and additive aids (TL;DR, takeaways, related links)." It **never transforms the body**.
- The one archetype that goes further, `report` (editorial-dashboard), only adds
  *synthesized top-matter* (hero / exec-summary / KPI strip / finding callouts) on top of
  the author's **verbatim** section HTML. Structurally that is still "a Markdown file on a
  website with some tags to click."
- None of the archetypes can produce a single interactive artifact.

The v2 spec made a decision that is the actual ceiling: **typed blocks, NOT raw model
HTML** — `render.py` owns all HTML for XSS-safety + testability, and raw model HTML was
*explicitly rejected*. A fixed block vocabulary structurally cannot express "a live ring
you add nodes to" or "a drag-drop board that exports Markdown." To reach the bar set by
Thariq's work, the model must be allowed to author real interactive HTML/CSS/JS — under
controlled conditions. This spec revisits that decision.

## Inspiration — Thariq Shihipar, "The unreasonable effectiveness of HTML"

Source: https://thariqs.github.io/html-effectiveness/ — a gallery of **20 working HTML
artifacts across 9 categories**, each proving one claim: *render information in the shape
it actually has.* Markdown flattens spatial/interactive information; HTML does not.

The 9 categories (and the artifacts that define them):

1. **Exploration & Planning** — 3 code approaches side-by-side; live visual-design
   directions; implementation plan (timeline + data-flow diagram + risk table).
2. **Code Review & Understanding** — annotated diff (margin notes, severity tags, jump
   links); PR writeup; module map (boxes/arrows, hot path).
3. **Design** — living design system (tokens → copyable swatches); component-variants sheet.
4. **Prototyping** — animation sandbox (duration/easing sliders); clickable 4-screen flow.
5. **Decks** — arrow-key slide deck, one HTML file, no build.
6. **Illustrations & Diagrams** — inline-SVG figure sheet; annotated flowchart (click a
   step → runs/timings/failure path).
7. **Research & Learning** — feature explainer (TL;DR, collapsible request-path, tabbed
   configs, FAQ); concept explainer (a **live** ring you add/remove nodes from, hover-linked
   glossary).
8. **Reports** — weekly status + chart; incident timeline.
9. **Custom Editing Interfaces** — triage board (drag tickets → export Markdown);
   feature-flag editor (dependency warnings + copy-diff); prompt tuner (edit template,
   inputs re-render live).

**Core principle (one line):** the agent should author real interactive artifacts — SVG,
JS widgets, drag/drop, live re-render — and **every editor ends in an export button** that
round-trips back to Markdown / the agent. "You stay in the loop; the loop gets tighter."

## Locked decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Add a config-selectable **`site.render_mode`** with three values: `blocks`, `hybrid`, `full`. Support all three; expand `blocks` too. | User wants the choice in `md2x.yaml`, not a single hard-coded strategy. |
| 2 | `render_mode` and `fidelity` are **orthogonal axes**. `render_mode` = how HTML is produced; `fidelity` (`preserve`/`light-enhance`/`synthesize`) = how much AI may rewrite prose. | Decouples "dynamic layout" from "content latitude." |
| 3 | Out-of-box default = **`render_mode: hybrid` + `fidelity: synthesize`** (flipped in the final PR, after the eval gate is green). | User's "don't sit on the content" — dynamic + transformed by default; restraint is opt-down. |
| 4 | The skill is **bundled into the repo and injected into md2x's agno agents every run** (instructions + reference patterns + design-system contract), composed per `(archetype × render_mode × fidelity)`. | "A skill the LLM uses every generation," literally and automatically. The agno agents are API agents, not Claude Code — so the skill is injected as instructions. |
| 5 | "Live / real-time" = **rich client-side interactivity in self-contained static files** (drag/drop, sliders, live re-render, clickable SVG) — no backend now, but structure for **backend seams later** via a `postMessage` export contract. | Output deploys as static files (Vercel); a tiny isolation + message contract makes a later live endpoint a drop-in, no rewrite. |
| 6 | `full` mode pages are served **standalone** — a bare AI-authored HTML file per page, linked from nav, no md2x chrome. Security baseline stays: **CSP + sanitize + no external network**. | User chose standalone over nav-wrapped. Security (the "can't touch your code / can't phone home" isolation) is orthogonal to chrome and is retained. |
| 7 | Guardrails + evals are built on **agno-native primitives** (provider-agnostic), with deterministic pytest. Anthropic-only features (Managed-Agents Outcomes, Advisor, refusal stop-reason) are **optional** enhancements when the model is Claude — never required. | Keeps the model-agnostic promise (md2x supports anthropic / openai / groq / openai-like). |
| 8 | Full rebuild — all archetypes move onto the new model; delivered as **focused, independently shippable PRs** off `main`. | User chose "skill + full rebuild"; matches the established PR workflow. |

## Architecture

Three **orthogonal** config axes, all driven by the skill:

```yaml
site:
  archetype: explainer     # WHAT kind of site (12 rebuilt archetypes)
  render_mode: hybrid      # HOW html is produced: blocks | hybrid | full
  fidelity: synthesize     # how much AI may rewrite prose: preserve | light-enhance | synthesize
```

**Design DNA, derived once.** The architect agent emits a `DesignSystem` (palette, type
scale, spacing, density, components) → one stylesheet of CSS variables
(`--ds-accent`, `--ds-bg`, `--ds-fg`, `--ds-space-*`, `--ds-font-*`, density) **plus a real
living-design-system page** (Thariq's tokens→swatches). Every artifact/iframe consumes those
variables, so even free-form `hybrid`/`full` output stays on-brand.

**Data flow** (extends the v2 end-state):

```text
inputs
  → build_doc (verbatim fragment + figure manifest)
  → architect agent  [+ skill] → DesignSystem + SitePlan (nav, order, per-page render_mode, per-page artifacts)
  → per page: page/author agent [+ skill] → PageDoc(blocks incl. artifact blocks)  ──or──  full standalone HTML doc
  → render(mode, design-system, sandbox) → write_site → (deploy)
```

Logged end to end (logging subsystem already shipped). "Seams later": artifacts are
isolated with a tiny `postMessage` export contract; swapping a `srcdoc` artifact for a live
endpoint later needs no rewrite.

## The skill (bundled, injected every run)

Lives in the package so it ships and every run loads it. Markdown files (diffable,
editable, and re-exposable later as a Claude Code `SKILL.md`):

```text
src/md2x/site/skill/
  SKILL.md              # spine: Thariq thesis, the contract, how to think
  principles.md         # render info in its shape · interactivity · export round-trip · density/scannability
  design-system.md      # DesignSystem contract: consume --ds-* vars, never hardcode color/space
  export-contract.md    # the postMessage schema every editor/artifact implements
  render-modes/
    blocks.md  hybrid.md  full.md
  artifacts/            # pattern library — one file each, with a known-good template
    triage-board.md  prompt-tuner.md  feature-flags.md  flowchart.md  module-map.md
    annotated-diff.md  live-demo.md  deck.md  animation-sandbox.md  clickable-flow.md
    svg-figure.md  comparison.md  chart.md
  archetypes/           # per-archetype specialization
    reading.md  presentation.md  flyer.md  product.md  docs.md  review.md
    plan.md  explainer.md  report.md  editor.md  design.md  custom.md
```

**Injection** — a small `skill.py` loader composes files into the agent `instructions`
given `(archetype × render_mode × fidelity)`:

- **architect** gets `SKILL + principles + design-system` → also plans *which artifact
  patterns each page needs* → `SitePlan` gains per-page `render_mode` + `artifacts: [id]` +
  the `DesignSystem`.
- **page/author** gets `SKILL + principles + design-system + <render-mode>.md +
  <archetype>.md + selected artifacts/*.md` → emits the page.
- Composed instruction size + source list logged at DEBUG.

## Render modes

**Shared:** the `DesignSystem` stylesheet is injected into every page **and into every
iframe**, so free-form output stays on-brand.

### `blocks`
`PageDoc { blocks: Block[] }`. Expanded union:
`hero · summary · prose · kpi_strip · callout · card_grid · timeline · table · code · quote ·
figure · chart(data→inline SVG) · tabs · collapsible · steps · diagram_svg(sanitized inline
SVG) · glossary · raw_html(rare, sanitized escape hatch)`.
`render.py` owns the HTML → fully assertable (block→DOM). Interactivity (tabs/collapsible/
steps) = one tiny shared vanilla-JS file, no per-block model JS. This is today's report path
generalized to all archetypes + a bigger vocabulary. Safest, most testable.

### `hybrid` (target default)
Same block tree **plus an `artifact` block**:

```text
artifact { kind, title, html, css, js, export?: { format, label } }
```

- `render.py` mounts each artifact in `<iframe sandbox="allow-scripts" srcdoc=… >` + CSP,
  injects `--ds-*` vars, auto-sizes via `postMessage`.
- If `export` is set → host renders a "copy as Markdown / download" button wired to the
  iframe's `postMessage({ type: 'md2x:export', payload })`. That is the round-trip contract.
- Everything outside artifacts stays typed/safe. **Blast radius = the iframe.**

### `full`
A new `author` agent emits one self-contained interactive HTML doc per page
(`{ html, title, export? }`) built against the design-system vars.

- Served **standalone**: a bare HTML file linked from nav (no md2x chrome).
- Sanitize + lock down: CSP `default-src 'none'; style-src 'unsafe-inline';
  script-src 'unsafe-inline'` → no external network, no remote fetch. Logged.
- Max fidelity; weakest testability — covered by structural invariants (see Evals Tier 1).

**Safety ladder:** `blocks` ⊂ `hybrid` ⊂ `full`. Every guardrail trip logs `WARNING`.

## Archetypes + artifact-pattern library

**Archetype** = site-level preset → `{ shell, default_layout, default_render_mode,
skill_file, suggested_artifacts }`. **Artifact pattern** = a reusable interactive widget the
agent drops into any archetype (hybrid/full) → one skill file + one known-good template.

**Rebuilt archetypes (12)** — all rewritten on Thariq principles, mapped to his 9 categories:

| Group | Archetypes | Thariq category |
|---|---|---|
| Narrative | `reading` · `presentation` · `flyer` · `product` | Decks, marketing |
| Technical | `docs` · `review` · `plan` · `explainer` | Code Review, Exploration/Planning, Research/Learning |
| Data / ops | `report` · `editor` · `design` | Reports, Custom Editing Interfaces, Design |
| Escape | `custom` | style_prompt drives everything |

(`resume` / `changelog` / `portfolio` / `academic` from the v2 spec are trivial extra
presets — a skill file + shell each; fold in later, not core to this rebuild.)

**Artifact-pattern library** (hybrid/full; architect selects per page):
`triage-board · prompt-tuner · feature-flags · flowchart · module-map · annotated-diff ·
live-demo · deck · animation-sandbox · clickable-flow · svg-figure · comparison · chart`.
Lighter ones (`tabs` `collapsible` `timeline` `kpi-strip` `glossary`) are **blocks** in
`blocks` mode, **artifacts** when richer. **Every editor-type artifact MUST implement the
export contract** (Thariq's "always end with an export button").

**Architect selection:** reads outlines + archetype → emits per-page `render_mode` (may
override site default) + `artifacts: [id]`. The skill teaches the catalog + when each applies.

## Guardrails + evals

Built on **agno-native** primitives (provider-agnostic) + deterministic pytest.

**Guardrails — two layers, every generation:**

- **Prompt layer** (in the skill): no fabricating facts absent from source · faithful
  meaning · only real page slugs · valid output for the mode · artifacts must consume
  `--ds-*` vars + ship the export contract when interactive · no external network/CDN.
- **Code layer** (deterministic; each trip logs `WARNING`):
  - agno `pre_hooks`: **prompt-injection / jailbreak guardrail default-on** (a hostile
    Markdown doc can't hijack the agent). **PII / moderation opt-in via config** (don't
    mangle the author's own content by default).
  - agno `post_hooks` + structured-output schema: blocks are schema-validated/repaired
    (today's path); **`full`/`hybrid` artifact HTML** runs a sanitizer (parses, strips
    external `<script src>`/`fetch`, enforces CSP, confirms self-contained). Repair-or-drop.
  - render invariants (v2 guardrails generalized): slugs/order cover all docs · sanitize
    colors/CSS · HTML-escape every AI string · cap input/output sizes.

**Evals — end-to-end site generation, 3 tiers:**

- **Tier 1 — deterministic (pytest, free, every CI run):** output HTML parses · no broken
  internal links · every doc → a page · design-system vars present (no stray hardcoded hex)
  · CSP present on full/hybrid · interactive editors expose the export button · size caps ·
  basic a11y (heading order, img alt). Over a small fixture markdown set.
- **Tier 2 — LLM-as-judge (agno Agent-as-Judge, opt-in, costs tokens):** a reference dataset
  of ~4 sample docs (report, explainer, deck, editor) → generate → judge against the
  **Thariq rubric**: (1) info rendered in its shape, (2) density + scannability, (3)
  faithfulness/no-fabrication, (4) interactivity present where the archetype calls for it,
  (5) on-brand. Score per dimension, threshold to pass. Same rubric the skill teaches —
  generation and grading share one source of truth.
- **Tier 3 — performance (agno `PerformanceEval`, optional):** per-archetype latency + token
  usage, to catch regressions.

Wiring: `tests/evals/` (Tier 1, CI) + `evals/` (Tier 2/3, opt-in behind `[ai]` + a flag).

## Delivery — focused PRs off `main`

Each PR is TDD + logged + independently shippable. Dependencies: A→B→{C,D,E}→F→G→H.

| PR | Scope | Ships |
|---|---|---|
| **A** | Skill scaffold (`src/md2x/site/skill/`) + `skill.py` loader; inject into architect/page instructions | Plumbing; behavior-preserving |
| **B** | `DesignSystem` schema → CSS vars + living-design-system page; config `render_mode` key + validation | Design DNA + config axis |
| **C** | `blocks` mode — generalize report pipeline to all archetypes + expanded vocabulary + shared interactivity JS | Safe typed blocks everywhere |
| **D** | `hybrid` mode — `artifact` block + sandboxed-iframe mount + CSP + `postMessage` export | Interactive artifacts |
| **E** | `full` mode — author agent → standalone sanitized HTML page | Max-fidelity pages |
| **F** | Archetype rebuild (12) + artifact-pattern library + architect per-page selection | Thariq taxonomy live |
| **G** | Guardrails (pre/post hooks + sanitizer) + evals (Tier 1 pytest, Tier 2 judge, Tier 3 perf) | Safety + quality gate |
| **H** | Flip defaults → `hybrid` + `synthesize`; README + `md2x.yaml` comment docs | Dynamic-by-default, once eval gate green |

The default flips **last** (PR-H) — modes land behind config first so each is validated
before becoming out-of-box.

## Constraints

- **Never commit the WIP `md2x.yaml` / `examples/` changes** — they are the user's local
  working state (a conflicted `md2x.yaml` and a removed `examples/sample.md`). Commit only the
  specific paths each PR touches; never `git add -A`.
- **Provider-agnostic** — everything routes through the existing model factory; no hard
  dependency on a single provider. Anthropic-only features are optional add-ons.
- **TDD** — red→green→refactor per PR; the existing test suite stays green.
- **Logging** — every pipeline step at INFO, model/prompt/timing/usage at DEBUG, every
  degradation or guardrail trip at WARNING (subsystem already in place).

## Open questions / future

- Anthropic-only enhancements (Managed-Agents Outcomes grade→revise loop, Advisor secondary
  model, `stop_reason: "refusal"` handling) — wire in as optional when `ai.model` is Claude.
- Extra doc-type presets (`resume`, `changelog`, `portfolio`, `academic`) — cheap follow-ups.
- A future live-data path (backend) reuses the artifact `postMessage` contract; out of scope now.
