"""agno-native input guardrails, provider-agnostic.

Every site agent (architect, page, blocks, full, report) gets these as
`pre_hooks`. Prompt-injection defense is default-on so a hostile Markdown
document cannot hijack the agent ("ignore previous instructions ..."); PII and
moderation are opt-in via the `ai.guardrails` config so the author's own content
is not mangled by default.

A guardrail trip raises `agno.exceptions.InputCheckError`, which each pipeline
stage's existing try/except degrades to the deterministic path (logged WARNING) —
generation never crashes on a flagged input.

The agno import is lazy (inside the function), so this module loads on the
`--no-ai` path; an environment without agno simply gets no hooks.
"""
from __future__ import annotations

from ..log import get_logger

log = get_logger(__name__)


def build_pre_hooks(cfg: dict) -> list:
    """Return the agno pre-hook guardrails enabled by `cfg['ai']['guardrails']`.

    Defaults: prompt_injection on, pii off, moderation off. Returns [] if agno
    (or the guardrails module) is unavailable.
    """
    g = (cfg.get("ai") or {}).get("guardrails") or {}
    try:
        from agno.guardrails import (
            OpenAIModerationGuardrail, PIIDetectionGuardrail,
            PromptInjectionGuardrail,
        )
    except Exception as e:  # agno missing or API moved
        log.debug("guardrails unavailable (%s); none applied", e)
        return []

    hooks: list = []
    if g.get("prompt_injection", True):
        hooks.append(PromptInjectionGuardrail())
    if g.get("pii", False):
        hooks.append(PIIDetectionGuardrail())
    if g.get("moderation", False):
        hooks.append(OpenAIModerationGuardrail())
    log.debug("guardrails: %d pre-hook(s) active (%s)",
              len(hooks), ", ".join(type(h).__name__ for h in hooks) or "none")
    return hooks
