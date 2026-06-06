"""The Thariq rubric — the single source of truth for judging a living site.

Both ``run_quality_eval.py`` and ``run_performance_eval.py`` import ``RUBRIC``
and ``DIMENSIONS`` from here, so the bar we hold the AI site generator to is
defined in exactly one place.

The north star (Thariq): ``md2x site`` must *transform* a Markdown document into
a polished, living website — render each piece of information in the shape it
actually has — not merely re-render the prose. The five dimensions below encode
that bar. The judge in the quality eval receives ``RUBRIC`` verbatim as its
``additional_guidelines`` and scores the generated HTML against it.

This module is pure data: no imports, no agno, no model calls. It is safe to
import anywhere (including CI) and costs nothing.
"""
from __future__ import annotations

# A short, stable handle for each scored dimension. Keep in lockstep with the
# five numbered sections of RUBRIC below (scripts may iterate / display these).
DIMENSIONS: list[str] = [
    "shape",          # 1. information rendered in its shape, not a wall of prose
    "density",        # 2. density + scannability
    "faithfulness",   # 3. faithful to the source; nothing fabricated
    "interactivity",  # 4. interactivity where the archetype calls for it
    "on_brand",       # 5. on-brand, self-contained, consumes the design tokens
]

# Each dimension is scored 0-10 by the LLM judge. The OVERALL score the eval
# reports is agno's single accuracy score (1-10) formed against this rubric;
# treat these five as the lens the judge reasons through before scoring.
RUBRIC: str = """\
You are judging whether an AI turned a Markdown document into a POLISHED, LIVING
WEBSITE — one that renders each piece of information in the shape it actually
has — rather than just re-rendering the prose as styled text. The material you
are scoring (the <agent_output>) is the generated HTML for one page. The
<agent_input> is the original Markdown source. Score the page 0-10, where 0 is a
plain wall of text and 10 is an exemplary living site. Reason explicitly through
ALL FIVE dimensions below, then give one overall score that reflects them
together; a serious failure on dimension 3 (faithfulness) or 5 (self-contained)
should cap the score low regardless of polish.

1. SHAPE — information rendered in its shape (not a wall of prose).
   - 0: Everything is paragraphs/<p> and generic headings; structure the source
     implied (metrics, steps, options, chronology, warnings) is flattened into
     undifferentiated text.
   - 10: Each kind of information appears in the format that fits it — metrics as
     KPI tiles or charts, procedures as numbered steps/timelines, comparisons or
     variants as tables/tabs, warnings as callouts, definitions as a glossary —
     and the choice of shape is justified by the content, not decorative.

2. DENSITY + SCANNABILITY — fast to scan, high signal-per-pixel.
   - 0: Long uniform text where every word carries equal visual weight; the
     reader must read everything to find the one fact that matters; no visual
     hierarchy, no scan path.
   - 10: Clear hierarchy (hero, sections, emphasis); the key number/decision/
     status is visible at a glance; whitespace and grouping are deliberate;
     information is dense without feeling cramped.

3. FAITHFULNESS — true to the source, nothing fabricated.
   - 0: Invents figures, claims, owners, statuses, dates, or sections not present
     in the source; or contradicts the source; or drops material facts.
   - 10: Every number, name, and claim is traceable to the source; nothing is
     invented; restructuring (e.g. a table from a list) preserves meaning exactly
     and omits nothing important.

4. INTERACTIVITY — present where the archetype calls for it (and not forced).
   - 0: An archetype that wants interaction (an editor/triage board, switchable
     config variants, a chart, an FAQ) is rendered as static, dead text; OR
     gratuitous interactivity is bolted onto content that did not call for it.
   - 10: Interaction matches the archetype — tabs/toggles for parallel variants,
     a working editor that ends in an export/copy action for editable content,
     collapsible FAQs, hoverable/animated charts — and it genuinely helps the
     reader rather than being ornamental.

5. ON-BRAND + SELF-CONTAINED — consumes the design tokens, no external network.
   - 0: Hardcoded colors/fonts that ignore the injected --ds-* design tokens; OR
     pulls in remote assets (CDN scripts, web fonts, <link href> to the network,
     fetch/XHR, remote <img>); OR is not self-contained.
   - 10: Styles exclusively through the --ds-* custom properties (var(--ds-accent),
     var(--ds-fg), var(--ds-space-*), …) so it stays on-brand; fully
     self-contained with all CSS/JS inline and ZERO external network references;
     it would render identically fully offline.
"""


__all__ = ["RUBRIC", "DIMENSIONS"]
