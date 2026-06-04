from pathlib import Path
import md2x.pandoc as pandoc
from md2x.config import DEFAULTS, deep_merge


def _cmd(over=None):
    cfg = deep_merge(DEFAULTS, over or {})
    return pandoc.build_pandoc_cmd(Path("in.md"), Path("out.pdf"), cfg, "pandoc", "xelatex")


def test_defaults_include_core_flags():
    cmd = _cmd()
    assert "--pdf-engine=xelatex" in cmd
    assert "geometry:margin=0.85in" in cmd
    assert "--toc" in cmd
    assert "--toc-depth=2" in cmd
    assert "--highlight-style=tango" in cmd


def test_fonts_none_omitted_set_emitted():
    assert not any("mainfont" in c for c in _cmd())
    cmd = _cmd({"fonts": {"main": "Helvetica", "cjk": "Noto"}})
    assert "mainfont=Helvetica" in cmd
    assert "CJKmainfont=Noto" in cmd


def test_no_toc_and_landscape_and_sections():
    cmd = _cmd({"output": {"toc": False, "number_sections": True},
                "page": {"orientation": "landscape"}})
    assert "--toc" not in cmd
    assert "--number-sections" in cmd
    assert "classoption=landscape" in cmd


def test_citeproc_listings_headerincludes_extra():
    cmd = _cmd({"output": {"citation_processing": True},
                "code": {"line_numbers": True},
                "advanced": {"pandoc_extra_args": ["--standalone"]}})
    assert "--citeproc" in cmd
    assert "--listings" in cmd
    assert "--standalone" in cmd
    assert any(c.startswith("header-includes=") for c in cmd)
