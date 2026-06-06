"""Report archetype (AI site v2 thin slice).

Transforms a Markdown report into an editorial-dashboard page — hero + dek,
synthesized executive summary, an extracted KPI stat-strip, key-finding
callouts, then the author's sections (prose verbatim). This is the first
archetype to use the v2 "blocks" model; others follow in the full PR3.

Public surface (package-root exports):
  - ReportPage / Stat / Callout / Section  — the typed block model
  - build_report_page(doc)                 — deterministic builder (--no-ai / fallback)
  - render_report(page, accent)            — editorial-dashboard HTML
  - generate_report_site(...)              — orchestrates build + render + write

The AI builder run_report_page(doc, cfg) lives in the .agent submodule and is
imported lazily (it needs agno / the [ai] extra), so it is intentionally NOT a
package-root export — importing this package must keep working without agno.
"""
from __future__ import annotations

from .blocks import (
    Callout,
    ReportPage,
    Section,
    Stat,
    build_report_page,
)
from .render import generate_report_site, render_report

__all__ = [
    "Callout",
    "ReportPage",
    "Section",
    "Stat",
    "build_report_page",
    "render_report",
    "generate_report_site",
]
