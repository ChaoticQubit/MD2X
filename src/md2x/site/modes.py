"""The two prose-independent site axes, validated.

render_mode = HOW html is produced: blocks | hybrid | full.
fidelity    = how much the AI may rewrite prose: preserve | light-enhance | synthesize.
Both are orthogonal to the archetype. Unknown values warn and fall back to the
default rather than crash (consistent with the unsafe-accent fallback).
"""
from __future__ import annotations

from ..log import get_logger

log = get_logger(__name__)

RENDER_MODES = ("blocks", "hybrid", "full", "authored")
DEFAULT_RENDER_MODE = "blocks"
FIDELITIES = ("preserve", "light-enhance", "synthesize")
DEFAULT_FIDELITY = "light-enhance"


def validate_render_mode(mode: str) -> str:
    if mode in RENDER_MODES:
        return mode
    log.warning("unknown render_mode %r; using %r (choose from %s)",
                mode, DEFAULT_RENDER_MODE, ", ".join(RENDER_MODES))
    return DEFAULT_RENDER_MODE


def validate_fidelity(fidelity: str) -> str:
    if fidelity in FIDELITIES:
        return fidelity
    log.warning("unknown fidelity %r; using %r (choose from %s)",
                fidelity, DEFAULT_FIDELITY, ", ".join(FIDELITIES))
    return DEFAULT_FIDELITY
