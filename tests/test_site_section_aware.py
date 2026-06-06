"""Section-aware living-site tests.

The eval that was missing: feed a REAL multi-section document through the
pipeline and assert every section survives. The 8000-char input truncation in
the AI agents silently amputated large docs (section 1 of 16 survived); these
tests fail loudly on any such content loss, on the deterministic path (free, no
model) and on the AI path (fake agent, no network).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from md2x.site.blocks import (
    Callout, Figure, Hero, PageDoc, Prose, Section, build_page_doc,
    figures_from_html,
)
from md2x.site.blocks_render import (
    _BLOCKS_JS, _section_nav_html, render_block, render_blocks,
)
from md2x.site.schemas import Doc, NavItem, SitePlan

CHARTER = Path("/Users/chaoticqubit/Documents/FDET_Charter.md")


def _doc(fragment_html: str, title: str = "Doc", path: str = "doc.md") -> Doc:
    return Doc(path=Path(path), title=title, outline=[],
               fragment_html=fragment_html)


def _charter_doc() -> Doc:
    """Build a Doc straight from the charter markdown (no pandoc). split_sections
    keys off <h2>, so promote ATX headings to tags."""
    raw = CHARTER.read_text(encoding="utf-8")
    frag = re.sub(r"(?m)^##\s+(.+?)\s*$", r"<h2>\1</h2>", raw)
    frag = re.sub(r"(?m)^#\s+(.+?)\s*$", r"<h1>\1</h1>", frag)
    return _doc(frag, title="FDET", path=str(CHARTER))


# --- Task 1: Section block --------------------------------------------------

def test_section_renders_anchor_heading_and_children():
    s = Section(title="Operating Model", anchor="operating-model",
                blocks=[Prose(html="<p>pods</p>")])
    out = render_block(s)
    assert 'id="operating-model"' in out
    assert "<h2" in out and "Operating Model" in out
    assert "<p>pods</p>" in out
    assert out.count("<section") == 1


# --- Task 2: deterministic coverage (the real-charter eval) -----------------

def test_build_page_doc_wraps_sections():
    doc = _doc("<h1>D</h1><p>intro</p><h2>Alpha</h2><p>aaa</p>"
               "<h2>Beta</h2><p>bbb</p>")
    page = build_page_doc(doc)
    secs = [b for b in page.blocks if isinstance(b, Section)]
    assert [s.title for s in secs] == ["Alpha", "Beta"]
    assert secs[0].anchor == "alpha"
    # verbatim body preserved inside the section
    assert any(isinstance(b, Prose) and "aaa" in b.html for b in secs[0].blocks)


@pytest.mark.skipif(not CHARTER.exists(), reason="charter fixture absent")
def test_build_page_doc_covers_every_charter_section():
    page = build_page_doc(_charter_doc())
    secs = [b for b in page.blocks if isinstance(b, Section)]
    assert len(secs) >= 14, f"only {len(secs)} sections — content amputated"
    out = render_blocks(page.blocks)
    for needle in ["Operating Model", "Skills Matrix", "Year-1 Budget",
                   "Governance and Risk", "Closing Narrative", "Project Pipeline"]:
        assert needle in out, f"section vanished: {needle}"


# --- Task 3: section nav ----------------------------------------------------

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


def test_section_nav_links_other_docs():
    page = PageDoc(slug="a", title="A", blocks=[Hero(title="A")])
    plan = SitePlan(nav=[NavItem(title="A", slug="a"), NavItem(title="B", slug="b")],
                    order=["a", "b"])
    nav = _section_nav_html(page, plan, "a")
    assert 'href="b.html"' in nav and ">B<" in nav


# --- Task 4: scroll-spy -----------------------------------------------------

def test_blocks_js_has_scrollspy():
    assert "IntersectionObserver" in _BLOCKS_JS
    assert "nav-secs" in _BLOCKS_JS


# --- Task 5: diagram figures ------------------------------------------------

def test_figures_from_html_extracts_local_diagrams():
    h = '<p>x</p><img src="diagrams/fdet-charter/mermaid_03.png" alt="Org chart">'
    figs = figures_from_html(h)
    assert len(figs) == 1 and isinstance(figs[0], Figure)
    assert figs[0].src == "diagrams/fdet-charter/mermaid_03.png"
    assert figs[0].alt == "Org chart"


def test_figures_from_html_ignores_remote():
    assert figures_from_html('<img src="https://e/x.png">') == []
    assert figures_from_html('<img src="data:image/png;base64,AAAA">') == []


# --- Task 6: section-aware AI synthesis (fake agent, no network) -------------

def test_run_page_blocks_is_section_aware_with_fallback(monkeypatch):
    import md2x.site.blocks_agent as BA
    from md2x.site.blocks import Callout
    frag = ("<h1>Doc</h1><p>intro</p>"
            "<h2>Alpha</h2><p>aaa</p>"
            "<h2>Beta</h2><p>bbb</p>"
            "<h2>Gamma</h2><p>ggg</p>")
    doc = _doc(frag, title="Doc")

    calls = {}
    def fake_section(title, section_html, cfg, artifacts=None):
        calls[title] = section_html
        if title == "Beta":
            raise RuntimeError("model died")          # force verbatim fallback
        return [Callout(text=f"synth {title}")]
    monkeypatch.setattr(BA, "run_section_blocks", fake_section)

    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "hybrid",
                    "fidelity": "synthesize"}}
    page = BA.run_page_blocks(doc, cfg)

    secs = {s.title: s for s in page.blocks if isinstance(s, Section)}
    assert set(secs) == {"Alpha", "Beta", "Gamma"}    # nothing vanished
    assert isinstance(page.blocks[0], Hero)
    # Beta fell back to verbatim Prose carrying its body:
    assert any(isinstance(b, Prose) and "bbb" in b.html for b in secs["Beta"].blocks)
    # Alpha was synthesized:
    assert any(isinstance(b, Callout) for b in secs["Alpha"].blocks)
    # each section saw its OWN full html — never a slice of the whole doc:
    assert "aaa" in calls["Alpha"] and "ggg" in calls["Gamma"]
    assert "bbb" not in calls.get("Alpha", "")


def test_run_page_blocks_no_h2_uses_deterministic(monkeypatch):
    import md2x.site.blocks_agent as BA
    doc = _doc("<h1>D</h1><p>just prose, no headings</p>", title="D")
    # run_section_blocks must never be called when there are no H2s
    monkeypatch.setattr(BA, "run_section_blocks",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "blocks",
                    "fidelity": "synthesize"}}
    page = BA.run_page_blocks(doc, cfg)
    assert any(isinstance(b, Prose) and "just prose" in b.html for b in page.blocks)


# --- Task 7: section-aware full mode ----------------------------------------

def test_full_page_is_section_aware(monkeypatch):
    import md2x.site.full_agent as FA
    frag = "<h1>D</h1><p>i</p><h2>Alpha</h2><p>aaa</p><h2>Beta</h2><p>bbb</p>"
    doc = _doc(frag, title="D")
    seen = {}
    def fake(title, section_html, cfg, artifacts=None):
        seen[title] = section_html
        return f"<div>S:{title}</div>"
    monkeypatch.setattr(FA, "run_full_section", fake)
    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "full",
                    "fidelity": "synthesize"}}
    fp = FA.run_full_page(doc, cfg)
    assert "S:Alpha" in fp.html and "S:Beta" in fp.html      # both authored
    assert 'id="alpha"' in fp.html and 'id="beta"' in fp.html  # anchored
    assert "aaa" in seen["Alpha"] and "bbb" in seen["Beta"]    # full section html


def test_full_page_section_fallback_to_verbatim(monkeypatch):
    import md2x.site.full_agent as FA
    doc = _doc("<h1>D</h1><h2>Alpha</h2><p>aaa</p><h2>Beta</h2><p>bbb</p>", title="D")
    def fake(title, section_html, cfg, artifacts=None):
        if title == "Beta":
            raise RuntimeError("died")
        return f"<div>S:{title}</div>"
    monkeypatch.setattr(FA, "run_full_section", fake)
    cfg = {"ai": {"concurrency": 2, "retries": 0},
           "site": {"archetype": "reading", "render_mode": "full",
                    "fidelity": "synthesize"}}
    fp = FA.run_full_page(doc, cfg)
    assert "S:Alpha" in fp.html       # synthesized
    assert "bbb" in fp.html           # Beta fell back to verbatim — not vanished
