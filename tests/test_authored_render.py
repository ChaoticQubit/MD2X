"""AuthoredSection: the inline, scoped+linted, sanitized section block."""
from md2x.site import blocks_render as br
from md2x.site.blocks import AuthoredSection, Hero, PageDoc
from md2x.site.schemas import SitePlan, NavItem


def test_authored_section_scopes_css_and_sanitizes():
    b = AuthoredSection(anchor="roles", title="Roles",
                        css=".card{color:#ff0000;background:var(--ds-card)}",
                        html='<div class="card">Hi</div><script>evil()</script>')
    h = br.render_block(b)
    assert '<section id="roles"' in h and "b-section-h" in h
    assert "#roles .card" in h                 # scoped to the section root
    assert "#ff0000" not in h                    # raw colour linted out
    assert "var(--ds-card)" in h                 # token kept
    assert "<script>" not in h                   # JS sanitized
    assert "<style>" in h                        # css inlined via the field


def test_authored_html_inline_style_block_is_stripped():
    b = AuthoredSection(anchor="x", title="X",
                        html='<style>.a{color:#fff}</style><p>k</p>', css="")
    h = br.render_block(b)
    assert "color:#fff" not in h and "<p>k</p>" in h


def test_authored_section_no_css_emits_no_style_tag():
    h = br.render_block(AuthoredSection(anchor="x", title="X", html="<p>k</p>", css=""))
    assert "<style>" not in h and "<p>k</p>" in h


def test_authored_strips_leading_duplicate_heading():
    b = AuthoredSection(anchor="roles", title="Roles",
                        html="<h2>Roles</h2><p>Body</p><h3>Sub</h3>", css="")
    h = br.render_block(b)
    assert h.count("<h2") == 1          # only the page's section heading survives
    assert "<h3>Sub</h3>" in h          # genuine subheadings are kept
    assert "<p>Body</p>" in h


def test_authored_strips_wrapped_title_heading():
    # a title heading the builder wrapped in a div is still removed
    b = AuthoredSection(anchor="roles", title="Roles",
                        html="<div class='x'><h2>Roles</h2><p>y</p></div>", css="")
    h = br.render_block(b)
    assert h.count("<h2") == 1 and "<p>y</p>" in h


def test_authored_keeps_non_title_headings():
    b = AuthoredSection(anchor="plan", title="90 Day Plan",
                        html="<h3>Days 1-30</h3><p>a</p><h3>Days 31-60</h3>", css="")
    h = br.render_block(b)
    assert h.count("<h3") == 2          # genuine subheadings survive


def test_authored_table_becomes_sortable_b_table():
    b = AuthoredSection(anchor="m", title="M",
                        html="<table><thead><tr><th>A</th></tr></thead>"
                             "<tbody><tr><td>1</td></tr></tbody></table>", css="")
    h = br.render_block(b)
    assert 'class="b-table" data-sortable' in h


def test_section_nav_lists_authored_sections():
    page = PageDoc(slug="p", title="P", blocks=[
        Hero(title="P"), AuthoredSection(anchor="a", title="Alpha", html="", css="")])
    plan = SitePlan(nav=[NavItem(title="P", slug="p")], order=["p"])
    nav = br._section_nav_html(page, plan, "p")
    assert 'href="#a"' in nav and "Alpha" in nav
