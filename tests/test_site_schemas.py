from pathlib import Path
from md2x.site.schemas import Doc, NavItem, SitePlan, PageEnhancement


def test_doc_construction():
    d = Doc(path=Path("a.md"), title="A", outline=["Intro"], fragment_html="<p>x</p>")
    assert d.title == "A"
    assert d.slug == "a"


def test_siteplan_defaults():
    plan = SitePlan(nav=[NavItem(title="A", slug="a")], order=["a"])
    assert plan.nav[0].slug == "a"
    assert plan.index_title  # has a non-empty default


def test_designsystem_defaults():
    from md2x.site.schemas import DesignSystem
    ds = DesignSystem()
    assert ds.accent == "#2563eb"
    assert ds.density == "comfortable"
    assert ds.bg and ds.fg and ds.font_sans


def test_siteplan_has_default_designsystem():
    plan = SitePlan(nav=[NavItem(title="A", slug="a")], order=["a"])
    assert plan.design.accent == "#2563eb"


def test_page_enhancement_empty_default():
    enh = PageEnhancement()
    assert enh.tldr == ""
    assert enh.takeaways == []
    assert enh.related == []
