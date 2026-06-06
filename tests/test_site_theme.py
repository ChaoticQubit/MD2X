"""The shared blocks-mode engine: assets/site.css + assets/site.js, plus the
behaviour hooks the renderers emit for it to wire up."""
from pathlib import Path

import md2x.config as config
from md2x.site import blocks_render as br
from md2x.site import blocks as B
from md2x.site.theme import SITE_CSS, SITE_JS
from md2x.site.schemas import Doc, NavItem, SitePlan, PageEnhancement


# --- the engine is self-contained ------------------------------------------

def test_engine_has_no_network():
    for asset in (SITE_CSS, SITE_JS):
        assert "http://" not in asset and "https://" not in asset
        assert "<script" not in asset and "cdn" not in asset.lower()


def test_site_js_is_state_driven():
    # the state primitive every widget is built from, and it's exposed
    assert "function createStore(" in SITE_JS
    assert "win.md2x={ createStore:createStore };" in SITE_JS
    # the named state functions
    for fn in ("revealOnScroll", "countUp", "scrollSpy", "tabs",
               "sortableTables", "copyButtons", "themeToggle",
               "readingProgress", "hybridBroker"):
        assert "function " + fn + "(" in SITE_JS, fn
    # real animation / interactivity, not static markup
    assert "IntersectionObserver" in SITE_JS
    assert "requestAnimationFrame" in SITE_JS
    assert "localStorage" in SITE_JS          # persisted theme state


def test_site_js_is_resilient():
    # a single feature throwing must not blank the page
    assert 'try{ fn(); }catch' in SITE_JS
    assert "prefers-reduced-motion" in SITE_JS


def test_site_css_has_design_system_and_animation():
    assert "[data-reveal]" in SITE_CSS
    assert "prefers-reduced-motion" in SITE_CSS    # animation off-switch
    assert "--accent" in SITE_CSS and "--shadow-md" in SITE_CSS
    assert "data-theme" in SITE_CSS                # dark-mode toggle hook
    for cls in (".b-kpi-card", ".b-section-h", ".b-table", ".b-codewrap"):
        assert cls in SITE_CSS, cls


# --- renderers emit the behaviour hooks ------------------------------------

def test_blocks_carry_reveal_hook():
    assert "data-reveal" in br.render_block(B.Hero(title="T"))
    assert "data-reveal" in br.render_block(B.Summary(text="s"))
    assert "data-reveal" in br.render_block(
        B.KpiStrip(items=[B.Kpi(value="20", label="x")]))


def test_kpi_value_has_count_hook():
    h = br.render_block(B.KpiStrip(items=[B.Kpi(value="42", label="teams")]))
    assert "data-count" in h and "42" in h


def test_code_block_has_copy_button():
    h = br.render_block(B.Code(code="print(1)", lang="python"))
    assert "b-codewrap" in h and "b-copy" in h
    assert "print(1)" in h and "language-python" in h


def test_table_is_sortable_and_wrapped():
    h = br.render_block(B.Table(headers=["A", "B"], rows=[["1", "2"]]))
    assert "b-tablewrap" in h and "data-sortable" in h
    h2 = br.render_block(B.Table(rows=[["1"]]))     # no headers -> not sortable
    assert "data-sortable" not in h2


def test_chart_is_wrapped_for_grow_animation():
    h = br.render_block(B.Chart(kind="bar", points=[B.ChartPoint("a", 1)]))
    assert "b-chartwrap" in h and "data-reveal" in h and "<svg" in h


# --- the writer emits the shared engine and links it -----------------------

def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def test_write_blocks_site_emits_shared_assets(tmp_path):
    cfg = _cfg()
    docs = [Doc(path=tmp_path / "intro.md", title="Intro", outline=["A"],
                fragment_html="<p>Hello world.</p>")]
    plan = SitePlan(nav=[NavItem(title="Intro", slug="intro")], order=["intro"])
    out = tmp_path / "out"
    br.write_blocks_site(out, docs, plan, {"intro": PageEnhancement()}, cfg,
                         use_ai=False)
    css = out / "assets" / "site.css"
    js = out / "assets" / "site.js"
    assert css.exists() and js.exists()
    assert "createStore" in js.read_text()
    assert "[data-reveal]" in css.read_text()

    page = (out / "intro.html").read_text()
    assert '<link rel="stylesheet" href="assets/site.css">' in page
    assert '<script src="assets/site.js"></script>' in page
    assert 'classList.add("js")' in page          # no-JS reveal guard
    assert "--ds-accent" in page                   # per-page tokens stay inline
    assert "http://" not in page and "https://" not in page
