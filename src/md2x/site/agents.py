"""agno-backed agents: architect + page. The only module that imports
agno/pydantic. Outputs are converted to the shared dataclasses before returning,
so downstream code never sees pydantic. (The home/index page is built
deterministically by render.py from the architect's SitePlan — there is no
separate index agent.)

Verified against agno 2.6.11: Agent accepts output_schema=<PydanticModel> and
retries=N; agent.run(prompt) returns a RunOutput whose .content is the typed
object. If you upgrade agno and these move, change ONLY this file.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .archetypes import get_archetype, get_suggested_artifacts, resolve_layout
from .guardrails import build_pre_hooks
from .invoke import invoke_agent
from .models import build_model, is_openai_like
from .schemas import Doc, NavItem, SitePlan, PageEnhancement, DesignSystem
from .skill import load_skill

log = get_logger(__name__)


# ---- pydantic schemas the LLM fills (agno structured output) ---------------

class _NavItemModel(BaseModel):
    title: str
    slug: str
    group: str = ""
    # Architect per-page selection (PR-F).
    render_mode: str = Field(default="", description="blocks|hybrid|full override "
                             "for this page, or empty to use the site default.")
    artifacts: list[str] = Field(default_factory=list,
                                 description="Artifact pattern ids to use on this page.")


class _DesignSystemModel(BaseModel):
    accent: str = "#2563eb"
    bg: str = "#ffffff"
    fg: str = "#1f2328"
    muted: str = "#57606a"
    card: str = "#f6f8fa"
    border: str = "#d0d7de"
    radius: str = "8px"
    font_sans: str = Field(default=DesignSystem().font_sans)
    font_mono: str = Field(default=DesignSystem().font_mono)
    density: str = Field(default="comfortable",
                         description="comfortable | compact")


class _SitePlanModel(BaseModel):
    nav: list[_NavItemModel]
    order: list[str]
    index_title: str = "Documentation"
    index_intro: str = ""
    theme_accent: str = ""
    design: _DesignSystemModel = Field(default_factory=_DesignSystemModel)


class _EnhancementModel(BaseModel):
    tldr: str = Field(default="", description="One-sentence summary; may be empty.")
    takeaways: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list,
                               description="Slugs of related pages.")


# ---- converters ------------------------------------------------------------

def _to_site_plan(pm: _SitePlanModel) -> SitePlan:
    d = pm.design
    design = DesignSystem(
        accent=d.accent, bg=d.bg, fg=d.fg, muted=d.muted, card=d.card,
        border=d.border, radius=d.radius, font_sans=d.font_sans,
        font_mono=d.font_mono, density=d.density,
    )
    page_artifacts = {n.slug: list(n.artifacts) for n in pm.nav if n.artifacts}
    page_modes = {n.slug: n.render_mode.strip() for n in pm.nav if n.render_mode.strip()}
    return SitePlan(
        nav=[NavItem(title=n.title, slug=n.slug, group=n.group) for n in pm.nav],
        order=list(pm.order),
        index_title=pm.index_title or "Documentation",
        index_intro=pm.index_intro,
        theme_accent=pm.theme_accent,
        design=design,
        page_artifacts=page_artifacts,
        page_modes=page_modes,
    )


def _to_enhancement(em: _EnhancementModel) -> PageEnhancement:
    return PageEnhancement(tldr=em.tldr, takeaways=list(em.takeaways),
                           related=list(em.related))


# ---- agent construction ----------------------------------------------------

def _make_agent(cfg: dict, role: str, instructions: str, schema):
    ai = cfg["ai"]
    retries = ai.get("retries", 2)
    log.debug("building %s agent (retries=%d, schema=%s)",
              role, retries, schema.__name__)
    log.debug("%s instructions:\n%s", role, instructions)
    return Agent(
        model=build_model(ai, role=role),
        instructions=instructions,
        output_schema=schema,
        retries=retries,
        # local endpoints ignore native response_format -> inject schema into prompt
        use_json_mode=is_openai_like(ai, role),
        pre_hooks=build_pre_hooks(cfg),
    )


def _outline_digest(docs: list[Doc]) -> str:
    lines = []
    for d in docs:
        lines.append(f"- slug={d.slug!r} title={d.title!r} "
                     f"sections={d.outline}")
    return "\n".join(lines)


# ---- public runners --------------------------------------------------------

def run_architect(docs: list[Doc], cfg: dict) -> SitePlan:
    site = cfg["site"]
    arch = get_archetype(site["archetype"])
    layout = resolve_layout(site["layout"], site["archetype"])
    skill = load_skill(site["archetype"],
                       site.get("render_mode", "blocks"),
                       site.get("fidelity", "light-enhance"))
    instr = (
        (skill + "\n\n---\n\n" if skill else "")
        + arch["architect_instructions"]
        + (f"\n\nUser style brief: {site['style_prompt']}"
           if site.get("style_prompt") else "")
        + f"\n\nTarget layout: {layout}."
        + "\n\nAlso emit a DesignSystem (palette + radius + density) that fits the "
          "content and style brief; it becomes the site's --ds-* design tokens."
        + "\n\nFor each page you may set render_mode (blocks|hybrid|full) and pick "
          "the artifact patterns that fit it, drawn from this archetype's suggested "
          f"set: {get_suggested_artifacts(site['archetype']) or 'none'}."
        + "\n\nUse exactly the given slugs. Output a complete SitePlan."
    )
    agent = _make_agent(cfg, "architect", instr, _SitePlanModel)
    prompt = ("Plan a website for these documents:\n"
              + _outline_digest(docs))
    log.info("architect: running over %d doc(s) (archetype=%s, layout=%s)",
             len(docs), site["archetype"], layout)
    log.debug("architect prompt (%d chars):\n%s", len(prompt), prompt)
    resp = invoke_agent(agent, prompt, role="architect", label=site["archetype"],
                        expect=_SitePlanModel, timeout=cfg["ai"].get("timeout"))
    log.debug("architect raw response: %r", resp.content)
    return _to_site_plan(resp.content)


def run_page(doc: Doc, plan: SitePlan, cfg: dict) -> PageEnhancement:
    """Light-enhance only — additive blocks. Never rewrites the body."""
    if cfg["site"]["fidelity"] == "preserve":
        log.debug("page %s: fidelity=preserve; skipping agent", doc.slug)
        return PageEnhancement()
    arch = get_archetype(cfg["site"]["archetype"])
    other = ", ".join(f"{n.slug} ({n.title})" for n in plan.nav
                      if n.slug != doc.slug) or "(none)"
    skill = load_skill(cfg["site"]["archetype"],
                       cfg["site"].get("render_mode", "blocks"),
                       cfg["site"].get("fidelity", "light-enhance"))
    instr = (
        (skill + "\n\n---\n\n" if skill else "")
        + arch["page_instructions"]
        + "\n\nProduce ONLY additive aids: a one-sentence TL;DR, up to 4 key "
          "takeaways, and slugs of related pages. Do NOT rewrite or quote the "
          "body. Leave fields empty if nothing adds value."
        + f"\n\nOther pages you may relate to: {other}."
    )
    agent = _make_agent(cfg, "page", instr, _EnhancementModel)
    prompt = (f"Page '{doc.title}' (slug {doc.slug}). Section headings: "
              f"{doc.outline}. Body HTML:\n{doc.fragment_html[:6000]}")
    log.info("page-enhance %s: body %d chars (truncated to 6000 for the prompt)",
             doc.slug, len(doc.fragment_html))
    log.debug("page %s prompt (%d chars):\n%s", doc.slug, len(prompt), prompt)
    resp = invoke_agent(agent, prompt, role="page-enhance", label=doc.slug,
                        expect=_EnhancementModel, timeout=cfg["ai"].get("timeout"))
    log.debug("page %s raw response: %r", doc.slug, resp.content)
    enh = _to_enhancement(resp.content)
    log.info("page %s: tldr=%s, %d takeaway(s), %d related",
             doc.slug, bool(enh.tldr), len(enh.takeaways), len(enh.related))
    return enh
