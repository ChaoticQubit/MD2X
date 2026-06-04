"""Gated real end-to-end test: Markdown -> PDF via the actual toolchain.

Skipped unless pandoc + xelatex + dot all resolve. Uses the `dot` renderer
(prefer: dot) so it does not depend on the Node `mmdc` binary.
"""
import shutil
from pathlib import Path
import pytest
from md2x.binaries import resolve_binary
from md2x.config import DEFAULTS, deep_merge
from md2x.pipeline import build

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "examples" / "sample.md"

_HAVE = (bool(resolve_binary("pandoc"))
         and bool(resolve_binary("xelatex"))
         and bool(resolve_binary("dot")))


@pytest.mark.skipif(not _HAVE, reason="pandoc+xelatex+dot not all resolvable")
def test_real_md_to_pdf(tmp_path):
    work = tmp_path / "doc.md"
    shutil.copy(SAMPLE, work)
    out = tmp_path / "doc.pdf"
    # force dot renderer so mmdc (may be absent on PATH) isn't required
    cfg = deep_merge(DEFAULTS, {"mermaid": {"prefer": "dot"}})
    rc = build(work, out, cfg)
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 1024
    assert out.read_bytes()[:4] == b"%PDF"
    # the flowchart block was rendered to a real PNG
    assert (tmp_path / "diagrams" / "mermaid_01.png").exists()


_HAVE_PANDOC = bool(resolve_binary("pandoc"))


@pytest.mark.skipif(not _HAVE_PANDOC, reason="pandoc not resolvable")
def test_real_md_to_docx(tmp_path):
    work = tmp_path / "doc.md"
    shutil.copy(SAMPLE, work)
    out = tmp_path / "doc.docx"
    # Force dot renderer; if no renderer is present the Mermaid block degrades
    # to source text and the DOCX still builds (pandoc-only path).
    cfg = deep_merge(DEFAULTS, {"mermaid": {"prefer": "dot"}})
    rc = build(work, out, cfg)
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 1024
    assert out.read_bytes()[:4] == b"PK\x03\x04"  # .docx is a zip container
