"""Diagram renderers: mmdc (preferred) and Graphviz dot (flowchart fallback)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .mermaid import mermaid_to_dot


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
