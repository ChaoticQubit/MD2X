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
from .schemas import slugify

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


@dataclass
class Export:
    """Round-trip contract for an editor artifact (Thariq: every editor ends in
    an export button)."""
    format: str = "markdown"               # markdown | json | text
    label: str = "Copy"


@dataclass
class Artifact:
    """A self-contained interactive widget mounted in a sandboxed, CSP-locked
    iframe (hybrid mode). Its html/css/js are isolated — the blast radius is the
    iframe. When it is an editor, `export` wires the md2x:export round-trip."""
    kind: str                              # e.g. triage-board, prompt-tuner, chart
    title: str = ""
    html: str = ""
    css: str = ""
    js: str = ""
    export: "Export | None" = None


@dataclass
class Section:
    """A titled, anchored group of child blocks — one H2 region. Renders a
    <section id=anchor> with an <h2>, so the sidebar can deep-link to it and the
    document is navigable instead of one undifferentiated scroll."""
    title: str
    anchor: str
    blocks: list["Block"] = field(default_factory=list)


@dataclass
class AuthoredSection:
    """A section whose inner HTML + CSS the AI authored directly (authored mode).
    The renderer scopes+lints the CSS to `#<anchor>` and sanitizes the HTML, so it
    is safe to inline in the main document. Carries no JS — JS lives in Artifact."""
    anchor: str
    title: str
    html: str = ""
    css: str = ""


Block = Union[
    Hero, Summary, Prose, KpiStrip, Callout, CardGrid, Timeline, Table, Code,
    Quote, Figure, Chart, Tabs, Collapsible, Steps, DiagramSvg, Glossary, RawHtml,
    Artifact, Section, AuthoredSection,
]

# Tuple form for isinstance dispatch in the renderer.
BLOCK_TYPES = (
    Hero, Summary, Prose, KpiStrip, Callout, CardGrid, Timeline, Table, Code,
    Quote, Figure, Chart, Tabs, Collapsible, Steps, DiagramSvg, Glossary, RawHtml,
    Artifact, Section, AuthoredSection,
)


@dataclass
class PageDoc:
    """One page as a typed block tree."""
    slug: str
    title: str
    blocks: list[Block] = field(default_factory=list)


_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")
_IMG_RE = re.compile(r'(?is)<img\b[^>]*\bsrc=["\'](?P<src>[^"\']+)["\'][^>]*>')
_ALT_RE = re.compile(r'(?is)\balt=["\'](?P<alt>[^"\']*)["\']')


def figures_from_html(html_fragment: str) -> list[Figure]:
    """Pull LOCAL <img> (rendered diagrams) out of a fragment as Figure blocks.

    The synthesize path turns prose into plain-text blocks, which would drop a
    section's rendered diagrams; surfacing them as Figure blocks lands them back
    in their section. Remote/data srcs are skipped — the renderer refuses them.
    """
    out: list[Figure] = []
    for m in _IMG_RE.finditer(html_fragment or ""):
        src = m.group("src").strip()
        if re.match(r"(?i)^(https?:|data:|javascript:|//)", src):
            continue
        alt_m = _ALT_RE.search(m.group(0))
        out.append(Figure(src=src, alt=alt_m.group("alt") if alt_m else ""))
    return out


def build_page_doc(doc) -> PageDoc:
    """Deterministic PageDoc from a Doc — no LLM. Prose stays verbatim.

    Hero(title) + intro Prose + one anchored Section per H2 (verbatim body, so
    every section's tables, lists, and rendered diagrams are preserved). This is
    the complete baseline: --no-ai, fidelity: preserve, and the per-section
    agent-failure fallback all rest on it, so a document is never amputated.
    """
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    blocks: list[Block] = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    for i, sec in enumerate(sections):
        anchor = slugify(sec.title) if sec.title else f"section-{i + 1}"
        blocks.append(Section(title=sec.title, anchor=anchor,
                              blocks=[Prose(html=sec.html)] if sec.html else []))
    if len(blocks) == 1:                   # no intro, no sections
        blocks.append(Prose(html=doc.fragment_html))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
