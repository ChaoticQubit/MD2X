import json
import stat
from pathlib import Path
import pytest
import md2x.pipeline as pipeline
import md2x.renderers as renderers
from md2x.config import DEFAULTS, deep_merge


def _fake_pandoc(tmp_path: Path) -> str:
    """
    Create an executable fake `pandoc` script inside the given directory that, when run with a `-o <output>` argument, writes a minimal fake PDF payload to that output.
    
    Parameters:
        tmp_path (Path): Directory in which to create the fake `pandoc` executable.
    
    Returns:
        str: Filesystem path to the created fake `pandoc` executable.
    """
    p = tmp_path / "pandoc"
    p.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "out=sys.argv[sys.argv.index('-o')+1]\n"
        "open(out,'wb').write(b'%PDF-1.5 fake')\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def _patch_bins(monkeypatch, tmp_path, mmdc="mmdc", dot="dot"):
    pan = _fake_pandoc(tmp_path)
    def fake_resolve(name, override=None):
        return {"pandoc": pan, "xelatex": "xelatex", "mmdc": mmdc, "dot": dot}[name]
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)


def _make_md(tmp_path: Path, body: str) -> Path:
    md = tmp_path / "doc.md"
    md.write_text(body)
    return md


MD = "# Title\n\n```mermaid\nflowchart TD\nA[Start]-->B[End]\n```\n\nafter\n"


def test_build_embeds_figure_and_caption(monkeypatch, tmp_path):
    """
    Verifies that building a Markdown document with a Mermaid block embeds the rendered diagram as an image with a caption in the rewritten Markdown and produces a PDF.

    The test uses a fake renderer that writes a PNG to the expected path and returns a successful renderer name. It asserts the build exits successfully, the output PDF begins with a PDF header, and the intermediate rewritten Markdown contains the embedded image link and a corresponding figure caption.
    """
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(renderers, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"keep_intermediate": True}})
    rc = pipeline.build(md, tmp_path / "out.pdf", cfg)
    assert rc == 0
    assert (tmp_path / "out.pdf").read_bytes().startswith(b"%PDF")
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "![Start](diagrams/mermaid_01.png)" in rewritten
    assert "Figure 1: Start." in rewritten


def test_on_failure_keep_source(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(renderers, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"keep_intermediate": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "Mermaid source preserved" in rewritten
    assert "flowchart TD" in rewritten


def test_on_failure_omit(monkeypatch, tmp_path):
    """
    Verifies that when rendering fails and `mermaid.on_failure` is set to "omit", the Mermaid source block is removed from the rewritten Markdown.

    This test patches binaries and forces `renderers.render_block` to fail, builds the document with `keep_intermediate` enabled, and asserts that the intermediate rewritten file does not contain the original Mermaid source (`flowchart TD`).
    """
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(renderers, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"mermaid": {"on_failure": "omit"},
                                "advanced": {"keep_intermediate": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "flowchart TD" not in rewritten


def test_on_failure_error_exits(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(renderers, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"mermaid": {"on_failure": "error"}})
    with pytest.raises(SystemExit):
        pipeline.build(md, tmp_path / "out.pdf", cfg)


def test_emit_manifest(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(renderers, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"emit_manifest": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    man = json.loads((tmp_path / "doc._md2x.json").read_text())
    assert man[0]["renderer"] == "dot" and man[0]["ok"] is True
    assert man[0]["caption"] == "Start"


def test_no_clobber_refuses(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    out = tmp_path / "out.pdf"
    out.write_text("existing")
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"no_clobber": True}})
    with pytest.raises(SystemExit):
        pipeline.build(md, out, cfg)


def test_missing_pandoc_exits(monkeypatch, tmp_path):
    def fake_resolve(name, override=None):
        return None if name == "pandoc" else "x"
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)
    md = _make_md(tmp_path, MD)
    with pytest.raises(SystemExit):
        pipeline.build(md, tmp_path / "out.pdf", deep_merge(DEFAULTS, {}))


def test_keep_intermediate_false_deletes(monkeypatch, tmp_path):
    """
    Verifies that intermediate rewritten Markdown is removed when intermediate retention is disabled.

    Invokes the build pipeline with a stubbed successful renderer and default configuration (keep_intermediate disabled), then asserts that the intermediate file `doc._md2x.md` does not exist after the build.
    """
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(renderers, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    pipeline.build(md, tmp_path / "out.pdf", deep_merge(DEFAULTS, {}))
    assert not (tmp_path / "doc._md2x.md").exists()


def _fake_pandoc_recording(tmp_path: Path):
    """
    Create an executable fake `pandoc` script that records its invocation and writes a minimal DOCX-like ZIP header to the output file.
    
    Parameters:
        tmp_path (Path): Directory where the fake `pandoc` script and its argv log will be created.
    
    Returns:
        (str, Path): Tuple containing the filesystem path to the fake `pandoc` executable (as a string) and the Path to the argv log file.
    """
    p = tmp_path / "pandoc"
    log = tmp_path / "pandoc_argv.txt"
    p.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open(r'{log}', 'w').write(' '.join(sys.argv))\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'wb').write(b'PK\\x03\\x04 fake docx')\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p), log


def test_build_docx_does_not_require_xelatex(monkeypatch, tmp_path):
    pan, log = _fake_pandoc_recording(tmp_path)
    # xelatex intentionally MISSING — must not abort for a docx target.
    def fake_resolve(name, override=None):
        """
        Map a tool name to a fake executable path or command name for tests.
        
        Parameters:
            name (str): The tool name to resolve (e.g., "pandoc", "xelatex", "mmdc", "dot").
            override: Ignored; present for API compatibility.
        
        Returns:
            str: The resolved executable path or command name for the requested tool.
        
        Raises:
            KeyError: If `name` is not one of the supported tool keys.
        """
        return {"pandoc": pan, "xelatex": None, "mmdc": "mmdc", "dot": "dot"}[name]
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)

    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        """
        Write a minimal PNG signature to the given output path and indicate a successful render with the renderer name.

        Parameters:
            src (str): Original source content for the block (unused by this fake renderer).
            png (str or Path): Path where the PNG output will be written.
            cfg (Mapping): Configuration used for rendering (unused by this fake renderer).
            mmdc_bin (str): Path or name of the mermaid CLI binary (unused by this fake renderer).
            dot_bin (str): Path or name of the Graphviz `dot` binary (unused by this fake renderer).

        Returns:
            tuple: (ok, renderer) where `ok` is `True` indicating success, and `renderer` is the string `"dot"`.
        """
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(renderers, "render_block", fake_render)

    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {})
    rc = pipeline.build(md, tmp_path / "out.docx", cfg)
    assert rc == 0
    assert (tmp_path / "out.docx").exists()
    argv = log.read_text()
    assert "-t docx" in argv
    assert "--pdf-engine" not in argv
