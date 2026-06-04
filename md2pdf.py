#!/usr/bin/env python3
"""
md2pdf.py — Convert Markdown (with Mermaid blocks) to PDF.

Self-contained workflow:
  1. Loads YAML config (md2pdf.yaml next to the input or in the project root).
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
    ./md2pdf.py INPUT.md [-o OUTPUT.pdf] [--config md2pdf.yaml]
                          [--toc-depth N] [--no-toc]
                          [--margin 0.85in] [--fontsize 10.5pt]
                          [--theme default|forest|dark|neutral]
                          [--keep-intermediate]

Requires: Python 3.10+. PyYAML if any YAML config is present (auto-installed
by install.sh into .venv). The script falls back to bundled defaults if
PyYAML is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────
# Project layout
# ──────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_BIN     = PROJECT_ROOT / ".bin"
LOCAL_TOOLS   = PROJECT_ROOT / ".tools"
LOCAL_NPM_BIN = PROJECT_ROOT / "node_modules" / ".bin"
LOCAL_VENV    = PROJECT_ROOT / ".venv"


def _ensure_venv_yaml():
    """If PyYAML is missing but .venv has it, add .venv site-packages to sys.path."""
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    for p in LOCAL_VENV.glob("lib/python*/site-packages"):
        sys.path.insert(0, str(p))
    try:
        import yaml  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "WARN: PyYAML not found. Config file will be ignored. "
            "Run ./install.sh to set up the venv with PyYAML.\n"
        )


_ensure_venv_yaml()


# ──────────────────────────────────────────────────────────────────────────
# Default config (used when no YAML present)
# ──────────────────────────────────────────────────────────────────────────

DEFAULTS: dict[str, Any] = {
    "output": {
        "toc": True,
        "toc_depth": 2,
        "default_suffix": ".pdf",
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
        # lookup, no system-font dependency). Override in md2pdf.yaml.
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
}


def deep_merge(base: dict, over: dict) -> dict:
    """Recursive dict merge — values in `over` win, missing keys preserved."""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(explicit: Path | None, md_path: Path) -> dict:
    """Find and load YAML config; fall back to defaults."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    candidates += [
        md_path.parent / "md2pdf.yaml",
        md_path.parent / "md2pdf.yml",
        PROJECT_ROOT / "md2pdf.yaml",
        PROJECT_ROOT / "md2pdf.yml",
    ]
    for p in candidates:
        if p and p.exists():
            try:
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                print(f"[md2pdf] using config {p}")
                return deep_merge(DEFAULTS, data)
            except ImportError:
                sys.stderr.write(f"WARN: PyYAML missing — skipping {p}\n")
                break
            except Exception as e:
                sys.stderr.write(f"WARN: failed to parse {p}: {e}\n")
                break
    print("[md2pdf] using built-in defaults (no YAML found)")
    return DEFAULTS


# ──────────────────────────────────────────────────────────────────────────
# Binary resolution
# ──────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────
# Mermaid extraction
# ──────────────────────────────────────────────────────────────────────────

MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
CAPTION_HINT_RE = re.compile(
    r"^\s*(?:title|%%\s*title)\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_caption(source: str, fallback: str) -> str:
    m = CAPTION_HINT_RE.search(source)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    first = re.search(r"\[(.*?)\]", source)
    if first:
        t = first.group(1).strip()
        if len(t) <= 60:
            return t
    return fallback


# ──────────────────────────────────────────────────────────────────────────
# Renderers
# ──────────────────────────────────────────────────────────────────────────

def render_via_mmdc(source: str, out_png: Path, cfg: dict, mmdc_bin: str) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(source)
        in_path = f.name
    try:
        cmd = [
            mmdc_bin,
            "-i", in_path,
            "-o", str(out_png),
            "-t", cfg["mermaid"]["theme"],
            "-b", cfg["mermaid"]["background"],
            "-w", str(cfg["images"]["mmdc_width"]),
            "-H", str(cfg["images"]["mmdc_height"]),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        ok = res.returncode == 0 and out_png.exists()
        if not ok:
            sys.stderr.write(f"mmdc failed: {res.stderr[:400]}\n")
        return ok
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


MERMAID_EDGE_RE = re.compile(
    r"""
    \s*
    (?P<a>[A-Za-z0-9_\.\-]+)
    (?:\s*\[(?P<la>[^\]]*)\])?
    \s*
    (?P<arrow>-->|---|-\.->|==>|--|\.\.>)
    (?:\s*\|(?P<label>[^|]+)\|)?
    \s*
    (?P<b>[A-Za-z0-9_\.\-]+)
    (?:\s*\[(?P<lb>[^\]]*)\])?
    \s*$
    """,
    re.VERBOSE,
)
MERMAID_NODE_RE = re.compile(
    r"""^\s*(?P<id>[A-Za-z0-9_\.\-]+)\s*\[(?P<label>[^\]]*)\]\s*$""",
    re.VERBOSE,
)


def mermaid_to_dot(source: str) -> str | None:
    if not source.strip():
        return None
    first = source.strip().splitlines()[0].lower()
    if not first.startswith(("flowchart", "graph")):
        return None
    parts = first.split()
    direction = parts[1].upper() if len(parts) > 1 else "TB"
    rd = {"TB": "TB", "TD": "TB", "BT": "BT", "LR": "LR", "RL": "RL"}.get(direction, "TB")

    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str, str]] = []
    for raw in source.splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith(("%", "subgraph", "end", "classDef",
                                        "click", "style", "linkStyle")):
            continue
        em = MERMAID_EDGE_RE.match(line)
        if em:
            a = em.group("a"); b = em.group("b")
            if em.group("la") and a not in nodes:
                nodes[a] = em.group("la")
            if em.group("lb") and b not in nodes:
                nodes[b] = em.group("lb")
            style = "solid"
            arrow = em.group("arrow")
            if "." in arrow:
                style = "dashed"
            elif "==" in arrow:
                style = "bold"
            edges.append((a, b, style, (em.group("label") or "").strip()))
            continue
        nm = MERMAID_NODE_RE.match(line)
        if nm:
            nodes[nm.group("id")] = nm.group("label")

    out = [
        "digraph G {",
        f"  rankdir={rd};",
        '  bgcolor="white";',
        '  node [shape=box, style="rounded,filled", fillcolor="#D9E2F3",',
        '        fontname="Helvetica", fontsize=11, color="#1F4E79"];',
        '  edge [color="#2E75B6"];',
    ]
    for nid, lbl in nodes.items():
        safe = lbl.replace('"', '\\"')
        out.append(f'  {nid} [label="{safe}"];')
    for a, b, style, label in edges:
        attrs = []
        if style != "solid":
            attrs.append(f"style={style}")
        if label:
            safe = label.replace('"', '\\"')
            attrs.append(f'label="{safe}"')
        suffix = (" [" + ", ".join(attrs) + "]") if attrs else ""
        out.append(f"  {a} -> {b}{suffix};")
    out.append("}")
    return "\n".join(out)


def render_via_dot(source: str, out_png: Path, cfg: dict, dot_bin: str) -> bool:
    dot_src = mermaid_to_dot(source)
    if dot_src is None:
        return False
    res = subprocess.run(
        [dot_bin, "-Tpng", f"-Gdpi={cfg['images']['dpi']}",
         "-Gsize=8.5,5.5!", "-Gratio=compress", "-o", str(out_png)],
        input=dot_src, text=True, capture_output=True,
    )
    return res.returncode == 0 and out_png.exists()


def render_block(source: str, out_png: Path, cfg: dict,
                 mmdc_bin: str | None, dot_bin: str | None) -> tuple[bool, str]:
    prefer = cfg["mermaid"]["prefer"]
    if prefer == "mmdc":
        chain = ["mmdc", "dot"]
    elif prefer == "dot":
        chain = ["dot", "mmdc"]
    else:
        chain = ["mmdc", "dot"] if mmdc_bin else ["dot", "mmdc"]

    for r in chain:
        if r == "mmdc" and mmdc_bin and render_via_mmdc(source, out_png, cfg, mmdc_bin):
            return True, "mmdc"
        if r == "dot" and dot_bin and render_via_dot(source, out_png, cfg, dot_bin):
            return True, "dot"
    return False, "none"


# ──────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────

def build_pandoc_cmd(input_md: Path, output_pdf: Path, cfg: dict,
                     pandoc_bin: str, xelatex_bin: str) -> list[str]:
    cmd: list[str] = [
        pandoc_bin, str(input_md),
        "-o", str(output_pdf),
        f"--pdf-engine={xelatex_bin}",
        "-V", f"geometry:margin={cfg['page']['margin']}",
        "-V", f"fontsize={cfg['page']['fontsize']}",
        "-V", f"papersize={cfg['page']['paper']}",
        "-V", f"linestretch={cfg['page']['line_spacing']}",
        "-V", "colorlinks=true",
        "-V", f"linkcolor={cfg['colors']['link']}",
        "-V", f"urlcolor={cfg['colors']['url']}",
        "-V", f"toccolor={cfg['colors']['toc']}",
        f"--highlight-style={cfg['code']['highlight_style']}",
    ]
    # Only pass font vars when explicitly set — otherwise xelatex uses
    # its built-in Computer Modern (no fontspec lookup needed).
    if cfg["fonts"].get("main"):
        cmd += ["-V", f"mainfont={cfg['fonts']['main']}"]
    if cfg["fonts"].get("sans"):
        cmd += ["-V", f"sansfont={cfg['fonts']['sans']}"]
    if cfg["fonts"].get("mono"):
        cmd += ["-V", f"monofont={cfg['fonts']['mono']}"]
    if cfg["page"]["orientation"] == "landscape":
        cmd += ["-V", "classoption=landscape"]
    if cfg["output"]["toc"]:
        cmd += ["--toc", f"--toc-depth={cfg['output']['toc_depth']}"]
    if cfg["output"]["number_sections"]:
        cmd.append("--number-sections")
    if cfg["output"]["citation_processing"]:
        cmd.append("--citeproc")
    if cfg["fonts"].get("cjk"):
        cmd += ["-V", f"CJKmainfont={cfg['fonts']['cjk']}"]
    if cfg["code"]["line_numbers"]:
        cmd.append("--listings")
    hi = cfg["advanced"].get("header_includes", [])
    if hi:
        cmd += ["-V", "header-includes=" + "".join(hi)]
    cmd += cfg["advanced"].get("pandoc_extra_args", [])
    return cmd


def build(md_path: Path, out_path: Path, cfg: dict) -> int:
    md_path = md_path.resolve()
    out_path = out_path.resolve()
    work_dir = md_path.parent
    diag_dir = work_dir / "diagrams"
    diag_dir.mkdir(exist_ok=True)

    if cfg["advanced"].get("no_clobber") and out_path.exists():
        sys.exit(f"refusing to overwrite existing file (no_clobber): {out_path}")

    bins = cfg["binaries"]
    pandoc_bin  = resolve_binary("pandoc",  bins.get("pandoc"))
    xelatex_bin = resolve_binary("xelatex", bins.get("xelatex"))
    mmdc_bin    = resolve_binary("mmdc",    bins.get("mmdc"))
    dot_bin     = resolve_binary("dot",     bins.get("dot"))

    if not pandoc_bin:
        sys.exit("ERROR: pandoc not found. Run ./install.sh")
    if not xelatex_bin:
        sys.exit("ERROR: xelatex not found. Run ./install.sh")
    if not mmdc_bin and not dot_bin:
        sys.stderr.write("WARN: neither mmdc nor dot found — Mermaid blocks "
                         "will be kept as code blocks.\n")

    print(f"[md2pdf] pandoc:  {pandoc_bin}")
    print(f"[md2pdf] xelatex: {xelatex_bin}")
    print(f"[md2pdf] mmdc:    {mmdc_bin or '(none)'}")
    print(f"[md2pdf] dot:     {dot_bin or '(none)'}")

    md = md_path.read_text(encoding="utf-8")
    blocks = list(MERMAID_RE.finditer(md))
    print(f"[md2pdf] found {len(blocks)} mermaid blocks in {md_path.name}")

    chunks: list[str] = []
    last_end = 0
    manifest: list[dict] = []

    for idx, m in enumerate(blocks, 1):
        chunks.append(md[last_end:m.start()])
        src = m.group(1)
        png = diag_dir / f"mermaid_{idx:02d}.png"
        ok, renderer = render_block(src, png, cfg, mmdc_bin, dot_bin)
        caption = extract_caption(src, f"Diagram {idx}")
        manifest.append({
            "index": idx, "renderer": renderer, "ok": ok,
            "caption": caption, "png": str(png.relative_to(work_dir)),
        })

        if ok:
            rel = png.relative_to(work_dir).as_posix()
            chunks.append(
                f"\n![{caption}]({rel}){{width={cfg['images']['width']}}}\n"
            )
            if cfg["images"]["show_captions"]:
                prefix = cfg["images"]["caption_prefix"]
                if prefix:
                    chunks.append(f"\n*{prefix} {idx}: {caption}.*\n")
                else:
                    chunks.append(f"\n*{caption}.*\n")
            print(f"  [{idx:02d}] {renderer} → {png.name}")
        else:
            policy = cfg["mermaid"]["on_failure"]
            if policy == "error":
                sys.exit(f"ERROR: failed to render mermaid block {idx}.")
            elif policy == "omit":
                print(f"  [{idx:02d}] OMITTED (no renderer succeeded)")
            else:
                chunks.append(
                    f"\n*[Diagram {idx} — Mermaid source preserved; "
                    f"renderer unavailable]*\n\n```\n{src}\n```\n"
                )
                print(f"  [{idx:02d}] WARN: kept source; no renderer succeeded")
        last_end = m.end()

    chunks.append(md[last_end:])
    rewritten = "".join(chunks)

    tmp_md = work_dir / (md_path.stem + "._md2pdf.md")
    tmp_md.write_text(rewritten, encoding="utf-8")

    cmd = build_pandoc_cmd(tmp_md, out_path, cfg, pandoc_bin, xelatex_bin)
    print(f"[md2pdf] running pandoc …")
    res = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr or res.stdout or "")
        return res.returncode
    print(f"[md2pdf] wrote {out_path} ({out_path.stat().st_size} bytes)")

    if cfg["advanced"].get("emit_manifest"):
        man_path = work_dir / (md_path.stem + "._md2pdf.json")
        man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[md2pdf] manifest → {man_path}")

    if not cfg["advanced"].get("keep_intermediate"):
        try:
            tmp_md.unlink()
        except OSError:
            pass
    return 0


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

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

    out = args.output or args.input.with_suffix(cfg["output"]["default_suffix"])
    return build(args.input, out, cfg)


if __name__ == "__main__":
    sys.exit(main() or 0)
