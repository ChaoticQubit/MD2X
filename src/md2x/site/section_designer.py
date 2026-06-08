"""Per-page section-designer agent (authored mode).

Sees the whole document's sections at once and emits a `DesignTree`: the ordered
set of website sections, each with a realization, layout, and component hints. It
may merge/split/reorder and add a hero/overview — coherence decisions that need
the whole page in view, which is why this is one call per page (not per section).

agno + pydantic are imported here only; imported lazily from authored_agent so the
`--no-ai` path never needs the [ai] extra.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field
from agno.agent import Agent

from ..log import get_logger
from .design_tree import DesignTree, SectionSpec
from .guardrails import build_pre_hooks
from .invoke import invoke_agent
from .models import build_model, is_openai_like
from .report.blocks import split_sections
from .schemas import slugify
from .skill import load_skill

log = get_logger(__name__)

_TAG = re.compile(r"(?is)<[^>]+>")
_WS = re.compile(r"\s+")
_MAX_SECTIONS = 24

_SYSTEM = (
    "You are an information architect designing a single, scannable web page from "
    "a long document. You are given the document's sections (heading + a short "
    "preview). Design the WEBSITE's sections: keep them 1:1, or merge related "
    "ones, split an overloaded one, reorder for impact, and you MAY add a short "
    "hero/overview at the top. For EACH website section choose:\n"
    "  - realization: 'inline' for normal content (text, tables, cards, steps, "
    "charts) — DEFAULT. 'artifact' ONLY when it genuinely needs custom "
    "interactivity (a draggable board, a live calculator, a tunable widget).\n"
    "  - layout: one of stack | grid | split | feature | table-led — the visual "
    "shape that fits the content.\n"
    "  - components: short builder hints, e.g. 'table:sortable,search', "
    "'cards:links,cols=3', 'kpis', 'steps', 'timeline', 'callout', 'chart:bar'.\n"
    "  - source_anchors: the heading slug(s) this section draws from.\n"
    "Stay faithful to the source — do not invent sections with no basis. Aim for a "
    "tight page a busy reader grasps at a glance."
)


class _SpecM(BaseModel):
    anchor: str = ""
    title: str = ""
    intent: str = ""
    realization: str = "inline"
    layout: str = "stack"
    components: list[str] = Field(default_factory=list)
    source_anchors: list[str] = Field(default_factory=list)


class _TreeM(BaseModel):
    sections: list[_SpecM] = Field(default_factory=list)


def _preview(html: str, n: int = 180) -> str:
    text = _WS.sub(" ", _TAG.sub(" ", html or "")).strip()
    return text[:n]


def _build_agent(cfg: dict) -> Agent:
    site = cfg["site"]
    skill = load_skill(site["archetype"], site.get("render_mode", "authored"),
                       site.get("fidelity", "synthesize"))
    instr = (skill + "\n\n---\n\n" if skill else "") + _SYSTEM
    return Agent(
        model=build_model(cfg["ai"], role="designer"),
        instructions=instr,
        output_schema=_TreeM,
        retries=cfg["ai"].get("retries", 2),
        use_json_mode=is_openai_like(cfg["ai"], "designer"),
        pre_hooks=build_pre_hooks(cfg),
    )


def _to_tree(slug: str, m: _TreeM, fallback_titles: list[str]) -> DesignTree:
    out: list[SectionSpec] = []
    for s in m.sections[:_MAX_SECTIONS]:
        title = (s.title or "").strip()
        if not title:
            continue
        anchor = slugify(s.anchor) if s.anchor.strip() else slugify(title)
        out.append(SectionSpec(
            anchor=anchor, title=title, intent=s.intent.strip(),
            realization=(s.realization or "inline").strip().lower(),
            layout=(s.layout or "stack").strip().lower(),
            components=[c for c in s.components if c and c.strip()],
            source_anchors=[slugify(a) for a in s.source_anchors if a and a.strip()],
        ))
    if not out:                                   # model returned nothing usable
        out = [SectionSpec(anchor=slugify(t), title=t, source_anchors=[slugify(t)])
               for t in fallback_titles]
        return DesignTree(slug=slug, sections=out)

    # Coverage guardrail: the designer MAY merge, split, or reorder sections, but
    # it must not silently DROP one — a heading the reader expects (e.g.
    # "Certifications") vanishing from the site is a content bug, not a design
    # choice. A source heading counts as covered when some spec lists it in
    # source_anchors, or when a spec's own anchor is that heading's slug. Append a
    # 1:1 section, in source order, for any heading nothing covers.
    covered: set[str] = set()
    for spec in out:
        covered.add(spec.anchor)
        covered.update(spec.source_anchors)
    appended = 0
    for title in fallback_titles:
        sl = slugify(title)
        if sl in covered:
            continue
        out.append(SectionSpec(anchor=sl, title=title, source_anchors=[sl]))
        covered.add(sl)
        appended += 1
    if appended:
        log.info("designer: %s -> appended %d uncovered source section(s) "
                 "(coverage guardrail)", slug, appended)
    return DesignTree(slug=slug, sections=out)


def run_designer(doc, cfg: dict) -> DesignTree:
    """Design the website's sections for one document. Returns a DesignTree; the
    caller maps each spec to its source section and builds it."""
    _intro, sections = split_sections(doc.fragment_html)
    titles = [s.title for s in sections if s.title]
    digest = "\n".join(f"- {s.title} (slug: {slugify(s.title)}): {_preview(s.html)}"
                       for s in sections if s.title) or "(no sub-sections)"
    agent = _build_agent(cfg)
    prompt = (
        f"Document title: {doc.title}\n\n"
        f"Document sections (heading (slug): preview):\n{digest}\n\n"
        "Design the website's sections now. Use the given slugs in source_anchors."
    )
    log.info("designer: %s -> planning from %d source section(s)",
             doc.slug, len(titles))
    resp = invoke_agent(agent, prompt, role="designer", label=doc.slug,
                        expect=_TreeM, timeout=cfg["ai"].get("timeout"))
    tree = _to_tree(doc.slug, resp.content, titles)
    log.info("designer: %s -> %d website section(s) (%d artifact)",
             doc.slug, len(tree.sections),
             sum(1 for s in tree.sections if s.realization == "artifact"))
    return tree
