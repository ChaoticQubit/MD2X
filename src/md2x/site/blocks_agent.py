"""AI block-authoring agent for `fidelity: synthesize`.

Authors a typed `PageDoc` from a document: the model may restructure the content
into the richer block vocabulary (hero, summary, KPIs, callouts, cards, timeline,
steps, tabs, table, quote, code, glossary). The renderer escapes every string, so
the model's output can never inject markup — it only chooses structure + text.

agno + pydantic are imported here only; this module is imported lazily from
blocks_render so `--no-ai` / non-synthesize paths never need the [ai] extra.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import (
    Artifact, Callout, Card, CardGrid, Code, Event, Export, Glossary, Hero, Kpi,
    KpiStrip, PageDoc, Prose, Quote, Step, Steps, Summary, Tab, Table, Tabs,
    Term, Timeline, build_page_doc,
)
from .guardrails import build_pre_hooks
from .models import build_model
from .sanitize import sanitize_artifact_html
from .skill import load_skill

log = get_logger(__name__)

_MAX_BLOCKS = 24
_MAX_ITEMS = 12

_SYSTEM = (
    "You restructure a Markdown document into a typed block tree for a polished, "
    "scannable web page. Render information in the shape it actually has: use KPI "
    "strips for metrics, timelines for chronology, steps for procedures, tables "
    "for tabular data, callouts for warnings, tabs for parallel variants.\n"
    "GUARDRAILS — follow exactly:\n"
    "  - Use ONLY facts present in the source; never invent figures or claims.\n"
    "  - Open with one `hero` (the title). Keep prose faithful to the author.\n"
    "  - Prefer specific blocks over walls of `prose`, but do not fabricate "
    "structure the content does not support.\n"
    "  - Plain text in every field — no HTML, no Markdown."
)


class _KpiM(BaseModel):
    value: str = ""
    label: str = ""


class _CardM(BaseModel):
    title: str = ""
    body: str = ""
    href: str = ""


class _EventM(BaseModel):
    when: str = ""
    title: str = ""
    body: str = ""


class _StepM(BaseModel):
    title: str = ""
    body: str = ""


class _TabM(BaseModel):
    label: str = ""
    text: str = ""


class _TermM(BaseModel):
    term: str = ""
    definition: str = ""


class _BlockM(BaseModel):
    type: str = Field(description="hero|summary|prose|callout|kpi_strip|card_grid|"
                                  "timeline|steps|tabs|table|quote|code|glossary|"
                                  "artifact (artifact only in hybrid mode)")
    title: str = ""
    subtitle: str = ""
    kicker: str = ""
    text: str = ""
    label: str = "Note"
    tone: str = "info"
    cite: str = ""
    code: str = ""
    lang: str = ""
    items: list[_KpiM] = Field(default_factory=list)
    cards: list[_CardM] = Field(default_factory=list)
    events: list[_EventM] = Field(default_factory=list)
    steps: list[_StepM] = Field(default_factory=list)
    tabs: list[_TabM] = Field(default_factory=list)
    terms: list[_TermM] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    # artifact fields (hybrid): a self-contained interactive widget.
    kind: str = ""
    html: str = ""
    css: str = ""
    js: str = ""
    export_format: str = ""
    export_label: str = ""


class _PageDocModel(BaseModel):
    blocks: list[_BlockM] = Field(default_factory=list)


def _to_block(m: _BlockM):
    t = (m.type or "").strip().lower()
    if t == "hero":
        return Hero(title=m.title, subtitle=m.subtitle, kicker=m.kicker)
    if t == "summary":
        return Summary(text=m.text) if m.text.strip() else None
    if t == "prose":
        # The model emits plain text; wrap as an escaped paragraph so the verbatim
        # Prose path never carries model markup.
        import html as _h
        return Prose(html=f"<p>{_h.escape(m.text)}</p>") if m.text.strip() else None
    if t == "callout":
        return Callout(text=m.text, label=m.label or "Note", tone=m.tone or "info")
    if t == "kpi_strip":
        return KpiStrip(items=[Kpi(value=k.value, label=k.label)
                               for k in m.items[:_MAX_ITEMS] if k.value.strip()])
    if t == "card_grid":
        return CardGrid(cards=[Card(title=c.title, body=c.body, href=c.href)
                               for c in m.cards[:_MAX_ITEMS] if c.title.strip()])
    if t == "timeline":
        return Timeline(events=[Event(when=e.when, title=e.title, body=e.body)
                                for e in m.events[:_MAX_ITEMS] if e.title.strip()])
    if t == "steps":
        return Steps(steps=[Step(title=s.title, body=s.body)
                            for s in m.steps[:_MAX_ITEMS] if s.title.strip()])
    if t == "tabs":
        import html as _h
        return Tabs(tabs=[Tab(label=tb.label, html=f"<p>{_h.escape(tb.text)}</p>")
                          for tb in m.tabs[:_MAX_ITEMS] if tb.label.strip()])
    if t == "table":
        return Table(headers=list(m.headers),
                     rows=[list(r) for r in m.rows[:_MAX_ITEMS * 4]])
    if t == "quote":
        return Quote(text=m.text, cite=m.cite)
    if t == "code":
        return Code(code=m.code, lang=m.lang)
    if t == "glossary":
        return Glossary(terms=[Term(term=g.term, definition=g.definition)
                               for g in m.terms[:_MAX_ITEMS] if g.term.strip()])
    if t == "artifact":
        exp = (Export(format=m.export_format or "markdown", label=m.export_label)
               if m.export_label.strip() else None)
        return Artifact(kind=m.kind or "widget", title=m.title,
                        html=sanitize_artifact_html(m.html), css=m.css, js=m.js,
                        export=exp)
    log.warning("blocks agent: unknown block type %r; dropped", m.type)
    return None


def run_page_blocks(doc, cfg: dict, artifacts=None) -> PageDoc:
    """Author a PageDoc with the LLM. Falls back to deterministic if empty.

    `artifacts` is the architect's per-page artifact selection; it is injected
    into the skill so the agent sees exactly those pattern templates.
    """
    ai = cfg["ai"]
    site = cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "blocks"),
                       site.get("fidelity", "synthesize"), artifacts=artifacts)
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    agent = Agent(
        model=build_model(ai, role="page"),
        instructions=instr,
        output_schema=_PageDocModel,
        retries=ai.get("retries", 2),
        pre_hooks=build_pre_hooks(cfg),
    )
    body = doc.fragment_html[:8000]
    prompt = (f"Document title: {doc.title}\nSection headings: {doc.outline}\n\n"
              f"Document body (HTML):\n{body}")
    log.info("blocks agent: authoring %s (%d body chars)",
             doc.slug, len(doc.fragment_html))
    log.debug("blocks %s prompt (%d chars):\n%s", doc.slug, len(prompt), prompt)
    t0 = time.perf_counter()
    resp = agent.run(prompt)
    log.debug("blocks %s: responded in %.2fs", doc.slug, time.perf_counter() - t0)
    log.debug("blocks %s raw response: %r", doc.slug, resp.content)
    metrics = getattr(resp, "metrics", None)
    if metrics is not None:
        log.debug("blocks %s token usage: %s", doc.slug, metrics)

    model: _PageDocModel = resp.content
    blocks = [b for b in (_to_block(m) for m in model.blocks[:_MAX_BLOCKS])
              if b is not None]
    if not blocks:
        log.warning("blocks agent: %s produced no blocks; deterministic fallback",
                    doc.slug)
        return build_page_doc(doc)
    # Guarantee a hero leads the page.
    if not blocks or not isinstance(blocks[0], Hero):
        blocks.insert(0, Hero(title=doc.title))
    log.info("blocks agent: %s -> %d block(s)", doc.slug, len(blocks))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
