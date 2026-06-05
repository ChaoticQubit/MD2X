"""Archetype registry: each preset bundles the design intent and the agent
instructions used to plan and render a site in that style."""
from __future__ import annotations

ARCHETYPES: dict[str, dict] = {
    "reading": {
        "shell": "sidebar",
        "default_layout": "multi-page",
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
        "architect_instructions": (
            "Plan a technical documentation portal: a persistent nav tree, search, "
            "and a code-first layout."
        ),
        "page_instructions": (
            "Render as a docs page: persistent sidebar nav, anchored headings, and "
            "first-class code blocks."
        ),
    },
    "report": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "architect_instructions": (
            "Plan a status/data report: summary cards up top, then sections with "
            "tables and callouts."
        ),
        "page_instructions": (
            "Render as a report: summary callouts, clean tables, and highlighted "
            "key figures."
        ),
    },
    "custom": {
        "shell": "sidebar",
        "default_layout": "multi-page",
        "architect_instructions": (
            "Follow the user's style brief exactly to plan the site structure."
        ),
        "page_instructions": (
            "Follow the user's style brief exactly to render each page."
        ),
    },
}


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
