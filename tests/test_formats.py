from pathlib import Path
import pytest
from md2x.formats import detect_target, TARGETS


def test_detect_by_extension():
    assert detect_target(Path("a.pdf"), None).name == "pdf"
    assert detect_target(Path("a.docx"), None).name == "docx"
    assert detect_target(Path("a.html"), None).name == "html"
    assert detect_target(Path("a.htm"), None).name == "html"
    assert detect_target(Path("a.epub"), None).name == "epub"
    assert detect_target(Path("a.tex"), None).name == "latex"


def test_override_beats_extension():
    assert detect_target(Path("a.pdf"), "docx").name == "docx"


def test_default_pdf_when_none_or_unknown_ext():
    assert detect_target(None, None).name == "pdf"
    assert detect_target(Path("a.weird"), None).name == "pdf"


def test_unknown_override_raises():
    with pytest.raises(ValueError):
        detect_target(Path("a.pdf"), "rtf")


def test_target_fields():
    assert TARGETS["pdf"].needs_xelatex is True
    assert TARGETS["pdf"].writer is None
    h = TARGETS["html"]
    assert h.writer == "html" and h.standalone and h.embed and not h.needs_xelatex
    assert TARGETS["docx"].suffix == ".docx" and not TARGETS["docx"].needs_xelatex
