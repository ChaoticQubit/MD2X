from pathlib import Path
import md2x.pandoc as pandoc
from md2x.config import DEFAULTS, deep_merge
from md2x.formats import TARGETS


def _cmd(over=None):
    """
    Builds the pandoc command list to produce out.pdf from in.md using XeLaTeX.
    
    Parameters:
        over (dict | None): Optional overrides merged into DEFAULTS; keys follow the configuration schema used by the pandoc builder.
    
    Returns:
        cmd (list[str]): Ordered list of command-line arguments for invoking pandoc to generate out.pdf with the XeLaTeX PDF engine.
    """
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


def test_pdf_command_snapshot():
    """Lock the exact PDF pandoc invocation. If this changes, PDF output changed."""
    cfg = deep_merge(DEFAULTS, {})
    cmd = pandoc.build_pandoc_cmd(Path("in.md"), Path("out.pdf"), cfg, "pandoc", "xelatex")
    hi = "\n".join([
        r"\usepackage{float}",
        r"\floatplacement{figure}{H}",
        r"\usepackage[export]{adjustbox}",
        r"\usepackage{microtype}",
        r"\usepackage{booktabs}",
    ])
    assert cmd == [
        "pandoc", "in.md", "-o", "out.pdf",
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=0.85in",
        "-V", "fontsize=10.5pt",
        "-V", "papersize=letter",
        "-V", "linestretch=1.15",
        "-V", "colorlinks=true",
        "-V", "linkcolor=NavyBlue",
        "-V", "urlcolor=NavyBlue",
        "-V", "toccolor=NavyBlue",
        "--highlight-style=tango",
        "--toc", "--toc-depth=2",
        "-V", "header-includes=" + hi,
    ]


def _gen(target_name, over=None):
    """
    Builds a pandoc command for the specified output target by merging defaults with optional overrides.
    
    Parameters:
        target_name (str): Key identifying the target in TARGETS (e.g., "pdf", "docx", "html").
        over (dict, optional): Configuration overrides that are deep-merged into DEFAULTS.
    
    Returns:
        list: Ordered list of command-line arguments for invoking pandoc to produce the target output.
    """
    cfg = deep_merge(DEFAULTS, over or {})
    t = TARGETS[target_name]
    return pandoc.build_generic_cmd(Path("in.md"), Path("out" + t.suffix), cfg, "pandoc", t)


def test_generic_docx_excludes_latex_flags():
    cmd = _gen("docx")
    assert "-t" in cmd and "docx" in cmd
    assert "--highlight-style=tango" in cmd
    assert not any("--pdf-engine" in c for c in cmd)
    assert not any("geometry" in c for c in cmd)
    assert "-V" not in cmd  # generic builder emits no template variables


def test_generic_html_standalone_embed():
    cmd = _gen("html")
    assert "-t" in cmd and "html" in cmd
    assert "--standalone" in cmd
    assert "--embed-resources" in cmd


def test_generic_passthrough_flags():
    cmd = _gen("docx", {"output": {"number_sections": True, "citation_processing": True},
                        "advanced": {"pandoc_extra_args": ["--reference-doc=ref.docx"]}})
    assert "--number-sections" in cmd
    assert "--citeproc" in cmd
    assert "--reference-doc=ref.docx" in cmd


def test_generic_toc_toggle_off():
    cmd = _gen("html", {"output": {"toc": False}})
    assert "--toc" not in cmd


def test_build_cmd_dispatch():
    """
    Ensure pandoc.build_cmd selects correct flags and format-specific options for PDF and DOCX outputs.
    
    Verifies that the command built for the PDF target includes the `--pdf-engine=xelatex` flag, and that the command built for the DOCX target does not include that flag and selects the docx format (contains `-t` and `docx`).
    """
    cfg = deep_merge(DEFAULTS, {})
    pdf = pandoc.build_cmd(Path("in.md"), Path("out.pdf"), cfg, TARGETS["pdf"], "pandoc", "xelatex")
    assert "--pdf-engine=xelatex" in pdf
    docx = pandoc.build_cmd(Path("in.md"), Path("out.docx"), cfg, TARGETS["docx"], "pandoc", "xelatex")
    assert "--pdf-engine=xelatex" not in docx
    assert "-t" in docx and "docx" in docx
