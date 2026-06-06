"""Full-mode author agent: emits one self-contained interactive HTML document.

The model authors the whole page (max fidelity). The render layer
(full_render.render_full_page) then injects the CSP + design tokens and strips
external references, so even a free-form document stays locked down and on-brand.

agno + pydantic are imported here only; this module is imported lazily from
full_render so `--no-ai` / `fidelity: preserve` never need the [ai] extra.
"""
from __future__ import annotations

import html as _html
import re
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import Export
from .full_render import FullPage
from .guardrails import build_pre_hooks
from .models import build_model
from .report.blocks import split_sections
from .schemas import slugify
from .skill import load_skill

log = get_logger(__name__)

_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")

_SYSTEM = (
    "You author ONE self-contained, interactive HTML fragment for a single "
    "section of a page — render the information in the shape it actually has "
    "(diagrams, live widgets, clickable steps, editors), not a wall of prose.\n"
    "HARD CONSTRAINTS — follow exactly:\n"
    "  - Output a FRAGMENT, not a full document: no <html>, <head>, <body>, or "
    "<title>. Do not repeat the section heading (the page renders it).\n"
    "  - Self-contained: inline any CSS/JS. NO external network — no CDN, no "
    "remote fonts, no <script src>, no <link href>, no fetch/XHR.\n"
    "  - Consume the design tokens: style with the injected --ds-* variables "
    "(var(--ds-accent), var(--ds-fg), var(--ds-space-2), ...) so it is on-brand.\n"
    "  - Scope any CSS to this section (prefer a wrapper class / specific "
    "selectors) so sections do not collide.\n"
    "  - Faithful: use ONLY facts present in the source; never invent figures.\n"
    "Return the section HTML fragment in `html`."
)


class _FullPageModel(BaseModel):
    html: str = Field(default="", description="The self-contained HTML fragment for this section.")
    title: str = ""
    export_format: str = Field(default="", description="markdown|json|text if this is an editor.")
    export_label: str = Field(default="", description="Export button label if this is an editor.")


def _build_agent(cfg: dict, artifacts=None) -> Agent:
    ai, site = cfg["ai"], cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "full"),
                       site.get("fidelity", "synthesize"), artifacts=artifacts)
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    return Agent(
        model=build_model(ai, role="page"),
        instructions=instr,
        output_schema=_FullPageModel,
        retries=ai.get("retries", 2),
        pre_hooks=build_pre_hooks(cfg),
    )


def run_full_section(title: str, section_html: str, cfg: dict,
                     artifacts=None) -> str:
    """Author ONE section's self-contained HTML fragment from its FULL html.

    Small input → no truncation. Returns the fragment string (empty on no output;
    the caller then falls back to the section's verbatim HTML)."""
    agent = _build_agent(cfg, artifacts)
    prompt = (f"Section heading: {title}\n\n"
              "Author the self-contained interactive HTML fragment for ONLY this "
              f"section:\n{section_html}")
    t0 = time.perf_counter()
    resp = agent.run(prompt)
    log.debug("full section %r: responded in %.2fs", title,
              time.perf_counter() - t0)
    return (getattr(resp.content, "html", "") or "").strip()


def run_full_page(doc, cfg: dict, artifacts=None) -> FullPage:
    """Author a standalone page section-by-section, in parallel. Each H2 becomes
    an anchored <section>; a section whose author fails or returns nothing falls
    back to its verbatim HTML, so the document is never amputated."""
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    if not sections:
        log.info("full agent: %s has no H2 sections; deterministic page", doc.slug)
        from .full_render import _deterministic_page
        return _deterministic_page(doc)

    log.info("full agent: %s -> %d section(s), authoring (concurrency=%s)",
             doc.slug, len(sections), cfg["ai"].get("concurrency", 4))

    def author(sec) -> str:
        try:
            frag = run_full_section(sec.title, sec.html, cfg, artifacts)
        except Exception as e:
            log.warning("full agent: section %r failed (%s); verbatim fallback",
                        sec.title, e)
            log.debug("full section %r failure", sec.title, exc_info=True)
            frag = ""
        if not frag:
            frag = sec.html                      # author's verbatim HTML
        anchor = slugify(sec.title) if sec.title else f"section-{id(sec) & 0xffff}"
        heading = (f'<h2 class="b-section-h">{_html.escape(sec.title)}</h2>'
                   if sec.title else "")
        return (f'<section id="{anchor}" class="b-section">{heading}{frag}</section>')

    workers = max(1, int(cfg["ai"].get("concurrency", 4) or 1))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        rendered = list(ex.map(author, sections))

    intro = f'<div class="intro">{intro_html}</div>' if intro_html else ""
    body = (f'<main style="max-width:880px;margin:0 auto;padding:40px 24px;'
            f'font-family:var(--ds-font-sans,system-ui);color:var(--ds-fg,#1f2328)">'
            f'<h1>{_html.escape(doc.title)}</h1>{intro}{"".join(rendered)}</main>')
    log.info("full agent: %s assembled %d section(s)", doc.slug, len(rendered))
    return FullPage(html=body, title=doc.title)
