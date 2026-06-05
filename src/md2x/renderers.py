"""Diagram renderers: mmdc (preferred) and Graphviz dot (flowchart fallback)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .mermaid import mermaid_to_dot, MERMAID_RE, extract_caption


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


class MermaidRenderError(Exception):
    """Raised when a Mermaid block fails to render and on_failure == 'error'."""


def render_into_markdown(md: str, work_dir: Path, cfg: dict,
                         mmdc_bin: str | None, dot_bin: str | None,
                         diag_subdir: str = ""
                         ) -> tuple[str, list[dict]]:
    """Render every ```mermaid``` block in `md` to an image and return the
    rewritten Markdown plus a manifest (one entry per block).

    Applies cfg['mermaid']['on_failure']:
      - 'error'       -> raise MermaidRenderError
      - 'omit'        -> drop the block
      - 'keep_source' -> keep the fenced source (default)
    Writes diagram PNGs under work_dir/'diagrams'[/diag_subdir]. The subdir
    namespaces output so the site generator can keep diagrams from different
    source docs from colliding; default "" preserves convert behavior exactly.
    Print-free; callers report.
    """
    diag_dir = work_dir / "diagrams"
    if diag_subdir:
        diag_dir = diag_dir / diag_subdir
    diag_dir.mkdir(parents=True, exist_ok=True)
    blocks = list(MERMAID_RE.finditer(md))
    chunks: list[str] = []
    manifest: list[dict] = []
    last_end = 0
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
            chunks.append(f"\n![{caption}]({rel}){{width={cfg['images']['width']}}}\n")
            if cfg["images"]["show_captions"]:
                prefix = cfg["images"]["caption_prefix"]
                if prefix:
                    chunks.append(f"\n*{prefix} {idx}: {caption}.*\n")
                else:
                    chunks.append(f"\n*{caption}.*\n")
        else:
            policy = cfg["mermaid"]["on_failure"]
            if policy == "error":
                raise MermaidRenderError(f"failed to render mermaid block {idx}")
            if policy != "omit":
                chunks.append(
                    f"\n*[Diagram {idx} — Mermaid source preserved; "
                    f"renderer unavailable]*\n\n```\n{src}\n```\n"
                )
        last_end = m.end()
    chunks.append(md[last_end:])
    return "".join(chunks), manifest
