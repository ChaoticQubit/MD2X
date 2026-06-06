import pytest
from md2x.site.archetypes import (
    ARCHETYPES, ARCHETYPE_NAMES, get_archetype, get_default_render_mode,
    get_suggested_artifacts, resolve_layout,
)


def test_all_twelve_presets_have_complete_contract():
    expected = {"reading", "presentation", "flyer", "product", "docs", "review",
                "plan", "explainer", "report", "editor", "design", "custom"}
    assert set(ARCHETYPES) == expected
    assert set(ARCHETYPE_NAMES) == expected
    for name, a in ARCHETYPES.items():
        assert a["shell"] in ("sidebar", "deck", "landing")
        assert a["default_layout"] in ("multi-page", "single-page")
        assert a["default_render_mode"] in ("blocks", "hybrid", "full")
        assert isinstance(a["suggested_artifacts"], list)
        assert a["architect_instructions"]
        assert a["page_instructions"]


def test_render_mode_and_artifact_accessors():
    assert get_default_render_mode("editor") == "hybrid"
    assert get_default_render_mode("reading") == "blocks"
    assert "triage-board" in get_suggested_artifacts("editor")
    assert get_suggested_artifacts("custom") == []


def test_shell_mapping():
    assert ARCHETYPES["reading"]["shell"] == "sidebar"
    assert ARCHETYPES["docs"]["shell"] == "sidebar"
    assert ARCHETYPES["report"]["shell"] == "sidebar"
    assert ARCHETYPES["presentation"]["shell"] == "deck"
    assert ARCHETYPES["flyer"]["shell"] == "landing"
    assert ARCHETYPES["product"]["shell"] == "landing"
    assert ARCHETYPES["custom"]["shell"] == "sidebar"


def test_get_archetype_unknown_raises():
    with pytest.raises(ValueError):
        get_archetype("nope")


def test_resolve_layout_auto_uses_default():
    assert resolve_layout("auto", "reading") == "multi-page"
    assert resolve_layout("auto", "flyer") == "single-page"


def test_resolve_layout_explicit_overrides():
    assert resolve_layout("single-page", "reading") == "single-page"
