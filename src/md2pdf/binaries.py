"""Resolve an executable across the local install layout, then PATH."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .paths import LOCAL_BIN, LOCAL_TOOLS, LOCAL_NPM_BIN


def resolve_binary(name: str, override: str | None = None) -> str | None:
    """Find an executable. Search order:
       explicit override → .bin/ → .tools/**/bin/ → node_modules/.bin/ → PATH.
    """
    if override:
        p = Path(override).expanduser()
        return str(p) if p.exists() else None
    candidate = LOCAL_BIN / name
    if candidate.exists():
        return str(candidate)
    candidate = LOCAL_NPM_BIN / name
    if candidate.exists():
        return str(candidate)
    if LOCAL_TOOLS.exists():
        for sub in LOCAL_TOOLS.rglob(f"bin/{name}"):
            if sub.is_file() and os.access(sub, os.X_OK):
                return str(sub)
    return shutil.which(name)
