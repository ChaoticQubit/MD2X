"""Build an agno model from config — model/provider agnostic.

A string spec ("provider:model_id") is handed straight to agno. A dict spec
targets any OpenAI-compatible / local endpoint via OpenAILike. agno (and pydantic)
are imported lazily so this module loads even without the [ai] extra; only the
dict path needs agno installed.
"""
from __future__ import annotations

import os
from typing import Any

from ..log import get_logger

log = get_logger(__name__)


def build_model(ai_cfg: dict, role: str = "model") -> Any:
    spec = ai_cfg.get(f"{role}_model") or ai_cfg["model"]
    if isinstance(spec, str):
        log.debug("role %s: native model spec %r", role, spec)
        return spec  # agno accepts "provider:model_id" directly
    provider = spec.get("provider", "openai-like")
    if provider == "openai-like":
        from agno.models.openai.like import OpenAILike
        # api_key is OPTIONAL: local endpoints (Ollama, LM Studio, llama.cpp,
        # vLLM) need no auth. Name an env var via `api_key_env` for a hosted
        # endpoint that does require one; omit it for a local server. The OpenAI
        # client still wants a non-empty string, so md2x supplies a harmless
        # placeholder when none is configured.
        key_env = spec.get("api_key_env")
        if key_env:
            api_key = os.environ.get(key_env)
            if not api_key:
                raise RuntimeError(
                    f"environment variable {key_env} is not set "
                    f"(named in ai.model.api_key_env)"
                )
        else:
            api_key = spec.get("api_key") or "not-needed"
            log.debug("role %s: openai-like, no api_key_env; using placeholder key",
                      role)
        # Apply tuning params to the model object where the API supports it.
        # (Native "provider:model_id" string models carry no params — agno uses
        # the provider defaults for those.)
        extra: dict = {}
        if ai_cfg.get("temperature") is not None:
            extra["temperature"] = ai_cfg["temperature"]
        if ai_cfg.get("max_tokens") is not None:
            extra["max_tokens"] = ai_cfg["max_tokens"]
        log.debug("role %s: openai-like id=%s base_url=%s key_env=%s params=%s",
                  role, spec["id"], spec["base_url"], key_env, extra)
        return OpenAILike(id=spec["id"], base_url=spec["base_url"],
                          api_key=api_key, **extra)
    raise ValueError(
        f"unknown ai model provider: {provider!r} "
        f"(use a 'provider:model_id' string for native providers, "
        f"or provider: openai-like for OpenAI-compatible endpoints)"
    )


def is_openai_like(ai_cfg: dict, role: str = "model") -> bool:
    """True when ``role``'s resolved model is a dict spec targeting an
    OpenAI-compatible / local endpoint, rather than a native "provider:model_id"
    string.

    Such endpoints often advertise OpenAI structured-output support yet ignore
    the `response_format` JSON schema (a local proxy claims support but no-ops
    it), so the model free-forms JSON that fails the pydantic output schema. The
    agents key `use_json_mode` off this so agno injects the schema into the
    prompt instead of trusting native enforcement; native string models keep
    native structured output.
    """
    spec = ai_cfg.get(f"{role}_model") or ai_cfg["model"]
    return isinstance(spec, dict) and spec.get("provider", "openai-like") == "openai-like"
