"""The intermediate representation between the designer and builder agents.

A `DesignTree` is the per-page output of the section-designer: an ordered list of
`SectionSpec`, each describing WHAT a section should be (its realization, layout,
and component hints) — not yet its HTML. The section-builder turns one spec into a
real `AuthoredSection` or `Artifact`. Pure data — no agno — so it imports anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SectionSpec:
    anchor: str
    title: str
    intent: str = ""                       # 1-line: what this section must convey
    realization: str = "inline"            # inline | artifact
    layout: str = "stack"                  # stack | grid | split | feature | table-led
    components: list[str] = field(default_factory=list)   # hints e.g. "table:sortable"
    source_anchors: list[str] = field(default_factory=list)  # doc H2(s) it draws from


@dataclass
class DesignTree:
    slug: str
    sections: list[SectionSpec] = field(default_factory=list)
