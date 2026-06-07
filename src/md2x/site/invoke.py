"""Instrumented, time-bounded wrapper around an agno `Agent.run` call.

Every LLM call in the site pipeline goes through `invoke_agent`, so each one is
observable and bounded:

  * INFO when it starts (role, label, prompt size, timeout) and when it finishes
    (duration + token usage) — visible at the default log level, not buried at
    DEBUG. A slow model now shows a "calling…" line and a later "ok in Ns" line
    instead of silence.
  * a wall-clock timeout: a call that exceeds `ai.timeout` seconds is abandoned on
    a daemon thread and the caller falls back, so one stuck endpoint can never
    freeze the whole run (the 10–40 min hangs this replaces).
  * a typed-output check: if the provider answers with a plain string instead of
    the expected schema (e.g. an input guardrail blocked the prompt), that is
    raised as `AgentRejected` with the real reason — not a misleading
    AttributeError three call-frames away.

This is the single place LLM calls become legible; instrument here, not at every
call site.
"""
from __future__ import annotations

import threading
import time

from ..log import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = 120.0


class AgentRejected(RuntimeError):
    """The model returned no usable typed output — an input guardrail blocked the
    prompt, or the provider answered with a plain string instead of the schema."""


def _usage(resp) -> str:
    """Best-effort token usage from agno's RunOutput.metrics (shape varies by
    provider/version), formatted for one log line."""
    m = getattr(resp, "metrics", None)
    if m is None:
        return "tokens=n/a"

    def pick(*names):
        for n in names:
            v = getattr(m, n, None)
            if v is None and isinstance(m, dict):
                v = m.get(n)
            if v is None:
                continue
            if isinstance(v, (list, tuple)):        # sometimes per-message lists
                nums = [x for x in v if isinstance(x, (int, float))]
                if nums:
                    return sum(nums)
                continue
            return v
        return None

    inp = pick("input_tokens", "prompt_tokens")
    out = pick("output_tokens", "completion_tokens")
    tot = pick("total_tokens")
    if tot is None and (inp is not None or out is not None):
        tot = (inp or 0) + (out or 0)
    return f"tokens in={inp} out={out} total={tot}"


def invoke_agent(agent, prompt, *, role, label, expect=None, timeout=None):
    """Run ``agent.run(prompt)`` with INFO logging and a wall-clock ``timeout``.

    Returns the RunOutput. Raises ``TimeoutError`` if the call exceeds the
    deadline, or ``AgentRejected`` if ``expect`` is given and the response content
    is not that type. The caller is expected to fall back on either — the reason
    is already logged here.
    """
    timeout = float(timeout) if timeout else DEFAULT_TIMEOUT
    log.info("llm %s [%s]: calling (prompt %d chars, timeout %.0fs)",
             role, label, len(prompt), timeout)

    box: dict = {}

    def _work():
        try:
            box["resp"] = agent.run(prompt)
        except BaseException as e:                  # carry the real error across
            box["err"] = e

    t0 = time.perf_counter()
    th = threading.Thread(target=_work, name=f"llm-{role}", daemon=True)
    th.start()
    th.join(timeout)
    dt = time.perf_counter() - t0

    if th.is_alive():                               # deadline hit; abandon the thread
        log.warning("llm %s [%s]: TIMED OUT after %.1fs — falling back. Raise "
                    "ai.timeout or use a faster / structured-output model.",
                    role, label, dt)
        raise TimeoutError(f"{label}: timed out after {dt:.0f}s")
    if "err" in box:
        log.warning("llm %s [%s]: errored in %.1fs — %s", role, label, dt, box["err"])
        raise box["err"]

    resp = box.get("resp")
    content = getattr(resp, "content", None)
    if expect is not None and not isinstance(content, expect):
        snippet = repr(content)[:200]
        log.warning("llm %s [%s]: rejected in %.1fs — no %s (input guardrail or "
                    "unparseable output): %s", role, label, dt,
                    expect.__name__, snippet)
        raise AgentRejected(f"{label}: {snippet}")

    log.info("llm %s [%s]: ok in %.1fs (%s)", role, label, dt, _usage(resp))
    return resp
