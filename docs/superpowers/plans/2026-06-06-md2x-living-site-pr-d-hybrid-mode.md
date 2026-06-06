# PR-D — `hybrid` render mode (sandboxed artifacts) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Extend the `blocks` tree with one `artifact` block — a self-contained interactive widget mounted in a sandboxed, CSP-locked `<iframe srcdoc>` that receives the `--ds-*` tokens, auto-sizes via `postMessage`, and (when it is an editor) round-trips its content out through the `md2x:export` contract. Everything outside artifacts stays typed and safe; the blast radius is the iframe.

**Architecture:** `hybrid` reuses the entire `blocks` pipeline (`write_blocks_site`); the only delta is a new `Artifact` block the renderer mounts as an isolated iframe and an artifact-enabled synthesize agent. The iframe carries `sandbox="allow-scripts"` (no `allow-same-origin` → null origin, cannot read the parent) plus a CSP of `default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:` → the artifact's own inline JS runs, but it cannot fetch, phone home, or touch md2x. The host page carries a tiny message broker: it resizes each iframe on `md2x:resize` and, for editor artifacts, a "copy/export" button posts `md2x:request-export` in and copies the `md2x:export` payload that comes back.

**Tech Stack:** Python (stdlib `html`), agno/pydantic (synthesize only), pytest. No new deps.

---

## File Structure
- Modify `src/md2x/site/blocks.py` — add `Export` + `Artifact` block.
- Modify `src/md2x/site/blocks_render.py` — `render_block(block, ds_css="")` / `render_blocks(blocks, ds_css="")`; `_artifact` renderer (iframe srcdoc + CSP + resize/export); artifact CSS; `_HYBRID_JS` host broker; thread `ds_css` from `write_blocks_site`.
- Modify `src/md2x/site/blocks_agent.py` — emit `artifact` blocks (html/css/js + export) in hybrid; light artifact-HTML sanitize.
- Modify `src/md2x/site/pipeline.py` — route `render_mode in ("blocks","hybrid")` to `write_blocks_site`.
- Modify `src/md2x/site/skill/render-modes/hybrid.md` — the artifact + export contract (keep the "hybrid" marker).
- Test: extend `tests/test_site_blocks_render.py`; add to `tests/test_site_blocks_pipeline.py`.

---

## Contract

```python
# blocks.py
@dataclass
class Export:
    format: str = "markdown"        # markdown | json | text
    label: str = "Copy"
@dataclass
class Artifact:
    kind: str                       # e.g. triage-board, prompt-tuner, chart
    title: str = ""
    html: str = ""
    css: str = ""
    js: str = ""
    export: "Export | None" = None
```

**srcdoc** (escaped into the attribute): a full HTML doc — CSP meta, `<style>{ds_css}{artifact.css} html,body{margin:0;font-family:var(--ds-font-sans);color:var(--ds-fg);background:transparent}</style>`, `body = artifact.html`, `<script>{artifact.js}; <resize poster></script>`. The resize poster posts `{type:'md2x:resize',height}` on load + ResizeObserver.

**host mount:** `<div class="b-artifact"><div class="b-artifact-bar"><span>{title}</span>{export_btn?}</div><iframe sandbox="allow-scripts" srcdoc="{escaped}" title="{title}" loading="lazy"></iframe></div>`.

**host broker `_HYBRID_JS`:** on `md2x:resize` set the matching iframe height; on `md2x:export` copy the payload; export button posts `{type:'md2x:request-export',format}` into its iframe.

---

### Task 1: Artifact block + Export
- [ ] Failing test: `B.Artifact(kind="chart").export is None`; `Export()` defaults.
- [ ] Implement `Export` + `Artifact` in `blocks.py`; add both to `Block`/`BLOCK_TYPES`.
- [ ] PASS. Commit `feat(site): artifact block + export contract type (PR-D)`.

### Task 2: artifact renderer + iframe sandbox + broker
- [ ] Failing tests:
  - `render_block(Artifact(kind="x", title="T", html="<b>hi</b>"), ds_css=":root{--ds-accent:#abc}")` → contains `sandbox="allow-scripts"`, `srcdoc=`, the CSP string `default-src 'none'`, the injected `--ds-accent`, and `b-artifact`; NO `allow-same-origin`; no raw `<b>hi</b>` outside the escaped srcdoc (i.e. `&lt;b&gt;` present in the attribute).
  - export button: `Artifact(..., export=Export(label="Copy MD", format="markdown"))` → `b-export` + `data-format="markdown"` + `Copy MD`.
  - no export → no `b-export`.
  - srcdoc has no external URL (`http://`/`https://`).
- [ ] Implement `_artifact(b, ds_css)`; change `render_block`/`render_blocks` to accept `ds_css=""` and pass it through (other blocks ignore it); register in `_RENDERERS` via a small wrapper that receives ds_css; add `.b-artifact`/`.b-artifact-bar`/`.b-export`/iframe CSS to `_BLOCKS_CSS`; append the `_HYBRID_JS` broker to the page tail in `_blocks_page_html`; thread `ds_css` from `_render_doc_page`/`write_blocks_site` into `render_blocks`.
- [ ] PASS. Commit `feat(site): mount artifacts in sandboxed CSP iframes + postMessage broker (PR-D)`.

### Task 3: synthesize agent emits artifacts (hybrid)
- [ ] Failing test (monkeypatched agent): a `_BlockM(type="artifact", kind="chart", html="<canvas></canvas>", export_format="json", export_label="Export")` converts to an `Artifact` with `export.format=="json"`; an artifact whose html contains `<script src="https://x">` is sanitized (external src removed).
- [ ] Implement: add artifact fields to `_BlockM` (`kind`, `html`, `css`, `js`, `export_format`, `export_label`); convert `type=="artifact"` → `Artifact(... export=Export(...) if export_label else None)`; run `html/css/js` through a light `_sanitize_artifact` (strip `<script src=…>`, external `src/href`, `fetch(`→`/*fetch*/`); CSP is the real guard, this is defense-in-depth). Add `artifact` to the type-enum description.
- [ ] PASS. Commit `feat(site): synthesize agent authors artifact blocks in hybrid (PR-D)`.

### Task 4: pipeline routing + skill
- [ ] Failing test: `generate_site` with `render_mode="hybrid"`, `--no-ai` → routes to `write_blocks_site` (monkeypatch capture).
- [ ] Implement: pipeline branch `if cfg["site"]["render_mode"] in ("blocks", "hybrid")`. Update `skill/render-modes/hybrid.md` to teach the artifact block + export contract.
- [ ] PASS. Commit `feat(site): route hybrid through the block pipeline + artifact skill (PR-D)`.

### Task 5: regression
- [ ] Full suite green; WIP untouched. Update PR-D task; proceed to PR-E.

---

## Self-Review
- Spec coverage: artifact block ✓ (T1), sandboxed-iframe mount + CSP + `--ds-*` injection + auto-size ✓ (T2), export round-trip ✓ (T2 broker + T1 type), agent authoring ✓ (T3), routing ✓ (T4). 
- Safety: `sandbox="allow-scripts"` without `allow-same-origin` + `default-src 'none'` CSP = no network, no parent access. Sanitizer is defense-in-depth; CSP is the boundary.
- Backward-compat: `render_block`/`render_blocks` gain an optional `ds_css=""` (existing calls unaffected); blocks pages always include the broker JS (harmless when no artifacts).
