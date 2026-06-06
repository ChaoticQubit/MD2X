"""argparse wiring + runner for the `md2x site` subcommand."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from ..config import load_config
from ..log import get_logger
from .archetypes import ARCHETYPE_NAMES, resolve_layout
from .modes import FIDELITIES, RENDER_MODES
from .pipeline import generate_site

log = get_logger(__name__)


def add_site_subparser(sub, parents=()) -> None:
    sp = sub.add_parser("site", parents=list(parents),
                        help="Generate an AI website from Markdown files")
    sp.add_argument("inputs", nargs="+", type=Path,
                    help="Markdown files and/or directories")
    sp.add_argument("-o", "--out-dir", type=Path, default=Path("site"),
                    help="Output directory (default: ./site)")
    sp.add_argument("--archetype", default=None, choices=list(ARCHETYPE_NAMES))
    sp.add_argument("--render-mode", default=None, choices=list(RENDER_MODES),
                    help="How HTML is produced: blocks | hybrid | full")
    sp.add_argument("--layout", default=None,
                    choices=["auto", "multi-page", "single-page"])
    sp.add_argument("--style", default=None, help="Free-text style nudge")
    sp.add_argument("--fidelity", default=None, choices=list(FIDELITIES),
                    help="How much the AI may rewrite prose")
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
    if args.render_mode is not None:
        cfg["site"]["render_mode"] = args.render_mode
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
    log.info("site: archetype=%s layout=%s fidelity=%s ai=%s -> %s",
             cfg["site"]["archetype"], layout, cfg["site"]["fidelity"],
             "off" if args.no_ai else "on", args.out_dir)
    rc = generate_site(args.inputs, args.out_dir, cfg,
                       use_ai=not args.no_ai, layout=layout)
    if rc != 0:
        log.error("site generation failed (exit %d)", rc)
        return rc

    if args.deploy:
        from .deploy import deploy
        cfg["deploy"]["provider"] = args.deploy
        log.info("deploying via %s", args.deploy)
        try:
            url = deploy(args.out_dir, cfg)
            log.info("deployed: %s", url)
        except Exception as e:
            log.error("deploy failed: %s", e)
            log.debug("deploy traceback", exc_info=True)
            return 1

    if args.open_after:
        index = args.out_dir / "index.html"
        if index.exists():
            log.info("opening %s in browser", index)
            webbrowser.open(index.resolve().as_uri())
        else:
            log.warning("--open given but %s does not exist", index)
    return 0
