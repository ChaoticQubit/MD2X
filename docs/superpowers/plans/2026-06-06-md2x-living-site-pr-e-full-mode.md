# PR-E — `full` render mode (standalone author page) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** A new `author` agent emits one self-contained interactive HTML document per page; it is served **standalone** (a bare file linked from the index, no md2x chrome), but locked down: a CSP `<meta>` of `default-src 'none'` + a sanitizer strip external/network references, so the page can't phone home or pull remote code. Max fidelity, weakest testability — covered by structural invariants.

**Architecture:** `full_agent.run_full_page(doc, cfg)` returns a `FullPage(html, title, export)`. `full_render.render_full_page` injects the CSP meta + `--ds-*` tokens into the author's `<head>` (wrapping a fragment if needed) and runs `sanitize_full` (strips external `<script src>`/`<link>`, neutralizes external `<iframe>`/`<img>` URLs — inline scripts/styles are kept; that is the point of full mode; CSP is the real network boundary). `write_full_site` writes one standalone `<slug>.html` per doc + a minimal standalone index + the design-system page. `--no-ai`/`preserve`/failure use a deterministic FullPage that wraps the verbatim fragment.

**Tech Stack:** Python (stdlib `html`, `re`), agno/pydantic (author agent only), pytest.

---

## File Structure
- Create `src/md2x/site/full_render.py` — `FullPage`, `sanitize_full`, `render_full_page`, `write_full_site`, `_FULL_CSP`.
- Create `src/md2x/site/full_agent.py` — `run_full_page` (lazy agno).
- Modify `src/md2x/site/pipeline.py` — split plan/enh; route `render_mode == "full"` to `write_full_site` (no per-page enhancement).
- Modify `src/md2x/site/skill/render-modes/full.md` — enrich (keep the "full" marker).
- Test: `tests/test_site_full.py`; add a routing test to `tests/test_site_blocks_pipeline.py` (or a new `tests/test_site_full_pipeline.py`).

---

## Contract

```python
@dataclass
class FullPage:
    html: str                       # author's document (full doc or fragment)
    title: str = ""
    export: "Export | None" = None

_FULL_CSP = ("default-src 'none'; style-src 'unsafe-inline'; "
             "script-src 'unsafe-inline'; img-src data:; font-src data:")
```

`render_full_page(fp, ds_css)`: inject `<meta http-equiv="Content-Security-Policy" content="{_FULL_CSP}"><style>{ds_css}</style>` right after `<head>` (or synthesize a head / wrap a bare fragment), then `sanitize_full`. The CSP is a real meta tag here (not an escaped srcdoc), so `default-src 'none'` appears literally.

---

### Task 1: FullPage + sanitizer + page wrap
**Files:** Create `src/md2x/site/full_render.py`; Test `tests/test_site_full.py`.

- [ ] Failing tests:
  - `render_full_page(FullPage(html="<h1>Hi</h1><p>body</p>", title="T"), ":root{--ds-accent:#abc}")` → `<!doctype html` present, `Content-Security-Policy` + `default-src 'none'` present, `--ds-accent` present, body text `Hi`/`body` preserved.
  - keeps a full author doc's head: `render_full_page(FullPage(html="<!doctype html><html><head><style>.x{color:red}</style></head><body><div id=app></div><script>window.ok=1</script></body></html>", title="T"), "")` → `.x{color:red}` kept, `window.ok=1` kept (inline script survives), CSP injected once into head.
  - `sanitize_full` strips external `<script src="https://e/x.js">` and `<link href="https://e/x.css">`; neutralizes `<img src="https://e/x.png">` (no `https://e` left); keeps inline `<script>let a=1</script>`.
  - output has no `http://`/`https://`.
- [ ] Implement `FullPage` (import `Export` from `.blocks`), `_FULL_CSP`, `sanitize_full`, `render_full_page`.
- [ ] PASS. Commit `feat(site): standalone full-page wrap + sanitizer + CSP (PR-E)`.

### Task 2: author agent
**Files:** Create `src/md2x/site/full_agent.py`; Test add to `tests/test_site_full.py` (monkeypatched).

- [ ] Failing test: monkeypatched agent → `run_full_page` returns a `FullPage` whose html is the model's html and whose `export` is set when `export_label` present.
- [ ] Implement `_FullPageModel(html, title, export_format, export_label)`, `_SYSTEM` (author one self-contained interactive doc; consume `--ds-*`; no external network; editors implement the export contract; stay faithful to source facts), `run_full_page(doc, cfg)` building the agent via `build_model` + the loaded skill, returning `FullPage`. Lazy agno import.
- [ ] PASS. Commit `feat(site): full-mode author agent (PR-E)`.

### Task 3: write_full_site
**Files:** `src/md2x/site/full_render.py`; Test `tests/test_site_full.py`.

- [ ] Failing test: `write_full_site(out, docs, plan, cfg, use_ai=False)` writes `index.html` + one `<slug>.html` per doc + `design-system.html`; each page is standalone (CSP present, no `nav class="side"` chrome), preserves body text, no external URLs; index links the pages.
- [ ] Implement: per doc → `FullPage` (deterministic wrap of `f"<main><h1>{title}</h1>{fragment}</main>"`, or `run_full_page` when `use_ai and fidelity != preserve`, degrade on error) → `render_full_page(fp, ds_css)` → write. Index = minimal standalone doc (ds vars + CSP) linking slugs. Reuse `_accent`/`_design_for`/`design_css_vars`/`render_design_system_page`/`_copy_diagrams` from render/design_css.
- [ ] PASS. Commit `feat(site): write_full_site — standalone author pages (PR-E)`.

### Task 4: pipeline routing
**Files:** `src/md2x/site/pipeline.py`; Test `tests/test_site_full_pipeline.py`.

- [ ] Failing test: `generate_site` with `render_mode="full"`, `--no-ai` → routes to `write_full_site` (monkeypatch capture); body preserved; no per-page enhancement agent runs.
- [ ] Implement: split plan-building from enh-building; `if mode == "full": write_full_site(...)` (skip `_enhance_all`); else compute enh and route blocks/hybrid → `write_blocks_site`, else `write_site`.
- [ ] PASS. Commit `feat(site): route render_mode=full through standalone author pages (PR-E)`.

### Task 5: skill + regression
- [ ] Enrich `skill/render-modes/full.md` (self-contained, CSP/no-network, export contract, consume `--ds-*`). Commit `docs(skill): full-mode authoring contract (PR-E)`.
- [ ] Full suite green; WIP untouched. Update PR-E task; proceed to PR-F.

---

## Self-Review
- Spec coverage: author agent → standalone HTML ✓ (T2/T3), served standalone no chrome ✓ (T3), CSP + sanitize + no external network ✓ (T1), structural invariants in tests ✓ (T1/T3).
- Safety: top-level page CSP `default-src 'none'` blocks all subresource/network; sanitizer strips external refs (defense-in-depth). Inline scripts/styles kept — full mode's purpose.
- Backward-compat: new route + new files; blocks/hybrid/shell paths unchanged. Pipeline refactor preserves the architect degrade-to-default behavior.
