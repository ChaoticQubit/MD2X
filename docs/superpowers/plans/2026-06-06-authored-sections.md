# Authored Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new opt-in `render_mode: authored` where the AI authors each section's own HTML/CSS (inline, seamless) or a sandboxed iframe widget, under a hard design-system contract (CSS scoped + linted to `--ds-*` tokens) so sections vary in components but share one visual DNA.

**Architecture:** `authored` is a thin variant of the existing `blocks` writer. A per-page **designer** agent emits a `DesignTree` (list of `SectionSpec`); parallel per-section **builder** agents emit either an `AuthoredSection` block (inline HTML+CSS, no JS) or reuse the existing `Artifact` block (CSP iframe for JS). The block renderer scopes + lints each authored section's CSS at render time (single trust boundary) and sanitizes its HTML with the existing `sanitize_inline`. Assembly, nav, scroll-spy, and shared `assets/site.{css,js}` are reused unchanged from blocks mode. Every failure path falls back to the typed blocks render, then verbatim — never amputated.

**Tech Stack:** Python 3, dataclasses, agno + pydantic (lazy-imported), pytest. No new deps.

---

## File Structure

New:
- `src/md2x/site/css_contract.py` — `scope_css(css, root)`, `lint_css(css)`, `enforce_section_css(css, root)`. The hard-enforcement engine.
- `src/md2x/site/design_tree.py` — `SectionSpec`, `DesignTree` dataclasses (pure data, no agno).
- `src/md2x/site/section_designer.py` — `run_designer(doc, cfg) -> DesignTree` (per-page agent).
- `src/md2x/site/section_builder.py` — `run_builder(spec, section_html, cfg) -> Block` (per-section agent → `AuthoredSection` | `Artifact`).
- `src/md2x/site/authored_agent.py` — `run_authored_page(doc, cfg, plan) -> PageDoc` (orchestrator: designer → parallel builders → assemble, with fallbacks).

Modify:
- `src/md2x/site/blocks.py` — add `AuthoredSection` dataclass; add to `Block`/`BLOCK_TYPES`.
- `src/md2x/site/blocks_render.py` — `_authored_section` renderer; dispatch in `render_block`; include `AuthoredSection` in `_section_nav_html`; authored branch in `_page_doc_for`.
- `src/md2x/site/design_css.py` — add `--ds-fs-1..6` type-scale tokens (+ `--ds-space-5/6`) to `_tokens`.
- `src/md2x/site/modes.py` — add `"authored"` to `RENDER_MODES`.
- `src/md2x/site/pipeline.py` — route `authored` through `write_blocks_site`; skip enhancement aids for authored.

Tests:
- `tests/test_css_contract.py`, `tests/test_design_tree.py`, `tests/test_section_builder.py`, `tests/test_authored_render.py`, `tests/test_authored_pipeline.py`.

Runner: `.venv/bin/python -m pytest`. Live: `.venv/bin/md2x site <md> -o site`.

---

## Task 1: css_contract.scope_css

**Files:** Create `src/md2x/site/css_contract.py`; Test `tests/test_css_contract.py`.

Scope every selector under a root so a section's CSS cannot escape its `<section>`. `:root`/`html`/`body` collapse to the root itself. `@media`/`@supports` bodies are scoped recursively; `@keyframes` pass through; `@import`/`@font-face`/`@charset` are dropped.

- [ ] **Step 1: failing tests**

```python
# tests/test_css_contract.py
from md2x.site.css_contract import scope_css, lint_css, enforce_section_css


def test_scope_prefixes_each_selector():
    out = scope_css(".a,.b{color:var(--ds-fg)}", "#s1")
    assert "#s1 .a" in out and "#s1 .b" in out

def test_scope_collapses_root_html_body():
    out = scope_css("body{padding:var(--ds-space-3)} :root{--x:1}", "#s1")
    assert "#s1 body" not in out and "#s1{padding" in out
    assert "#s1{--x:1}" in out

def test_scope_strips_import_and_fontface():
    out = scope_css('@import url(http://x);@font-face{font-family:x}.a{color:red}', "#s1")
    assert "@import" not in out and "@font-face" not in out and "#s1 .a" in out

def test_scope_handles_media_and_keyframes():
    css = "@media (max-width:600px){.a{color:var(--ds-fg)}}@keyframes k{from{opacity:0}}"
    out = scope_css(css, "#s1")
    assert "@media" in out and "#s1 .a" in out
    assert "@keyframes k" in out and "#s1 from" not in out
```

- [ ] **Step 2: run, expect ImportError/fail** — `.venv/bin/python -m pytest tests/test_css_contract.py -x`

- [ ] **Step 3: implement** (comment-strip → tokenize rules on a brace stack → rewrite selector lists). Real algorithm, no placeholders:

```python
"""Hard design-system enforcement for authored sections: scope a section's CSS
to its root and strip declarations that would break the shared visual DNA.

This is the single trust boundary that makes `render_mode: authored` safe to mix
into the main document — model CSS can neither escape its <section> nor introduce
an off-palette colour, foreign font, or off-scale size."""
from __future__ import annotations

import re

from ..log import get_logger

log = get_logger(__name__)

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_ROOTISH = re.compile(r"(?i)^(:root|html|body)$")
# at-rules we drop wholesale (network / font loading / charset)
_DROP_AT = re.compile(r"(?i)^@(import|font-face|charset|namespace)\b")
# at-rules whose *body* contains nested rules to scope
_NEST_AT = re.compile(r"(?i)^@(media|supports|container)\b")


def _split_rules(css: str):
    """Yield (prelude, body, is_block) at brace depth 0. prelude is the selector
    or at-rule head; body is the text inside the matching braces."""
    i, n, depth, start = 0, len(css), 0, 0
    head = None
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                head = css[start:i].strip()
                body_start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                yield head, css[body_start:i], True
                start = i + 1
    tail = css[start:].strip()
    if tail:
        yield tail, "", False


def _scope_selector_list(selectors: str, root: str) -> str:
    out = []
    for sel in selectors.split(","):
        sel = sel.strip()
        if not sel:
            continue
        if _ROOTISH.match(sel):
            out.append(root)
        else:
            out.append(f"{root} {sel}")
    return ",".join(out)


def scope_css(css: str, root: str) -> str:
    css = _COMMENT.sub("", css or "")
    parts = []
    for head, body, is_block in _split_rules(css):
        if not is_block:
            continue                       # stray declaration at top level — drop
        if head.startswith("@"):
            if _DROP_AT.match(head):
                log.debug("css_contract: dropped at-rule %r", head[:40])
                continue
            if head.lower().startswith("@keyframes"):
                parts.append(f"{head}{{{body}}}")     # keyframe selectors are not page selectors
                continue
            if _NEST_AT.match(head):
                parts.append(f"{head}{{{scope_css(body, root)}}}")
                continue
            log.debug("css_contract: dropped unknown at-rule %r", head[:40])
            continue
        parts.append(f"{_scope_selector_list(head, root)}{{{body.strip()}}}")
    return "".join(parts)
```

- [ ] **Step 4: run scope tests** — `.venv/bin/python -m pytest tests/test_css_contract.py -k scope -v` → PASS
- [ ] **Step 5: commit** — `git add src/md2x/site/css_contract.py tests/test_css_contract.py && git commit -m "feat(site): css_contract.scope_css — scope authored CSS to its section root"`

---

## Task 2: css_contract.lint_css + enforce_section_css

**Files:** Modify `src/md2x/site/css_contract.py`; Test `tests/test_css_contract.py`.

Drop declarations that break the shared DNA: raw colour literals (hex/rgb/hsl not via `var()`), any `font-family` not using `var(--ds-font-*)`, and off-scale `px` (allow a small set: scale steps + 1/2/3px borders). Keep everything else.

- [ ] **Step 1: failing tests**

```python
def test_lint_drops_raw_color_keeps_token():
    out = lint_css("#s .a{color:#ff0000;background:var(--ds-card)}")
    assert "color:#ff0000" not in out and "background:var(--ds-card)" in out

def test_lint_drops_foreign_font_keeps_token_font():
    out = lint_css("#s .a{font-family:Comic Sans} #s .b{font-family:var(--ds-font-sans)}")
    assert "Comic Sans" not in out and "var(--ds-font-sans)" in out

def test_lint_drops_offscale_px_keeps_scale_and_borders():
    out = lint_css("#s .a{margin:17px;padding:16px;border-width:1px}")
    assert "17px" not in out and "padding:16px" in out and "border-width:1px" in out

def test_enforce_section_css_scopes_then_lints():
    out = enforce_section_css(".a{color:#fff;gap:8px}", "#s1")
    assert "#s1 .a" in out and "#fff" not in out and "gap:8px" in out
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement** (append to `css_contract.py`):

```python
_PX_OK = {"0", "1px", "2px", "3px", "4px", "8px", "12px", "16px",
          "24px", "32px", "48px", "64px"}
_COLOR_LIT = re.compile(r"(?i)#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(")
_PX = re.compile(r"(?i)\b\d+(?:\.\d+)?px\b")


def _decl_ok(prop: str, value: str) -> bool:
    p, v = prop.strip().lower(), value.strip()
    if not p:
        return False
    has_var = "var(" in v
    if _COLOR_LIT.search(v) and not has_var:
        return False                              # raw colour → force a token
    if p in ("font", "font-family") and not has_var:
        return False                              # foreign font stack
    for px in _PX.findall(v):
        if px.lower() not in _PX_OK:
            return False                          # off-scale px
    return True


def lint_css(css: str) -> str:
    """Drop declarations that violate the contract; keep the rest. Operates on
    already-scoped CSS (rules of the form `<sel>{<decls>}`)."""
    out = []
    for head, body, is_block in _split_rules(css):
        if not is_block:
            continue
        if head.startswith("@"):
            if head.lower().startswith(("@media", "@supports", "@container")):
                out.append(f"{head}{{{lint_css(body)}}}")
            elif head.lower().startswith("@keyframes"):
                out.append(f"{head}{{{body}}}")
            continue
        kept = []
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, value = decl.split(":", 1)
            if _decl_ok(prop, value):
                kept.append(f"{prop.strip()}:{value.strip()}")
            else:
                log.debug("css_contract: dropped decl %r", decl.strip()[:60])
        if kept:
            out.append(f"{head}{{{';'.join(kept)}}}")
    return "".join(out)


def enforce_section_css(css: str, root: str) -> str:
    return lint_css(scope_css(css, root))
```

- [ ] **Step 4: run** — `.venv/bin/python -m pytest tests/test_css_contract.py -v` → all PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): css_contract.lint_css — strip off-DNA colour/font/px declarations"`

---

## Task 3: design_css type-scale tokens

**Files:** Modify `src/md2x/site/design_css.py:65-81` (`_tokens`); Test `tests/test_css_contract.py` (append) or existing design test.

Add fixed type-scale + extend spacing so the contract has tokens the builder references and the linter implicitly allows (via `var(--ds-*)`).

- [ ] **Step 1: failing test**

```python
# tests/test_css_contract.py (append)
from md2x.site.design_css import design_css_vars
from md2x.site.schemas import DesignSystem

def test_design_tokens_include_type_scale():
    css = design_css_vars(DesignSystem())
    for t in ("--ds-fs-1", "--ds-fs-3", "--ds-fs-6", "--ds-space-6"):
        assert t in css
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement** — in `_tokens`, after the space tokens, add:

```python
        "--ds-space-5": "3.5rem", "--ds-space-6": "5rem",
        "--ds-fs-1": "0.78rem", "--ds-fs-2": "0.92rem", "--ds-fs-3": "1rem",
        "--ds-fs-4": "1.25rem", "--ds-fs-5": "1.6rem", "--ds-fs-6": "2.2rem",
```

- [ ] **Step 4: run** → PASS. Re-run `tests/test_design*` to ensure no regression.
- [ ] **Step 5: commit** — `git commit -am "feat(site): add --ds-fs-* type scale + --ds-space-5/6 contract tokens"`

---

## Task 4: AuthoredSection block + renderer + nav

**Files:** Modify `blocks.py`, `blocks_render.py`; Test `tests/test_authored_render.py`.

`AuthoredSection(anchor, title, html, css)` renders a real `<section id>` with its CSS scoped+linted and HTML sanitized (plus a defensive `<style>` strip so CSS can only arrive via the `css` field). `_section_nav_html` must list it alongside `Section`.

- [ ] **Step 1: failing tests**

```python
# tests/test_authored_render.py
from md2x.site import blocks_render as br
from md2x.site.blocks import AuthoredSection, Section, Hero, PageDoc
from md2x.site.schemas import SitePlan, NavItem

def test_authored_section_scopes_css_and_sanitizes():
    b = AuthoredSection(anchor="roles", title="Roles",
                        css=".card{color:#ff0000;background:var(--ds-card)}",
                        html='<div class="card">Hi</div><script>evil()</script>')
    h = br.render_block(b)
    assert '<section id="roles"' in h and "b-section-h" in h
    assert "#roles .card" in h                 # scoped
    assert "#ff0000" not in h                   # linted out
    assert "var(--ds-card)" in h
    assert "<script>" not in h                  # sanitized
    assert "<style>" in h                       # css inlined via field

def test_authored_html_inline_style_block_is_stripped():
    b = AuthoredSection(anchor="x", title="X",
                        html='<style>.a{color:#fff}</style><p>k</p>', css="")
    h = br.render_block(b)
    assert "color:#fff" not in h and "<p>k</p>" in h

def test_section_nav_lists_authored_sections():
    page = PageDoc(slug="p", title="P", blocks=[
        Hero(title="P"), AuthoredSection(anchor="a", title="Alpha", html="", css="")])
    plan = SitePlan(nav=[NavItem(title="P", slug="p")], order=["p"])
    nav = br._section_nav_html(page, plan, "p")
    assert 'href="#a"' in nav and "Alpha" in nav
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3a: blocks.py** — add after `Section` (before the `Block` union), and include in `Block` + `BLOCK_TYPES`:

```python
@dataclass
class AuthoredSection:
    """A section whose inner HTML + CSS the AI authored directly (authored mode).
    The renderer scopes+lints the CSS to `#<anchor>` and sanitizes the HTML, so it
    is safe to inline in the main document. Carries no JS — JS lives in Artifact."""
    anchor: str
    title: str
    html: str = ""
    css: str = ""
```

- [ ] **Step 3b: blocks_render.py** — import `AuthoredSection` and `enforce_section_css`, add renderer + dispatch + nav:

```python
# imports
from .blocks import ( ... AuthoredSection ... )
from .css_contract import enforce_section_css

_INLINE_STYLE = re.compile(r"(?is)<style\b.*?</style\s*>")

def _authored_section(b: AuthoredSection) -> str:
    scoped = enforce_section_css(b.css, f"#{_e(b.anchor)}")
    html_no_style = _INLINE_STYLE.sub("", b.html or "")
    safe = sanitize_inline(html_no_style)
    style = f"<style>{scoped}</style>" if scoped else ""
    return (f'<section id="{_e(b.anchor)}" class="b-section b-authored" data-reveal>'
            f'{style}<h2 class="b-section-h">{_e(b.title)}</h2>{safe}</section>')
```

In `render_block`, add before the `_RENDERERS` lookup:

```python
    if isinstance(block, AuthoredSection):
        return _authored_section(block)
```

In `_section_nav_html`, change the section filter:

```python
    secs = [b for b in page.blocks if isinstance(b, (Section, AuthoredSection))]
```

- [ ] **Step 4: run** — `.venv/bin/python -m pytest tests/test_authored_render.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): AuthoredSection block — scoped+linted inline section render"`

---

## Task 5: design_tree IR

**Files:** Create `src/md2x/site/design_tree.py`; Test `tests/test_design_tree.py`.

- [ ] **Step 1: failing test**

```python
# tests/test_design_tree.py
from md2x.site.design_tree import SectionSpec, DesignTree

def test_section_spec_defaults():
    s = SectionSpec(anchor="a", title="A")
    assert s.realization == "inline" and s.layout == "stack"
    assert s.components == [] and s.source_anchors == []

def test_design_tree_holds_sections():
    t = DesignTree(slug="p", sections=[SectionSpec(anchor="a", title="A")])
    assert t.slug == "p" and len(t.sections) == 1
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement**

```python
"""The intermediate representation between the designer and builder agents."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SectionSpec:
    anchor: str
    title: str
    intent: str = ""
    realization: str = "inline"            # inline | artifact
    layout: str = "stack"                  # stack | grid | split | feature | table-led
    components: list[str] = field(default_factory=list)
    source_anchors: list[str] = field(default_factory=list)


@dataclass
class DesignTree:
    slug: str
    sections: list[SectionSpec] = field(default_factory=list)
```

- [ ] **Step 4: run** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): DesignTree IR for authored mode"`

---

## Task 6: section_designer agent

**Files:** Create `src/md2x/site/section_designer.py`; Test `tests/test_section_builder.py` (designer half).

Per-page agent: sees all H2 section headings + a digest, emits a `DesignTree`. Uses `invoke_agent` (timeout + logging). Tests monkeypatch `invoke_agent` so no network.

- [ ] **Step 1: failing test**

```python
# tests/test_section_builder.py
import md2x.config as config
from md2x.site import section_designer as sd
from md2x.site.design_tree import DesignTree

def _cfg():
    return config.deep_merge(config.DEFAULTS, {})

class _Resp:
    def __init__(self, content): self.content = content

def test_run_designer_maps_model_to_tree(monkeypatch):
    fake = sd._TreeM(sections=[
        sd._SpecM(anchor="roles", title="Roles", realization="inline",
                  layout="grid", components=["table:sortable"], source_anchors=["roles"])])
    monkeypatch.setattr(sd, "invoke_agent", lambda *a, **k: _Resp(fake))
    tree = sd.run_designer(_make_doc(), _cfg())
    assert isinstance(tree, DesignTree)
    assert tree.sections[0].anchor == "roles" and tree.sections[0].layout == "grid"
```

(Add a `_make_doc()` helper that builds a `Doc` with two H2 sections — reuse from existing tests.)

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement** — model schema + runner. Mirror `blocks_agent._build_agent` (uses `build_model(ai, role="designer")`, `build_pre_hooks`, `invoke_agent`). System prompt: "You are an information architect. Given a document's sections, design the WEBSITE's sections: you may merge, split, reorder, or add (a hero/overview/CTA). For each, choose realization (inline unless it needs custom JS interactivity → artifact), a layout, and component hints (e.g. 'table:sortable,search', 'cards:links,cols=3'). Stay faithful to the source." Convert `_TreeM`→`DesignTree`. On the architect role override, `designer_model` falls back to `model` via `build_model`.

- [ ] **Step 4: run** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): section_designer agent — per-page DesignTree"`

---

## Task 7: section_builder agent

**Files:** Create `src/md2x/site/section_builder.py`; Test `tests/test_section_builder.py` (builder half).

Per-section agent: given a `SectionSpec` + the source section HTML + the token list, authors the section. Returns `AuthoredSection` (inline) or `Artifact` (artifact). The renderer enforces CSS; the builder just carries raw output into the block (single trust boundary stays at render).

- [ ] **Step 1: failing tests**

```python
from md2x.site import section_builder as sb
from md2x.site.blocks import AuthoredSection, Artifact
from md2x.site.design_tree import SectionSpec

def test_builder_inline_returns_authored_section(monkeypatch):
    fake = sb._BuiltM(realization="inline", html="<div class='c'>x</div>",
                      css=".c{color:var(--ds-fg)}")
    monkeypatch.setattr(sb, "invoke_agent", lambda *a, **k: _Resp(fake))
    blk = sb.run_builder(SectionSpec(anchor="a", title="A"), "<p>src</p>", _cfg())
    assert isinstance(blk, AuthoredSection) and blk.anchor == "a"
    assert ".c{color:var(--ds-fg)}" in blk.css

def test_builder_artifact_returns_artifact(monkeypatch):
    fake = sb._BuiltM(realization="artifact", kind="board",
                      html="<div></div>", css="", js="console.log(1)")
    monkeypatch.setattr(sb, "invoke_agent", lambda *a, **k: _Resp(fake))
    blk = sb.run_builder(SectionSpec(anchor="t", title="T", realization="artifact"),
                         "<p>src</p>", _cfg())
    assert isinstance(blk, Artifact) and blk.kind == "board"
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement** — `_BuiltM(realization, html, css, js, kind, title)`; agent built like blocks_agent with `build_model(ai, role="page")`; system prompt gives the token contract: "Author this ONE section. Use ONLY `var(--ds-*)` tokens (palette: --ds-accent/bg/fg/muted/card/border; spacing: --ds-space-1..6; type: --ds-fs-1..6; radius --ds-radius; fonts --ds-font-sans/mono). Never write a raw hex colour or a foreign font — they will be stripped. CSS goes in `css` (it is scoped to this section automatically); HTML in `html` (no <script>, no <style>). If realization is artifact, put the interactive widget's html/css/js (JS allowed — it runs sandboxed in an iframe)." Convert: inline → `AuthoredSection(anchor=spec.anchor, title=spec.title, html=m.html, css=m.css)`; artifact → `Artifact(kind=m.kind or spec.anchor, title=spec.title, html=sanitize_artifact_html(m.html), css=m.css, js=m.js)`.

- [ ] **Step 4: run** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): section_builder agent — authored inline/artifact section"`

---

## Task 8: authored_agent orchestrator

**Files:** Create `src/md2x/site/authored_agent.py`; Test `tests/test_authored_pipeline.py`.

`run_authored_page(doc, cfg, plan) -> PageDoc`: split sections → designer (fallback: mirror H2s) → map each spec to its source HTML → parallel builders (fallback per section: `run_section_blocks` typed → `_condensed_fallback`) → assemble `[Hero, Prose(intro)?, *blocks]`. Never amputate.

- [ ] **Step 1: failing test** (fully stubbed — no network)

```python
# tests/test_authored_pipeline.py
from md2x.site import authored_agent as aa
from md2x.site.blocks import AuthoredSection, Hero, PageDoc
from md2x.site.design_tree import DesignTree, SectionSpec

def test_authored_page_assembles_sections(monkeypatch):
    doc = _make_doc()   # H2 "Roles", "Triage"
    monkeypatch.setattr(aa, "run_designer", lambda d, c: DesignTree(slug=doc.slug,
        sections=[SectionSpec(anchor="roles", title="Roles", source_anchors=["roles"]),
                  SectionSpec(anchor="triage", title="Triage", source_anchors=["triage"])]))
    monkeypatch.setattr(aa, "run_builder",
        lambda spec, html, cfg: AuthoredSection(anchor=spec.anchor, title=spec.title,
                                                html="<p>x</p>", css=""))
    page = aa.run_authored_page(doc, _cfg(), _plan())
    assert isinstance(page, PageDoc) and isinstance(page.blocks[0], Hero)
    anchors = [b.anchor for b in page.blocks if isinstance(b, AuthoredSection)]
    assert anchors == ["roles", "triage"]

def test_authored_page_falls_back_when_builder_raises(monkeypatch):
    doc = _make_doc()
    monkeypatch.setattr(aa, "run_designer", lambda d, c: DesignTree(slug=doc.slug,
        sections=[SectionSpec(anchor="roles", title="Roles", source_anchors=["roles"])]))
    def boom(*a, **k): raise RuntimeError("model down")
    monkeypatch.setattr(aa, "run_builder", boom)
    page = aa.run_authored_page(doc, _cfg(), _plan())
    # never amputated: the section still appears (typed/condensed fallback)
    from md2x.site.blocks import Section
    assert any(isinstance(b, (Section, AuthoredSection)) for b in page.blocks)
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3: implement** — mirror `blocks_agent.run_page_blocks` structure (split_sections, ThreadPoolExecutor on `cfg["ai"]["concurrency"]`, per-section try/except). Designer wrapped in try/except → on failure build specs `[SectionSpec(anchor=slugify(sec.title), title=sec.title, source_anchors=[...])]`. Map spec→source html by matching `source_anchors`/anchor to `slugify(sec.title)`, fallback to positional. Per-section builder failure → `from .blocks_agent import run_section_blocks, _condensed_fallback`; wrap result in `Section(title, anchor, kids)`. Log every stage (logging-first).

- [ ] **Step 4: run** — `.venv/bin/python -m pytest tests/test_authored_pipeline.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): authored_agent — designer->builders->assemble with never-amputate fallback"`

---

## Task 9: wire mode + pipeline + page-doc branch

**Files:** Modify `modes.py`, `pipeline.py`, `blocks_render.py:_page_doc_for`; Test `tests/test_authored_pipeline.py` (append).

- [ ] **Step 1: failing tests**

```python
from md2x.site.modes import validate_render_mode

def test_authored_is_a_valid_mode():
    assert validate_render_mode("authored") == "authored"

def test_page_doc_for_authored_uses_authored_agent(monkeypatch, tmp_path):
    from md2x.site import blocks_render as br
    from md2x.site.blocks import PageDoc, Hero
    cfg = _cfg(); cfg["site"]["render_mode"] = "authored"; cfg["site"]["fidelity"] = "synthesize"
    called = {}
    def fake_authored(doc, c, plan): called["hit"] = True; return PageDoc(slug=doc.slug, title=doc.title, blocks=[Hero(title=doc.title)])
    monkeypatch.setattr("md2x.site.authored_agent.run_authored_page", fake_authored)
    page = br._page_doc_for(_make_doc(), cfg, _plan(), use_ai=True)
    assert called.get("hit") and isinstance(page, PageDoc)
```

- [ ] **Step 2: run, expect fail**
- [ ] **Step 3a: modes.py** — `RENDER_MODES = ("blocks", "hybrid", "full", "authored")`.
- [ ] **Step 3b: blocks_render.py `_page_doc_for`** — add at the top of the `use_ai` branch:

```python
    if use_ai and cfg["site"].get("render_mode") == "authored":
        try:
            from .authored_agent import run_authored_page   # lazy: needs agno
            return run_authored_page(doc, cfg, plan)
        except Exception as e:
            log.warning("authored agent failed for %s (%s); deterministic page",
                        doc.slug, e)
            log.debug("authored %s failure", doc.slug, exc_info=True)
            return build_page_doc(doc)
```

- [ ] **Step 3c: pipeline.py** — route authored through the blocks writer and skip enhancement aids:

```python
        if mode in ("blocks", "hybrid", "authored"):
            if mode == "authored":
                enh = {d.slug: PageEnhancement() for d in docs}   # sections own the page
            from .blocks_render import write_blocks_site
            write_blocks_site(out_dir, docs, plan, enh, cfg, use_ai=use_ai)
```

(Place the `enh` override so it also applies when `use_ai`; simplest: compute `enh` then, if `mode=="authored"`, reset to empties before the writer.)

- [ ] **Step 4: run** — full file → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(site): wire render_mode=authored into modes + pipeline + page builder"`

---

## Task 10: integration — authored end-to-end (no network)

**Files:** Test `tests/test_authored_pipeline.py` (append).

- [ ] **Step 1: test** — `--no-ai` authored mode must produce a valid site deterministically (designer/builder never run; `_page_doc_for` returns `build_page_doc`):

```python
def test_authored_no_ai_writes_seamless_site(tmp_path):
    import md2x.config as config
    from md2x.site.blocks_render import write_blocks_site
    from md2x.site.schemas import Doc, SitePlan, NavItem, PageEnhancement
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "authored"
    doc = Doc(path=tmp_path / "c.md", title="Charter", outline=["Roles"],
              fragment_html="<h1>Charter</h1><h2>Roles</h2><p>Body.</p>")
    plan = SitePlan(nav=[NavItem(title="Charter", slug="c")], order=["c"])
    out = tmp_path / "site"
    write_blocks_site(out, [doc], plan, {"c": PageEnhancement()}, cfg, use_ai=False)
    page = (out / "c.html").read_text()
    assert '<section id="roles"' in page
    assert (out / "assets" / "site.js").exists()
    assert "http://" not in page and "https://" not in page
```

- [ ] **Step 2: run** → PASS
- [ ] **Step 3: full suite** — `.venv/bin/python -m pytest -q` → all green (target: prior 268 + new)
- [ ] **Step 4: commit** — `git commit -am "test(site): authored mode end-to-end (no-ai deterministic)"`

---

## Task 11: live smoke (AI)

**Files:** none (manual run).

- [ ] Backup `md2x.yaml`; set `render_mode: authored`; run `.venv/bin/md2x site ~/Documents/FDET_Charter.md -o site 2>&1 | tee /tmp/authored.log`.
- [ ] Assert from the log: designer ran (1/page), N builders ran, `ok=N timeout=0`, 0 amputated.
- [ ] Screenshot `site/fdet_charter.html` (headless Chrome); verify: one seamless page, varied section layouts, shared palette/fonts, 0 raw-hex leaks (`grep -c '#[0-9a-f]\{6\}' site/*.html` outside `:root`), scroll-spy works.
- [ ] Restore `md2x.yaml` (keep `render_mode` change per user; never commit the yaml).

---

## Self-Review (planner)

- **Spec coverage:** pipeline (T6-9), IR (T5), inline+artifact realizations (T4,T7), hard enforcement scope+lint (T1-2), tokens (T3), per-page designer (T6), deterministic assembler (T8 — pure Python), no inline JS (T4 strips `<style>`/`<script>`; JS only via Artifact), never-amputate fallback (T8,T9), config mode (T9), smoke (T11). All covered.
- **Deviations from spec (intentional, lower risk):** (a) reuse existing `sanitize_inline` instead of a new `sanitize_inline_html`; (b) type/space scales are fixed `--ds-*` tokens in `design_css` rather than architect-authored — same enforcement, less LLM surface; (c) authored reuses the blocks writer rather than a new `authored_render.py`. Noted here so the executor doesn't "fix" them back.
- **Type consistency:** `AuthoredSection(anchor,title,html,css)`, `SectionSpec(anchor,title,intent,realization,layout,components,source_anchors)`, `DesignTree(slug,sections)`, `enforce_section_css(css,root)`, `run_designer(doc,cfg)`, `run_builder(spec,section_html,cfg)`, `run_authored_page(doc,cfg,plan)` — used consistently across tasks.
- **Placeholders:** none — every code step shows real code; agent prompts are described with their exact contract content.
