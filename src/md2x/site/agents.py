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

from .archetypes import get_archetype, resolve_layout
from .models import build_model
from .schemas import Doc, NavItem, SitePlan, PageEnhancement


# ---- pydantic schemas the LLM fills (agno structured output) ---------------

class _NavItemModel(BaseModel):
    title: str
    slug: str
    group: str = ""


class _SitePlanModel(BaseModel):
    nav: list[_NavItemModel]
    order: list[str]
    index_title: str = "Documentation"
    index_intro: str = ""
    theme_accent: str = ""


class _EnhancementModel(BaseModel):
    tldr: str = Field(default="", description="One-sentence summary; may be empty.")
    takeaways: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list,
                               description="Slugs of related pages.")


# ---- converters ------------------------------------------------------------

def _to_site_plan(pm: _SitePlanModel) -> SitePlan:
    return SitePlan(
        nav=[NavItem(title=n.title, slug=n.slug, group=n.group) for n in pm.nav],
        order=list(pm.order),
        index_title=pm.index_title or "Documentation",
        index_intro=pm.index_intro,
        theme_accent=pm.theme_accent,
    )


def _to_enhancement(em: _EnhancementModel) -> PageEnhancement:
    return PageEnhancement(tldr=em.tldr, takeaways=list(em.takeaways),
                           related=list(em.related))


# ---- agent construction ----------------------------------------------------

def _make_agent(cfg: dict, role: str, instructions: str, schema):
    ai = cfg["ai"]
    return Agent(
        model=build_model(ai, role=role),
        instructions=instructions,
        output_schema=schema,
        retries=ai.get("retries", 2),
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
    instr = (
        arch["architect_instructions"]
        + (f"\n\nUser style brief: {site['style_prompt']}"
           if site.get("style_prompt") else "")
        + f"\n\nTarget layout: {layout}."
        + "\n\nUse exactly the given slugs. Output a complete SitePlan."
    )
    agent = _make_agent(cfg, "architect", instr, _SitePlanModel)
    prompt = ("Plan a website for these documents:\n"
              + _outline_digest(docs))
    resp = agent.run(prompt)
    return _to_site_plan(resp.content)


def run_page(doc: Doc, plan: SitePlan, cfg: dict) -> PageEnhancement:
    """Light-enhance only — additive blocks. Never rewrites the body."""
    if cfg["site"]["fidelity"] == "preserve":
        return PageEnhancement()
    arch = get_archetype(cfg["site"]["archetype"])
    other = ", ".join(f"{n.slug} ({n.title})" for n in plan.nav
                      if n.slug != doc.slug) or "(none)"
    instr = (
        arch["page_instructions"]
        + "\n\nProduce ONLY additive aids: a one-sentence TL;DR, up to 4 key "
          "takeaways, and slugs of related pages. Do NOT rewrite or quote the "
          "body. Leave fields empty if nothing adds value."
        + f"\n\nOther pages you may relate to: {other}."
    )
    agent = _make_agent(cfg, "page", instr, _EnhancementModel)
    prompt = (f"Page '{doc.title}' (slug {doc.slug}). Section headings: "
              f"{doc.outline}. Body HTML:\n{doc.fragment_html[:6000]}")
    resp = agent.run(prompt)
    return _to_enhancement(resp.content)
