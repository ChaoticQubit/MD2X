"""Shared site data types — plain dataclasses, no external dependencies.

Used by both the AI path and the deterministic --no-ai path. The agno-backed
agents (agents.py) convert their pydantic outputs into these before returning,
so everything downstream consumes only these types.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "page"


@dataclass
class Doc:
    """One source Markdown file converted to a faithful HTML fragment."""
    path: Path
    title: str
    outline: list[str]
    fragment_html: str

    @property
    def slug(self) -> str:
        return slugify(self.path.stem)


@dataclass
class NavItem:
    title: str
    slug: str
    group: str = ""


@dataclass
class SitePlan:
    """The architect's plan for the whole site."""
    nav: list[NavItem]
    order: list[str]                       # slugs in render order
    index_title: str = "Documentation"
    index_intro: str = ""
    theme_accent: str = ""                 # "" = use config theme.accent


@dataclass
class PageEnhancement:
    """Additive, never-destructive extras for one page (light-enhance mode)."""
    tldr: str = ""
    takeaways: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)   # slugs
