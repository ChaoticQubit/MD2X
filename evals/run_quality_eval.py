#!/usr/bin/env python3
"""Tier-2 quality eval (LLM-as-judge) for the ``md2x site`` AI generator.

OPT-IN. This costs tokens and needs a real model, so it MUST NOT run in CI or on
import. Run it explicitly:

    MD2X_RUN_EVALS=1 python evals/run_quality_eval.py

What it does, for each reference document in ``evals/reference/``:
  1. Build a ``Doc`` straight from the raw Markdown (no pandoc) — good enough as
     eval input; a real ``md2x site`` run uses the full pandoc pipeline.
  2. Generate the page HTML through the real md2x entry points (the block agent
     in hybrid mode, or the full-page agent in full mode).
  3. Score that generated HTML with an agno ``AccuracyEval`` whose judge reasons
     through the Thariq rubric (``thariq_rubric.RUBRIC``). The ``input`` is the
     source text, the ``expected_output`` is a one-line description of an
     excellent living-site rendering.
  4. Print a per-doc + overall table and PASS/FAIL against a threshold.

Design notes:
  - Provider-agnostic: the judge model comes from the project factory
    ``build_model(cfg["ai"], "page")``; no provider/SDK is hardcoded.
  - agno's ``AccuracyEval.run()`` always generates the answer to judge by calling
    ``agent.run(...)``. We have ALREADY generated the page, so we wrap it in a
    tiny fixed-response agent that simply returns that HTML — the judge then
    scores the true md2x output instead of re-generating anything.
  - Every agno / model import lives INSIDE a function, never at module top level,
    so this file imports cleanly without the [ai] extra installed.
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path

# Pure-data, zero-cost import (no agno, no model) — safe at module top.
from thariq_rubric import RUBRIC

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"

# One reference doc per archetype, with the render_mode that best exercises it.
#   hybrid -> typed blocks + optionally sandboxed interactive artifacts
#   full   -> one standalone, self-contained interactive HTML document
CASES: list[dict[str, str]] = [
    {"name": "report",    "archetype": "report",    "render_mode": "hybrid"},
    {"name": "explainer", "archetype": "explainer", "render_mode": "hybrid"},
    {"name": "deck",      "archetype": "presentation", "render_mode": "hybrid"},
    {"name": "editor",    "archetype": "editor",    "render_mode": "full"},
]

# A one-line description of an excellent rendering, per archetype. This is the
# AccuracyEval ``expected_output`` — the judge treats it as the target the rubric
# elaborates on.
EXPECTED: dict[str, str] = {
    "report": (
        "A scannable status page: a hero with the headline status, the KPIs as a "
        "tile/chart strip, risks as callouts, decisions and next-steps as tight "
        "lists — every figure faithful to the source, styled only via --ds-* "
        "tokens, fully self-contained."
    ),
    "explainer": (
        "A clear explainer page: the request path as numbered steps, the config "
        "variants as switchable tabs, the tuning knobs and FAQ as scannable "
        "structure — faithful to the source, on-brand via --ds-* tokens, no "
        "external network."
    ),
    "deck": (
        "A polished talk page: one idea per section with strong visual hierarchy "
        "and a clear scan path, the key shifts surfaced as emphasis/callouts — "
        "faithful to the outline, on-brand via --ds-* tokens, self-contained."
    ),
    "editor": (
        "A working triage page: an interactive board the reader can filter and "
        "edit, ending in an export/copy-to-Markdown button; priorities and exit "
        "criteria are clear — faithful to the source items, on-brand via --ds-* "
        "tokens, self-contained with all JS inline and no network."
    ),
}

PASS_THRESHOLD = 7.0  # overall avg_score (0-10) at or above this => PASS


def _make_cfg(archetype: str, render_mode: str) -> dict:
    """Build a real md2x config for one case (DEFAULTS + a few overrides)."""
    from md2x.config import DEFAULTS, deep_merge
    return deep_merge(
        DEFAULTS,
        {
            "site": {
                "archetype": archetype,
                "render_mode": render_mode,
                "fidelity": "synthesize",   # let the agent restructure the content
            },
            # Provider-agnostic default; override via md2x.yaml / env for other
            # providers. build_model() consumes this dict.
            "ai": {"model": "anthropic:claude-sonnet-4-6", "retries": 2},
        },
    )


def _doc_from_markdown(name: str):
    """Construct a ``Doc`` directly from a reference .md file — no pandoc.

    Real ``md2x site`` runs feed Doc through the full pandoc pipeline (faithful
    HTML, real outline). For eval input the raw text wrapped in a <p> is enough:
    the agents read ``fragment_html`` and ``title``/``outline`` only.
    """
    from md2x.site.schemas import Doc
    path = REFERENCE_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    # Derive a title from the first ATX heading, else the filename.
    title = name.replace("-", " ").title()
    outline: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("# ") and title == name.replace("-", " ").title():
            title = s[2:].strip()
        elif s.startswith("## "):
            outline.append(s[3:].strip())
    return Doc(path=path, title=title, outline=outline,
               fragment_html="<p>" + raw + "</p>")


def _generate_html(doc, cfg: dict) -> str:
    """Run the real md2x AI generator for one page and return its HTML string.

    hybrid -> blocks agent + block renderer; full -> full-page agent + full
    renderer. Both paths inject the sanitized --ds-* design tokens so the judge
    sees exactly what ships.

    The agent functions raise on a model failure (the real site writers, not the
    agents, own the fallback). We mirror that fallback here so a transient AI
    failure yields the deterministic page the judge can still score, exactly as
    production would ship — rather than aborting the whole doc.
    """
    from md2x.site.design_css import design_css_vars
    from md2x.site.schemas import DesignSystem
    ds_css = design_css_vars(DesignSystem(accent=cfg["site"]["theme"]["accent"]))
    mode = cfg["site"]["render_mode"]
    if mode == "full":
        from md2x.site.full_render import render_full_page
        try:
            from md2x.site.full_agent import run_full_page
            fp = run_full_page(doc, cfg)
        except Exception as e:
            print(f"   full agent failed ({e}); deterministic fallback page")
            from md2x.site.full_render import _deterministic_page
            fp = _deterministic_page(doc)
        return render_full_page(fp, ds_css)
    # hybrid (and any block-based mode)
    from md2x.site.blocks_render import _blocks_page_html, render_blocks
    try:
        from md2x.site.blocks_agent import run_page_blocks
        page = run_page_blocks(doc, cfg)
    except Exception as e:
        print(f"   blocks agent failed ({e}); deterministic fallback page")
        from md2x.site.blocks import build_page_doc
        page = build_page_doc(doc)
    body = render_blocks(page.blocks, ds_css=ds_css)
    # Wrap the block body in the same self-contained page shell the real site
    # writer uses, so the judge sees the complete shipped page — tokens + block
    # CSS + shared JS inline — not just the bare body fragment.
    accent = cfg["site"]["theme"]["accent"]
    return _blocks_page_html(page.title, accent, ds_css,
                             f'<main>{body}</main>')


def _fixed_agent(html: str, name: str):
    """A tiny agno Agent whose ``run()`` returns the already-generated HTML.

    AccuracyEval.run() generates the answer-to-judge by calling agent.run(); we
    already have the page, so this agent just hands it back. The judge model
    (set on AccuracyEval) does the real LLM-as-judge scoring.
    """
    from agno.agent import Agent
    from agno.run.agent import RunOutput

    class _FixedAgent(Agent):
        def run(self, *args, **kwargs):  # type: ignore[override]
            return RunOutput(content=html)

    # No model is needed on this agent (run() is overridden), but agno reads
    # ``.name`` / ``.id`` for result logging, so give it a name.
    return _FixedAgent(name=f"md2x-site::{name}")


def _evaluate(case: dict, judge_model, html: str) -> float | None:
    """Score one generated page with the rubric-driven judge; return avg_score."""
    from agno.eval.accuracy import AccuracyEval
    name = case["name"]
    src = (REFERENCE_DIR / f"{name}.md").read_text(encoding="utf-8")
    eval_ = AccuracyEval(
        name=f"thariq-living-site::{name}",
        input=src,
        expected_output=EXPECTED[name],
        agent=_fixed_agent(html, name),
        model=judge_model,                 # the LLM judge (provider-agnostic)
        additional_guidelines=RUBRIC,      # the Thariq rubric, verbatim
        num_iterations=1,
        print_results=True,
    )
    result = eval_.run(print_summary=False, print_results=True)
    return None if result is None else float(result.avg_score)


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    name_w = max([len("Document")] + [len(r[0]) for r in rows])
    mode_w = max([len("Mode")] + [len(r[1]) for r in rows])
    print()
    print(f"{'Document':<{name_w}}  {'Mode':<{mode_w}}  {'Score (0-10)'}")
    print(f"{'-' * name_w}  {'-' * mode_w}  {'-' * 12}")
    for doc_name, mode, score in rows:
        print(f"{doc_name:<{name_w}}  {mode:<{mode_w}}  {score}")


def main() -> None:
    if not os.getenv("MD2X_RUN_EVALS"):
        print("Set MD2X_RUN_EVALS=1 to run (uses tokens).")
        return

    # Build the judge model once via the project factory (provider-agnostic).
    cfg0 = _make_cfg("reading", "hybrid")
    from md2x.site.models import build_model
    judge_model = build_model(cfg0["ai"], "page")

    rows: list[tuple[str, str, str]] = []
    scores: list[float] = []

    for case in CASES:
        name, mode = case["name"], case["render_mode"]
        print(f"\n=== {name} ({case['archetype']} / {mode}) ===")
        try:
            cfg = _make_cfg(case["archetype"], mode)
            doc = _doc_from_markdown(name)
            html = _generate_html(doc, cfg)
            print(f"generated {len(html)} chars of HTML; judging...")
            score = _evaluate(case, judge_model, html)
            if score is None:
                rows.append((name, mode, "ERROR (no result)"))
            else:
                scores.append(score)
                rows.append((name, mode, f"{score:.2f}"))
        except Exception as e:  # defensive: one bad doc must not sink the run
            print(f"!! {name} failed: {e}")
            traceback.print_exc()
            rows.append((name, mode, f"ERROR ({type(e).__name__})"))

    _print_table(rows)

    if not scores:
        print("\nNo documents scored successfully — FAIL.")
        raise SystemExit(1)

    overall = sum(scores) / len(scores)
    verdict = "PASS" if overall >= PASS_THRESHOLD else "FAIL"
    print(f"\nOverall: {overall:.2f} / 10 across {len(scores)} doc(s) "
          f"(threshold {PASS_THRESHOLD:.1f}) -> {verdict}")
    raise SystemExit(0 if overall >= PASS_THRESHOLD else 1)


if __name__ == "__main__":
    main()
