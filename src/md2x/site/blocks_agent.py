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
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .blocks import (
    Artifact, Callout, Card, CardGrid, Code, Collapsible, Event, Export, Figure,
    Glossary, Hero, Kpi, KpiStrip, PageDoc, Prose, Quote, Section, Step, Steps,
    Summary, Tab, Table, Tabs, Term, Timeline, build_page_doc, figures_from_html,
)
from .guardrails import build_pre_hooks
from .invoke import invoke_agent
from .models import build_model
from .report.blocks import split_sections
from .sanitize import sanitize_artifact_html
from .schemas import slugify
from .skill import load_skill

log = get_logger(__name__)

_MAX_BLOCKS = 24
_MAX_ITEMS = 12
_MAX_SECTION_BLOCKS = 10
_MAX_SECTION_INPUT = 10000        # cap a section's input so huge ones don't time out
_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")

_SYSTEM = (
    "You are an information designer. Turn ONE section of a long document into a "
    "tight, scannable web module that a busy reader grasps at a glance. DISTILL "
    "HARD — the source is far too long; your output must be a small fraction of "
    "it. The reader wants the meaning fast, not the original wording.\n"
    "RULES — follow exactly:\n"
    "  - Open with ONE `summary` block: a single full sentence stating the "
    "section's most important point — a real takeaway, not a label or the topic "
    "name — <=25 words. Always first.\n"
    "  - Then show only the essentials, in the shape the facts actually have: "
    "`kpi_strip` for metrics/numbers, `table` for comparisons or rows of data, "
    "`steps` for a procedure, `timeline` for chronology, `card_grid` for "
    "parallel items, `callout` for the single critical insight or warning. Pick "
    "the few that fit; skip the rest.\n"
    "  - Cut ruthlessly: no narrative, no preamble, no restating the heading. "
    "Favour short labelled items over sentences. Use `prose` only when nothing "
    "else fits, and keep each prose block under ~40 words.\n"
    "  - Whole-section budget: aim for <=120 words of text in total.\n"
    "  - Stay faithful to the facts: compress and rephrase freely, but never "
    "invent a figure, name, or claim. You may drop detail; you may not add it.\n"
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
    """Distil ONE section into a short, glance-able block tree from its html.

    Returns the section's child blocks (no hero, no page title — the page owns
    those). An oversized section is capped to `_MAX_SECTION_INPUT` so one long
    section can't stall the run; a glance summary only needs the gist.
    """
    if len(section_html) > _MAX_SECTION_INPUT:
        log.debug("blocks section %r: input %d chars capped to %d for distillation",
                  title, len(section_html), _MAX_SECTION_INPUT)
        section_html = section_html[:_MAX_SECTION_INPUT]
    agent = _build_agent(cfg, artifacts)
    prompt = (
        f"Section heading: {title}\n\n"
        "Distil ONLY the section below into a glance-able module. Start with a "
        "<=25-word `summary` that states the key point as a full sentence (not a "
        "label), then the essential facts as the tightest blocks "
        "that fit (kpi_strip / table / steps / timeline / card_grid / callout). "
        "Cut everything non-essential — aim for <=120 words of text total. Do "
        "NOT emit a hero or repeat the heading.\n\n"
        f"Section body (HTML):\n{section_html}"
    )
    resp = invoke_agent(agent, prompt, role="blocks-section", label=title,
                        expect=_PageDocModel, timeout=cfg["ai"].get("timeout"))
    model: _PageDocModel = resp.content
    return [b for b in (_to_block(m) for m in model.blocks[:_MAX_SECTION_BLOCKS])
            if b is not None and not isinstance(b, Hero)]


def _condensed_fallback(section_html: str) -> list:
    """Glance-able degradation when a section can't be synthesised: show the
    first paragraph, tuck the remainder behind a collapsible. A lead plus a
    "show full section" toggle beats dumping the whole verbatim body inline."""
    section_html = (section_html or "").strip()
    if not section_html:
        return []
    if len(section_html) < 700:                   # already short — show as-is
        return [Prose(html=section_html)]
    m = re.search(r"(?is)<p\b.*?</p>", section_html)
    if not m:
        return [Prose(html=section_html)]
    lead, rest = m.group(0), section_html[:m.start()] + section_html[m.end():]
    out: list = [Prose(html=lead)]
    if rest.strip():
        out.append(Collapsible(summary="Show full section", html=rest))
    return out


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
            log.warning("blocks agent: section %r failed (%s); condensed fallback",
                        sec.title, e)
            log.debug("blocks section %r failure", sec.title, exc_info=True)
            kids = []
        if not kids:                              # synth failed/empty → glance-able fallback
            kids = _condensed_fallback(sec.html)  # verbatim already carries diagrams
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
