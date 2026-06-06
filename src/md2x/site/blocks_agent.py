"""AI block-authoring agent for `fidelity: synthesize`.

Authors a typed `PageDoc` from a document: the model may restructure the content
into the richer block vocabulary (hero, summary, KPIs, callouts, cards, timeline,
steps, tabs, table, quote, code, glossary). The renderer escapes every string, so
the model's output can never inject markup — it only chooses structure + text.

agno + pydantic are imported here only; this module is imported lazily from
blocks_render so `--no-ai` / non-synthesize paths never need the [ai] extra.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import (
    Artifact, Callout, Card, CardGrid, Code, Event, Export, Figure, Glossary,
    Hero, Kpi, KpiStrip, PageDoc, Prose, Quote, Section, Step, Steps, Summary,
    Tab, Table, Tabs, Term, Timeline, build_page_doc, figures_from_html,
)
from .guardrails import build_pre_hooks
from .models import build_model
from .report.blocks import split_sections
from .sanitize import sanitize_artifact_html
from .schemas import slugify
from .skill import load_skill

log = get_logger(__name__)

_MAX_BLOCKS = 24
_MAX_ITEMS = 12
_MAX_SECTION_BLOCKS = 12
_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")

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


def _build_agent(cfg: dict, artifacts=None) -> Agent:
    """One block-authoring agent, reused across a doc's sections."""
    ai, site = cfg["ai"], cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "blocks"),
                       site.get("fidelity", "synthesize"), artifacts=artifacts)
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    return Agent(
        model=build_model(ai, role="page"),
        instructions=instr,
        output_schema=_PageDocModel,
        retries=ai.get("retries", 2),
        pre_hooks=build_pre_hooks(cfg),
    )


def run_section_blocks(title: str, section_html: str, cfg: dict,
                       artifacts=None) -> list:
    """Restructure ONE section into blocks from its FULL html.

    Sections are small, so nothing is truncated and the model can focus on the
    real shape of that one section. Returns the section's child blocks (no hero,
    no page title — the page owns those).
    """
    agent = _build_agent(cfg, artifacts)
    prompt = (
        f"Section heading: {title}\n\n"
        "Restructure ONLY the section below into typed blocks. Do NOT emit a "
        "hero or repeat the section heading (the page renders it). Render the "
        "information in the shape it has — KPI strips for metrics, tables for "
        "tabular data, steps for procedures, timelines for chronology.\n\n"
        f"Section body (HTML):\n{section_html}"
    )
    t0 = time.perf_counter()
    resp = agent.run(prompt)
    log.debug("blocks section %r: responded in %.2fs", title,
              time.perf_counter() - t0)
    model: _PageDocModel = resp.content
    return [b for b in (_to_block(m) for m in model.blocks[:_MAX_SECTION_BLOCKS])
            if b is not None and not isinstance(b, Hero)]


def run_page_blocks(doc, cfg: dict, artifacts=None) -> PageDoc:
    """Author a PageDoc by enriching each H2 section independently and in
    parallel. Any section whose agent fails or returns nothing falls back to its
    verbatim HTML, so a document can never be amputated — worst case is the
    complete deterministic render.

    `artifacts` is the architect's per-page artifact selection, injected into the
    skill so each section's agent sees exactly those pattern templates.
    """
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    if not sections:                              # no H2 → deterministic whole-doc
        log.info("blocks agent: %s has no H2 sections; deterministic page", doc.slug)
        return build_page_doc(doc)

    log.info("blocks agent: %s -> %d section(s), enriching (concurrency=%s)",
             doc.slug, len(sections), cfg["ai"].get("concurrency", 4))

    def enrich(sec) -> Section:
        figs = figures_from_html(sec.html)
        try:
            kids = run_section_blocks(sec.title, sec.html, cfg, artifacts)
        except Exception as e:                    # one bad section never sinks the doc
            log.warning("blocks agent: section %r failed (%s); verbatim fallback",
                        sec.title, e)
            log.debug("blocks section %r failure", sec.title, exc_info=True)
            kids = []
        if not kids:                              # empty synth → keep author's HTML
            kids = [Prose(html=sec.html)] if sec.html else []
        else:
            kids.extend(figs)                     # land the section's rendered diagrams
        anchor = slugify(sec.title) if sec.title else f"section-{id(sec) & 0xffff}"
        return Section(title=sec.title, anchor=anchor, blocks=kids)

    workers = max(1, int(cfg["ai"].get("concurrency", 4) or 1))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        section_blocks = list(ex.map(enrich, sections))

    blocks: list = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    blocks.extend(section_blocks)
    log.info("blocks agent: %s assembled hero + %s intro + %d section(s)",
             doc.slug, "1" if intro_html else "0", len(section_blocks))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
