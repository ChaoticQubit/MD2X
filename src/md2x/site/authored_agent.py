"""Authored-mode page orchestrator: designer -> parallel builders -> assemble.

Mirrors `blocks_agent.run_page_blocks` but for `render_mode: authored`. One
per-page designer call produces a DesignTree; each section is then built in
parallel into an AuthoredSection (inline) or Artifact (iframe). Every failure
degrades — designer failure mirrors the source H2s, a builder failure falls back
to the typed blocks render, then to condensed verbatim — so a document is never
amputated; worst case equals the deterministic render.

agno is reached only through the lazily-imported designer/builder, so this module
is itself import-safe; it is imported lazily from blocks_render's authored branch.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from ..log import get_logger
from .blocks import (AuthoredSection, Hero, PageDoc, Prose, Section,
                     build_page_doc, figures_from_html)
from .design_tree import DesignTree, SectionSpec
from .report.blocks import split_sections
from .schemas import slugify
from .section_builder import run_builder
from .section_designer import run_designer

log = get_logger(__name__)

_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")


def _source_anchor(title: str, idx: int) -> str:
    return slugify(title) if title else f"section-{idx + 1}"


def _fallback_tree(doc, sections) -> DesignTree:
    """Designer-failure fallback: one inline section per source H2, 1:1."""
    specs = []
    for i, s in enumerate(sections):
        a = _source_anchor(s.title, i)
        specs.append(SectionSpec(anchor=a, title=s.title or a.replace("-", " "),
                                 source_anchors=[a]))
    return DesignTree(slug=doc.slug, sections=specs)


def _section_fallback(spec: SectionSpec, src_html: str, cfg: dict) -> Section:
    """Builder-failure fallback for one section: typed blocks render, else
    condensed verbatim. Re-appends the section's rendered diagrams (parity with
    blocks mode) so a synthesized section never silently drops its images."""
    from .blocks_agent import run_section_blocks, _condensed_fallback
    figs = figures_from_html(src_html)
    try:
        kids = run_section_blocks(spec.title, src_html, cfg)
    except Exception as e:
        log.warning("authored: typed fallback for %r failed (%s); condensed",
                    spec.anchor, e)
        kids = []
    if kids:
        kids.extend(figs)
    else:
        kids = _condensed_fallback(src_html)        # verbatim already carries images
    return Section(title=spec.title, anchor=spec.anchor, blocks=kids)


def run_authored_page(doc, cfg: dict, plan=None) -> PageDoc:
    """Author a PageDoc for one document in authored mode."""
    intro_html, sections = split_sections(doc.fragment_html)
    intro_html = _H1_RE.sub("", intro_html).strip()
    if not sections:                                # no H2 -> deterministic whole-doc
        log.info("authored: %s has no H2 sections; deterministic page", doc.slug)
        return build_page_doc(doc)

    # 1. design the website's sections (per page); fall back to mirroring the source.
    try:
        tree = run_designer(doc, cfg)
    except Exception as e:
        log.warning("authored: designer failed for %s (%s); mirroring source sections",
                    doc.slug, e)
        log.debug("authored designer %s failure", doc.slug, exc_info=True)
        tree = _fallback_tree(doc, sections)
    if not tree.sections:
        tree = _fallback_tree(doc, sections)

    # 2. map each spec to its source HTML (by anchor, else positional).
    by_anchor = {_source_anchor(s.title, i): s.html for i, s in enumerate(sections)}
    src_order = [s.html for s in sections]

    def source_for(spec: SectionSpec, idx: int) -> str:
        for a in (spec.source_anchors or [spec.anchor]):
            if a in by_anchor:
                return by_anchor[a]
        return src_order[idx] if idx < len(src_order) else ""

    # 3. build each section in parallel; a failure degrades, never amputates.
    def build(item):
        idx, spec = item
        src = source_for(spec, idx)
        try:
            blk = run_builder(spec, src, cfg)
        except Exception as e:
            log.warning("authored: builder failed for %r (%s); typed fallback",
                        spec.anchor, e)
            log.debug("authored builder %r failure", spec.anchor, exc_info=True)
            return [_section_fallback(spec, src, cfg)]
        out = [blk]
        if isinstance(blk, AuthoredSection):        # keep diagrams the author dropped
            html = blk.html or ""
            out.extend(f for f in figures_from_html(src) if f.src and f.src not in html)
        return out

    workers = max(1, int(cfg["ai"].get("concurrency", 4) or 1))
    log.info("authored: %s -> building %d section(s) (concurrency=%s)",
             doc.slug, len(tree.sections), workers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        nested = list(ex.map(build, list(enumerate(tree.sections))))
    built = [b for sub in nested for b in sub]

    # 4. assemble: hero + optional intro + the authored sections.
    blocks = [Hero(title=doc.title)]
    if intro_html:
        blocks.append(Prose(html=intro_html))
    blocks.extend(built)
    log.info("authored: %s assembled hero + %s intro + %d block(s)",
             doc.slug, "1" if intro_html else "0", len(built))
    return PageDoc(slug=doc.slug, title=doc.title, blocks=blocks)
