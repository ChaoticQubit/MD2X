"""The typed block vocabulary shared by every archetype in `blocks` mode.

A `PageDoc` is a flat list of typed blocks. `blocks_render.py` owns the block→DOM
mapping (so output is fully assertable and XSS-safe), and `build_page_doc` derives
a deterministic PageDoc from a Doc's verbatim fragment HTML (powers `--no-ai`,
`fidelity: preserve`, and the agent-failure fallback). The AI path that authors a
richer block tree at `fidelity: synthesize` lives in `blocks_agent.py`.

This module is pure data — no agno/pydantic — so it imports on the `--no-ai` path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Union

from .report.blocks import split_sections

# --- leaf records -----------------------------------------------------------


@dataclass
class Kpi:
    value: str
    label: str = ""


@dataclass
class Card:
    title: str
    body: str = ""
    href: str = ""


@dataclass
class Event:
    when: str
    title: str
    body: str = ""


@dataclass
class ChartPoint:
    label: str
    value: float


@dataclass
class Tab:
    label: str
    html: str


@dataclass
class Step:
    title: str
    body: str = ""


@dataclass
class Term:
    term: str
    definition: str


# --- block types ------------------------------------------------------------


@dataclass
class Hero:
    title: str
    subtitle: str = ""
    kicker: str = ""


@dataclass
class Summary:
    text: str


@dataclass
class Prose:
    """Author-verbatim HTML — the only never-escaped, never-sanitized block
    (it is the document's own trusted body)."""
    html: str


@dataclass
class KpiStrip:
    items: list[Kpi] = field(default_factory=list)


@dataclass
class Callout:
    text: str
    label: str = "Note"
    tone: str = "info"                     # info | warn | success


@dataclass
class CardGrid:
    cards: list[Card] = field(default_factory=list)


@dataclass
class Timeline:
    events: list[Event] = field(default_factory=list)


@dataclass
class Table:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Code:
    code: str
    lang: str = ""


@dataclass
class Quote:
    text: str
    cite: str = ""


@dataclass
class Figure:
    src: str
    caption: str = ""
    alt: str = ""


@dataclass
class Chart:
    kind: str                              # bar | line
    points: list[ChartPoint] = field(default_factory=list)


@dataclass
class Tabs:
    tabs: list[Tab] = field(default_factory=list)


@dataclass
class Collapsible:
    summary: str
    html: str
    open: bool = False


@dataclass
class Steps:
    steps: list[Step] = field(default_factory=list)


@dataclass
class DiagramSvg:
    svg: str                               # sanitized at render time


@dataclass
class Glossary:
    terms: list[Term] = field(default_factory=list)


@dataclass
class RawHtml:
    """Escape hatch — sanitized at render time. Use rarely."""
    html: str


Block = Union[
    Hero, Summary, Prose, KpiStrip, Callout, CardGrid, Timeline, Table, Code,
    Quote, Figure, Chart, Tabs, Collapsible, Steps, DiagramSvg, Glossary, RawHtml,
]

# Tuple form for isinstance dispatch in the renderer.
BLOCK_TYPES = (
    Hero, Summary, Prose, KpiStrip, Callout, CardGrid, Timeline, Table, Code,
    Quote, Figure, Chart, Tabs, Collapsible, Steps, DiagramSvg, Glossary, RawHtml,
)


@dataclass
class PageDoc:
    """One page as a typed block tree."""
    slug: str
    title: str
    blocks: list[Block] = field(default_factory=list)


_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")


def build_page_doc(doc) -> PageDoc:
    """Deterministic PageDoc from a Doc — no LLM. Prose stays verbatim.

    Hero(title) + one Prose per section (intro, then each H2 block). The leading
    H1 is dropped from the intro because the Hero already shows the title.
    """
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    blocks: list[Block] = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    for sec in sections:
        body = f"<h2>{sec.title}</h2>{sec.html}" if sec.title else sec.html
        blocks.append(Prose(html=body))
    if len(blocks) == 1:                   # no intro, no sections
        blocks.append(Prose(html=doc.fragment_html))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
