"""md2x CLI — argument parsing and entry point.

Convert Markdown (with Mermaid blocks) to PDF.

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
from .pipeline import build
from .formats import detect_target


def apply_cli_overrides(cfg: dict, args: argparse.Namespace) -> dict:
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert Markdown (with Mermaid blocks) to PDF."
    )
    ap.add_argument("input", type=Path, help="Path to source .md")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Output .pdf path (default: alongside input)")
    ap.add_argument("-c", "--config", type=Path, default=None,
                    help="Explicit YAML config file")
    ap.add_argument("-t", "--to", default=None,
                    choices=["pdf", "docx", "html", "epub", "latex"],
                    help="Output format (default: infer from -o extension, else pdf)")
    ap.add_argument("--no-toc", action="store_true", help="Disable ToC")
    ap.add_argument("--toc-depth", type=int, default=None,
                    help="Heading depth for ToC")
    ap.add_argument("--margin", default=None, help="Page margin (e.g. 0.85in)")
    ap.add_argument("--fontsize", default=None, help="Body font size (e.g. 10.5pt)")
    ap.add_argument("--theme", default=None,
                    choices=["default", "forest", "dark", "neutral"],
                    help="Mermaid theme")
    ap.add_argument("--keep-intermediate", action="store_true",
                    help="Don't delete the intermediate .md")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    cfg = load_config(args.config, args.input)
    cfg = apply_cli_overrides(cfg, args)

    # Resolve format once; write it back so build() is authoritative.
    target = detect_target(args.output, args.to or cfg["output"].get("format"))
    cfg["output"]["format"] = target.name
    out = args.output or args.input.with_suffix(target.suffix)
    return build(args.input, out, cfg)
