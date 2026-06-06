from pathlib import Path
import pytest

import md2x.config as config
from md2x.site import blocks_render as br
from md2x.site import blocks as B
from md2x.site.schemas import Doc, NavItem, SitePlan, PageEnhancement


# --- per-block markup -------------------------------------------------------

def test_hero_and_kpi_and_callout_markup():
    assert '<header class="b-hero">' in br.render_block(B.Hero(title="T"))
    kpi = br.render_block(B.KpiStrip(items=[B.Kpi(value="+20%", label="rev")]))
    assert "b-kpi" in kpi and "+20%" in kpi
    co = br.render_block(B.Callout(text="careful", tone="warn"))
    assert "tone-warn" in co and "careful" in co


def test_table_escapes_cells():
    t = br.render_block(B.Table(headers=["H"], rows=[["<x>"]]))
    assert "<th>H</th>" in t and "&lt;x&gt;" in t and "<x>" not in t


def test_callout_text_is_escaped():
    h = br.render_block(B.Callout(text="<script>x</script>"))
    assert "&lt;script&gt;" in h and "<script>x</script>" not in h


def test_chart_is_inline_svg_no_network():
    h = br.render_block(B.Chart(kind="bar",
                                points=[B.ChartPoint("a", 1), B.ChartPoint("b", 2)]))
    assert "<svg" in h and "b-bar" in h and "viewBox" in h
    assert "http://" not in h and "https://" not in h


def test_tabs_have_roles():
    h = br.render_block(B.Tabs(tabs=[B.Tab("One", "<p>1</p>"),
                                     B.Tab("Two", "<p>2</p>")]))
    assert 'role="tab"' in h and "b-panel" in h


def test_figure_drops_external_src():
    assert br.render_block(B.Figure(src="https://evil/x.png")) == ""
    local = br.render_block(B.Figure(src="diagrams/x.png", alt="a"))
    assert "<img" in local and 'src="diagrams/x.png"' in local


def test_steps_and_glossary_and_collapsible():
    assert "b-steps" in br.render_block(B.Steps(steps=[B.Step(title="do")]))
    assert "<dl" in br.render_block(B.Glossary(terms=[B.Term("t", "d")]))
    assert "<details" in br.render_block(B.Collapsible(summary="s", html="<p>x</p>"))


def test_prose_is_verbatim():
    assert "<em>kept</em>" in br.render_block(B.Prose(html="<em>kept</em>"))


# --- sanitizers -------------------------------------------------------------

def test_sanitize_inline_strips_script_and_handlers():
    s = br.sanitize_inline("<script>x</script><p onclick='e()'>hi</p>")
    assert "<script" not in s and "onclick" not in s and "hi" in s


def test_sanitize_svg_keeps_shapes_drops_script():
    s = br.sanitize_svg("<svg><script>bad</script><rect x='1'/></svg>")
    assert "<rect" in s and "<script" not in s


def test_render_blocks_concatenates():
    h = br.render_blocks([B.Hero(title="T"), B.Summary(text="s")])
    assert "b-hero" in h and "b-summary" in h


# --- site writer ------------------------------------------------------------

def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def test_write_blocks_site_emits_pages(tmp_path):
    cfg = _cfg()
    docs = [Doc(path=tmp_path / "intro.md", title="Intro", outline=["A"],
                fragment_html="<p>The quick brown fox.</p>"),
            Doc(path=tmp_path / "guide.md", title="Guide", outline=["B"],
                fragment_html="<p>Second page.</p>")]
    plan = SitePlan(nav=[NavItem(title=d.title, slug=d.slug) for d in docs],
                    order=[d.slug for d in docs])
    enh = {"intro": PageEnhancement(tldr="Quick summary."),
           "guide": PageEnhancement()}
    out = tmp_path / "out"
    br.write_blocks_site(out, docs, plan, enh, cfg)
    assert (out / "index.html").exists()
    assert (out / "design-system.html").exists()
    intro = (out / "intro.html").read_text()
    assert "--ds-accent" in intro                  # design tokens present
    assert "The quick brown fox." in intro          # body verbatim
    assert "Quick summary." in intro                # enhancement above blocks
    assert "Guide" in intro                          # sidebar nav
    assert "http://" not in intro and "https://" not in intro


# --- synthesize agent conversion -------------------------------------------

def test_run_page_blocks_converts_and_drops_unknown(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site import blocks_agent

    class _Resp:
        content = blocks_agent._PageDocModel(blocks=[
            blocks_agent._BlockM(type="hero", title="T"),
            blocks_agent._BlockM(type="kpi_strip",
                                 items=[blocks_agent._KpiM(value="+20%", label="rev")]),
            blocks_agent._BlockM(type="bogus"),
        ])

    class _Agent:
        def __init__(self, *a, **k):
            pass

        def run(self, prompt):
            return _Resp()

    monkeypatch.setattr(blocks_agent, "Agent", _Agent)
    monkeypatch.setattr(blocks_agent, "build_model", lambda ai, role: None)
    doc = Doc(path=Path("a.md"), title="A", outline=[], fragment_html="<p>x</p>")
    cfg = {"site": {"archetype": "reading", "render_mode": "blocks",
                    "fidelity": "synthesize"},
           "ai": {"model": "x:y", "page_model": None, "retries": 1}}
    page = blocks_agent.run_page_blocks(doc, cfg)
    assert isinstance(page.blocks[0], B.Hero)
    assert any(isinstance(b, B.KpiStrip) for b in page.blocks)
    assert len(page.blocks) == 2                     # unknown 'bogus' dropped
