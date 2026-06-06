"""Bundled 'living site' skill: Markdown files composed into agent instructions.

load_skill() reads the relevant files for a given (archetype, render_mode,
fidelity, artifacts) and returns one instruction string injected into the
architect/page agents every run. Pure-Python (no agno/pydantic), so it imports on
the --no-ai path. Per-archetype and per-artifact files are added in later PRs;
their absence is skipped gracefully.
"""
from __future__ import annotations

from importlib.resources import files

from ...log import get_logger

log = get_logger(__name__)

# Always included, in this order.
_CORE = ("SKILL.md", "principles.md", "design-system.md", "export-contract.md")


def _read(rel: str) -> str | None:
    """Read a bundled skill file by package-relative path, or None if absent."""
    try:
        return (files("md2x.site.skill") / rel).read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, OSError):
        return None


def load_skill(archetype: str, render_mode: str = "blocks",
               fidelity: str = "light-enhance",
               artifacts: list[str] | None = None) -> str:
    """Compose the skill for one (archetype, render_mode, fidelity, artifacts).

    Returns a single instruction string. Missing optional files (render-mode,
    archetype, artifacts not yet authored) are skipped and logged at DEBUG.
    """
    parts: list[str] = []
    sources: list[str] = []

    def add(rel: str, *, optional: bool) -> None:
        txt = _read(rel)
        if txt:
            parts.append(txt.strip())
            sources.append(rel)
        elif optional:
            log.debug("skill: optional file missing, skipped: %s", rel)

    for name in _CORE:
        add(name, optional=False)
    add(f"render-modes/{render_mode}.md", optional=True)
    add(f"archetypes/{archetype}.md", optional=True)
    for art in (artifacts or []):
        add(f"artifacts/{art}.md", optional=True)

    composed = "\n\n---\n\n".join(parts)
    log.debug("skill: composed %d chars from %d source(s): %s",
              len(composed), len(sources), ", ".join(sources))
    return composed
