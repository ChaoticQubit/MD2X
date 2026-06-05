"""argparse wiring + runner for the `md2x site` subcommand."""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from ..config import load_config
from .archetypes import resolve_layout
from .pipeline import generate_site


def add_site_subparser(sub) -> None:
    sp = sub.add_parser("site", help="Generate an AI website from Markdown files")
    sp.add_argument("inputs", nargs="+", type=Path,
                    help="Markdown files and/or directories")
    sp.add_argument("-o", "--out-dir", type=Path, default=Path("site"),
                    help="Output directory (default: ./site)")
    sp.add_argument("--archetype", default=None,
                    choices=["reading", "presentation", "flyer", "product",
                             "docs", "report", "custom"])
    sp.add_argument("--layout", default=None,
                    choices=["auto", "multi-page", "single-page"])
    sp.add_argument("--style", default=None, help="Free-text style nudge")
    sp.add_argument("--fidelity", default=None,
                    choices=["preserve", "light-enhance"])
    sp.add_argument("--model", default=None, help="Override ai.model")
    sp.add_argument("--no-ai", action="store_true",
                    help="Deterministic templates; no LLM/network")
    sp.add_argument("--deploy", default=None, choices=["vercel"])
    sp.add_argument("--open", dest="open_after", action="store_true",
                    help="Open the index in a browser")
    sp.add_argument("-c", "--config", type=Path, default=None)
    sp.set_defaults(func=run_site)


def _apply_site_overrides(cfg: dict, args) -> None:
    if args.archetype is not None:
        cfg["site"]["archetype"] = args.archetype
    if args.layout is not None:
        cfg["site"]["layout"] = args.layout
    if args.style is not None:
        cfg["site"]["style_prompt"] = args.style
    if args.fidelity is not None:
        cfg["site"]["fidelity"] = args.fidelity
    if args.model is not None:
        cfg["ai"]["model"] = args.model


def run_site(args) -> int:
    first = Path(args.inputs[0])
    anchor = first if first.is_file() else (first / "_")
    cfg = load_config(args.config, anchor)
    _apply_site_overrides(cfg, args)

    layout = resolve_layout(cfg["site"]["layout"], cfg["site"]["archetype"])
    rc = generate_site(args.inputs, args.out_dir, cfg,
                       use_ai=not args.no_ai, layout=layout)
    if rc != 0:
        return rc

    if args.deploy:
        from .deploy import deploy
        cfg["deploy"]["provider"] = args.deploy
        try:
            url = deploy(args.out_dir, cfg)
            print(f"[md2x site] deployed: {url}")
        except Exception as e:
            sys.stderr.write(f"ERROR: deploy failed: {e}\n")
            return 1

    if args.open_after:
        index = args.out_dir / "index.html"
        if index.exists():
            webbrowser.open(index.resolve().as_uri())
    return 0
