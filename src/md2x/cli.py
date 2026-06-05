"""md2x CLI — argument parsing and entry point.

Convert Markdown (with Mermaid blocks) to PDF, DOCX, HTML, EPUB, or LaTeX.

Self-contained workflow:
  1. Loads YAML config (md2x.yaml next to the input or in the project root).
  2. Resolves every binary (pandoc, xelatex, mmdc, dot) from the local
     install layout produced by install.sh, falling back to PATH:
       PROJECT/.bin/<name>
       PROJECT/.tools/.../bin/<name>
       PROJECT/node_modules/.bin/<name>
       <system PATH>
  3. Renders each ```mermaid``` block to PNG via mmdc (preferred) or dot
     (fallback for flowchart/graph syntax only).
  4. Rewrites the markdown, embedding each diagram as a captioned figure
     sized to fit one printed page.
  5. Hands the rewritten document to pandoc + xelatex.

CLI flags override YAML; YAML overrides built-in defaults.

Usage:
    ./md2x.py INPUT.md [-o OUTPUT.pdf] [--config md2x.yaml]
                          [--toc-depth N] [--no-toc]
                          [--margin 0.85in] [--fontsize 10.5pt]
                          [--theme default|forest|dark|neutral]
                          [--keep-intermediate]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .dotenv import load_default_env
from .log import get_logger, setup_logging
from .pipeline import build
from .formats import detect_target
from .paths import ensure_venv_yaml
from .site.cli import add_site_subparser


def apply_cli_overrides(cfg: dict, args: argparse.Namespace) -> dict:
    """
    Apply command-line argument overrides to a loaded configuration dictionary.
    
    This updates cfg in place according to provided CLI flags:
    - --no-toc sets cfg["output"]["toc"] = False
    - --toc-depth sets cfg["output"]["toc_depth"]
    - --margin sets cfg["page"]["margin"]
    - --fontsize sets cfg["page"]["fontsize"]
    - --keep-intermediate sets cfg["advanced"]["keep_intermediate"] = True
    - --theme sets cfg["mermaid"]["theme"]
    
    Parameters:
        cfg (dict): Configuration dictionary loaded from YAML to be modified.
        args (argparse.Namespace): Parsed CLI arguments containing override values.
    
    Returns:
        dict: The same configuration dictionary with applied overrides.
    """
    if args.no_toc:
        cfg["output"]["toc"] = False
    if args.toc_depth is not None:
        cfg["output"]["toc_depth"] = args.toc_depth
    if args.margin is not None:
        cfg["page"]["margin"] = args.margin
    if args.fontsize is not None:
        cfg["page"]["fontsize"] = args.fontsize
    if args.keep_intermediate:
        cfg["advanced"]["keep_intermediate"] = True
    if args.theme is not None:
        cfg["mermaid"]["theme"] = args.theme
    return cfg


KNOWN_SUBCMDS = {"convert", "site"}


def logging_parent_parser() -> argparse.ArgumentParser:
    """Shared logging flags, attached to every subcommand via ``parents=``."""
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("logging")
    g.add_argument("-v", "--verbose", action="count", default=0,
                   help="More logs (-v = DEBUG: prompts, responses, timings)")
    g.add_argument("--quiet", action="store_true",
                   help="Only warnings and errors")
    g.add_argument("--log-level", default=None,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Explicit level (overrides -v/--quiet and "
                        "MD2X_LOG_LEVEL)")
    g.add_argument("--log-file", type=Path, default=None,
                   help="Also write a full DEBUG trace to this file")
    return p


def _normalize_argv(argv: list[str]) -> list[str]:
    """Back-compat: route bare invocations to the `convert` subcommand.

    `md2x doc.md`, `md2x --check`, `md2x doc.md --to docx` all keep working.
    Top-level help (`-h`/`--help`) and an empty argv are left untouched so the
    top parser can show the subcommand list.

    Note: a file literally named `site` or `convert` must be run as
    `md2x convert site` to avoid being read as a subcommand.
    """
    if not argv:
        return argv
    if argv[0] in ("-h", "--help"):
        return argv
    if argv[0] in KNOWN_SUBCMDS:
        return argv
    return ["convert", *argv]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="md2x",
        description="Convert Markdown to documents, or generate an AI website.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    logp = logging_parent_parser()

    cv = sub.add_parser("convert", parents=[logp],
                        help="Convert one Markdown file to PDF/DOCX/HTML/EPUB/LaTeX")
    cv.add_argument("input", nargs="?", type=Path, default=None,
                    help="Path to source .md")
    cv.add_argument("-o", "--output", type=Path, default=None,
                    help="Output file path; format inferred from its extension")
    cv.add_argument("-c", "--config", type=Path, default=None,
                    help="Explicit YAML config file")
    cv.add_argument("-t", "--to", default=None,
                    choices=["pdf", "docx", "html", "epub", "latex"],
                    help="Output format")
    cv.add_argument("--no-toc", action="store_true", help="Disable ToC")
    cv.add_argument("--toc-depth", type=int, default=None,
                    help="Heading depth for ToC")
    cv.add_argument("--margin", default=None, help="Page margin (e.g. 0.85in)")
    cv.add_argument("--fontsize", default=None, help="Body font size (e.g. 10.5pt)")
    cv.add_argument("--theme", default=None,
                    choices=["default", "forest", "dark", "neutral"],
                    help="Mermaid theme")
    cv.add_argument("--keep-intermediate", action="store_true",
                    help="Don't delete the intermediate .md")
    cv.add_argument("--check", action="store_true",
                    help="Print resolved binary paths and exit")
    cv.set_defaults(func=run_convert)

    add_site_subparser(sub, parents=[logp])
    return ap


def run_convert(args: argparse.Namespace) -> int:
    if args.check:
        from .binaries import resolve_binary
        for n in ("pandoc", "xelatex", "mmdc", "dot"):
            print(f"  {n:8s} {resolve_binary(n) or 'MISSING'}")
        return 0
    if args.input is None:
        sys.stderr.write("md2x convert: error: input is required (or use --check)\n")
        return 2
    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    cfg = load_config(args.config, args.input)
    cfg = apply_cli_overrides(cfg, args)
    target = detect_target(args.output, args.to or cfg["output"].get("format"))
    cfg["output"]["format"] = target.name
    out = args.output or args.input.with_suffix(target.suffix)
    return build(args.input, out, cfg)


def main() -> int:
    ensure_venv_yaml()
    setup_logging()  # default-init so startup steps below are captured
    argv = _normalize_argv(sys.argv[1:])
    ap = build_parser()
    args = ap.parse_args(argv)
    # Reconfigure now that -v/--quiet/--log-level/--log-file are known.
    setup_logging(verbosity=args.verbose, quiet=args.quiet,
                  level=args.log_level, log_file=args.log_file)
    log = get_logger("md2x.cli")
    log.debug("invocation: md2x %s", " ".join(argv))
    for p in load_default_env():
        log.info("loaded environment from %s", p)
    return args.func(args)
