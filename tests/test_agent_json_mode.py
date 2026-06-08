"""Local (openai-like) endpoints often advertise OpenAI structured-output
support but silently ignore the `response_format` schema, so the model free-forms
JSON that fails pydantic validation (the architect dropped its required nav/order
this way). Every site agent must therefore build with `use_json_mode=True` when
the resolved model is a local dict spec — that makes agno inject the output
schema into the prompt instead of trusting native enforcement. Native
"provider:model_id" string models keep native structured output (use_json_mode
stays False).
"""
import pytest

OPENAI_LIKE = {"provider": "openai-like", "id": "x", "base_url": "http://h/v1"}
NATIVE = "anthropic:claude-sonnet-4-6"


class _FakeAgent:
    """Captures the kwargs it was constructed with so tests can assert on them."""
    def __init__(self, **kw):
        self.kw = kw


def _cfg(model):
    return {
        "ai": {"model": model, "retries": 2},
        "site": {"archetype": "presentation", "render_mode": "authored",
                 "fidelity": "synthesize", "layout": "single-page",
                 "style_prompt": ""},
    }


def _patch(monkeypatch, mod):
    monkeypatch.setattr(mod, "Agent", _FakeAgent)
    monkeypatch.setattr(mod, "build_model", lambda ai, role="model": "MODEL")
    monkeypatch.setattr(mod, "build_pre_hooks", lambda cfg: [])


# ── architect ──────────────────────────────────────────────────────────────

def test_architect_uses_json_mode_for_openai_like(monkeypatch):
    from md2x.site import agents
    _patch(monkeypatch, agents)
    ag = agents._make_agent(_cfg(OPENAI_LIKE), "architect", "instr",
                            agents._SitePlanModel)
    assert ag.kw["use_json_mode"] is True


def test_architect_no_json_mode_for_native(monkeypatch):
    from md2x.site import agents
    _patch(monkeypatch, agents)
    ag = agents._make_agent(_cfg(NATIVE), "architect", "instr",
                            agents._SitePlanModel)
    assert ag.kw["use_json_mode"] is False


# ── designer ───────────────────────────────────────────────────────────────

def test_designer_uses_json_mode_for_openai_like(monkeypatch):
    from md2x.site import section_designer as sd
    _patch(monkeypatch, sd)
    assert sd._build_agent(_cfg(OPENAI_LIKE)).kw["use_json_mode"] is True


def test_designer_no_json_mode_for_native(monkeypatch):
    from md2x.site import section_designer as sd
    _patch(monkeypatch, sd)
    assert sd._build_agent(_cfg(NATIVE)).kw["use_json_mode"] is False


# ── builder ────────────────────────────────────────────────────────────────

def test_builder_uses_json_mode_for_openai_like(monkeypatch):
    from md2x.site import section_builder as sb
    _patch(monkeypatch, sb)
    assert sb._build_agent(_cfg(OPENAI_LIKE)).kw["use_json_mode"] is True


def test_builder_no_json_mode_for_native(monkeypatch):
    from md2x.site import section_builder as sb
    _patch(monkeypatch, sb)
    assert sb._build_agent(_cfg(NATIVE)).kw["use_json_mode"] is False
