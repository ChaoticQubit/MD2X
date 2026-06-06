"""Gated real end-to-end test: Markdown -> PDF via the actual toolchain.

Skipped unless pandoc + xelatex + dot all resolve. Uses the `dot` renderer
(prefer: dot) so it does not depend on the Node `mmdc` binary.

The sample document is defined inline (SAMPLE_MD) rather than read from a repo
fixture, so the test is self-contained and has no on-disk file dependency.
"""
from pathlib import Path
import pytest
from md2x.binaries import resolve_binary
from md2x.config import DEFAULTS, deep_merge
from md2x.pipeline import build

# A self-contained sample exercising headings, prose, a code block, a table,
# and a Mermaid flowchart (dot-renderable) that becomes a captioned figure.
SAMPLE_MD = """\
# md2x Sample Document

This sample exercises the full pipeline: headings, prose, a code block, a
table, and a Mermaid flowchart that gets rendered to a captioned figure.

## Pipeline Overview

The converter resolves local binaries, renders each Mermaid block to PNG, then
hands a rewritten Markdown file to pandoc + xelatex.

```mermaid
flowchart TD
    A[Markdown input] --> B{Mermaid block?}
    B -->|yes| C[Render PNG via mmdc or dot]
    B -->|no| D[Pass through]
    C --> E[Embed captioned figure]
    D --> E
    E --> F[pandoc + xelatex]
    F --> G[PDF output]
```

## Code

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

## Table

| Stage   | Tool     | Output  |
|---------|----------|---------|
| Render  | dot/mmdc | PNG     |
| Typeset | xelatex  | PDF     |

## Closing

If you can read this as a PDF with the diagram above rendered as an image, the
pipeline works end to end.
"""


def _write_sample(tmp_path: Path) -> Path:
    work = tmp_path / "doc.md"
    work.write_text(SAMPLE_MD, encoding="utf-8")
    return work


_HAVE = (bool(resolve_binary("pandoc"))
         and bool(resolve_binary("xelatex"))
         and bool(resolve_binary("dot")))


@pytest.mark.skipif(not _HAVE, reason="pandoc+xelatex+dot not all resolvable")
def test_real_md_to_pdf(tmp_path):
    work = _write_sample(tmp_path)
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
    """
    End-to-end test that converts the sample Markdown to DOCX using the real build pipeline and verifies the produced file.

    The test forces the Mermaid renderer preference to "dot" (so diagrams are rendered when a renderer is available; if not, Mermaid blocks degrade to source text and the DOCX still builds). It is skipped when Pandoc is not available.

    Verifications:
    - the build process exits with code 0;
    - the output .docx file exists;
    - the output file is larger than 1024 bytes;
    - the output file begins with the ZIP container signature (`b"PK\x03\x04"`).
    """
    work = _write_sample(tmp_path)
    out = tmp_path / "doc.docx"
    # Force dot renderer; if no renderer is present the Mermaid block degrades
    # to source text and the DOCX still builds (pandoc-only path).
    cfg = deep_merge(DEFAULTS, {"mermaid": {"prefer": "dot"}})
    rc = build(work, out, cfg)
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 1024
    assert out.read_bytes()[:4] == b"PK\x03\x04"  # .docx is a zip container
