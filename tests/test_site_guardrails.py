import pytest

import md2x.config as config


def test_default_config_has_guardrails_block():
    cfg = config.deep_merge(config.DEFAULTS, {})
    g = cfg["ai"]["guardrails"]
    assert g["prompt_injection"] is True
    assert g["pii"] is False and g["moderation"] is False


def test_build_pre_hooks_default_prompt_injection():
    pytest.importorskip("agno")
    from md2x.site.guardrails import build_pre_hooks
    from agno.guardrails import PromptInjectionGuardrail
    hooks = build_pre_hooks({"ai": {"guardrails": {"prompt_injection": True}}})
    assert len(hooks) == 1
    assert isinstance(hooks[0], PromptInjectionGuardrail)


def test_build_pre_hooks_pii_opt_in_adds_second():
    pytest.importorskip("agno")
    from md2x.site.guardrails import build_pre_hooks
    hooks = build_pre_hooks({"ai": {"guardrails": {"prompt_injection": True,
                                                   "pii": True}}})
    assert len(hooks) == 2


def test_build_pre_hooks_all_off_is_empty():
    pytest.importorskip("agno")
    from md2x.site.guardrails import build_pre_hooks
    assert build_pre_hooks({"ai": {"guardrails": {"prompt_injection": False}}}) == []


def test_make_agent_wires_pre_hooks(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site import agents
    captured = {}

    class FakeAgent:
        def __init__(self, *a, **k):
            captured["pre_hooks"] = k.get("pre_hooks")

    monkeypatch.setattr(agents, "Agent", FakeAgent)
    cfg = {"ai": {"model": "x:y", "architect_model": None, "retries": 1}}
    agents._make_agent(cfg, "architect", "instr", agents._SitePlanModel)
    assert captured["pre_hooks"]   # non-empty: prompt-injection default-on
