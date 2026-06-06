"""Smoke test: the opt-in Tier-2/3 eval scripts import cleanly without running
(no tokens, no model, no network). Keeps the harness from rotting in CI while the
expensive evals themselves stay opt-in behind MD2X_RUN_EVALS."""
import sys
from pathlib import Path

import pytest

_EVALS = Path(__file__).resolve().parents[2] / "evals"


@pytest.fixture(autouse=True)
def _evals_on_path():
    sys.path.insert(0, str(_EVALS))
    try:
        yield
    finally:
        sys.path[:] = [p for p in sys.path if p != str(_EVALS)]
        for m in ("thariq_rubric", "run_quality_eval", "run_performance_eval"):
            sys.modules.pop(m, None)


def test_rubric_is_pure_data():
    import thariq_rubric
    assert isinstance(thariq_rubric.RUBRIC, str) and thariq_rubric.RUBRIC
    assert len(thariq_rubric.DIMENSIONS) == 5


def test_eval_scripts_import_and_expose_main():
    import run_quality_eval
    import run_performance_eval
    assert hasattr(run_quality_eval, "main")
    assert hasattr(run_performance_eval, "main")
