"""Minimal .env loader (zero dependencies).

Reads simple ``KEY=VALUE`` lines so secrets (LLM API keys, deploy tokens) can
live in a ``.env`` file instead of being exported by hand. The real process
environment always wins — a variable already present in ``os.environ`` is never
overwritten — so ``.env`` is a fallback only. This matches python-dotenv's
default behaviour without adding a dependency.
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path


def _parse(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines, skipping blanks and ``#`` comments.

    Supports an optional leading ``export`` and one layer of matching single or
    double quotes around the value. Inline comments are NOT stripped, so values
    may safely contain ``#`` (API keys sometimes do).
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        out[key] = val
    return out


def load_dotenv(paths: Iterable[Path | str]) -> list[Path]:
    """Load each existing path into ``os.environ`` without overriding real env.

    Pre-existing variables (real environment or an earlier file in ``paths``)
    take precedence — values are applied with ``setdefault``. Returns the list
    of files actually read.
    """
    loaded: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            continue
        rp = p.resolve()
        if rp in seen:          # cwd and project root may be the same dir
            continue
        seen.add(rp)
        try:
            data = _parse(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        for k, v in data.items():
            os.environ.setdefault(k, v)
        loaded.append(p)
    return loaded


def load_default_env() -> list[Path]:
    """Load ``.env`` from the current directory, then the project root.

    The current directory is read first, so a project-local ``.env`` overrides
    the repo-root one; both lose to a variable already set in the environment.
    """
    from .paths import PROJECT_ROOT

    return load_dotenv([Path.cwd() / ".env", PROJECT_ROOT / ".env"])
