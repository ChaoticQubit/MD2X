"""The instrumented, time-bounded LLM-call wrapper every agent routes through."""
import time

import pytest

from md2x.site.invoke import invoke_agent, AgentRejected


class _Resp:
    def __init__(self, content, metrics=None):
        self.content = content
        self.metrics = metrics


class _Agent:
    def __init__(self, fn):
        self._fn = fn

    def run(self, prompt):
        return self._fn(prompt)


class Good:                      # stand-in for an expected output schema
    pass


def test_returns_response_on_typed_content():
    good = Good()
    agent = _Agent(lambda p: _Resp(good, metrics={"input_tokens": 10,
                                                  "output_tokens": 5,
                                                  "total_tokens": 15}))
    resp = invoke_agent(agent, "hi", role="t", label="x", expect=Good, timeout=5)
    assert resp.content is good


def test_rejects_untyped_content_from_guardrail():
    # a blocked prompt comes back as a plain string, not the schema
    agent = _Agent(lambda p: _Resp("Validation failed: PII detected"))
    with pytest.raises(AgentRejected) as ei:
        invoke_agent(agent, "hi", role="t", label="sec", expect=Good, timeout=5)
    assert "PII" in str(ei.value)               # the real reason, not AttributeError


def test_times_out_without_hanging():
    def _slow(p):
        time.sleep(3)
        return _Resp(Good())
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        invoke_agent(_Agent(_slow), "hi", role="t", label="slow",
                     expect=Good, timeout=0.2)
    assert time.perf_counter() - t0 < 1.5       # returned promptly; didn't wait 3s


def test_propagates_underlying_error():
    def _boom(p):
        raise ValueError("api 500")
    with pytest.raises(ValueError):
        invoke_agent(_Agent(_boom), "hi", role="t", label="e",
                     expect=Good, timeout=5)


def test_no_expect_skips_type_check():
    resp = invoke_agent(_Agent(lambda p: _Resp("anything")),
                        "hi", role="t", label="x", timeout=5)
    assert resp.content == "anything"
