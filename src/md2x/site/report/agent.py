"""AI builder for the report archetype.

Starts from the deterministic ReportPage (sections = author's verbatim HTML) and
overrides only the *synthesized top-matter*: a hero dek, an executive summary,
the KPI stat strip, and key-finding callouts. The author's prose is never
rewritten — synthesis is additive, top-of-page framing.

agno + pydantic are imported here only; this module is imported lazily so
`--no-ai` and non-report archetypes never need the [ai] extra.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field
from agno.agent import Agent

from ...log import get_logger
from ..guardrails import build_pre_hooks
from ..models import build_model
from .blocks import Callout, ReportPage, Stat, build_report_page

log = get_logger(__name__)

# Guardrail ceilings (also re-enforced below regardless of what the model returns).
_MAX_STATS = 4
_MAX_FINDINGS = 3
_MAX_SUMMARY = 600
_MAX_DEK = 200

_SYSTEM = (
    "You turn a Markdown report into the top of a polished, scannable web "
    "report page. You produce ONLY framing that helps a busy reader grasp the "
    "report fast:\n"
    "  • dek: one punchy sentence (<25 words) capturing the report's thrust.\n"
    "  • summary: a 2-4 sentence executive summary in your own words.\n"
    "  • stats: up to 4 headline KPIs literally present in the text "
    "(value + short label), e.g. {value:'+20%', label:'revenue'}.\n"
    "  • findings: up to 3 key takeaways, one short sentence each.\n\n"
    "GUARDRAILS — follow exactly:\n"
    "  - Use ONLY facts, numbers, and claims present in the source. Never "
    "invent figures or conclusions. If a field has no support, leave it empty.\n"
    "  - Do NOT restate the whole report; this is a summary layer above the "
    "author's sections, which are shown verbatim below your output.\n"
    "  - Stats must be real numbers from the text, not estimates.\n"
    "  - Plain text only — no Markdown, no HTML."
)


class _StatModel(BaseModel):
    value: str = Field(description="The metric as written, e.g. '+20%' or '$1.4M'.")
    label: str = Field(description="Short label, e.g. 'revenue'.")


class _ReportTopModel(BaseModel):
    dek: str = Field(default="", description="One-sentence hero subtitle.")
    summary: str = Field(default="", description="2-4 sentence executive summary.")
    stats: list[_StatModel] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list,
                                description="Up to 3 key takeaways, one sentence each.")


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def run_report_page(doc, cfg: dict) -> ReportPage:
    """AI ReportPage: deterministic skeleton + synthesized top-matter."""
    page = build_report_page(doc)  # sections (verbatim) + deterministic fallbacks

    if cfg["site"].get("fidelity") == "preserve":
        log.debug("report %s: fidelity=preserve; keeping deterministic page", doc.slug)
        return page

    ai = cfg["ai"]
    agent = Agent(
        model=build_model(ai, role="page"),
        instructions=_SYSTEM,
        output_schema=_ReportTopModel,
        retries=ai.get("retries", 2),
        pre_hooks=build_pre_hooks(cfg),
    )
    body = doc.fragment_html[:8000]
    prompt = (f"Report title: {doc.title}\nSection headings: {doc.outline}\n\n"
              f"Report body (HTML):\n{body}")
    log.info("report agent: synthesizing top-matter for %s (%d body chars)",
             doc.slug, len(doc.fragment_html))
    log.debug("report %s prompt (%d chars):\n%s", doc.slug, len(prompt), prompt)
    t0 = time.perf_counter()
    resp = agent.run(prompt)
    log.debug("report %s: responded in %.2fs", doc.slug, time.perf_counter() - t0)
    log.debug("report %s raw response: %r", doc.slug, resp.content)
    metrics = getattr(resp, "metrics", None)
    if metrics is not None:
        log.debug("report %s token usage: %s", doc.slug, metrics)

    top: _ReportTopModel = resp.content
    return _merge(page, top, doc.slug)


def _merge(page: ReportPage, top: _ReportTopModel, slug: str) -> ReportPage:
    """Apply guardrails and overlay the AI top-matter onto the page."""
    if top.dek.strip():
        page.dek = _clip(top.dek, _MAX_DEK)
    if top.summary.strip():
        page.summary = _clip(top.summary, _MAX_SUMMARY)

    stats = [Stat(value=s.value.strip(), label=s.label.strip())
             for s in top.stats if s.value.strip()][:_MAX_STATS]
    if stats:
        page.stats = stats  # else keep deterministic extraction

    page.findings = [Callout(text=_clip(f, 200))
                     for f in top.findings if f.strip()][:_MAX_FINDINGS]

    log.info("report %s: dek=%s summary=%s stats=%d findings=%d",
             slug, bool(page.dek), bool(page.summary),
             len(page.stats), len(page.findings))
    return page
