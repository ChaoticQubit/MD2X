# PR-C — `blocks` render mode for all archetypes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox steps.

**Goal:** Generalize the report blocks pipeline to every archetype: a typed `PageDoc { blocks }` vocabulary that `render.py`-style code owns (assertable block→DOM), plus one shared interactivity JS, consuming the `--ds-*` tokens from PR-B.

**Architecture:** New `blocks.py` (typed vocabulary — the contract PR-D's `artifact` block and PR-F extend) + `blocks_render.py` (block→HTML, block CSS/JS, minimal inline sanitizer). A deterministic `build_page_doc(doc)` powers `--no-ai`/preserve; an optional `run_page_blocks(doc, cfg)` authors blocks at `fidelity: synthesize`. `write_blocks_site` mirrors the proven `generate_report_site`: self-contained pages with the sidebar nav, `--ds-*` layer, block CSS/JS inlined. The pipeline routes non-report archetypes to it when `render_mode == "blocks"`. Existing shells (deck/landing/single-page) are untouched here; PR-F maps archetypes onto block layouts.

**render_mode × fidelity composition (blocks mode):**
| fidelity | PageDoc source |
|---|---|
| preserve / `--no-ai` | `build_page_doc(doc)` = `[Hero(title), Prose(verbatim section HTML)]` |
| light-enhance | deterministic PageDoc + the existing `PageEnhancement` aids rendered above the blocks |
| synthesize | `run_page_blocks(doc, cfg)` authors the full block tree |

**Tech Stack:** Python dataclasses, agno/pydantic (synthesize only), pytest. No new deps.

---

## File Structure
- Create `src/md2x/site/blocks.py` — typed block vocabulary + `PageDoc` + `build_page_doc`.
- Create `src/md2x/site/blocks_render.py` — `render_blocks`, `_BLOCKS_CSS`, `_BLOCKS_JS`, `sanitize_inline`, `sanitize_svg`, `write_blocks_site`.
- Create `src/md2x/site/blocks_agent.py` — `run_page_blocks` (lazy agno import; synthesize).
- Modify `src/md2x/site/pipeline.py` — route `render_mode == "blocks"` (non-report) to `write_blocks_site`.
- Test: `tests/test_site_blocks.py`, `tests/test_site_blocks_render.py`, `tests/test_site_blocks_pipeline.py`.

---

## The block vocabulary (contract — pin exactly)

```python
# blocks.py — leaf records
@dataclass
class Kpi: value: str; label: str = ""
@dataclass
class Card: title: str; body: str = ""; href: str = ""
@dataclass
class Event: when: str; title: str; body: str = ""
@dataclass
class ChartPoint: label: str; value: float
@dataclass
class Tab: label: str; html: str
@dataclass
class Step: title: str; body: str = ""
@dataclass
class Term: term: str; definition: str

# block types (each a dataclass; Block = Union of all)
Hero(title, subtitle="", kicker="")
Summary(text)
Prose(html)                       # author-verbatim HTML
KpiStrip(items: list[Kpi])
Callout(text, label="Note", tone="info")   # tone: info|warn|success
CardGrid(cards: list[Card])
Timeline(events: list[Event])
Table(headers: list[str], rows: list[list[str]])
Code(code, lang="")
Quote(text, cite="")
Figure(src, caption="", alt="")
Chart(kind, points: list[ChartPoint])       # kind: bar|line -> inline SVG
Tabs(tabs: list[Tab])
Collapsible(summary, html, open=False)
Steps(steps: list[Step])
DiagramSvg(svg)                   # sanitized inline SVG
Glossary(terms: list[Term])
RawHtml(html)                     # sanitized escape hatch

@dataclass
class PageDoc: slug: str; title: str; blocks: list = field(default_factory=list)
```

`build_page_doc(doc) -> PageDoc`: reuse `split_sections` (import from `.report.blocks`) →
`[Hero(doc.title)] + [Prose(intro_html)] + [Prose("<h2>title</h2>"+sec.html) per section]`.
Whole-body text is preserved verbatim (Prose is not escaped).

---

### Task 1: block model + deterministic builder
**Files:** Create `src/md2x/site/blocks.py`; Test `tests/test_site_blocks.py`.

- [ ] Failing test: `PageDoc` defaults; every leaf/block dataclass constructs; `build_page_doc(Doc(...))` returns a PageDoc whose first block is `Hero` with the title and whose Prose blocks contain the body text verbatim.
- [ ] Implement the dataclasses above + `Block` union alias + `build_page_doc`.
- [ ] Run → PASS. Commit `feat(site): typed block vocabulary + deterministic builder (PR-C)`.

### Task 2: block renderer + CSS/JS + sanitizer
**Files:** Create `src/md2x/site/blocks_render.py`; Test `tests/test_site_blocks_render.py`.

- [ ] Failing tests (block→DOM):
  - Each block renders its signature markup: `Hero`→`<header class="b-hero">` + escaped title; `KpiStrip`→`.b-kpi` cards with values; `Callout`→`.b-callout` + tone class; `CardGrid`→`.b-cards`; `Timeline`→`.b-timeline`; `Table`→`<table>` with `<th>`/`<td>` (cells escaped); `Code`→`<pre><code>` (escaped); `Quote`→`<blockquote>`; `Figure`→`<figure><img>` (alt escaped, `src` only if relative); `Chart`(bar)→inline `<svg>` with a `<rect>` per point (no external); `Tabs`→`.b-tabs` with `role="tab"` buttons + panels; `Collapsible`→`<details>`; `Steps`→`.b-steps` ordered; `Glossary`→`<dl>`; `DiagramSvg`→sanitized `<svg>`; `RawHtml`→sanitized.
  - Escaping: a `Callout(text="<script>x</script>")` renders escaped, no live `<script>`.
  - `sanitize_inline("<script>x</script><p onclick='e'>hi</p>")` strips `<script>` and `onclick`.
  - `sanitize_svg("<svg><script>x</script><rect/></svg>")` keeps `<rect`, drops `<script>`.
  - `render_blocks([...])` concatenates; output has no `http://`/`https://`.
- [ ] Implement: `render_block` dispatch (by type), `render_blocks(blocks)`, per-block helpers, `_chart_svg`, `sanitize_inline` (regex: strip `<script…>…</script>`, `on\w+=` attrs, `javascript:` URLs, `<iframe|<object|<embed`), `sanitize_svg` (allowlist `svg,g,path,rect,circle,line,polyline,polygon,text,defs,title` + drop `<script>`/`on*`), `_BLOCKS_CSS` (component styles referencing `var(--ds-*)`/`var(--accent)`/`var(--card)`), `_BLOCKS_JS` (tabs only; collapsible=native `<details>`, steps=CSS counters). All AI text escaped via `html.escape`; `Prose.html`/`DiagramSvg`/`RawHtml` are the only raw paths (latter two sanitized).
- [ ] Run → PASS. Commit `feat(site): block renderer + shared interactivity + sanitizer (PR-C)`.

### Task 3: write_blocks_site integration
**Files:** `src/md2x/site/blocks_render.py` (add `write_blocks_site`); Test `tests/test_site_blocks_render.py`.

- [ ] Failing test: `write_blocks_site(docs, out, plan, enh, cfg)` writes `index.html`, one `<slug>.html` per doc, `design-system.html`; each page contains the `--ds-accent` token, the sidebar nav (other doc titles), the block markup, and body text verbatim; enhancement TL;DR (when present in `enh`) appears above the blocks; no external URLs.
- [ ] Implement using render.py helpers (`_accent`, `_design_for`, `_nav_html`, `_enhancement_html`, `design_css_vars`, `render_design_system_page`, `_copy_diagrams`). Page = `_document`-style doc with head = ds `<style>` + `_BLOCKS_CSS`; body = `<div class="layout">{nav}<main>{enh_html}{render_blocks(page.blocks)}</main></div>`; tail = `_BLOCKS_JS`. Build each PageDoc: `synthesize`+ai → `run_page_blocks` (lazy import, degrade to deterministic on error); else `build_page_doc`.
- [ ] Run → PASS. Commit `feat(site): write_blocks_site — typed-block pages with nav (PR-C)`.

### Task 4: synthesize agent
**Files:** Create `src/md2x/site/blocks_agent.py`; Test add to `tests/test_site_blocks_render.py` (monkeypatch).

- [ ] Failing test: with `_make`-style agent monkeypatched, `run_page_blocks` converts a `_PageDocModel` into a `PageDoc` with typed blocks; counts capped; unknown block `type` dropped.
- [ ] Implement: `_BlockModel(type, +optional fields & sub-models)` for a focused emit set (`hero, summary, prose, callout, kpi_strip, card_grid, timeline, steps, tabs, table, quote, code, glossary`), `_PageDocModel(blocks)`, agent built via `build_model(ai, role="page")`, instructions reuse the loaded skill (caller passes), convert with guardrail caps (≤ N blocks, escape deferred to render). Lazy agno import (module imported only from `write_blocks_site`).
- [ ] Run → PASS. Commit `feat(site): synthesize block-authoring agent (PR-C)`.

### Task 5: pipeline routing
**Files:** `src/md2x/site/pipeline.py`; Test `tests/test_site_blocks_pipeline.py`.

- [ ] Failing test: `generate_site` with `render_mode="blocks"`, `--no-ai`, non-report archetype → routes to `write_blocks_site` (monkeypatch to capture), body text preserved; report archetype still routes to `generate_report_site`.
- [ ] Implement: after the report short-circuit, add `if cfg["site"]["render_mode"] == "blocks": return _generate_blocks_site(...)` that builds the plan (architect AI or `default_site_plan`) + enhancements (light-enhance) then calls `write_blocks_site`. Keep `full`/`hybrid` falling through to the existing shell path for now (PR-D/E swap them in).
- [ ] Run → PASS. Commit `feat(site): route render_mode=blocks through the block pipeline (PR-C)`.

### Task 6: regression
- [ ] Full suite green. WIP (`md2x.yaml`/`examples`) untouched. Update PR-C task; proceed to PR-D.

---

## Self-Review
- Spec coverage: expanded vocabulary ✓ (Task 1/2), render.py owns HTML/assertable ✓ (Task 2 block→DOM tests), shared interactivity JS ✓ (Task 2 `_BLOCKS_JS`), generalized to all archetypes ✓ (Task 3/5). 
- Sanitizer for `diagram_svg`/`raw_html` introduced here (minimal); PR-G hardens + adds the artifact-HTML sanitizer.
- Backward-compat: blocks path is a new route; existing shells/tests unchanged. Default `render_mode=blocks` reroutes the no-ai pipeline through `write_blocks_site`, which preserves body text (Prose verbatim) and the index — existing pipeline assertions hold.
