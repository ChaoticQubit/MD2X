"""Full-mode author agent: emits one self-contained interactive HTML document.

The model authors the whole page (max fidelity). The render layer
(full_render.render_full_page) then injects the CSP + design tokens and strips
external references, so even a free-form document stays locked down and on-brand.

agno + pydantic are imported here only; this module is imported lazily from
full_render so `--no-ai` / `fidelity: preserve` never need the [ai] extra.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import Export
from .full_render import FullPage
from .models import build_model
from .skill import load_skill

log = get_logger(__name__)

_SYSTEM = (
    "You author ONE self-contained, interactive HTML document for this page — "
    "render the information in the shape it actually has (diagrams, live widgets, "
    "clickable steps, editors), not a wall of prose.\n"
    "HARD CONSTRAINTS — follow exactly:\n"
    "  - Self-contained: inline ALL CSS and JS. NO external network — no CDN, no "
    "remote fonts, no <script src>, no <link href>, no fetch/XHR. It must work "
    "fully offline as a single file.\n"
    "  - Consume the design tokens: style with the injected --ds-* variables "
    "(var(--ds-accent), var(--ds-fg), var(--ds-space-2), ...) so the page is on-brand.\n"
    "  - Faithful: use ONLY facts present in the source; never invent figures or claims.\n"
    "  - If the page is an editor, end it with an export button that implements the "
    "export contract: on 'md2x:request-export' postMessage to the parent "
    "{type:'md2x:export', format, payload} (set export_label/export_format).\n"
    "Return the full HTML document in `html`."
)


class _FullPageModel(BaseModel):
    html: str = Field(default="", description="The complete self-contained HTML document.")
    title: str = ""
    export_format: str = Field(default="", description="markdown|json|text if this is an editor.")
    export_label: str = Field(default="", description="Export button label if this is an editor.")


def run_full_page(doc, cfg: dict, artifacts=None) -> FullPage:
    """Author a standalone HTML page with the LLM.

    `artifacts` is the architect's per-page artifact selection, injected into the
    skill so the author sees those pattern templates.
    """
    ai = cfg["ai"]
    site = cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "full"),
                       site.get("fidelity", "synthesize"), artifacts=artifacts)
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    agent = Agent(
        model=build_model(ai, role="page"),
        instructions=instr,
        output_schema=_FullPageModel,
        retries=ai.get("retries", 2),
    )
    body = doc.fragment_html[:8000]
    prompt = (f"Document title: {doc.title}\nSection headings: {doc.outline}\n\n"
              f"Document body (HTML):\n{body}")
    log.info("full agent: authoring %s (%d body chars)", doc.slug, len(doc.fragment_html))
    log.debug("full %s prompt (%d chars):\n%s", doc.slug, len(prompt), prompt)
    t0 = time.perf_counter()
    resp = agent.run(prompt)
    log.debug("full %s: responded in %.2fs", doc.slug, time.perf_counter() - t0)
    log.debug("full %s raw response (%d chars)", doc.slug,
              len(getattr(resp.content, "html", "") or ""))
    metrics = getattr(resp, "metrics", None)
    if metrics is not None:
        log.debug("full %s token usage: %s", doc.slug, metrics)

    model: _FullPageModel = resp.content
    export = (Export(format=model.export_format or "markdown", label=model.export_label)
              if model.export_label.strip() else None)
    html = model.html or ""
    if not html.strip():
        log.warning("full agent: %s returned empty html; deterministic fallback", doc.slug)
        from .full_render import _deterministic_page
        return _deterministic_page(doc)
    log.info("full agent: %s -> %d char document, export=%s",
             doc.slug, len(html), bool(export))
    return FullPage(html=html, title=model.title or doc.title, export=export)
