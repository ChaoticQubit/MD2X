# Section-Aware Living Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `md2x site` from amputating large documents — make the H2 section the unit of generation so every section survives, is anchored, navigable, diagram-bearing, and synthesized in its real shape.

**Architecture:** Today both AI agents do `body = doc.fragment_html[:8000]` → one completion → the doc dies at the 8K mark (≈section 1 of 16). We invert it: `split_sections()` (already exists) cuts the doc at each `<h2>`; each section is enriched *independently and in parallel* from its **full** HTML; any section that fails or returns empty falls back to verbatim `Prose` (which carries its tables/lists/diagram `<img>`s). A new `Section(title, anchor, blocks)` block wraps each in `<section id>`, the sidebar is rebuilt from those sections, and `diagrams/<slug>/*.png` refs become `Figure` blocks. Content can never fully vanish again — worst case is the complete deterministic render.

**Tech Stack:** Python 3.10+, dataclasses, agno/pydantic (AI path, lazy), ThreadPoolExecutor, pytest.

---

## File Structure

- `src/md2x/site/blocks.py` — add `Section` block; add `figures_from_html()`; rewrite `build_page_doc` to emit anchored `Section`s (complete, deterministic baseline).
- `src/md2x/site/blocks_render.py` — render `Section` (recursive); add `_section_nav_html()`; use it in `_render_doc_page`; add `.b-section` CSS + scroll-spy JS.
- `src/md2x/site/blocks_agent.py` — split-then-map: `run_section_blocks()` (per-section agent on FULL section html) + rewrite `run_page_blocks` to orchestrate parallel sections + per-section verbatim fallback + diagram figures.
- `src/md2x/site/full_agent.py` / `full_render.py` — section-aware full mode (one fragment per section, assembled; verbatim fallback).
- `tests/test_site_section_aware.py` — NEW: the eval that was missing (real charter → all sections present), plus unit tests for `Section`, nav, figures, fallback.

---

### Task 1: `Section` block + recursive renderer + CSS

**Files:** Modify `src/md2x/site/blocks.py`, `src/md2x/site/blocks_render.py`. Test `tests/test_site_section_aware.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_site_section_aware.py
from md2x.site.blocks import Section, Prose, Hero
from md2x.site.blocks_render import render_block, render_blocks

def test_section_renders_anchor_heading_and_children():
    s = Section(title="Operating Model", anchor="operating-model",
                blocks=[Prose(html="<p>pods</p>")])
    out = render_block(s)
    assert 'id="operating-model"' in out
    assert "<h2" in out and "Operating Model" in out
    assert "<p>pods</p>" in out          # child rendered
    assert out.count("<section") == 1
```

- [ ] **Step 2: Verify fail** — `pytest tests/test_site_section_aware.py::test_section_renders_anchor_heading_and_children -v` → FAIL (no `Section`).

- [ ] **Step 3: Implement.** In `blocks.py`, after `RawHtml` (around line 172) add:

```python
@dataclass
class Section:
    """A titled, anchored group of child blocks (one H2 region). Renders a
    <section id=anchor> with an <h2> so the sidebar can deep-link to it."""
    title: str
    anchor: str
    blocks: list["Block"] = field(default_factory=list)
```

Add `Section` to the `Block` union and `BLOCK_TYPES` tuple (both lists, around lines 195–206). In `blocks_render.py` `render_block` (line 263), handle `Section` before the dict lookup:

```python
def render_block(block: Block, ds_css: str = "") -> str:
    if isinstance(block, Artifact):
        return _artifact(block, ds_css)
    if isinstance(block, Section):
        inner = render_blocks(block.blocks, ds_css)
        return (f'<section id="{_e(block.anchor)}" class="b-section">'
                f'<h2 class="b-section-h">{_e(block.title)}</h2>{inner}</section>')
    fn = _RENDERERS.get(type(block))
    ...
```

Import `Section` in `blocks_render.py` (line 17 import block). Add CSS to `_BLOCKS_CSS`:

```css
.b-section { scroll-margin-top: 16px; padding-top: 8px; }
.b-section-h { font-size: 1.5rem; margin: 0 0 var(--ds-space-2,1rem);
  padding-bottom: 6px; border-bottom: 1px solid var(--border); letter-spacing:-.01em; }
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** `git add src/md2x/site/blocks.py src/md2x/site/blocks_render.py tests/test_site_section_aware.py` → `feat(site): Section block — anchored H2 region with child blocks`

---

### Task 2: deterministic `build_page_doc` emits anchored Sections (complete baseline)

**Files:** Modify `src/md2x/site/blocks.py`. Test `tests/test_site_section_aware.py`.

- [ ] **Step 1: Failing test** — this is the *real-charter eval that was missing*. It runs the deterministic (no-LLM) path and asserts every section survives.

```python
from pathlib import Path
import pytest
from md2x.site.blocks import build_page_doc, Section
from md2x.site.blocks_render import render_blocks
from md2x.site.schemas import Doc

CHARTER = Path("/Users/chaoticqubit/Documents/FDET_Charter.md")

def _charter_doc():
    # Build a Doc straight from raw markdown wrapped as a fragment (no pandoc):
    # split_sections keys off <h2>, so convert "## X" lines to <h2>X</h2>.
    import re
    raw = CHARTER.read_text(encoding="utf-8")
    frag = re.sub(r"(?m)^##\s+(.+)$", r"<h2>\1</h2>", raw)
    frag = re.sub(r"(?m)^#\s+(.+)$", r"<h1>\1</h1>", frag)
    return Doc(path=CHARTER, title="FDET", outline=[], fragment_html=frag)

@pytest.mark.skipif(not CHARTER.exists(), reason="charter fixture absent")
def test_build_page_doc_covers_every_section():
    doc = _charter_doc()
    page = build_page_doc(doc)
    secs = [b for b in page.blocks if isinstance(b, Section)]
    assert len(secs) >= 14            # 16 H2 sections in the charter
    html = render_blocks(page.blocks)
    for needle in ["Operating Model", "Skills Matrix", "Year-1 Budget",
                   "Governance and Risk", "Closing Narrative"]:
        assert needle in html, f"section vanished: {needle}"
```

- [ ] **Step 2: Verify fail** — current `build_page_doc` emits `Prose` per section, not `Section`; `secs` is empty → FAIL.

- [ ] **Step 3: Implement.** Rewrite `build_page_doc` (blocks.py:220) to wrap each section:

```python
from .schemas import slugify

def build_page_doc(doc) -> PageDoc:
    """Deterministic PageDoc — no LLM. Hero + intro Prose + one anchored
    Section per H2 (verbatim body, so tables/lists/diagrams are preserved)."""
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    blocks: list[Block] = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    for sec in sections:
        anchor = slugify(sec.title) if sec.title else f"section-{len(blocks)}"
        blocks.append(Section(title=sec.title, anchor=anchor,
                              blocks=[Prose(html=sec.html)] if sec.html else []))
    if len(blocks) == 1:
        blocks.append(Prose(html=doc.fragment_html))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
```

- [ ] **Step 4: Verify pass.** Run the whole new test file.

- [ ] **Step 5: Commit** `feat(site): deterministic build_page_doc emits anchored sections (complete coverage)`

---

### Task 3: sidebar nav rebuilt from the page's sections

**Files:** Modify `src/md2x/site/blocks_render.py`. Test `tests/test_site_section_aware.py`.

- [ ] **Step 1: Failing test**

```python
from md2x.site.blocks import PageDoc, Hero, Section, Prose
from md2x.site.blocks_render import _section_nav_html
from md2x.site.schemas import SitePlan, NavItem

def test_section_nav_lists_section_anchors():
    page = PageDoc(slug="fdet", title="FDET", blocks=[
        Hero(title="FDET"),
        Section(title="Operating Model", anchor="operating-model", blocks=[]),
        Section(title="Budget", anchor="budget", blocks=[]),
    ])
    plan = SitePlan(nav=[NavItem(title="FDET", slug="fdet")], order=["fdet"])
    nav = _section_nav_html(page, plan, "fdet")
    assert 'href="#operating-model"' in nav
    assert 'href="#budget"' in nav
    assert "Operating Model" in nav and "Budget" in nav
```

- [ ] **Step 2: Verify fail** (`_section_nav_html` undefined).

- [ ] **Step 3: Implement** in `blocks_render.py` (near `_render_doc_page`). The sidebar shows the doc title, this page's section anchors, and — when the site has multiple docs — links to the other docs.

```python
from .render import _href

def _section_nav_html(page: PageDoc, plan: SitePlan, active_slug: str) -> str:
    secs = [b for b in page.blocks if isinstance(b, Section)]
    parts = ['<nav class="side">']
    parts.append(f'<a class="nav-doc" href="#{_e(page.slug)}">{_e(page.title)}</a>')
    if secs:
        parts.append('<div class="nav-secs">')
        for s in secs:
            parts.append(f'<a href="#{_e(s.anchor)}">{_e(s.title)}</a>')
        parts.append("</div>")
    others = [n for n in plan.nav if n.slug != active_slug]
    if others:
        parts.append('<div class="group">More</div>')
        for n in others:
            parts.append(f'<a href="{_href(n.slug, False)}">{_e(n.title)}</a>')
    parts.append("</nav>")
    return "".join(parts)
```

Wire it into `_render_doc_page` (line 419): build the page first, then nav from it:

```python
def _render_doc_page(doc, plan, enh, cfg, use_ai):
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    page = _page_doc_for(doc, cfg, plan, use_ai)
    nav = _section_nav_html(page, plan, doc.slug)
    enh_html = _enhancement_html(enh, plan, single_page=False)
    main = (f'<main id="{_e(doc.slug)}">{enh_html}'
            f"{render_blocks(page.blocks, ds_css=ds_css)}</main>")
    body = f'<div class="layout">{nav}{main}</div>'
    return _blocks_page_html(doc.title, accent, ds_css, body)
```

Add CSS for `.nav-secs a` (indented, smaller) + active scroll-spy class to `_BLOCKS_CSS`:

```css
.nav-secs a { font-size:.86rem; padding-left:18px; color:var(--muted); }
.nav-secs a.active { color:var(--accent); font-weight:600; }
.nav-doc { font-weight:700; }
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** `feat(site): sidebar nav built from page sections (real in-page navigation)`

---

### Task 4: scroll-spy — highlight the active section in the sidebar

**Files:** Modify `src/md2x/site/blocks_render.py` (`_BLOCKS_JS`). Test: deterministic string check.

- [ ] **Step 1: Failing test**

```python
from md2x.site.blocks_render import _BLOCKS_JS
def test_blocks_js_has_scrollspy():
    assert "IntersectionObserver" in _BLOCKS_JS
    assert "nav-secs" in _BLOCKS_JS
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement** — append to `_BLOCKS_JS`:

```python
_BLOCKS_JS += (
    "(function(){var ls=document.querySelectorAll('.nav-secs a');if(!ls.length)return;"
    "var map={};ls.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});"
    "var ob=new IntersectionObserver(function(es){es.forEach(function(e){"
    "if(e.isIntersecting){ls.forEach(function(a){a.classList.remove('active');});"
    "var a=map[e.target.id];if(a)a.classList.add('active');}});},"
    "{rootMargin:'-10% 0px -80% 0px'});"
    "document.querySelectorAll('section.b-section').forEach(function(s){ob.observe(s);});})();"
)
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** `feat(site): scroll-spy highlights active section in sidebar`

---

### Task 5: diagram refs → Figure blocks (`figures_from_html`)

**Files:** Modify `src/md2x/site/blocks.py`. Test `tests/test_site_section_aware.py`.

- [ ] **Step 1: Failing test**

```python
from md2x.site.blocks import figures_from_html, Figure
def test_figures_from_html_extracts_local_diagrams():
    h = '<p>x</p><img src="diagrams/fdet-charter/mermaid_03.png" alt="Org chart">'
    figs = figures_from_html(h)
    assert len(figs) == 1 and isinstance(figs[0], Figure)
    assert figs[0].src == "diagrams/fdet-charter/mermaid_03.png"
    assert figs[0].alt == "Org chart"

def test_figures_from_html_ignores_remote():
    assert figures_from_html('<img src="https://e/x.png">') == []
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement** in `blocks.py`:

```python
_IMG_RE = re.compile(r'(?is)<img\b[^>]*\bsrc=["\'](?P<src>[^"\']+)["\'][^>]*>')
_ALT_RE = re.compile(r'(?is)\balt=["\'](?P<alt>[^"\']*)["\']')

def figures_from_html(html_fragment: str) -> list["Figure"]:
    """Pull LOCAL <img> (rendered diagrams) out of a fragment as Figure blocks.
    Remote/data srcs are dropped — the renderer would refuse them anyway."""
    out: list[Figure] = []
    for m in _IMG_RE.finditer(html_fragment or ""):
        src = m.group("src").strip()
        if re.match(r"(?i)^(https?:|data:|javascript:|//)", src):
            continue
        alt_m = _ALT_RE.search(m.group(0))
        out.append(Figure(src=src, alt=alt_m.group("alt") if alt_m else ""))
    return out
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** `feat(site): figures_from_html — surface rendered diagrams as Figure blocks`

---

### Task 6: section-aware AI synthesis (`run_section_blocks` + new `run_page_blocks`)

**Files:** Modify `src/md2x/site/blocks_agent.py`. Test `tests/test_site_section_aware.py` (with a fake agent — no network).

- [ ] **Step 1: Failing test** — prove the orchestrator covers every section AND falls back to verbatim when a section's agent dies.

```python
import md2x.site.blocks_agent as BA
from md2x.site.blocks import Section, Prose

def test_run_page_blocks_is_section_aware_with_fallback(monkeypatch):
    frag = ("<h1>Doc</h1><p>intro</p>"
            "<h2>Alpha</h2><p>aaa</p>"
            "<h2>Beta</h2><p>bbb</p>"
            "<h2>Gamma</h2><p>ggg</p>")
    from md2x.site.schemas import Doc
    from pathlib import Path
    doc = Doc(path=Path("doc.md"), title="Doc", outline=[], fragment_html=frag)

    calls = {}
    def fake_section(title, section_html, cfg, artifacts=None):
        calls[title] = section_html
        if title == "Beta":
            raise RuntimeError("model died")         # force fallback
        from md2x.site.blocks import Callout
        return [Callout(text=f"synth {title}")]
    monkeypatch.setattr(BA, "run_section_blocks", fake_section)

    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "hybrid",
                    "fidelity": "synthesize"}}
    page = BA.run_page_blocks(doc, cfg)
    secs = {s.title: s for s in page.blocks if isinstance(s, Section)}
    assert set(secs) == {"Alpha", "Beta", "Gamma"}     # nothing vanished
    # Beta fell back to verbatim Prose:
    assert any(isinstance(b, Prose) and "bbb" in b.html for b in secs["Beta"].blocks)
    # each section saw its OWN full html, never an 8000-char slice of the whole:
    assert "aaa" in calls["Alpha"] and "ggg" in calls["Gamma"]
```

- [ ] **Step 2: Verify fail** (`run_section_blocks` undefined; old `run_page_blocks` is whole-doc).

- [ ] **Step 3: Implement.** Replace `run_page_blocks` (blocks_agent.py:163) and add `run_section_blocks`. Key points: build the agent ONCE, map sections through a `ThreadPoolExecutor(max_workers=concurrency)`, wrap each result in a `Section`, append `figures_from_html(sec.html)`, and fall back to `Prose(sec.html)` on any exception/empty.

```python
from concurrent.futures import ThreadPoolExecutor
from .blocks import Figure, Section, figures_from_html
from .report.blocks import split_sections
from .schemas import slugify

_MAX_SECTION_BLOCKS = 12

def _build_agent(cfg, artifacts):
    ai, site = cfg["ai"], cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "blocks"),
                       site.get("fidelity", "synthesize"), artifacts=artifacts)
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    return Agent(model=build_model(ai, role="page"), instructions=instr,
                 output_schema=_PageDocModel, retries=ai.get("retries", 2),
                 pre_hooks=build_pre_hooks(cfg))

def run_section_blocks(title, section_html, cfg, artifacts=None) -> list:
    """Enrich ONE section from its FULL html (small → no truncation)."""
    agent = _build_agent(cfg, artifacts)
    prompt = (f"Section heading: {title}\n\n"
              f"Section body (HTML) — restructure ONLY this section into blocks "
              f"(no hero, no page title):\n{section_html}")
    resp = agent.run(prompt)
    model: _PageDocModel = resp.content
    blocks = [b for b in (_to_block(m) for m in model.blocks[:_MAX_SECTION_BLOCKS])
              if b is not None and not isinstance(b, Hero)]
    return blocks

def run_page_blocks(doc, cfg: dict, artifacts=None) -> PageDoc:
    """Section-aware: split → enrich each section in parallel → assemble.
    Any section that fails or returns empty falls back to verbatim Prose, so the
    document can never be amputated."""
    intro_html, sections = split_sections(doc.fragment_html)
    import re as _re
    intro_html = _re.sub(r"(?is)<h1\b[^>]*>.*?</h1>", "", intro_html).strip()
    log.info("blocks agent: %s -> %d section(s), %d intro chars",
             doc.slug, len(sections), len(intro_html))

    if not sections:                              # no H2 → deterministic whole-doc
        return build_page_doc(doc)

    def enrich(sec):
        figs = figures_from_html(sec.html)
        try:
            kids = run_section_blocks(sec.title, sec.html, cfg, artifacts)
        except Exception as e:
            log.warning("blocks agent: section %r failed (%s); verbatim",
                        sec.title, e)
            kids = []
        if not kids:
            kids = [Prose(html=sec.html)] if sec.html else []
        else:
            kids += [f for f in figs]             # land the diagrams
        anchor = slugify(sec.title) if sec.title else f"section-{id(sec)}"
        return Section(title=sec.title, anchor=anchor, blocks=kids)

    workers = max(1, int(cfg["ai"].get("concurrency", 4)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        section_blocks = list(ex.map(enrich, sections))

    blocks: list = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    blocks.extend(section_blocks)
    log.info("blocks agent: %s assembled %d section(s)", doc.slug, len(section_blocks))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
```

Drop the now-unused `body = doc.fragment_html[:8000]`. Keep `_to_block`, `_SYSTEM`, schemas.

- [ ] **Step 4: Verify pass** — `pytest tests/test_site_section_aware.py -v`.

- [ ] **Step 5: Run the full suite** — `.venv/bin/python -m pytest -q`. Fix any test that asserted the old whole-doc `run_page_blocks` (e.g. a monkeypatch fake returning a single block list). Expected: the blocks-pipeline test fakes may need `run_section_blocks`/`run_page_blocks` shape updates.

- [ ] **Step 6: Commit** `feat(site): section-aware AI synthesis — parallel per-section, verbatim fallback (no truncation)`

---

### Task 7: section-aware full mode

**Files:** Modify `src/md2x/site/full_agent.py`, `src/md2x/site/full_render.py`. Test `tests/test_site_section_aware.py`.

- [ ] **Step 1: Failing test** (fake per-section author, no network):

```python
import md2x.site.full_agent as FA
def test_full_page_is_section_aware(monkeypatch):
    frag = "<h1>D</h1><p>i</p><h2>Alpha</h2><p>aaa</p><h2>Beta</h2><p>bbb</p>"
    from md2x.site.schemas import Doc; from pathlib import Path
    doc = Doc(path=Path("d.md"), title="D", outline=[], fragment_html=frag)
    monkeypatch.setattr(FA, "run_full_section",
        lambda title, html, cfg, artifacts=None: f"<section><h2>{title}</h2><p>S</p></section>")
    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "full", "fidelity": "synthesize"}}
    fp = FA.run_full_page(doc, cfg)
    assert "Alpha" in fp.html and "Beta" in fp.html        # both sections present
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** In `full_agent.py`, add `run_full_section(title, section_html, cfg, artifacts)` (one focused HTML fragment per section, same agent shape but `_FullPageModel`), and rewrite `run_full_page` to split → enrich each section in parallel → concatenate fragments inside one `<main>`, with a verbatim `<section><h2>title</h2>{sec.html}</section>` fallback on failure/empty. No `[:8000]`. Keep the `_FullPageModel`/CSP injection in `full_render.render_full_page` unchanged.

- [ ] **Step 4: Verify pass + full suite.**

- [ ] **Step 5: Commit** `feat(site): section-aware full mode — per-section authoring, verbatim fallback`

---

### Task 8: end-to-end verification on the real charter (eyes-on)

- [ ] **Step 1:** `--no-ai` run on the charter into a scratch dir; assert all 16 sections + nav anchors + diagram `<img>`s present (deterministic, no tokens):

```bash
.venv/bin/python -m md2x.site.cli /Users/chaoticqubit/Documents/FDET_Charter.md \
  -o /tmp/md2x-verify --no-ai --render-mode hybrid
grep -c '<section id=' /tmp/md2x-verify/fdet-charter.html      # expect >= 14
grep -c 'href="#' /tmp/md2x-verify/fdet-charter.html           # nav anchors
grep -c 'diagrams/fdet-charter' /tmp/md2x-verify/fdet-charter.html  # diagrams placed
```

- [ ] **Step 2:** Read the generated HTML myself; confirm content + nav + diagrams + sections. NO success claim until this passes by eye.

- [ ] **Step 3:** Optional AI run with the configured nvidia models — confirm it still completes (section fallback guarantees completeness even if the model is weak).

- [ ] **Step 4:** Final full suite green. Commit any test/eval additions. WIP (`md2x.yaml`, `examples/`) untouched.

---

## Self-Review

- **Spec coverage:** content-loss → Task 6 (section-unit + fallback) + Task 2 (deterministic baseline); single-page/no-nav → Task 1 (anchors) + Task 3 (section nav) + Task 4 (scroll-spy); diagrams orphaned → Task 5 + wired in Task 6; flat render → Task 6 per-section synthesis; full mode → Task 7; the missing eval → Task 2 + Task 8. ✓
- **Type consistency:** `Section(title, anchor, blocks)` and `run_section_blocks(title, section_html, cfg, artifacts)` / `run_full_section(...)` used identically across Tasks 1/3/6/7. `figures_from_html` returns `list[Figure]`. ✓
- **Constraint:** never stage `md2x.yaml` / `examples/`; path-scoped `git add` only. Verification writes to `/tmp`, not the repo. ✓
- **Robustness:** worst case (every section's agent fails) === the complete deterministic render. Truncation is structurally impossible once `[:8000]` is gone and sections are the unit.
