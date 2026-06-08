"""Multi-page layout for the blocks/authored/hybrid writer.

`layout: multi-page` must produce more than one page even for a single rich
document: each top-level section becomes its own page (with its own URL and nav
entry), with an overview page linking them. Previously `layout` never reached the
blocks writer, so a single document always collapsed to one scrolling page
regardless of the flag. These tests run deterministically (use_ai=False) — no
network.
"""
from pathlib import Path

import md2x.config as config
from md2x.site import blocks_render as br
from md2x.site.blocks import AuthoredSection, Figure, Hero, PageDoc
from md2x.site.schemas import Doc, NavItem, SitePlan, PageEnhancement


def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def _doc(tmp_path, frag, slug="charter", title="Charter"):
    return Doc(path=tmp_path / f"{slug}.md", title=title, outline=[],
               fragment_html=frag)


# --- splitting a built page -------------------------------------------------

def test_split_groups_hero_and_attaches_trailing_figures():
    doc = Doc(path=Path("d.md"), title="D", outline=[], fragment_html="")
    page = PageDoc(slug="d", title="D", blocks=[
        Hero(title="D"),
        AuthoredSection(anchor="alpha", title="Alpha", html="<p>a</p>", css=""),
        Figure(src="diagrams/d/m1.png", alt="x"),
        AuthoredSection(anchor="beta", title="Beta", html="<p>b</p>", css=""),
    ])
    preamble, leaves = br._split_section_pages(doc, page)
    assert [type(b).__name__ for b in preamble] == ["Hero"]
    assert [lf[0] for lf in leaves] == ["d__alpha", "d__beta"]
    assert [lf[1] for lf in leaves] == ["Alpha", "Beta"]
    # the figure trailing Alpha groups with Alpha, not Beta (diagrams travel with
    # their section)
    assert any(isinstance(b, Figure) for b in leaves[0][2])
    assert not any(isinstance(b, Figure) for b in leaves[1][2])


# --- writer end-to-end ------------------------------------------------------

def test_multipage_writes_overview_plus_section_pages(tmp_path):
    cfg = _cfg()
    doc = _doc(tmp_path, "<h1>Charter</h1>"
                         "<h2>Mission</h2><p>mission body</p>"
                         "<h2>Certifications</h2><p>cert body</p>")
    plan = SitePlan(nav=[NavItem(title="Charter", slug="charter")],
                    order=["charter"])
    out = tmp_path / "site"
    br.write_blocks_site(out, [doc], plan, {"charter": PageEnhancement()}, cfg,
                         use_ai=False, layout="multi-page")
    assert (out / "charter.html").exists()                 # overview
    assert (out / "charter__mission.html").exists()
    assert (out / "charter__certifications.html").exists()
    cert = (out / "charter__certifications.html").read_text()
    assert "cert body" in cert                              # section on its own page
    assert "mission body" not in cert                       # other section is elsewhere
    assert 'href="charter__mission.html"' in cert           # cross-section nav
    overview = (out / "charter.html").read_text()
    assert 'href="charter__mission.html"' in overview       # overview links sections
    assert (out / "index.html").exists()


def test_multipage_authored_explodes_authored_sections(tmp_path, monkeypatch):
    """The user's live path: render_mode=authored produces AuthoredSection blocks;
    multi-page must give each its own page (stubbed agent, no network)."""
    import md2x.site.authored_agent as aa
    cfg = _cfg()
    cfg["site"]["render_mode"] = "authored"
    cfg["site"]["fidelity"] = "synthesize"
    doc = _doc(tmp_path, "<h1>Charter</h1>"
                         "<h2>Mission</h2><p>m</p>"
                         "<h2>Certifications</h2><p>c</p>")

    def fake_authored(d, c, plan):
        return PageDoc(slug=d.slug, title=d.title, blocks=[
            Hero(title=d.title),
            AuthoredSection(anchor="mission", title="Mission",
                            html="<p>mission authored</p>", css=""),
            AuthoredSection(anchor="certifications", title="Certifications",
                            html="<p>cert authored</p>", css=""),
        ])

    monkeypatch.setattr(aa, "run_authored_page", fake_authored)
    plan = SitePlan(nav=[NavItem(title="Charter", slug="charter")],
                    order=["charter"])
    out = tmp_path / "site"
    br.write_blocks_site(out, [doc], plan, {"charter": PageEnhancement()}, cfg,
                         use_ai=True, layout="multi-page")
    assert (out / "charter__mission.html").exists()
    assert (out / "charter__certifications.html").exists()
    assert "cert authored" in (out / "charter__certifications.html").read_text()
    assert "mission authored" in (out / "charter__mission.html").read_text()


def test_multipage_single_section_stays_one_page(tmp_path):
    cfg = _cfg()
    doc = _doc(tmp_path, "<h1>C</h1><h2>Only</h2><p>only body</p>",
               slug="c", title="C")
    plan = SitePlan(nav=[NavItem(title="C", slug="c")], order=["c"])
    out = tmp_path / "site"
    br.write_blocks_site(out, [doc], plan, {"c": PageEnhancement()}, cfg,
                         use_ai=False, layout="multi-page")
    assert (out / "c.html").exists()
    assert not (out / "c__only.html").exists()              # <2 sections: no split
    assert "only body" in (out / "c.html").read_text()


def test_default_layout_keeps_one_page_with_all_sections(tmp_path):
    cfg = _cfg()
    doc = _doc(tmp_path, "<h1>C</h1>"
                         "<h2>Mission</h2><p>mission body</p>"
                         "<h2>Certifications</h2><p>cert body</p>",
               slug="c", title="C")
    plan = SitePlan(nav=[NavItem(title="C", slug="c")], order=["c"])
    out = tmp_path / "site"
    br.write_blocks_site(out, [doc], plan, {"c": PageEnhancement()}, cfg,
                         use_ai=False)                       # no layout -> single page
    assert (out / "c.html").exists()
    assert not (out / "c__mission.html").exists()
    page = (out / "c.html").read_text()
    assert "mission body" in page and "cert body" in page   # both on one page
