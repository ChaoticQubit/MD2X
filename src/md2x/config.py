"""Configuration: built-in defaults, deep merge, YAML loader."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from .paths import PROJECT_ROOT


DEFAULTS: dict[str, Any] = {
    "output": {
        "toc": True,
        "toc_depth": 2,
        "format": None,  # null = infer from output extension (defaults to pdf)
        "number_sections": False,
        "citation_processing": False,
    },
    "page": {
        "margin": "0.85in",
        "fontsize": "10.5pt",
        "paper": "letter",
        "orientation": "portrait",
        "line_spacing": 1.15,
    },
    "fonts": {
        # null = let xelatex use Computer Modern (always present, no fontspec
        # lookup, no system-font dependency). Override in md2x.yaml.
        "main": None,
        "sans": None,
        "mono": None,
        "cjk": None,
    },
    "colors": {
        "link": "NavyBlue",
        "url": "NavyBlue",
        "toc": "NavyBlue",
        "heading": None,
    },
    "code": {
        "highlight_style": "tango",
        "line_numbers": False,
    },
    "images": {
        "width": "6.2in",
        "caption_prefix": "Figure",
        "show_captions": True,
        "dpi": 120,
        "mmdc_width": 1600,
        "mmdc_height": 1100,
    },
    "mermaid": {
        "theme": "default",
        "background": "white",
        "prefer": "auto",
        "on_failure": "keep_source",
    },
    "binaries": {
        "pandoc": None,
        "xelatex": None,
        "mmdc": None,
        "dot": None,
    },
    "advanced": {
        "header_includes": [
            r"\usepackage{float}",
            r"\floatplacement{figure}{H}",
            r"\usepackage[export]{adjustbox}",
            r"\usepackage{microtype}",
            r"\usepackage{booktabs}",
        ],
        "pandoc_extra_args": [],
        "keep_intermediate": False,
        "emit_manifest": False,
        "no_clobber": False,
    },
    "site": {
        "title": None,               # site/index title; None -> "Documentation"
        "layout": "auto",            # auto | multi-page | single-page
        "archetype": "reading",      # reading|presentation|flyer|product|docs|report|custom
        "style_prompt": "",
        "fidelity": "light-enhance", # preserve | light-enhance
        "theme": {"accent": "#2563eb", "dark_mode": True},
        "features": ["search", "animations", "smooth-scroll"],
        "recursive": True,
    },
    "ai": {
        # `md2x site` runs two agents: the ARCHITECT (plans the whole site once)
        # and the PER-PAGE agent (adds TL;DR/takeaways per doc). See md2x.yaml
        # for the long-form explanation of every key below.
        "model": "anthropic:claude-sonnet-4-6",  # default model for both agents
        "architect_model": None,  # override model for the architect (null=model)
        "page_model": None,       # override model for the per-page agent
        "temperature": 0.4,       # sampling randomness; lower = steadier output
        "max_tokens": None,       # cap on tokens per reply (null = provider default)
        "concurrency": 4,         # parallel per-page agent calls
        "retries": 2,             # agno retries on invalid structured output
    },
    "deploy": {
        "provider": "vercel",
        "token_env": "VERCEL_TOKEN",
        "project": None,
        "team_id": None,
        "production": True,
    },
}


def deep_merge(base: dict, over: dict) -> dict:
    """Recursive dict merge — values in `over` win, missing keys preserved.

    The result shares no mutable substructure with `base`, so callers (e.g.
    apply_cli_overrides) can mutate it without corrupting the shared DEFAULTS.
    """
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(explicit: Path | None, md_path: Path) -> dict:
    """
    Load YAML configuration from disk (searching several candidate locations) and merge it with built-in defaults.
    
    Parameters:
        explicit (Path | None): An explicit config file path to try first. If None, the explicit candidate is skipped.
        md_path (Path): Path to the Markdown file; its parent directory is searched for local `md2x.yaml`/`md2x.yml` files.
    
    Returns:
        dict: Configuration dictionary produced by deep-merging the built-in DEFAULTS with any YAML data found (YAML values override defaults). If no valid YAML is found, returns a copy of DEFAULTS.
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    candidates += [
        md_path.parent / "md2x.yaml",
        md_path.parent / "md2x.yml",
        PROJECT_ROOT / "md2x.yaml",
        PROJECT_ROOT / "md2x.yml",
    ]
    for p in candidates:
        if p and p.exists():
            try:
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                print(f"[md2x] using config {p}")
                return deep_merge(DEFAULTS, data)
            except ImportError:
                sys.stderr.write(f"WARN: PyYAML missing — skipping {p}\n")
                break
            except Exception as e:
                sys.stderr.write(f"WARN: failed to parse {p}: {e}\n")
                break
    print("[md2x] using built-in defaults (no YAML found)")
    return deep_merge(DEFAULTS, {})
