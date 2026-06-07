"""Per-section builder agent (authored mode).

Turns one `SectionSpec` + its source HTML into a real section, bound to the
design-system contract: either an `AuthoredSection` (inline HTML + CSS, no JS) or
an `Artifact` (a sandboxed CSP iframe widget, the only place model JS runs). The
renderer is the enforcement boundary (it scopes+lints the CSS and sanitizes the
HTML); this agent only carries the model's output into the right block.

agno + pydantic are imported here only; imported lazily from authored_agent.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import Artifact, AuthoredSection, Export
from .design_tree import SectionSpec
from .guardrails import build_pre_hooks
from .invoke import invoke_agent
from .models import build_model
from .sanitize import sanitize_artifact_html
from .skill import load_skill

log = get_logger(__name__)

_MAX_INPUT = 10000        # cap a section's source so a huge one can't stall the build

_SYSTEM = (
    "You are a front-end engineer authoring ONE section of a single-page website "
    "to a STRICT design-system contract. Distil the source into a glance-able "
    "module — lead with the key point, use the requested layout/components, do NOT "
    "paste the source verbatim. Be faithful to the facts.\n"
    "DESIGN CONTRACT — obey exactly (violations are deleted before render):\n"
    "  - Style ONLY with these CSS variables: colours var(--ds-accent) "
    "var(--ds-bg) var(--ds-fg) var(--ds-muted) var(--ds-card) var(--ds-border); "
    "spacing var(--ds-space-1..6); type var(--ds-fs-1..6); radius var(--ds-radius); "
    "fonts var(--ds-font-sans) var(--ds-font-mono).\n"
    "  - NEVER write a raw hex/rgb/hsl colour or a non-token font-family — they are "
    "stripped. Prefer the spacing/type tokens over raw px (off-scale px is stripped).\n"
    "  - INLINE realization: put CSS in `css` using plain selectors (.grid, .card) "
    "— it is auto-scoped to this section. Put HTML in `html`. NO <script>, NO "
    "<style>, NO JS: inline sections are static; scroll/reveal animation is added "
    "by the site engine.\n"
    "  - ARTIFACT realization: put a self-contained interactive widget in "
    "html/css/js — JS is allowed and runs sandboxed in an iframe. Set `kind`.\n"
    "Do NOT repeat the section title as a heading — the page already renders it. "
    "Make distinct, well-designed sections; the shared tokens keep them coherent."
)


class _BuiltM(BaseModel):
    realization: str = "inline"            # inline | artifact
    html: str = ""
    css: str = ""
    js: str = ""                           # artifact only
    kind: str = ""                         # artifact only
    export_format: str = ""
    export_label: str = ""


def _build_agent(cfg: dict) -> Agent:
    site = cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "authored"),
                       site.get("fidelity", "synthesize"))
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    return Agent(
        model=build_model(cfg["ai"], role="builder"),
        instructions=instr,
        output_schema=_BuiltM,
        retries=cfg["ai"].get("retries", 2),
        pre_hooks=build_pre_hooks(cfg),
    )


def run_builder(spec: SectionSpec, section_html: str, cfg: dict):
    """Author one section. Returns an AuthoredSection (inline) or Artifact."""
    src = section_html or ""
    if len(src) > _MAX_INPUT:
        log.debug("builder %s: source %d chars capped to %d", spec.anchor,
                  len(src), _MAX_INPUT)
        src = src[:_MAX_INPUT]
    agent = _build_agent(cfg)
    prompt = (
        f"Section title: {spec.title}\n"
        f"Intent: {spec.intent or '(none given)'}\n"
        f"Realization: {spec.realization}\n"
        f"Layout: {spec.layout}\n"
        f"Components: {', '.join(spec.components) or '(choose what fits)'}\n\n"
        f"Source content (HTML — distil, do not paste verbatim):\n{src}\n\n"
        "Author this section now, obeying the design contract."
    )
    resp = invoke_agent(agent, prompt, role="builder", label=spec.anchor,
                        expect=_BuiltM, timeout=cfg["ai"].get("timeout"))
    m: _BuiltM = resp.content
    real = (m.realization or spec.realization or "inline").strip().lower()
    if real == "artifact":
        exp = (Export(format=m.export_format or "markdown", label=m.export_label)
               if m.export_label.strip() else None)
        log.info("builder %s: artifact (kind=%s)", spec.anchor, m.kind or spec.anchor)
        return Artifact(kind=m.kind or spec.anchor or "widget", title=spec.title,
                        html=sanitize_artifact_html(m.html), css=m.css, js=m.js,
                        export=exp)
    log.info("builder %s: inline (%d B html, %d B css)",
             spec.anchor, len(m.html), len(m.css))
    return AuthoredSection(anchor=spec.anchor, title=spec.title,
                           html=m.html, css=m.css)
