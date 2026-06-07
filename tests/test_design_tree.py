"""The DesignTree / SectionSpec IR for authored mode."""
from md2x.site.design_tree import SectionSpec, DesignTree


def test_section_spec_defaults():
    s = SectionSpec(anchor="a", title="A")
    assert s.realization == "inline" and s.layout == "stack"
    assert s.components == [] and s.source_anchors == []


def test_section_spec_carries_hints():
    s = SectionSpec(anchor="roles", title="Roles", realization="artifact",
                    layout="grid", components=["table:sortable"],
                    source_anchors=["roles", "duties"])
    assert s.realization == "artifact" and s.components == ["table:sortable"]
    assert s.source_anchors == ["roles", "duties"]


def test_design_tree_holds_sections():
    t = DesignTree(slug="p", sections=[SectionSpec(anchor="a", title="A")])
    assert t.slug == "p" and len(t.sections) == 1


def test_design_tree_default_empty():
    assert DesignTree(slug="p").sections == []
