#!/usr/bin/env python3
"""Tier-3 performance eval for the ``md2x site`` deterministic render path.

OPT-IN. Even though this tier needs NO model (it measures the deterministic
block-build + render path), it is still gated behind ``MD2X_RUN_EVALS`` so it
never runs in CI or on import:

    MD2X_RUN_EVALS=1 python evals/run_performance_eval.py

What it measures: building a deterministic ``PageDoc`` from each reference
document (``build_page_doc`` — no LLM) and rendering it to HTML
(``render_blocks``), wrapped in agno's ``PerformanceEval`` so we get runtime and
peak-memory stats over several iterations. This is the floor of the pipeline:
the work every ``md2x site`` run does regardless of whether the AI agents fire.

Notes:
  - The deterministic md2x imports (config, schemas, blocks, blocks_render,
    design_css) carry NO agno/pydantic at module top, so this file imports fine
    without the [ai] extra. The agno ``PerformanceEval`` import is kept inside
    ``main()`` so importing this module stays free.
"""
from __future__ import annotations

import os
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"
REFERENCE_DOCS = ["report", "explainer", "deck", "editor"]


def _docs():
    """Build a Doc per reference file, straight from raw Markdown (no pandoc)."""
    from md2x.site.schemas import Doc
    docs = []
    for name in REFERENCE_DOCS:
        path = REFERENCE_DIR / f"{name}.md"
        raw = path.read_text(encoding="utf-8")
        title = name.replace("-", " ").title()
        for line in raw.splitlines():
            if line.strip().startswith("# "):
                title = line.strip()[2:].strip()
                break
        docs.append(Doc(path=path, title=title, outline=[],
                        fragment_html="<p>" + raw + "</p>"))
    return docs


def _build_generate_fn():
    """Return a zero-arg callable that does one deterministic build+render pass.

    No model is involved: ``build_page_doc`` derives a typed block tree from the
    verbatim fragment HTML and ``render_blocks`` turns it into the final, fully
    self-contained HTML string (with sanitized --ds-* design tokens).
    """
    from md2x.site.blocks import build_page_doc
    from md2x.site.blocks_render import render_blocks
    from md2x.site.design_css import design_css_vars
    from md2x.site.schemas import DesignSystem

    docs = _docs()
    ds_css = design_css_vars(DesignSystem())

    def generate() -> int:
        total = 0
        for doc in docs:
            page = build_page_doc(doc)
            total += len(render_blocks(page.blocks, ds_css=ds_css))
        return total

    return generate


def main() -> None:
    if not os.getenv("MD2X_RUN_EVALS"):
        print("Set MD2X_RUN_EVALS=1 to run "
              "(no model/tokens; measures the deterministic build+render path).")
        return

    from agno.eval.performance import PerformanceEval

    generate = _build_generate_fn()
    # Sanity: prove the path works (and warm imports) before measuring.
    chars = generate()
    print(f"deterministic build+render of {len(REFERENCE_DOCS)} doc(s) "
          f"produced {chars} chars of HTML; measuring...")

    perf = PerformanceEval(
        func=generate,
        name="md2x-site-deterministic-render",
        num_iterations=5,
        warmup_runs=1,
        measure_runtime=True,
        measure_memory=True,
    )
    # print_results/print_summary default to False in agno; ask for both so the
    # runtime + peak-memory stats are actually reported.
    result = perf.run(print_results=True, print_summary=True)

    # The rich tables above render to a TTY; also emit plain-text stats so the
    # numbers survive when stdout is piped/captured (e.g. in a log).
    avg_t = getattr(result, "avg_run_time", None)
    if avg_t is not None:
        print(f"\navg runtime: {avg_t * 1000:.3f} ms  "
              f"(min {getattr(result, 'min_run_time', 0) * 1000:.3f} / "
              f"max {getattr(result, 'max_run_time', 0) * 1000:.3f} ms)")
    avg_m = getattr(result, "avg_memory_usage", None)
    if avg_m is not None:
        print(f"avg peak memory: {avg_m:.4f} MiB  "
              f"(max {getattr(result, 'max_memory_usage', 0):.4f} MiB)")


if __name__ == "__main__":
    main()
