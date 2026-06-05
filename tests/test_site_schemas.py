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


def test_page_enhancement_empty_default():
    enh = PageEnhancement()
    assert enh.tldr == ""
    assert enh.takeaways == []
    assert enh.related == []
