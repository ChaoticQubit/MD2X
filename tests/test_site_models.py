import pytest
from md2x.site.models import build_model


def test_string_model_passthrough():
    assert build_model({"model": "anthropic:claude-sonnet-4-6"}) == \
        "anthropic:claude-sonnet-4-6"


def test_role_override_used_when_present():
    cfg = {"model": "openai:gpt-4o", "architect_model": "anthropic:claude-x"}
    assert build_model(cfg, role="architect") == "anthropic:claude-x"


def test_role_override_falls_back_to_model():
    cfg = {"model": "openai:gpt-4o", "page_model": None}
    assert build_model(cfg, role="page") == "openai:gpt-4o"


def test_unknown_provider_raises():
    cfg = {"model": {"provider": "mystery", "id": "x"}}
    with pytest.raises(ValueError):
        build_model(cfg)


def test_openai_like_builds_object(monkeypatch):
    pytest.importorskip("agno")
    monkeypatch.setenv("LOCAL_LLM_KEY", "secret-123")
    cfg = {"model": {"provider": "openai-like", "id": "llama-3.3-70b",
                     "base_url": "http://localhost:1234/v1",
                     "api_key_env": "LOCAL_LLM_KEY"},
           "temperature": 0.4}
    model = build_model(cfg)
    assert model.id == "llama-3.3-70b"
    assert model.base_url == "http://localhost:1234/v1"
    assert model.api_key == "secret-123"
    assert model.temperature == 0.4


def test_openai_like_missing_key_raises(monkeypatch):
    # if you NAME an env var, it must exist — a named-but-unset key is a mistake.
    pytest.importorskip("agno")
    monkeypatch.delenv("LOCAL_LLM_KEY", raising=False)
    cfg = {"model": {"provider": "openai-like", "id": "x",
                     "base_url": "http://h/v1", "api_key_env": "LOCAL_LLM_KEY"}}
    with pytest.raises(RuntimeError):
        build_model(cfg)


def test_openai_like_no_key_env_uses_placeholder(monkeypatch):
    # a local endpoint needs no auth: omit api_key_env entirely, no env var set.
    pytest.importorskip("agno")
    monkeypatch.delenv("LOCAL_LLM_KEY", raising=False)
    cfg = {"model": {"provider": "openai-like", "id": "qwen2.5:32b",
                     "base_url": "http://localhost:11434/v1"}}
    model = build_model(cfg)                       # must NOT raise
    assert model.id == "qwen2.5:32b"
    assert model.base_url == "http://localhost:11434/v1"
    assert model.api_key == "not-needed"


def test_openai_like_inline_api_key(monkeypatch):
    # an inline api_key (no env indirection) is honored when api_key_env is absent.
    pytest.importorskip("agno")
    cfg = {"model": {"provider": "openai-like", "id": "x",
                     "base_url": "http://h/v1", "api_key": "sk-inline"}}
    assert build_model(cfg).api_key == "sk-inline"
