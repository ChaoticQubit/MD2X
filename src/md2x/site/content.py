"""Convert a Markdown file to a faithful HTML fragment (verbatim body).

Reuses md2x's existing Mermaid rendering and pandoc so the body of every page
matches the PDF/HTML legs exactly — the AI layer never touches it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..binaries import resolve_binary
from ..renderers import render_into_markdown
from .schemas import Doc, slugify

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def extract_title(md_path: Path) -> str:
    """Return the text of the first H1 heading, or the file stem as fallback."""
    text = md_path.read_text(encoding="utf-8")
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else md_path.stem


def extract_outline(md_path: Path) -> list[str]:
    """Return a list of H2 heading texts (level-2 section names) in order."""
    text = md_path.read_text(encoding="utf-8")
    return [m.strip() for m in _H2_RE.findall(text)]


def md_to_fragment(md_path: Path, cfg: dict) -> str:
    """Render Mermaid, then run pandoc to an HTML fragment (no --standalone)."""
    pandoc_bin = resolve_binary("pandoc", cfg["binaries"].get("pandoc"))
    if not pandoc_bin:
        raise RuntimeError("pandoc not found. Run ./install.sh or install pandoc.")
    mmdc_bin = resolve_binary("mmdc", cfg["binaries"].get("mmdc"))
    dot_bin = resolve_binary("dot", cfg["binaries"].get("dot"))

    work_dir = md_path.parent
    md = md_path.read_text(encoding="utf-8")
    # Namespace diagrams per source doc so two docs (incl. recursive subdirs)
    # never collide on diagrams/mermaid_01.png. The image refs pandoc emits
    # become diagrams/<slug>/mermaid_NN.png — write_site copies them 1:1.
    slug = slugify(md_path.stem)
    rewritten, _manifest = render_into_markdown(
        md, work_dir, cfg, mmdc_bin, dot_bin, diag_subdir=slug
    )

    # Fragment only: intentionally omits --standalone and pandoc_extra_args, since
    # either could inject a full-document wrapper and break the fragment contract.
    cmd = [pandoc_bin, "-f", "markdown", "-t", "html", "--no-highlight"]
    res = subprocess.run(cmd, input=rewritten, text=True,
                         capture_output=True, cwd=work_dir)
    if res.returncode != 0:
        raise RuntimeError(f"pandoc failed for {md_path.name}: {res.stderr[:400]}")
    return res.stdout


def build_doc(md_path: Path, cfg: dict) -> Doc:
    """Build a :class:`Doc` from *md_path*, rendering diagrams and converting to HTML."""
    return Doc(
        path=md_path,
        title=extract_title(md_path),
        outline=extract_outline(md_path),
        fragment_html=md_to_fragment(md_path, cfg),
    )
