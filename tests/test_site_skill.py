from md2x.site.skill import load_skill


def test_load_skill_includes_core_files():
    out = load_skill("reading")
    # Spine + principles + design-system + export-contract always present.
    assert "Living Site Skill" in out
    assert "Render information in the shape" in out
    assert "--ds-accent" in out
    assert "md2x:export" in out


def test_load_skill_includes_active_render_mode():
    assert "Render mode: hybrid" in load_skill("reading", render_mode="hybrid")
    assert "Render mode: full" in load_skill("reading", render_mode="full")
    assert "Render mode: blocks" in load_skill("reading", render_mode="blocks")


def test_load_skill_tolerates_missing_archetype_and_artifacts():
    # No archetypes/*.md or artifacts/*.md exist yet (added in PR-F); must not raise.
    out = load_skill("does-not-exist", render_mode="blocks",
                     artifacts=["nope", "also-nope"])
    assert "Living Site Skill" in out  # still returns the core skill


def test_load_skill_unknown_render_mode_skips_silently():
    out = load_skill("reading", render_mode="banana")
    assert "Living Site Skill" in out
    assert "Render mode:" not in out  # banana.md doesn't exist; nothing injected


def test_skill_files_are_resolvable_as_package_data():
    from importlib.resources import files
    root = files("md2x.site.skill")
    assert (root / "SKILL.md").is_file()
    assert (root / "render-modes" / "hybrid.md").is_file()
