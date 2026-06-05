from pathlib import Path
import pytest
from md2x.site.schemas import Doc, SitePlan, PageEnhancement


def _docs():
    return [Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>"),
            Doc(path=Path("b.md"), title="B", outline=["y"], fragment_html="<p>b</p>")]


def test_pydantic_to_siteplan_conversion():
    pytest.importorskip("agno")
    from md2x.site import agents
    pm = agents._SitePlanModel(
        nav=[agents._NavItemModel(title="A", slug="a", group="")],
        order=["a"], index_title="Docs", index_intro="hi")
    plan = agents._to_site_plan(pm)
    assert isinstance(plan, SitePlan)
    assert plan.nav[0].slug == "a"
    assert plan.index_title == "Docs"


def test_pydantic_to_enhancement_conversion():
    pytest.importorskip("agno")
    from md2x.site import agents
    em = agents._EnhancementModel(tldr="t", takeaways=["a"], related=["b"])
    enh = agents._to_enhancement(em)
    assert isinstance(enh, PageEnhancement)
    assert enh.tldr == "t" and enh.takeaways == ["a"]


def test_run_architect_uses_canned_agent(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site import agents

    class FakeResp:
        content = agents._SitePlanModel(
            nav=[agents._NavItemModel(title="A", slug="a", group="")],
            order=["a"], index_title="Docs", index_intro="")

    class FakeAgent:
        def __init__(self, *a, **k): pass
        def run(self, prompt): return FakeResp()

    monkeypatch.setattr(agents, "Agent", FakeAgent)
    cfg = {"site": {"archetype": "reading", "style_prompt": "", "layout": "auto"},
           "ai": {"model": "x:y", "architect_model": None, "temperature": 0.4,
                  "max_tokens": None, "retries": 1}}
    plan = agents.run_architect(_docs(), cfg)
    assert isinstance(plan, SitePlan)
    assert plan.order == ["a"]


def test_run_page_preserve_returns_empty_enhancement():
    """fidelity=preserve must short-circuit before constructing any agent."""
    pytest.importorskip("agno")
    from md2x.site import agents
    doc = Doc(path=Path("x.md"), title="X", outline=[], fragment_html="<p>x</p>")
    plan = SitePlan(nav=[], order=[])
    cfg = {"site": {"archetype": "reading", "fidelity": "preserve"},
           "ai": {}}
    enh = agents.run_page(doc, plan, cfg)
    assert isinstance(enh, PageEnhancement)
    assert enh.tldr == "" and enh.takeaways == [] and enh.related == []
