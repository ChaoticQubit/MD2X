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


def test_section_nav_lists_authored_sections():
    page = PageDoc(slug="p", title="P", blocks=[
        Hero(title="P"), AuthoredSection(anchor="a", title="Alpha", html="", css="")])
    plan = SitePlan(nav=[NavItem(title="P", slug="p")], order=["p"])
    nav = br._section_nav_html(page, plan, "p")
    assert 'href="#a"' in nav and "Alpha" in nav
