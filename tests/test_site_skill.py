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


def test_run_architect_injects_skill_into_instructions(monkeypatch):
    import pytest
    pytest.importorskip("agno")
    from pathlib import Path
    from md2x.site import agents
    from md2x.site.schemas import Doc

    captured = {}

    def fake_make_agent(cfg, role, instructions, schema):
        captured["instructions"] = instructions

        class _Resp:
            content = agents._SitePlanModel(
                nav=[agents._NavItemModel(title="A", slug="a", group="")],
                order=["a"], index_title="Docs", index_intro="")

        class _Agent:
            def run(self, prompt):
                return _Resp()

        return _Agent()

    monkeypatch.setattr(agents, "_make_agent", fake_make_agent)
    docs = [Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>")]
    cfg = {"site": {"archetype": "reading", "style_prompt": "", "layout": "auto"},
           "ai": {"model": "x:y", "architect_model": None, "retries": 1}}
    agents.run_architect(docs, cfg)
    assert "Living Site Skill" in captured["instructions"]
    # archetype instructions still present after the injected skill
    assert "Plan a calm long-form reading site" in captured["instructions"]


def test_run_page_injects_skill_into_instructions(monkeypatch):
    import pytest
    pytest.importorskip("agno")
    from pathlib import Path
    from md2x.site import agents
    from md2x.site.schemas import Doc, SitePlan

    captured = {}

    def fake_make_agent(cfg, role, instructions, schema):
        captured["instructions"] = instructions

        class _Resp:
            content = agents._EnhancementModel(tldr="t", takeaways=[], related=[])

        class _Agent:
            def run(self, prompt):
                return _Resp()

        return _Agent()

    monkeypatch.setattr(agents, "_make_agent", fake_make_agent)
    doc = Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>")
    plan = SitePlan(nav=[], order=["a"])
    cfg = {"site": {"archetype": "reading", "fidelity": "light-enhance"},
           "ai": {"model": "x:y", "page_model": None, "retries": 1}}
    agents.run_page(doc, plan, cfg)
    assert "Living Site Skill" in captured["instructions"]
