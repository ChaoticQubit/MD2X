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
        if "api_key_env" not in spec:
            raise ValueError(
                "openai-like provider requires 'api_key_env' in the model spec "
                "(the name of the env var holding the API key)"
            )
        key_env = spec["api_key_env"]
        api_key = os.environ.get(key_env)
        if not api_key:
            raise RuntimeError(
                f"environment variable {key_env} is not set "
                f"(needed for ai.model provider 'openai-like')"
            )
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
