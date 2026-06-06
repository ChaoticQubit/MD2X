"""Archetype registry: each preset bundles the design intent, the agent
instructions used to plan/render a site in that style, and — for the living-site
model — its default render mode and the artifact patterns it tends to use.

Rebuilt on Thariq's taxonomy (12 presets). The per-archetype skill file
(skill/archetypes/<name>.md) and the suggested artifact files
(skill/artifacts/<id>.md) are composed into the agent instructions by the skill
loader; this registry supplies the structured metadata around them.
"""
from __future__ import annotations

ARCHETYPES: dict[str, dict] = {
    "reading": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "blocks",
        "suggested_artifacts": ["svg-figure", "comparison"],
        "architect_instructions": (
            "Plan a calm long-form reading site. Group related documents, order "
            "them so a reader can progress front-to-back, and produce a sidebar "
            "table of contents. Optimise for sustained reading and cross-linking."
        ),
        "page_instructions": (
            "Present this document as a focused long-form article: generous line "
            "length, a per-page table of contents, and quiet cross-links."
        ),
    },
    "presentation": {
        "shell": "deck",
        "default_layout": "single-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["deck", "chart", "svg-figure"],
        "architect_instructions": (
            "Plan a slide deck. Treat each top-level section as one slide; keep "
            "text minimal and sequence the slides for a talk."
        ),
        "page_instructions": (
            "Render content as deck slides: big type, one idea per slide, minimal "
            "prose, keyboard navigation between slides."
        ),
    },
    "flyer": {
        "shell": "landing",
        "default_layout": "single-page",
        "default_render_mode": "blocks",
        "suggested_artifacts": ["clickable-flow", "svg-figure"],
        "architect_instructions": (
            "Plan a single punchy landing page: a hero, a few bold sections, and "
            "clear calls to action."
        ),
        "page_instructions": (
            "Render as a marketing flyer: strong hero, bold visuals, scroll "
            "animations, prominent CTAs."
        ),
    },
    "product": {
        "shell": "landing",
        "default_layout": "single-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["comparison", "clickable-flow", "chart"],
        "architect_instructions": (
            "Plan a product page: hero, feature grid, screenshots, and section "
            "blocks that build a narrative."
        ),
        "page_instructions": (
            "Render as a product page: hero, feature cards, and alternating "
            "content/visual section blocks."
        ),
    },
    "docs": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "blocks",
        "suggested_artifacts": ["annotated-diff", "module-map", "live-demo"],
        "architect_instructions": (
            "Plan a technical documentation portal: a persistent nav tree, search, "
            "and a code-first layout."
        ),
        "page_instructions": (
            "Render as a docs page: persistent sidebar nav, anchored headings, "
            "first-class code blocks, and tabs for config variants."
        ),
    },
    "review": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["annotated-diff", "module-map", "flowchart"],
        "architect_instructions": (
            "Plan a code-review writeup: lead with a change summary, then "
            "severity-tagged findings, an annotated diff, and a module map of the "
            "affected area."
        ),
        "page_instructions": (
            "Render as a review: a summary up top, callouts for findings (tagged "
            "by severity), an annotated diff, and a map of the touched modules."
        ),
    },
    "plan": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["flowchart", "comparison", "chart"],
        "architect_instructions": (
            "Plan an implementation/exploration writeup: a phase timeline, a "
            "data-flow flowchart, a risk table, and a side-by-side comparison of "
            "candidate approaches."
        ),
        "page_instructions": (
            "Render as a plan: a timeline of phases, a flowchart of the data flow, "
            "a risk table, and an approach comparison."
        ),
    },
    "explainer": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["live-demo", "flowchart", "svg-figure", "comparison"],
        "architect_instructions": (
            "Plan a concept/feature explainer: a TL;DR, a collapsible request-path, "
            "tabbed configurations, a live interactive demo, a hover glossary, and "
            "an FAQ."
        ),
        "page_instructions": (
            "Render as an explainer: TL;DR summary, collapsible details, tabbed "
            "variants, a live demo where it helps understanding, and a glossary."
        ),
    },
    "report": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "blocks",
        "suggested_artifacts": ["chart"],
        "architect_instructions": (
            "Plan a status/data report: summary cards up top, then sections with "
            "tables and callouts."
        ),
        "page_instructions": (
            "Render as a report: summary callouts, clean tables, charts from real "
            "figures, and highlighted key findings."
        ),
    },
    "editor": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["triage-board", "prompt-tuner", "feature-flags"],
        "architect_instructions": (
            "Plan a custom editing interface: the page IS a working editor (triage "
            "board, prompt tuner, or flag editor) that always ends in an export "
            "button round-tripping back to Markdown/JSON."
        ),
        "page_instructions": (
            "Render as a custom editing interface: a real, interactive editor that "
            "ends in an export button (the md2x:export round-trip)."
        ),
    },
    "design": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "hybrid",
        "suggested_artifacts": ["animation-sandbox", "comparison"],
        "architect_instructions": (
            "Plan a design system site: a living token sheet (tokens to copyable "
            "swatches), a component-variants sheet, and an animation sandbox."
        ),
        "page_instructions": (
            "Render as a design reference: token swatches, component variants, and "
            "an animation sandbox — all driven by the --ds-* variables."
        ),
    },
    "custom": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "default_render_mode": "blocks",
        "suggested_artifacts": [],
        "architect_instructions": (
            "Follow the user's style brief exactly to plan the site structure."
        ),
        "page_instructions": (
            "Follow the user's style brief exactly to render each page."
        ),
    },
}

# Canonical ordered list of archetype names (CLI choices, validation, docs).
ARCHETYPE_NAMES = tuple(ARCHETYPES)


def get_archetype(name: str) -> dict:
    """Return the archetype dict for *name*, raising ValueError if unknown."""
    if name not in ARCHETYPES:
        raise ValueError(
            f"unknown archetype: {name!r} (choose from {sorted(ARCHETYPES)})"
        )
    return ARCHETYPES[name]


def resolve_layout(layout: str, archetype: str) -> str:
    """Resolve site.layout: 'auto' defers to the archetype's default_layout."""
    if layout == "auto":
        return get_archetype(archetype)["default_layout"]
    return layout


def get_shell(archetype: str) -> str:
    """Return the render.py SHELLS key for an archetype (sidebar|deck|landing)."""
    return get_archetype(archetype)["shell"]


def get_default_render_mode(archetype: str) -> str:
    """The render mode this archetype leans on when none is forced by config."""
    return get_archetype(archetype).get("default_render_mode", "blocks")


def get_suggested_artifacts(archetype: str) -> list[str]:
    """Artifact patterns this archetype tends to use (architect may pick others)."""
    return list(get_archetype(archetype).get("suggested_artifacts", []))
